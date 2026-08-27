from collections import Counter

from query_index import load_index

TEST_QUESTIONS = [
    "Qual é a política de reembolso da empresa?",
    "Como funciona a sincronização de estoque entre lojas?",
    "O que fazer em caso de vazamento de dados segundo a política de segurança e LGPD?",
]


def main():
    vectorstore = load_index()

    all_docs = list(vectorstore.docstore._dict.values())
    print(f"Total de chunks indexados: {len(all_docs)}\n")

    doc_types = Counter(doc.metadata.get("doc_type", "desconhecido") for doc in all_docs)
    print("Distribuição por doc_type:")
    for doc_type, count in doc_types.items():
        print(f"  {doc_type}: {count}")

    print("\nPerguntas de teste e os 5 chunks mais similares:\n")
    for question in TEST_QUESTIONS:
        print(f"Pergunta: {question}")
        results = vectorstore.similarity_search(question, k=5)
        for i, r in enumerate(results, 1):
            snippet = r.page_content[:120].replace("\n", " ")
            print(f"  {i}. [{r.metadata.get('doc_type')}] {snippet}...")
        print()


if __name__ == "__main__":
    main()
