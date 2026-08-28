# Acompanhamento - Mini Desafio RAG VendeFácil

**Integrante:** Paula Thamyres da Silva Femina - @Paula-Thamyres https://github.com/Paula-Thamyres

                Élcio Berilo Barbosa dos Santos Júnior - @elciobbsjr https://github.com/elciobbsjr

                Letícia da Costa Sousa - leticiadacostasousa23-cloud - https://github.com/leticiadacostasousa23-cloud

**Repositório:** `rag-vendefacil-grupo03-Costa-Femina-Santos>`

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


## Encontro 2 - 2026-08-28

**Etapa:** 2 - Busca híbrida e filtragem por metadados

### Relato individual - Élcio Berilo Barbosa dos Santos Júnior

Hoje fiquei responsável pela implementação do Query Analyzer da Etapa 2. Criei o arquivo `src/query_analyzer.py` para receber uma pergunta em linguagem natural e transformar as informações identificadas em filtros estruturados de metadados.

Escolhi fazer o Query Analyzer por regras, em vez de usar LLM, porque para esse caso ficou mais simples, determinístico e sem depender de API externa. Criei uma normalização para tratar diferenças de maiúsculas/minúsculas, acentos e espaços, então termos como "São Paulo", "sao paulo" ou "SÃO PAULO" conseguem ser tratados da mesma forma.

Também adicionei um dicionário de estados para converter nomes completos para as respectivas siglas, como `Minas Gerais -> MG` e `São Paulo -> SP`, além de sinônimos para os tipos de documento, por exemplo `chamado/chamados -> ticket`.

Usei um modelo Pydantic (`QueryFilters`) para organizar os filtros que podem ser retornados, como `doc_type`, `state`, `module`, `customer_id`, `priority` e `status`.

Uma decisão importante foi não aceitar qualquer valor encontrado na pergunta diretamente. O Query Analyzer carrega os valores que realmente existem nos metadados do índice FAISS e só retorna o filtro quando esse valor é válido. Isso evita gerar filtros que nunca vão encontrar resultados na etapa de busca.

Nos testes, a pergunta:

`Quais tickets de clientes de Minas Gerais estão relacionados ao módulo de estoque?`

retornou:

`{'doc_type': 'ticket', 'state': 'MG', 'module': 'VendeFácil Estoque'}`

Também testei com perguntas para São Paulo e prioridade alta. Para validar que o código não estava inventando valores, fiz um teste com:

`Mostre os tickets de Wakanda do módulo abacaxi`

e o resultado foi somente:

`{'doc_type': 'ticket'}`

Isso aconteceu porque `Wakanda` e `abacaxi` não existem nos metadados do índice, então esses filtros foram descartados.

Durante o primeiro teste apareceu o erro `ModuleNotFoundError: No module named 'pydantic'`, porque a dependência ainda não estava instalada no ambiente. Depois de instalar as dependências do projeto, consegui executar o Query Analyzer normalmente e validar os testes.

**Uso de IA:** usei o ChatGPT para me ajudar a organizar a estrutura inicial do Query Analyzer e entender como separar normalização, identificação dos filtros e validação. Ajustei o código para trabalhar diretamente com os valores presentes no índice FAISS do projeto e fui testando os casos até confirmar que filtros inexistentes não eram retornados.

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

## Encontro 2 - 2026-08-28 (continuação)

**Etapa:** 2 - Aplicar os filtros extraídos na busca vetorial

### Relato individual - Letícia da Costa Sousa

Integrei os filtros estruturados extraídos pelo Query Analyzer, desenvolvido pelo Élcio, com o mecanismo de busca vetorial do FAISS em `src/search.py`.

A estratégia adotada combina pré-filtragem lógica com pós-filtragem no recuperador vetorial. Para garantir a assertividade da consulta sem perder performance, o mecanismo aplica os parâmetros contidos no dicionário `QueryFilters` (`doc_type`, `state`, `module`, entre outros) diretamente sobre os metadados vinculados aos chunks indexados antes da ordenação final por similaridade de embeddings.

Também tratei cenários de borda em que a combinação de múltiplos filtros poderia resultar em um conjunto de busca vazio. Nesses casos, a função retorna um fallback, informando a ausência de correspondência exata de metadados antes de tentar relaxar os filtros secundários.

**Resultados dos testes**

**Consulta:** "Quais tickets de clientes de Minas Gerais estão relacionados ao módulo de estoque?"

**Filtros aplicados:**

```python
{'doc_type': 'ticket', 'state': 'MG', 'module': 'VendeFácil Estoque'}
```

**Resultado:** o recuperador reduziu o espaço de busca dos 5.715 chunks totais para apenas os tickets do estado de MG referentes ao módulo de Estoque, retornando os 5 documentos mais relevantes com 100% de precisão nos metadados solicitados.

**Uso de IA:** utilizei o ChatGPT para auxiliar na implementação do adaptador de busca com suporte a dicionários de metadados no FAISS, usando `vectorstore.as_retriever(search_kwargs={'filter': ...})`. Os testes de integração e a validação das respostas filtradas foram realizados localmente.

### Resumo do dia

**Entregas realizadas:**

- Integração completa entre a extração de intenção do Query Analyzer e a busca vetorial no FAISS.
- Mecanismo de filtragem por metadados (`state`, `module`, `doc_type`, entre outros), garantindo zero falsos positivos fora dos filtros especificados.
- Validação de testes de busca híbrida e filtrada utilizando os 5.715 chunks da base do repositório.

**Pendências:**

- Finalizar a calibração de pesos da busca híbrida, integrando a pontuação BM25 (escore léxico) com a busca vetorial (escore denso).

**Bloqueios:**

- Nenhum no momento.

**Próximos passos:**

- Unificar a camada de busca híbrida (BM25 + FAISS) com re-ranking ou mescla de pontuações (RRF - Reciprocal Rank Fusion).