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

> **Nota de manutenção (2026-08-31):** este bloco ficou salvo no repositório com
> marcadores de conflito de merge (`<<<<<<<`, `=======`, `>>>>>>>`) ainda presentes
> no arquivo, ou seja, o conflito entre os dois relatos abaixo nunca tinha sido
> resolvido de fato - só commitado como estava. Os marcadores foram removidos aqui
> para o arquivo voltar a ser Markdown válido, mas **nenhum conteúdo de nenhum dos
> dois relatos foi alterado ou removido**. Ver também o relato do Élcio em
> "Encontro 2 - 2026-08-31 (continuação)", que documenta que `src/search.py`
> não estava de fato presente no código do repositório quando ele revisou a Etapa 2.

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

---

## Encontro 2 - 2026-08-28 (continuação) - item 2 da Etapa 2

**Etapa:** 2 - Busca híbrida (densa + BM25) com fusão RRF

### Relato individual - Paula Thamyres da Silva Femina

Hoje fiquei com o item 2 da Etapa 2: combinar a busca densa (embeddings, via FAISS) com a busca esparsa (BM25), fundindo os dois rankings. Criei o arquivo
`src/hybrid_search.py` em cima do índice que já tinha montado na Etapa 1 - não precisei reprocessar nenhum arquivo de origem, só li os chunks direto do
docstore do FAISS pra montar o índice BM25 em cima do mesmo conjunto de documentos.

A primeira dúvida que tive foi como fundir os dois rankings, porque densa e esparsa devolvem scores em escalas totalmente diferentes (cosseno de
embedding não é comparável com score de BM25). Segui a recomendação do enunciado e usei Reciprocal Rank Fusion em vez de somar os scores: pra cada
recuperador, cada documento ganha `1 / (60 + posição no ranking)`, e eu somo essa pontuação nos dois rankings. Quem aparece bem posicionado nos dois
recuperadores sobe, e quem só aparece em um ainda tem chance de entrar no top-k final se a posição for boa o suficiente.

Pra montar o BM25 escrevi uma tokenização simples (minúsculo, sem acento, só letra/número) porque sem isso "São Paulo" e "sao paulo" viravam tokens
diferentes e o BM25 perdia sobreposição de termo à toa - reaproveitei amesma lógica de normalização que o Élcio já tinha usado no Query Analyzer,
só que aplicada token a token em vez de string inteira.

Fiz questão de escolher perguntas de teste que mostrassem os dois lados falhando sozinhos, como pede o enunciado: uma pergunta bem parafraseada, sem
nenhum termo literal do documento, pra evidenciar onde o BM25 (que só olha sobreposição de palavra) fica atrás do denso; e uma pergunta citando o
código exato de um ticket, onde o denso tende a perder pro BM25, que acha o identificador de cara mesmo sem entender o "significado" da frase. Rodei as
duas buscas separadas e a fusão lado a lado pra cada pergunta, pra deixar registrado o caso em que cada recuperador sozinho erra e a fusão corrige.

Uma coisa que me deixou em dúvida no início foi se o item 3 do enunciado (aplicar os filtros extraídos na busca vetorial) era parte da Etapa 2 ou já
seria Etapa 3 - reli o enunciado com calma e percebi que os itens 1, 2 e 3 são todos objetivos da própria Etapa 2 (a Etapa 3 é outra parte da trilha,
sobre síntese/Pydantic/LGPD). Como a gente dividiu o trio por item dentro da Etapa 2, fiz só o item 2 (fusão) e deixei o item 3 (aplicar o filtro na
busca) pro colega que ficou responsável por ele.

**Uso de IA:** usei o Claude pra tirar essa dúvida sobre a divisão dos itens2 e 3 dentro do enunciado da Etapa 2, e pra revisar a implementação da fusão
RRF (conferir se a fórmula estava certa e se eu não deveria somar os scores brutos das duas buscas). Também usei pra validar a lógica de tokenização do
BM25 com um teste isolado antes de rodar contra o índice real. A escolha das perguntas de teste e a execução contra o índice FAISS da minha máquina eu
fiz e conferi por mim.

