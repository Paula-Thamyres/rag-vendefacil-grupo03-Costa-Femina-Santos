import argparse
import json
import os
import sys
import time
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
sys.path.insert(0, PROJECT_ROOT)

from openai import RateLimitError

import config
from generate import answer_question, retrieve, _build_context
from query_index import load_index
from query_analyzer import QueryAnalyzer
from search import FilteredVectorSearch
from hybrid_search import HybridRetriever
from judge_prompt import call_judge

BENCHMARK_PATH = os.path.join(PROJECT_ROOT, "benchmark", "questions_and_ground_truth.json")
RESULTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
RELATORIO_PATH = os.path.join(PROJECT_ROOT, "RELATORIO.md")


def _infer_expected_refusal(ground_truth_answer: str):
    """
    Toda ground_truth_answer que espera recusa começa literalmente com um desses
    marcadores (confirmado lendo as 24 perguntas) - evita manter uma lista de IDs
    hardcoded, e trata corretamente Q17 (mesma categoria "Guardrails & LGPD", mas
    com resposta normal esperada).
    """
    text = ground_truth_answer.strip().upper()
    if text.startswith("FORA DO ESCOPO"):
        return True, "fora_de_escopo"
    if text.startswith("RECUSA DE RESPOSTA"):
        return True, "lgpd"
    return False, None


def _normalize_source_path(path: str) -> str:
    """expected_sources vem com prefixo 'data/'; o metadado real gravado na
    ingestão (e ecoado em sources_used) não tem esse prefixo."""
    return path.replace("\\", "/").removeprefix("data/")


def _sources_recall(expected_sources, sources_used):
    if not expected_sources:
        return None
    expected_norm = {_normalize_source_path(p) for p in expected_sources}
    actual_norm = {_normalize_source_path(s.filepath) for s in sources_used}
    return len(expected_norm & actual_norm) / len(expected_norm)


def _load_benchmark(limit=None, ids=None):
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = data["questions"]
    if ids:
        wanted = set(ids)
        questions = [q for q in questions if q["id"] in wanted]
    if limit is not None:
        questions = questions[:limit]

    return data, questions


def _call_with_rate_limit_retry(func, *args, max_attempts=4, backoff_seconds=12, **kwargs):
    """O tier gratuito da Groq tem um limite baixo de tokens/minuto (TPM); espera e
    tenta de novo em vez de contar essa pergunta como erro por causa disso."""
    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except RateLimitError:
            if attempt == max_attempts:
                raise
            print(f"    (rate limit da API, aguardando {backoff_seconds}s antes de tentar de novo...)")
            time.sleep(backoff_seconds)


def _run_question(q, vectorstore, analyzer, filtered_search, hybrid_retriever, skip_judge):
    expected_refusal, expected_refusal_reason = _infer_expected_refusal(q["ground_truth_answer"])

    record = {
        "id": q["id"],
        "category": q["category"],
        "question": q["question"],
        "expected_sources": q["expected_sources"],
        "expected_metadata": q["expected_metadata"],
        "ground_truth_answer": q["ground_truth_answer"],
        "key_points_for_evaluation": q["key_points_for_evaluation"],
        "expected_refusal": expected_refusal,
        "error": None,
        "generation": None,
        "filters_used": None,
        "sources_recall": None,
        "refusal_check": None,
        "judge": None,
        "pass": False,
    }

    t0 = time.perf_counter()
    try:
        response = _call_with_rate_limit_retry(
            answer_question, q["question"], vectorstore, analyzer, filtered_search, hybrid_retriever
        )
    except Exception as error:
        record["error"] = f"Erro na geração: {error}"
        return record
    generation_latency = time.perf_counter() - t0

    record["generation"] = {
        "answer": response.answer,
        "confidence_level": response.confidence_level,
        "is_refusal": response.is_refusal,
        "refusal_reason": response.refusal_reason,
        "sources_used": [s.model_dump() for s in response.sources_used],
        "reasoning": response.reasoning,
        "latency_seconds": round(generation_latency, 3),
    }

    if expected_refusal or response.is_refusal:
        refusal_check = {
            "expected_refusal": expected_refusal,
            "actual_refusal": response.is_refusal,
            "correct": expected_refusal == response.is_refusal,
            "expected_refusal_reason": expected_refusal_reason,
            "actual_refusal_reason": response.refusal_reason,
            "refusal_reason_correct": (
                response.refusal_reason == expected_refusal_reason
                if expected_refusal and response.is_refusal else None
            ),
        }
        record["refusal_check"] = refusal_check
        record["pass"] = refusal_check["correct"]
        return record

    record["sources_recall"] = _sources_recall(q["expected_sources"], response.sources_used)

    if skip_judge:
        record["pass"] = None
        return record

    try:
        docs, filters_used = retrieve(q["question"], vectorstore, analyzer, filtered_search, hybrid_retriever)
        record["filters_used"] = filters_used
        context_text = _build_context(docs)

        t1 = time.perf_counter()
        judge = _call_with_rate_limit_retry(
            call_judge, q["question"], context_text, response.answer,
            q["ground_truth_answer"], q["key_points_for_evaluation"],
        )
        judge_latency = time.perf_counter() - t1

        record["judge"] = {
            "context_relevance": judge.context_relevance.model_dump(),
            "groundedness": judge.groundedness.model_dump(),
            "answer_relevance": judge.answer_relevance.model_dump(),
            "key_points_coverage": judge.key_points_coverage.model_dump(),
            "overall_correct": judge.overall_correct,
            "overall_justification": judge.overall_justification,
            "latency_seconds": round(judge_latency, 3),
        }
        record["pass"] = judge.overall_correct
    except Exception as error:
        record["error"] = f"Erro no juiz: {error}"
        record["pass"] = False

    return record


