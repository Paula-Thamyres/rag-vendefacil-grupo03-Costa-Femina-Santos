from query_analyzer import QueryAnalyzer
from query_index import load_index


class FilteredVectorSearch:
    def __init__(self, vectorstore):
        self.vectorstore = vectorstore
        self.analyzer = QueryAnalyzer(vectorstore)

    def search(self, question: str, k: int = 5, use_filters: bool = True):
        """
        Faz busca vetorial no FAISS.

        Se use_filters=True:
        - extrai os filtros com o Query Analyzer;
        - aplica os filtros nos metadados;
        - aumenta fetch_k para evitar perder resultados válidos.
        """

        filters = self.analyzer.analyze(question).to_dict()

        # Busca normal, sem filtro
        if not use_filters or not filters:
            results = self.vectorstore.similarity_search(
                question,
                k=k
            )
            return filters, results

        # O FAISS do LangChain filtra depois da busca vetorial.
        # Como a base é pequena (~5.715 chunks), buscamos candidatos
        # suficientes para garantir que o filtro seja aplicado corretamente.
        fetch_k = len(self.vectorstore.index_to_docstore_id)

        results = self.vectorstore.similarity_search(
            question,
            k=k,
            fetch_k=fetch_k,
            filter=filters
        )

        return filters, results

    @staticmethod
    def validate_results(results, filters):
        """
        Confere se todos os resultados realmente obedecem aos filtros.
        """
        for doc in results:
            for field, expected in filters.items():
                actual = doc.metadata.get(field)

                if str(actual) != str(expected):
                    raise AssertionError(
                        f"Filtro inválido: {field} esperado={expected}, encontrado={actual}"
                    )

        return True


def print_results(title, results):
    print(f"\n{title}")

    if not results:
        print("Nenhum resultado encontrado.")
        return

    for i, doc in enumerate(results, 1):
        metadata = doc.metadata

        print(
            f"{i}. "
            f"chunk={metadata.get('chunk_id')} | "
            f"tipo={metadata.get('doc_type')} | "
            f"estado={metadata.get('state')} | "
            f"módulo={metadata.get('module')}"
        )

        print(f"   {doc.page_content[:150].replace(chr(10), ' ')}...")


if __name__ == "__main__":
    vectorstore = load_index()
    search_engine = FilteredVectorSearch(vectorstore)

    questions = [
        "Quais tickets de clientes de Minas Gerais estão relacionados ao módulo de estoque?",
        "Mostre os tickets de São Paulo relacionados ao módulo de estoque",
        "Quais chamados do Rio de Janeiro estão relacionados ao módulo de estoque?",
    ]

    for question in questions:
        print("\n" + "=" * 80)
        print(f"PERGUNTA: {question}")

        # Busca sem filtro
        _, results_without_filter = search_engine.search(
            question,
            k=5,
            use_filters=False
        )

        # Busca com filtro
        filters, results_with_filter = search_engine.search(
            question,
            k=5,
            use_filters=True
        )

        print(f"\nFiltros extraídos: {filters}")

        print_results(
            "SEM FILTRO:",
            results_without_filter
        )

        print_results(
            "COM FILTRO:",
            results_with_filter
        )

        # Validação automática
        search_engine.validate_results(
            results_with_filter,
            filters
        )

        print("\nValidação dos filtros: OK")