---

## Encontro 2 - 2026-08-31 (continuação)

**Etapa:** 2 - Busca híbrida e filtragem por metadados

### Relato individual - Élcio Berilo Barbosa dos Santos Júnior

Hoje retomei a Etapa 2 para revisar a integração entre o Query Analyzer e a aplicação dos filtros na busca vetorial.

Durante essa revisão, percebi que o item 3 da Etapa 2, referente à aplicação dos filtros extraídos na busca vetorial, aparecia no `ACOMPANHAMENTO.md` como já implementado, inclusive com referência ao arquivo `src/search.py`. Porém, ao conferir os arquivos atuais do repositório, essa implementação não estava presente. Por isso, precisei implementar e testar essa parte antes de considerar a Etapa 2 concluída.

Criei o arquivo `src/search.py` para integrar o `QueryAnalyzer` com a busca vetorial no FAISS. A busca passou a receber os filtros estruturados extraídos da pergunta, como `doc_type`, `state` e `module`, e utilizar esses valores diretamente na recuperação dos documentos.

Também utilizei um `fetch_k` maior na busca com filtro, porque o FAISS do LangChain primeiro recupera os candidatos por similaridade e só depois aplica os filtros de metadados. Dessa forma, evitamos casos em que existem documentos válidos na base, mas nenhum deles aparece entre os primeiros candidatos recuperados.

Nos primeiros testes encontrei outro problema: para perguntas relacionadas ao módulo de estoque, o Query Analyzer estava retornando `VendeFácil Estoque`, enquanto os tickets utilizavam o valor `estoque` nos metadados. Por causa dessa diferença, a busca filtrada retornava zero documentos mesmo existindo tickets válidos.

Ajustei a identificação do módulo no `query_analyzer.py` para priorizar o valor que realmente corresponde ao contexto da pergunta e aos metadados dos tickets. Depois da correção, o filtro passou a retornar `module: estoque`.

Para validar a implementação, executei três consultas envolvendo estado e módulo:

- tickets de Minas Gerais relacionados ao módulo de estoque;
- tickets de São Paulo relacionados ao módulo de estoque;
- chamados do Rio de Janeiro relacionados ao módulo de estoque.

Em cada caso comparei a busca sem filtro com a busca filtrada. Sem os filtros apareciam documentos de outros estados, outros módulos e até outros tipos de documento. Com os filtros aplicados, os resultados ficaram restritos aos tickets que realmente possuíam os metadados solicitados.

Também adicionei uma validação automática que verifica os metadados de cada documento retornado. Nos três testes a validação terminou com `Validação dos filtros: OK`.

Com isso, foi possível concluir a parte de aplicação dos filtros na busca vetorial que ainda não estava efetivamente implementada no repositório.

**Uso de IA:** usei o ChatGPT para revisar a integração entre o Query Analyzer e o FAISS, identificar por que a busca filtrada inicialmente retornava vazia e organizar os testes. A partir dos resultados no terminal, identifiquei a diferença entre `VendeFácil Estoque` e `estoque`, ajustei a lógica do Query Analyzer e executei novamente os testes até validar os três casos.

### Resumo do dia

**Entreguei hoje:**

- Revisão da implementação da Etapa 2 e identificação de que o item 3 estava registrado no acompanhamento, mas ainda não estava presente no código do repositório.
- Implementação de `src/search.py` para aplicar os filtros do Query Analyzer na busca vetorial.
- Ajuste no `src/query_analyzer.py` para corrigir a identificação do módulo `estoque`.
- Aplicação de `fetch_k` dimensionado para evitar perda de resultados em filtros seletivos.
- Comparação de busca com e sem filtro para três perguntas específicas de estado e módulo.
- Validação automática dos metadados dos documentos retornados.
- Testes concluídos com `Validação dos filtros: OK` nos três casos.

