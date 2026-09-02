"""
Etapa 3 - item 3: política de LGPD com três níveis de tratamento.

Este módulo é responsável por DECIDIR, antes (ou depois) da chamada ao LLM,
como uma pergunta/resposta deve ser tratada do ponto de vista de LGPD:

    RECUSAR   -> salário/remuneração individual, CPF, dados bancários/PIX,
                 credenciais (senha/token) em logs, dados de saúde.
                 -> is_refusal=True, refusal_reason="lgpd", sem citar trecho.

    MASCARAR  -> e-mail pessoal, telefone, endereço residencial, número de
                 cartão. -> resposta normal, mas com o dado ofuscado.

    RESPONDER -> agregados/estatísticas sem identificação individual,
                 customer_id como referência interna, dados de produto,
                 loja, política e manual. -> resposta normal com citação.

Seguindo a recomendação do guia do desafio ("classifique na ingestão, não na
hora de responder - filtrar por metadado é barato e determinístico; pedir
para o LLM decidir depois é caro e falível"), a classificação aqui é
determinística (baseada em regras), não delegada ao LLM. O LLM só é chamado
DEPOIS que já sabemos que a pergunta pode ser respondida.

Isso é levemente diferente do `sensitivity` (publico/interno/restrito) já
gravado em `metadata_schema.py` durante a ingestão: `sensitivity` descreve o
DOCUMENTO como um todo (ex: "employees.csv inteiro é restrito"), enquanto a
classificação abaixo descreve a INTENÇÃO DA PERGUNTA. As duas se
complementam: usamos as duas como camadas de defesa (ver `_is_restricted_docs`
em `generate.py`).
"""

import re
import unicodedata
from typing import Literal

LGPDCategory = Literal["recusar", "mascarar", "responder"]