def run_benchmark(limit=None, ids=None, skip_judge=False):
    if not config.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY não configurada. Defina-a no arquivo .env antes de rodar o benchmark."
        )

    data, questions = _load_benchmark(limit=limit, ids=ids)

    print("Carregando índice FAISS...")
    vectorstore = load_index()
    analyzer = QueryAnalyzer(vectorstore)
    filtered_search = FilteredVectorSearch(vectorstore)
    hybrid_retriever = HybridRetriever(vectorstore)

    total = len(questions)
    results = []
    print(f"\nRodando {total} pergunta(s) do benchmark...\n")

    for i, q in enumerate(questions, start=1):
        record = _run_question(q, vectorstore, analyzer, filtered_search, hybrid_retriever, skip_judge)
        results.append(record)

        if record["error"]:
            status = f"ERRO: {record['error']}"
        elif record["pass"] is None:
            status = "gerado (juiz pulado)"
        elif record["pass"]:
            status = "PASS"
        else:
            status = "FAIL"

        print(f"[{i}/{total}] {record['id']} ({record['category']}) - {status}")

    run_metadata = {
        "benchmark_name": data.get("benchmark_name"),
        "benchmark_version": data.get("version"),
        "generated_at": datetime.now().astimezone().isoformat(),
        "generation_model": config.GENERATION_MODEL,
        "judge_model": config.GENERATION_MODEL,
        "out_of_scope_score_threshold": config.OUT_OF_SCOPE_SCORE_THRESHOLD,
        "total_questions": total,
        "skip_judge": skip_judge,
    }

    _write_results_json(run_metadata, results)
    _write_relatorio(run_metadata, results, data)

    return run_metadata, results


def _write_results_json(run_metadata, results):
    payload = {"run_metadata": run_metadata, "results": results}
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\nResultados salvos em: {RESULTS_PATH}")


