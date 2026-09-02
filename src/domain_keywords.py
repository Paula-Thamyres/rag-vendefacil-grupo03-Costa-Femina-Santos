"""
Vocabulário de domínio da VendeFácil, usado como segunda camada do detector
de "fora de escopo" (generate.py -> is_out_of_scope()), combinado com a
distância de embedding.

Origem dos termos (nenhum foi inventado - todos vêm de dados reais do
projeto):
- Nomes dos 5 produtos reais, extraídos de data/structured/products.json
  (VendeFácil PDV, Estoque, Loja, Analytics, Pay).
- Valores reais do campo `module` presentes nos metadados do índice
  (conferidos em faiss_index/index.pkl: pdv, estoque, ecommerce, analytics,
  pay).
- Valores reais do campo `doc_type` presentes no índice (ticket, customer,
  employee, product, store, sale, manual, ata, policy, email, log).
- Termos operacionais frequentes nos manuais/políticas reais do dataset
  (tef, pinpad, sangria, sla, nfe, lgpd, reembolso etc.).

Mitigação registrada no ACOMPANHAMENTO.md do Encontro 3: "combinar a
distância com uma lista de palavras-chave do domínio (mesma lógica do
lgpd_policy.py)".
"""

import re
import unicodedata


def _normalize(text: str) -> str:
    """Remove acentos e caixa, igual ao normalize() do query_analyzer.py."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().strip().split())


# Nomes dos 5 produtos reais (data/structured/products.json)
_PRODUCT_TERMS = ["pdv", "estoque", "loja", "lojas", "analytics", "ecommerce"]

# Valores reais de doc_type presentes no índice (faiss_index/index.pkl)
_DOC_TYPE_TERMS = [
    "ticket", "tickets", "chamado", "chamados",
    "cliente", "clientes", "funcionario", "funcionarios",
    "produto", "produtos", "venda", "vendas",
    "manual", "manuais", "ata", "atas", "politica", "politicas",
    "email", "emails",
]

# Termos operacionais reais, conferidos nos manuais/políticas do dataset
_OPERATION_TERMS = [
    "vendefacil", "reembolso", "lgpd", "tef", "maquininha", "maquininhas",
    "sangria", "sincronizacao", "sla", "nfe", "nf-e", "pinpad", "firewall",
    "pay", "home office", "beneficio", "beneficios", "salario", "estoque",
    "pdv", "cnpj", "mrr", "sefaz",
]

DOMAIN_KEYWORDS = sorted(set(_PRODUCT_TERMS + _DOC_TYPE_TERMS + _OPERATION_TERMS))


def contains_domain_keyword(question: str) -> bool:
    """True se a pergunta cita algum termo real do domínio VendeFácil."""
    normalized = _normalize(question)
    for keyword in DOMAIN_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", normalized):
            return True
    return False


if __name__ == "__main__":
    testes = [
        ("Como funciona a sincronização de estoque entre lojas?", True),
        ("Quem descobriu o Brasil?", False),
        ("Me escreva um poema sobre o outono.", False),
        ("Qual é a política de reembolso da empresa?", True),
        ("Qual a capital da França?", False),
        ("Como faço bolo de chocolate?", False),
    ]
    print("Teste de contains_domain_keyword():")
    for pergunta, esperado in testes:
        obtido = contains_domain_keyword(pergunta)
        status = "OK" if obtido == esperado else "FALHOU"
        print(f"[{status}] esperado={esperado} obtido={obtido} | {pergunta}")
