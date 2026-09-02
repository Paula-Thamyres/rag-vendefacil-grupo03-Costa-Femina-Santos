import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from query_index import load_index
from domain_keywords import contains_domain_keyword
import config

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

threshold = config.OUT_OF_SCOPE_SCORE_THRESHOLD

print()
print(f"{'Categoria':<20} {'Top1':<10} {'Media top-3':<14} {'Keyword?':<10} {'Decisao (nova)':<20} Pergunta")
print("-" * 130)

acertos = 0
for categoria, pergunta in perguntas:
    resultados = vectorstore.similarity_search_with_score(pergunta, k=3)
    scores = [s for _, s in resultados]
    top1 = scores[0]
    media3 = sum(scores) / len(scores)

    tem_keyword = contains_domain_keyword(pergunta)
    # mesma lógica que vai em generate.py: keyword manda; senão, cai na distância
    if tem_keyword:
        esta_fora = False
    else:
        esta_fora = top1 > threshold

    decisao = "FORA (recusa)" if esta_fora else "DENTRO (responde)"
    esperado_fora = categoria == "FORA do escopo"
    acertou = esta_fora == esperado_fora
    if acertou:
        acertos += 1
    marcador = "OK" if acertou else "ERRO"

    print(f"{categoria:<20} {top1:<10.4f} {media3:<14.4f} {str(tem_keyword):<10} {decisao:<20} [{marcador}] {pergunta}")

print()
print(f"Acertos: {acertos}/{len(perguntas)}")
