"""
Testes de sanidade para lgpd_policy.py (Etapa 3 - item 3).

Não depende de índice FAISS, LLM ou API key - testa só as funções puras de
classificação e mascaramento. Rodar com: `python src/test_lgpd_policy.py`.
"""

from lgpd_policy import classify_question, has_only_restricted_docs, mask_pii


class _FakeDoc:
    def __init__(self, sensitivity):
        self.metadata = {"sensitivity": sensitivity}


def check(name: str, condition: bool):
    status = "OK" if condition else "FALHOU"
    print(f"[{status}] {name}")
    if not condition:
        raise AssertionError(name)


# --- Classificação: RECUSAR (>= 2 perguntas, direta e indireta) ------------
check(
    "recusar: pergunta direta de salário",
    classify_question("Qual o salário do funcionário João Pereira?") == "recusar",
)
check(
    "recusar: pergunta indireta (folha por pessoa)",
    classify_question("Quanto a folha da equipe de suporte custa por pessoa?") == "recusar",
)
check(
    "recusar: pedido de CPF",
    classify_question("Qual o CPF do cliente CUST001?") == "recusar",
)

# --- Classificação: MASCARAR (>= 2 perguntas) ------------------------------
check(
    "mascarar: e-mail",
    classify_question("Qual o e-mail de contato do cliente CUST001?") == "mascarar",
)
check(
    "mascarar: telefone",
    classify_question("Qual o telefone do cliente CUST014?") == "mascarar",
)

# --- Classificação: RESPONDER (>= 2 perguntas) -----------------------------
check(
    "responder: pergunta sobre política pública",
    classify_question("Qual é a política de reembolso da empresa?") == "responder",
)
check(
    "responder: pergunta sobre módulo de loja",
    classify_question("Quais módulos a loja de Belo Horizonte utiliza?") == "responder",
)

# --- Prioridade: recusar tem precedência sobre mascarar --------------------
check(
    "recusar tem prioridade sobre mascarar quando os dois aparecem juntos",
    classify_question("Qual o e-mail e o salário do funcionário X?") == "recusar",
)

# --- Segunda camada de defesa: chunks só "restrito" ------------------------
check(
    "has_only_restricted_docs: todos restritos -> True",
    has_only_restricted_docs([_FakeDoc("restrito"), _FakeDoc("restrito")]) is True,
)
check(
    "has_only_restricted_docs: mistura de níveis -> False",
    has_only_restricted_docs([_FakeDoc("restrito"), _FakeDoc("interno")]) is False,
)
check(
    "has_only_restricted_docs: lista vazia -> False",
    has_only_restricted_docs([]) is False,
)

# --- Mascaramento -----------------------------------------------------------
masked_email = mask_pii("Contato: gerencia@boacompra.com.br")
check("mask_pii: e-mail mascarado, sem @ visível igual ao original", "gerencia@boacompra.com.br" not in masked_email)
check("mask_pii: e-mail mascarado preserva domínio final", masked_email.endswith(".br"))

masked_phone = mask_pii("Telefone: (31) 91234-5678")
check("mask_pii: telefone mascarado, não igual ao original", "(31) 91234-5678" not in masked_phone)
check("mask_pii: telefone mascarado preserva DDD", "(31)" in masked_phone)

masked_cpf = mask_pii("CPF: 123.456.789-01")
check("mask_pii: CPF mascarado, não igual ao original", "123.456.789-01" not in masked_cpf)

masked_card = mask_pii("Cartão: 4111 1111 1111 1111")
check("mask_pii: cartão mascarado, preserva só os 4 últimos dígitos", masked_card.strip().endswith("1111"))
check("mask_pii: cartão mascarado, não igual ao original", "4111 1111 1111 1111" not in masked_card)

print("\nTodos os testes de lgpd_policy.py passaram.")
