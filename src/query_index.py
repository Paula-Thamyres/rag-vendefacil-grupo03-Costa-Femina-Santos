import os

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

INDEX_DIR = os.path.join(os.path.dirname(__file__), "..", "faiss_index")


def load_index() -> FAISS:
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return FAISS.load_local(
        INDEX_DIR,
        embeddings,
        allow_dangerous_deserialization=True,
    )


if __name__ == "__main__":
    vectorstore = load_index()
    query = "Qual a política de reembolso?"
    results = vectorstore.similarity_search(query, k=5)
    for r in results:
        print(r.metadata)
        print(r.page_content[:200])
        print("---")