**Ficou pendente:**

- Integrar a busca filtrada com a busca híbrida BM25 + FAISS + RRF em um fluxo único, caso seja necessário para a versão final da Etapa 2.
- Revisar e organizar o `ACOMPANHAMENTO.md`, removendo os marcadores de conflito de merge que ainda ficaram no arquivo.

**Bloqueios em aberto:**

- Nenhum bloqueio técnico na aplicação dos filtros. Os testes com MG, SP e RJ retornaram resultados coerentes com os metadados solicitados.

**Próximo passo:**

- Finalizar a organização da Etapa 2 no repositório e seguir para a Etapa 3, mantendo a integração entre Query Analyzer, recuperação e filtros preparada para o restante do pipeline.

**Uso de assistentes de IA:**

- ChatGPT utilizado para auxiliar na revisão da integração, diagnóstico da divergência entre os valores de módulo e organização dos testes. As alterações foram executadas e validadas localmente por meio das saídas do terminal.

---

---

## Encontro 3 - 2026-08-31

**Etapa:** 3 - Síntese estruturada, evidência e guardrails de LGPD

### Relato individual - Élcio Berilo Barbosa dos Santos Júnior

Depois de finalizar a revisão da Etapa 2, comecei o item 1 da Etapa 3, ficando responsável pela estrutura e validação das respostas do RAG com Pydantic.

Criei o arquivo `src/schema.py` com os modelos `SourceEvidence` e `RAGResponse`. O `SourceEvidence` organiza as informações da evidência que vai acompanhar cada resposta, mantendo `filepath`, `chunk_id` e `quotation`. Já o `RAGResponse` define a estrutura obrigatória da resposta final, incluindo `answer`, `confidence_level`, `sources_used`, `reasoning`, `is_refusal` e `refusal_reason`.

Usei `Literal` nos campos que possuem valores fechados. Para `confidence_level`, por exemplo, só são aceitos `alta`, `media`, `baixa` ou `recusado`. Fiz isso porque deixar esses campos como `str` permitiria valores diferentes do padrão, como `"muito alta"` ou `"ALTA"`, o que quebraria a consistência esperada pelo restante do pipeline.

Também implementei um `model_validator` para validar a relação entre recusa, nível de confiança, evidências e motivo da recusa. Se `is_refusal=True`, a resposta precisa ter `confidence_level="recusado"`, não pode possuir fontes e precisa informar um `refusal_reason`. Já quando `is_refusal=False`, a resposta precisa possuir pelo menos uma evidência, não pode utilizar confiança `recusado` e não deve possuir motivo de recusa.

Para testar essas regras, criei o arquivo `src/test_schema.py` com cinco casos diferentes. Os dois primeiros verificam uma resposta normal válida e uma recusa válida, e ambos passaram na validação. Os outros três foram criados propositalmente de forma incorreta para verificar se o Pydantic realmente impediria respostas inconsistentes.

No teste de resposta sem evidência, o modelo rejeitou corretamente a resposta porque `sources_used` estava vazio. No teste de recusa com confiança `alta`, o modelo também rejeitou a resposta porque uma recusa precisa obrigatoriamente utilizar `confidence_level="recusado"`. Por último, testei o valor `"muito alta"` no campo de confiança e o próprio `Literal` impediu a criação da resposta.

A execução de `python src/test_schema.py` terminou com `VALIDAÇÃO: OK` para os dois casos válidos e `VALIDAÇÃO: ERRO ESPERADO` para os três casos inválidos, confirmando que as regras implementadas estão funcionando.

Uma decisão que mantive foi deixar o schema responsável somente pela validação dos dados. O retry em caso de resposta inválida deverá ser feito na camada que chamar o LLM, porque é essa camada que consegue solicitar uma nova geração. Dessa forma, o `schema.py` continua independente do modelo ou serviço de IA escolhido para a síntese.