def _normalize(text: str) -> str:
    """Remove acentos e caixa, igual ao normalize() do query_analyzer.py."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().strip().split())


# ---------------------------------------------------------------------------
# Padrões que indicam pedido de dado que deve ser RECUSADO.
#
# Incluímos formas indiretas de perguntar (ver "Dicas para não travar" do
# guia: "quanto a folha da equipe de suporte custa por pessoa?", "liste os
# funcionários por ordem de remuneração"), não só a palavra óbvia "salário".
# ---------------------------------------------------------------------------
REFUSE_PATTERNS = [
    r"\bsalari",                       # salário, salarial, salários
    r"\bremunera",                     # remuneração, remunerado(s)
    r"\bfolha de pagamento\b",
    r"\bfolha\b.*\bpor pessoa\b",      # "a folha ... custa por pessoa"
    r"\bquanto\b.*\b(ganha|recebe)\b", # "quanto fulano ganha/recebe"
    r"\bordem de remuner",             # "por ordem de remuneração"
    r"\bcpf\b",
    r"\bpix\b",
    r"chave pix",
    r"conta banc",
    r"dados banc",
    r"\bsenha\b",
    r"\bsenhas\b",
    r"\btoken\b",
    r"credencia",                      # credencial, credenciais
    r"\bchave\b.{0,40}\bapi\b",        # "chave de api", "chave secreta de API de Produção"
    r"\bapi\b.{0,40}\bchave\b",
    r"\bapi key\b",
    r"\bsegredo",                      # segredo, segredos (ex.: "segredo JWT")
    r"\bjwt\b",
    r"\bsaude\b",
    r"atestado",
    r"diagnostic",
    r"\bdoenca\b",
]

# ---------------------------------------------------------------------------
# Padrões que indicam pedido de dado que deve ser MASCARADO (não recusado).
# ---------------------------------------------------------------------------
MASK_PATTERNS = [
    r"\be-?mail\b",
    r"\btelefone\b",
    r"\bcelular\b",
    r"\bcontato\b",
    r"\bendereco\b",
    r"\bcartao\b",
]

_REFUSE_RE = [re.compile(p) for p in REFUSE_PATTERNS]
_MASK_RE = [re.compile(p) for p in MASK_PATTERNS]


def classify_question(question: str) -> LGPDCategory:
    """
    Classifica a INTENÇÃO da pergunta em recusar / mascarar / responder,
    checando os padrões acima contra a versão normalizada da pergunta.

    A ordem importa: uma pergunta que casa com um padrão de "recusar" tem
    prioridade sobre um padrão de "mascarar" (ex: "qual o e-mail e o
    salário do funcionário X?" deve ser recusada por inteiro, não mascarada).
    """
    normalized = _normalize(question)

    if any(pattern.search(normalized) for pattern in _REFUSE_RE):
        return "recusar"

    if any(pattern.search(normalized) for pattern in _MASK_RE):
        return "mascarar"

    return "responder"


def has_only_restricted_docs(docs) -> bool:
    """
    Segunda camada de defesa: mesmo que a pergunta não bata em nenhum padrão
    de texto (ex.: fraseado muito indireto), se TODOS os chunks recuperados
    tiverem sensitivity="restrito" (ex.: registros de employees.csv), a
    resposta é recusada mesmo assim. Isso é o que o guia chama de "filtrar
    por metadado é barato e determinístico".
    """
    if not docs:
        return False
    return all(doc.metadata.get("sensitivity") == "restrito" for doc in docs)


# ---------------------------------------------------------------------------
# Mascaramento de PII no texto (resposta final e/ou trechos citados).
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[\w.\-]+@[\w.\-]+\.\w+")
_PHONE_RE = re.compile(r"\(?\d{2}\)?\s?9?\d{4}-?\d{4}")
_CPF_RE = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")


def _mask_email(match: re.Match) -> str:
    email = match.group(0)
    local, _, domain = email.partition("@")
    visible = local[:2] if len(local) > 2 else local[:1]
    tld = domain.split(".")[-1]
    return f"{visible}{'*' * 3}@{'*' * 3}.{tld}"


def _mask_phone(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) < 4:
        return "*" * len(digits)
    ddd = digits[:2]
    last_two = digits[-2:]
    return f"({ddd}) 9****-**{last_two}"


def _mask_cpf(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return f"***.***.{digits[6:9]}-**" if len(digits) == 11 else "***.***.***-**"


def _mask_card(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) < 4:
        return "*" * len(digits)
    return f"{'*' * (len(digits) - 4)}{digits[-4:]}"


def mask_pii(text: str) -> str:
    """
    Aplica mascaramento de e-mail, telefone, CPF e número de cartão no texto.

    A ordem de aplicação importa: e-mail e telefone primeiro (padrões mais
    específicos), CPF depois, e número de cartão por último (padrão mais
    genérico de dígitos, que poderia colidir com os anteriores).
    """
    if not text:
        return text

    text = _EMAIL_RE.sub(_mask_email, text)
    text = _PHONE_RE.sub(_mask_phone, text)
    text = _CPF_RE.sub(_mask_cpf, text)
    text = _CARD_RE.sub(_mask_card, text)
    return text


if __name__ == "__main__":
    test_questions = [
        ("Qual o salário do funcionário João Pereira?", "recusar"),
        ("Quanto a folha da equipe de suporte custa por pessoa?", "recusar"),
        ("Liste os funcionários por ordem de remuneração.", "recusar"),
        ("Qual a chave PIX cadastrada para reembolso?", "recusar"),
        ("Qual o e-mail de contato do cliente CUST001?", "mascarar"),
        ("Qual o telefone do cliente CUST014?", "mascarar"),
        ("Qual a política de reembolso da empresa?", "responder"),
        ("Quais módulos a loja de Belo Horizonte utiliza?", "responder"),
    ]

    print("=" * 70)
    print("Teste de classificação por pergunta")
    print("=" * 70)
    for question, expected in test_questions:
        got = classify_question(question)
        status = "OK" if got == expected else "FALHOU"
        print(f"[{status}] esperado={expected:10s} obtido={got:10s} | {question}")

    print("\n" + "=" * 70)
    print("Teste de mascaramento de PII")
    print("=" * 70)
    sample = (
        "Contato: gerencia@boacompra.com.br, telefone (31) 91234-5678, "
        "CPF 123.456.789-01, cartão 4111 1111 1111 1111."
    )
    print("Original: ", sample)
    print("Mascarado:", mask_pii(sample))
