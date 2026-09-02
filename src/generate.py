import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import json

from pydantic import ValidationError

import config
from hybrid_search import HybridRetriever
from lgpd_policy import classify_question, has_only_restricted_docs, mask_pii
from query_analyzer import QueryAnalyzer
from query_index import load_index
from schema import RAGResponse, SourceEvidence
from search import FilteredVectorSearch
from domain_keywords import contains_domain_keyword

SYSTEM_PROMPT = """\
Você é o assistente RAG interno da VendeFácil Tecnologia Ltda.

Responda SOMENTE com base no CONTEXTO fornecido pelo usuário. Nunca use
conhecimento próprio fora do CONTEXTO, mesmo que você "saiba" a resposta.

Sua saída deve ser SOMENTE um objeto JSON válido, sem nenhum texto antes ou
depois, sem markdown, seguindo EXATAMENTE este formato:

{
  "answer": "resposta em linguagem natural, objetiva, baseada só no contexto",
  "confidence_level": "alta" | "media" | "baixa",
  "sources_used": [
    {
      "filepath": "valor idêntico ao source_file do chunk usado",
      "chunk_id": "valor idêntico ao chunk_id do chunk usado",
      "quotation": "trecho LITERAL (copiado, não parafraseado) do chunk, até 500 caracteres"
    }
  ],
  "reasoning": "explicação breve de como você chegou na resposta a partir do contexto",
  "is_refusal": false,
  "refusal_reason": null
}

Regras obrigatórias:
- "sources_used" deve ter pelo menos 1 item sempre que "is_refusal" for false.
- Cada "quotation" deve ser um trecho literal do chunk citado (não invente, não resuma).
- Se o CONTEXTO não tiver informação suficiente para responder com segurança,
  responda com "is_refusal": true, "confidence_level": "recusado",
  "sources_used": [], "refusal_reason": "sem_evidencia".
- Nunca marque "confidence_level" como "recusado" se "is_refusal" for false, e vice-versa.
"""


def _build_context(docs) -> str:
    blocks = []
    for doc in docs:
        meta = doc.metadata
        header = (
            f"[chunk_id={meta.get('chunk_id')} | source_file={meta.get('source_file')} | "
            f"doc_type={meta.get('doc_type')}]"
        )
        blocks.append(f"{header}\n{doc.page_content}")
    return "\n\n---\n\n".join(blocks)


def _refusal(reason: str, message: str) -> RAGResponse:
    return RAGResponse(
        answer=message,
        confidence_level="recusado",
        sources_used=[],
        reasoning=(
            "Recusa aplicada antes da chamada ao LLM, com base na política de "
            "LGPD / disponibilidade de evidência (ver lgpd_policy.py)."
        ),
        is_refusal=True,
        refusal_reason=reason,
    )


def retrieve(question: str, vectorstore, analyzer: QueryAnalyzer,
             filtered_search: FilteredVectorSearch, hybrid_retriever: HybridRetriever,
             k: int = 5):

    filters = analyzer.analyze(question).to_dict()

    if filters:
        _, docs = filtered_search.search(question, k=k, use_filters=True)
        return docs, filters

    fused = hybrid_retriever.hybrid_search(question, k=k)
    return [doc for doc, _score in fused], filters


def is_out_of_scope(question: str, vectorstore, threshold: float = None) -> bool:

    if contains_domain_keyword(question):
        return False

    threshold = threshold if threshold is not None else config.OUT_OF_SCOPE_SCORE_THRESHOLD
    results = vectorstore.similarity_search_with_score(question, k=1)
    if not results:
        return True
    _, score = results[0]
    return score > threshold