**Uso de IA:** usei o ChatGPT para me ajudar a estruturar os modelos Pydantic, revisar as regras de consistência exigidas pelo enunciado e montar os testes de respostas válidas e inválidas. Executei os testes localmente e conferi os erros retornados pelo Pydantic em cada cenário antes de considerar essa parte validada.

### Resumo do dia

**Entreguei hoje:**

- Implementação de `src/schema.py` com os modelos `SourceEvidence` e `RAGResponse`.
- Uso de `Literal` para restringir os valores permitidos em `confidence_level` e `refusal_reason`.
- Implementação de `model_validator` para garantir a consistência entre recusa, confiança, fontes e motivo.
- Obrigatoriedade de pelo menos uma evidência para respostas não recusadas.
- Criação de `src/test_schema.py` para validar o comportamento do schema.
- Teste de resposta normal válida.
- Teste de recusa válida.
- Teste de resposta sem evidência, rejeitada corretamente.
- Teste de recusa com nível de confiança incorreto, rejeitada corretamente.
- Teste de `confidence_level="muito alta"`, rejeitado corretamente pelo `Literal`.
- Execução dos testes com os dois casos válidos aprovados e os três casos inválidos retornando os erros esperados.

**Ficou pendente:**

- Integrar o `RAGResponse` à camada que fará a chamada do LLM.
- Implementar o retry quando uma saída gerada pelo LLM não passar pela validação do Pydantic.
- Integrar as evidências recuperadas pelo pipeline aos campos `filepath`, `chunk_id` e `quotation`.
- Implementar os demais itens da Etapa 3, principalmente as regras de LGPD, mascaramento e tratamento de perguntas fora de escopo.

**Bloqueios em aberto:**

- Nenhum bloqueio na validação Pydantic. Os testes do schema executaram conforme esperado.

**Próximo passo:**

- Utilizar o `RAGResponse` como formato obrigatório da saída da etapa de síntese e integrar o retry na camada responsável pela chamada do LLM.
- Dar continuidade aos demais objetivos da Etapa 3 com a divisão das tarefas entre os integrantes.

**Uso de assistentes de IA:**

- ChatGPT utilizado para auxiliar na estruturação dos modelos Pydantic, revisão das regras de consistência e criação dos casos de teste. A implementação foi executada e validada localmente através de `python src/test_schema.py`.

---

## Encontro 3 - [PREENCHER DATA]

**Etapa:** 3 - Citação de evidência (item 2) e política de LGPD com três níveis (item 3)

### Relato individual - [PREENCHER SEU NOME]

> ⚠️ MODELO A PREENCHER - escreva em primeira pessoa, com o que você de fato
> testou e observou rodando na SUA máquina. Não copie este texto sem editar -
> na arguição do Demo Day qualquer linha pode ser questionada (seção 0.3).

Hoje trabalhei nos itens 2 e 3 da Etapa 3. Criei `src/lgpd_policy.py`, responsável
pela política de LGPD com três níveis (recusar / mascarar / responder), e
`src/generate.py`, que integra a recuperação (Etapa 2), a política de LGPD e a
chamada ao LLM para gerar respostas no formato `RAGResponse` já validado por
Pydantic (`src/schema.py`, feito pelo Élcio no Encontro 3 anterior).

A classificação de LGPD é feita por regras (regex sobre a pergunta normalizada),
não pelo LLM, seguindo a mesma lógica que o Élcio já tinha usado no
`query_analyzer.py` - o guia do desafio recomenda decidir isso de forma
determinística, "porque filtrar por metadado é barato e determinístico; pedir
para o LLM decidir depois é caro e falível". Como segunda camada de defesa,
também recuso a resposta se TODOS os chunks recuperados tiverem
`sensitivity="restrito"`, mesmo que a pergunta não bata em nenhum padrão de
texto (caso de fraseado muito indireto).