def _mean(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _build_relatorio_markdown(run_metadata, results, benchmark_data):
    lines = []
    lines.append(f"# Relatório do Benchmark - {run_metadata['benchmark_name']}")
    lines.append("")
    lines.append(f"- Executado em: {run_metadata['generated_at']}")
    lines.append(f"- Modelo de geração: {run_metadata['generation_model']}")
    lines.append(f"- Modelo do juiz: {run_metadata['judge_model']}")
    lines.append(f"- Threshold de fora-de-escopo: {run_metadata['out_of_scope_score_threshold']}")
    lines.append(f"- Total de perguntas executadas: {run_metadata['total_questions']}")
    lines.append("")

    declared_description = benchmark_data.get("description", "")
    actual_count = len(benchmark_data.get("questions", []))
    lines.append("## Nota sobre o arquivo de benchmark")
    lines.append("")
    lines.append(
        f"A descrição do arquivo `benchmark/questions_and_ground_truth.json` diz: "
        f"\"{declared_description}\", mas o array `questions` contém **{actual_count} "
        f"perguntas**. Recomenda-se corrigir o texto da descrição no JSON para "
        f"refletir o número real."
    )
    lines.append("")

    errors = [r for r in results if r["error"]]
    judged = [r for r in results if r["judge"]]
    passed = [r for r in results if r["pass"] is True]
    failed_or_error = [r for r in results if r["pass"] is not True]

    lines.append("## Resumo agregado")
    lines.append("")
    lines.append(f"- Perguntas com PASS: {len(passed)}/{len(results)}")
    lines.append(f"- Perguntas com FAIL ou erro: {len(failed_or_error)}/{len(results)}")
    lines.append(f"- Erros de execução: {len(errors)}")

    refusal_checks = [r["refusal_check"] for r in results if r["refusal_check"]]
    if refusal_checks:
        refusal_correct = sum(1 for rc in refusal_checks if rc["correct"])
        lines.append(f"- Acurácia de recusa: {refusal_correct}/{len(refusal_checks)}")

    if judged:
        ctx_mean = _mean([r["judge"]["context_relevance"]["score"] for r in judged])
        ground_mean = _mean([r["judge"]["groundedness"]["score"] for r in judged])
        ans_mean = _mean([r["judge"]["answer_relevance"]["score"] for r in judged])
        lines.append(f"- Context Relevance (média, 1-5): {ctx_mean:.2f}")
        lines.append(f"- Groundedness (média, 1-5): {ground_mean:.2f}")
        lines.append(f"- Answer Relevance (média, 1-5): {ans_mean:.2f}")
    lines.append("")

    lines.append("## Detalhamento por categoria")
    lines.append("")
    lines.append("| Categoria | N | PASS | FAIL/erro | Context Rel. | Groundedness | Answer Rel. |")
    lines.append("|---|---|---|---|---|---|---|")

    categories = []
    for r in results:
        if r["category"] not in categories:
            categories.append(r["category"])

    for category in categories:
        cat_results = [r for r in results if r["category"] == category]
        cat_pass = sum(1 for r in cat_results if r["pass"] is True)
        cat_fail = len(cat_results) - cat_pass
        cat_judged = [r for r in cat_results if r["judge"]]
        ctx = _mean([r["judge"]["context_relevance"]["score"] for r in cat_judged])
        ground = _mean([r["judge"]["groundedness"]["score"] for r in cat_judged])
        ans = _mean([r["judge"]["answer_relevance"]["score"] for r in cat_judged])
        ctx_s = f"{ctx:.2f}" if ctx is not None else "-"
        ground_s = f"{ground:.2f}" if ground is not None else "-"
        ans_s = f"{ans:.2f}" if ans is not None else "-"
        lines.append(f"| {category} | {len(cat_results)} | {cat_pass} | {cat_fail} | {ctx_s} | {ground_s} | {ans_s} |")
    lines.append("")

    lines.append("## Detalhamento por pergunta")
    lines.append("")
    lines.append("| ID | Categoria | Status | Recusa (esp./real) | Confiança | Sources recall |")
    lines.append("|---|---|---|---|---|---|")
    for r in results:
        status = "ERRO" if r["error"] else ("PASS" if r["pass"] else "FAIL")
        expected_r = "sim" if r["expected_refusal"] else "não"
        if r["generation"]:
            actual_r = "sim" if r["generation"]["is_refusal"] else "não"
            confidence = r["generation"]["confidence_level"]
        else:
            actual_r = "-"
            confidence = "-"
        recall = f"{r['sources_recall']:.0%}" if r["sources_recall"] is not None else "-"
        lines.append(f"| {r['id']} | {r['category']} | {status} | {expected_r}/{actual_r} | {confidence} | {recall} |")
    lines.append("")

    if errors:
        lines.append("## Falhas e erros de execução")
        lines.append("")
        for r in errors:
            lines.append(f"- **{r['id']}** ({r['category']}): {r['error']}")
        lines.append("")

    lines.append("## Limitações conhecidas")
    lines.append("")
    lines.append(
        "- O juiz LLM usa o mesmo modelo de geração (viés de auto-avaliação, "
        "conhecido em setups de LLM-as-judge)."
    )
    lines.append(
        "- O threshold de fora-de-escopo foi calibrado empiricamente (ver "
        "`src/check_threshold.py`) e pode gerar falsos positivos/negativos em "
        "perguntas de fronteira."
    )
    lines.append("")

    return "\n".join(lines)


def _write_relatorio(run_metadata, results, benchmark_data):
    markdown = _build_relatorio_markdown(run_metadata, results, benchmark_data)
    with open(RELATORIO_PATH, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"Relatório salvo em: {RELATORIO_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Roda o benchmark do VendeFácil RAG.")
    parser.add_argument("--limit", type=int, default=None, help="Roda só as N primeiras perguntas.")
    parser.add_argument("--ids", type=str, default=None, help="IDs separados por vírgula (ex: Q01,Q05).")
    parser.add_argument("--skip-judge", action="store_true", help="Pula a chamada ao juiz LLM.")
    args = parser.parse_args()

    ids = [i.strip() for i in args.ids.split(",")] if args.ids else None
    run_benchmark(limit=args.limit, ids=ids, skip_judge=args.skip_judge)


if __name__ == "__main__":
    main()
