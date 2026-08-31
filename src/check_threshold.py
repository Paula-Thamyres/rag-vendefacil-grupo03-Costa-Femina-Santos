import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from query_index import load_index

print("Carregando índice...")
vectorstore = load_index()

perguntas = [
    ("DENTRO do escopo", "Como funciona a sincronização de estoque entre lojas?"),
    ("DENTRO do escopo", "Qual é a política de reembolso da empresa?"),
    ("DENTRO do escopo", "Quais tickets de clientes de Minas Gerais estão relacionados ao módulo de estoque?"),
    ("DENTRO do escopo", "Qual o e-mail de contato do cliente CUST001?"),
    ("FORA do escopo", "Quem descobriu o Brasil?"),
    ("FORA do escopo", "Me escreva um poema sobre o outono."),
    ("FORA do escopo", "Qual a capital da França?"),
    ("FORA do escopo", "Como faço bolo de chocolate?"),
]

print()
print(f"{'Categoria':<20} {'Top1':<10} {'Media top-3':<14} Pergunta")
print("-" * 100)

for categoria, pergunta in perguntas:
    resultados = vectorstore.similarity_search_with_score(pergunta, k=3)
    scores = [s for _, s in resultados]
    top1 = scores[0]
    media3 = sum(scores) / len(scores)
    print(f"{categoria:<20} {top1:<10.4f} {media3:<14.4f} {pergunta}")