[PREENCHER: relate aqui o resultado de rodar `python src/test_lgpd_policy.py`
e, com uma OPENAI_API_KEY configurada no `.env`, de rodar `python src/generate.py`
com as 8 perguntas de teste (2 de recusa, 2 de mascaramento, 2 de resposta normal,
2 fora de escopo). Descreva o que funcionou, o que não funcionou de primeira, e
o que você ajustou.]

[PREENCHER: se você calibrou o `OUT_OF_SCOPE_SCORE_THRESHOLD`, relate qual valor
funcionou melhor pro índice de vocês e como você chegou nele.]

**Uso de IA:** usei o Claude para [PREENCHER: descreva o que pediu - ex: "gerar a
primeira versão de `lgpd_policy.py` e `generate.py`, revisar a integração com o
`search.py` e o `hybrid_search.py` já existentes, e investigar por que o Élcio
relatou não ter encontrado `src/search.py` no repositório mesmo havendo um relato
anterior dizendo que ele existia"]. Ajustei/testei [PREENCHER: o que você de fato
rodou e conferiu na sua máquina antes de aceitar o código].

### Resumo do dia

**Entreguei hoje:**

- `src/lgpd_policy.py`: classificação de pergunta em recusar/mascarar/responder
  por regras, mascaramento de e-mail/telefone/CPF/cartão, e segunda camada de
  defesa baseada no `sensitivity` dos chunks recuperados.
- `src/generate.py`: pipeline completo pergunta -> recuperação (Etapa 2) ->
  guardrail de LGPD -> chamada ao LLM -> `RAGResponse` validado -> mascaramento
  final se aplicável. Toda resposta não recusada cita `filepath` + `chunk_id` +
  trecho literal.
- Retry de validação: se a saída do LLM não bater com o schema Pydantic, o erro
  é devolvido ao próprio modelo pedindo correção (até `MAX_RETRIES` tentativas),
  sem `except: pass`.
- `src/test_lgpd_policy.py`: testes de sanidade da classificação e do
  mascaramento, sem depender de índice FAISS nem de API key.
- `config.py` e `.env.example` na raiz do projeto, centralizando a
  `OPENAI_API_KEY` e os parâmetros (`GENERATION_MODEL`, `MAX_RETRIES`,
  `OUT_OF_SCOPE_SCORE_THRESHOLD`).
- Corrigido `ACOMPANHAMENTO.md`: removidos marcadores de conflito de merge
  (`<<<<<<<`/`=======`/`>>>>>>>`) que tinham ficado commitados no arquivo desde
  o Encontro 2, sem apagar nenhum relato.
- Adicionado `.env` ao `.gitignore` (crítico: o projeto passou a usar uma
  API key de verdade a partir de hoje).

**Ficou pendente:**

- [PREENCHER conforme o que sobrar: ex. calibrar `OUT_OF_SCOPE_SCORE_THRESHOLD`
  com perguntas reais do índice; integrar busca híbrida + filtro no mesmo fluxo
  de recuperação (pendência já registrada pelo Élcio no Encontro 2); revisar
  `requirements.txt` final]

**Bloqueios em aberto:**

- [PREENCHER, ou "Nenhum bloqueio técnico no momento"]

**Próximo passo:**

- Etapa 4: rodar o benchmark de 20 perguntas, medir a RAG Triad e montar a
  interface de demonstração.

**Uso de assistentes de IA:**

- Claude usado para gerar a primeira versão de `lgpd_policy.py` e `generate.py`,
  revisar a integração com os módulos já existentes de recuperação (Etapa 2), e
  investigar a divergência entre o relato do Encontro 2 sobre `src/search.py` e
  o relato do Élcio no Encontro 2 (continuação). [PREENCHER: o que você
  pessoalmente rodou/testou/ajustou antes de aceitar.]

---