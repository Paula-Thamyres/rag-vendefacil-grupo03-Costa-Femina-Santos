from pydantic import ValidationError

from schema import RAGResponse


def test_case(name: str, data: dict):
    print("\n" + "=" * 70)
    print(name)

    try:
        response = RAGResponse.model_validate(data)
        print("VALIDAÇÃO: OK")
        print(response.model_dump())

    except ValidationError as error:
        print("VALIDAÇÃO: ERRO ESPERADO")
        print(error)


# 1. Resposta normal válida
test_case(
    "1 - RESPOSTA NORMAL VÁLIDA",
    {
        "answer": "O reembolso pode ser solicitado conforme a política interna.",
        "confidence_level": "alta",
        "sources_used": [
            {
                "filepath": "policies/reembolso.pdf",
                "chunk_id": "pdf-reembolso-1",
                "quotation": "O cliente poderá solicitar o reembolso conforme as condições previstas."
            }
        ],
        "reasoning": "A resposta está sustentada diretamente pelo documento.",
        "is_refusal": False,
        "refusal_reason": None
    }
)


# 2. Recusa válida
test_case(
    "2 - RECUSA VÁLIDA",
    {
        "answer": "Não posso fornecer esse dado.",
        "confidence_level": "recusado",
        "sources_used": [],
        "reasoning": "A solicitação envolve dado protegido.",
        "is_refusal": True,
        "refusal_reason": "lgpd"
    }
)


# 3. Resposta sem evidência - deve falhar
test_case(
    "3 - SEM EVIDÊNCIA",
    {
        "answer": "O reembolso é permitido.",
        "confidence_level": "alta",
        "sources_used": [],
        "reasoning": "Resposta sem fonte.",
        "is_refusal": False,
        "refusal_reason": None
    }
)


# 4. Recusa inconsistente - deve falhar
test_case(
    "4 - RECUSA COM CONFIANÇA ERRADA",
    {
        "answer": "Não posso fornecer esse dado.",
        "confidence_level": "alta",
        "sources_used": [],
        "reasoning": "Dado protegido.",
        "is_refusal": True,
        "refusal_reason": "lgpd"
    }
)


# 5. Valor fora do Literal - deve falhar
test_case(
    "5 - CONFIDENCE_LEVEL INVÁLIDO",
    {
        "answer": "Resposta qualquer.",
        "confidence_level": "muito alta",
        "sources_used": [
            {
                "filepath": "manual.md",
                "chunk_id": "manual-1",
                "quotation": "Trecho de evidência."
            }
        ],
        "reasoning": "Teste.",
        "is_refusal": False,
        "refusal_reason": None
    }
)