def generate_structured_response(question: str, context: str,
                                  max_retries: int = None) -> RAGResponse:
    """
    Chama o LLM pedindo saída no formato RAGResponse e valida com Pydantic.
    Em caso de falha de validação, pede pro próprio modelo corrigir (retry),
    em vez de silenciar o erro com `except: pass`.
    """
    max_retries = max_retries if max_retries is not None else config.MAX_RETRIES

    user_prompt = f"PERGUNTA: {question}\n\nCONTEXTO:\n{context}"
    last_error = None

    for attempt in range(1, max_retries + 1):
        raw = _call_llm(SYSTEM_PROMPT, user_prompt)

        try:
            data = json.loads(raw)
            return RAGResponse.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as error:
            last_error = error
            user_prompt = (
                f"PERGUNTA: {question}\n\nCONTEXTO:\n{context}\n\n"
                f"Sua resposta anterior (tentativa {attempt}) não seguiu o formato "
                f"exigido. Erro de validação: {error}\n"
                f"Responda de novo, SOMENTE com o JSON correto, corrigindo o erro acima."
            )

    raise RuntimeError(
        f"Não foi possível gerar uma resposta válida após {max_retries} tentativas. "
        f"Último erro: {last_error}"
    )


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """Isolado numa função própria para ser fácil de trocar de provedor/mocar em teste."""
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL)
    response = client.chat.completions.create(
        model=config.GENERATION_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


def _apply_masking(response: RAGResponse) -> RAGResponse:
    masked_sources = [
        SourceEvidence(
            filepath=source.filepath,
            chunk_id=source.chunk_id,
            quotation=mask_pii(source.quotation),
        )
        for source in response.sources_used
    ]
    return RAGResponse(
        answer=mask_pii(response.answer),
        confidence_level=response.confidence_level,
        sources_used=masked_sources,
        reasoning=response.reasoning,
        is_refusal=response.is_refusal,
        refusal_reason=response.refusal_reason,
    )


def answer_question(question: str, vectorstore, analyzer: QueryAnalyzer,
                     filtered_search: FilteredVectorSearch,
                     hybrid_retriever: HybridRetriever) -> RAGResponse:
    """Função principal: pergunta em texto livre -> RAGResponse validado."""

    category = classify_question(question)

    if is_out_of_scope(question, vectorstore):
        return _refusal(
            "fora_de_escopo",
            "Essa pergunta não está relacionada à operação da VendeFácil, "
            "então não posso respondê-la com base na minha base de conhecimento.",
        )

    docs, _filters = retrieve(question, vectorstore, analyzer, filtered_search, hybrid_retriever)

    if not docs:
        return _refusal(
            "sem_evidencia",
            "Não encontrei nenhum documento relevante na base para responder a essa pergunta.",
        )

    if category == "recusar" or has_only_restricted_docs(docs):
        return _refusal(
            "lgpd",
            "Não posso fornecer esse dado, pois envolve informação pessoal protegida "
            "pela LGPD (ex.: remuneração individual, CPF, dados bancários, "
            "credenciais ou dados de saúde).",
        )

    context = _build_context(docs)
    response = generate_structured_response(question, context)

    if category == "mascarar" and not response.is_refusal:
        response = _apply_masking(response)

    return response


if __name__ == "__main__":
    vectorstore = load_index()
    analyzer = QueryAnalyzer(vectorstore)
    filtered_search = FilteredVectorSearch(vectorstore)
    hybrid_retriever = HybridRetriever(vectorstore)

    # >= 2 perguntas por categoria, conforme critério de pronto da Etapa 3.
    TEST_QUESTIONS = [
        # RECUSAR (LGPD)
        "Qual o salário do funcionário com maior remuneração?",
        "Quanto a folha da equipe de suporte custa por pessoa?",
        # MASCARAR
        "Qual o e-mail de contato do cliente CUST001?",
        "Qual o telefone de contato registrado para o cliente CUST014?",
        # RESPONDER
        "Qual é a política de reembolso da empresa?",
        "Como funciona a sincronização de estoque entre lojas?",
        # FORA DE ESCOPO
        "Quem descobriu o Brasil?",
        "Me escreva um poema sobre o outono.",
    ]

    for question in TEST_QUESTIONS:
        print("\n" + "=" * 80)
        print(f"PERGUNTA: {question}")
        try:
            response = answer_question(
                question, vectorstore, analyzer, filtered_search, hybrid_retriever
            )
            print(response.model_dump_json(indent=2, exclude_none=False))
        except Exception as error:
            print(f"ERRO ao gerar resposta: {error}")
