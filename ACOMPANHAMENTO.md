# Acompanhamento - Mini Desafio RAG VendeFácil

**Integrante:** Paula Thamyres da Silva Femina - @Paula-Thamyres https://github.com/Paula-Thamyres

**Repositório:** `rag-vendefacil-<seu-grupo>-<seu-sobrenome>`

---

## Encontro 1 - 2026-08-26

**Etapa:** 1 - Ingestão heterogênea, metadados e indexação vetorial

### Relato individual - Paula Thamyres da Silva Femina

Foi implementado os leitores das seis fontes de dados em `src/loaders.py`: CSV/JSON
tabular (customers, employees, products, stores), JSONL de tickets, Markdown
(manuais, atas, políticas), PDF (políticas) e TXT (e-mails). Pra cada tipo de fonte
seguimos uma estratégia diferente de chunking em vez de usar uma configuração única -
pros dados tabulares, 1 registro vira 1 chunk, serializado em frase natural ao invés
de deixar no formato cru separado por vírgula, porque nos primeiros testes de
similaridade os chunks CSV crus não recuperavam bem (o embedding não separa campo de
valor numa string tipo "CUST001,Boa Compra,MG").

Escrevemos a primeira versão dos loaders de `customers.csv`, `products.json` e
`stores.json` olhando só pro exemplo do enunciado, e quando testei contra o dataset
de verdade do repositório-base, deu erro: o CSV de clientes não tem coluna `name`
nem `signup_date` (o certo é `company_name`, e não existe data de cadastro nesse
dataset), e os JSONs de produto e loja não são listas na raiz - são objetos com as
chaves `"products"` e `"network_stores"`. Travei uns 20 minutos tentando entender por
que `products.json` estourava `AttributeError: 'str' object has no attribute 'get'`
até perceber que estava iterando as chaves do dicionário em vez da lista de dentro.
Puxei `state` e `module` dos tickets pros
metadados também, já que a Etapa 2 vai precisar filtrar por isso.

Rodei o pipeline de ingestão completo: bateu 5.715 chunks no
total, com a distribuição por `doc_type` batendo exatamente com a contagem de linhas
de cada arquivo fonte (2000 clientes, 3000 vendas, 450 logs, 75 tickets etc.), e
confirmei que nenhum chunk ficou sem `doc_type` ou `sensitivity`.

**Uso de IA:** usei o Claude pra revisar o `loaders.py` comparando com os arquivos
reais de dados (baixei os originais do repositório-base pra checar nome de coluna e
estrutura do JSON, porque só pelo exemplo do enunciado eu não tinha como saber que
`products.json` era um objeto e não uma lista). A partir dessa comparação ele apontou
os três bugs de mapeamento de campo (customers, products, stores) e sugeriu também
capturar `state`/`module` dos tickets. As correções em si eu revisei e testei rodando
contra o dataset real antes de aceitar.

### Resumo do dia

**Entreguei hoje:**
- Leitores para os 6 formatos (`csv`, `json`, `jsonl`, `md`, `pdf`, `txt`)
- Schema de metadados padronizado (Pydantic) aplicado em todos os chunks
- Chunking adaptativo por natureza da fonte
- Índice FAISS salvo em disco (`save_local`), com recarga sem reindexar (`load_local`)
- Script de sanidade rodado: 5.715 chunks, distribuição por `doc_type` conferida, top-5 pra 3 perguntas de teste

**Ficou pendente:**
- Rodar a indexação FAISS completa em ambiente com acesso ao Hugging Face (validei a ingestão/chunking, mas a geração do índice vetorial em si preciso rodar na minha máquina)

**Bloqueios em aberto:**
- Nenhum bloqueio técnico no momento

**Próximo passo (início do encontro 2):**
- Busca híbrida (embeddings + BM25) e filtro por metadados (`state`, `module`, `customer_id`)

**Uso de assistentes de IA:**
- Claude usado para revisar os loaders contra a estrutura real dos dados e apontar os bugs de mapeamento de campo descritos acima; correção e teste feitos por mim.

---
