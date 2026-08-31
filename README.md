# Mini Desafio RAG - VendeFácil

**Autor:** Paula Thamyres da Silva Femina - @paula-thamyres - (https://github.com/Paula-Thamyres)
**Repositório base:** [mini-desafio-rag-vendefacil](https://github.com/feliperafael/mini-desafio-rag-vendefacil)

Assistente RAG Corporativo para a VendeFácil Tecnologia Ltda., empresa fictícia de
automação comercial. O objetivo é consultar seis fontes de dados diferentes
(cadastros, catálogo, chamados, logs, manuais, políticas e e-mails), aplicar filtros
por metadado e responder com citação de evidência, respeitando a LGPD.

\---

## Etapa 1 - Ingestão heterogênea, metadados e indexação vetorial

**Data:** 27/08/2026
**Status:** concluída

### O que eu fiz

Implementei um leitor para cada um dos seis formatos que a VendeFácil usa
(`customers.csv`, `employees.csv`, `products.json`, `stores.json`, `tickets.jsonl`,
`system\_logs.csv`, manuais e atas em `.md`, políticas em `.pdf` e e-mails em `.txt`),
cada um com sua própria estratégia de chunking - não dava pra tratar tudo como texto
corrido:

* **CSV/JSON tabular:** 1 registro = 1 chunk, sempre serializado em frase, nunca
partido ao meio. Testei bastante isso porque o primeiro instinto é jogar a linha
crua do CSV pro embedding, mas isso não funciona bem - o modelo não separa campo
de valor numa string tipo `"CUST001,Boa Compra,MG,estoque"`. Virou:
`"Cliente CUST001: Supermercado Boa Compra (Supermercado), CNPJ ..., localizado em Belo Horizonte/MG, plano Enterprise, produto principal VendeFácil Estoque, MRR de R$ 2450.0, situação Ativo, contato gerencia@boacompra.com.br."`
* **JSONL (tickets):** 1 ticket = 1 chunk. Quando o corpo (descrição + resolução)
passa de 1000 caracteres, split recursivo, mas o cabeçalho (ticket, cliente,
estado, módulo, prioridade, status) fica replicado em cada pedaço, senão perde o
contexto.
* **Markdown (manuais, atas, políticas):** split por cabeçalho
(`MarkdownHeaderTextSplitter`), com fallback por tamanho pras seções que passam de
1200 caracteres.
* **PDF (`reembolso.pdf`, `seguranca\_lgpd.pdf`):** split recursivo respeitando
quebra de parágrafo, com overlap de 120 caracteres.
* **TXT (e-mails):** conferi os 43 arquivos de e-mail do dataset e nenhum tem mais
de uma mensagem por arquivo, então cada arquivo já é a unidade semântica mínima -
1 arquivo = 1 chunk direto, sem precisar quebrar por marcador de thread.

Todo chunk carrega o schema mínimo (`source\_file`, `doc\_type`, `chunk\_id`,
`sensitivity`) via um `BaseModel` do Pydantic, mais os campos condicionais
(`customer\_id`, `state`, `module`, `priority`, `status`, `date`, `section`) quando
fazem sentido pra fonte.

**Sensibilidade classificada já na ingestão** (não deixei pro LLM decidir depois,
porque filtrar por metadado é determinístico e barato, e isso é o que vai sustentar
os guardrails de LGPD na Etapa 3):

|`sensitivity`|Onde|
|-|-|
|`restrito`|folha de funcionários (`employees.csv`, tem salário), e-mails (alguns trazem senha/chave de API), código de conduta, política de segurança/LGPD|
|`interno`|clientes, tickets, logs, manuais, atas, demais políticas|
|`publico`|catálogo de produtos, cadastro de lojas|

Depois de gerar os chunks, vetorizei com `sentence-transformers/all-MiniLM-L6-v2`
via `HuggingFaceEmbeddings` e indexei no FAISS, salvando com `save\_local` em
`faiss\_index/`. `query\_index.py` recarrega com `load\_local` sem reindexar do zero.

### Números reais do índice (rodando `sanity\_check.py`)

|`doc\_type`|chunks|
|-|-|
|customer|2000|
|sale|3000|
|log|450|
|ticket|75|
|ata|38|
|manual|24|
|store|50|
|policy|18|
|email|45|
|employee|10|
|product|5|
|**Total**|**5715**|

Zero chunks sem `doc\_type` ou `sensitivity` - confirmei isso rodando um filtro em
cima de todos os documentos indexados, não só olhando por cima.

**As 3 perguntas de teste do `sanity\_check.py`:**

1. Qual é a política de reembolso da empresa?
2. Como funciona a sincronização de estoque entre lojas?
3. O que fazer em caso de vazamento de dados segundo a política de segurança e LGPD?

### Onde travei e o que corrigi

Escrevi a primeira versão dos loaders de `customers.csv`, `products.json` e
`stores.json` olhando só pro exemplo de serialização do enunciado - e quando rodei
contra o dataset de verdade, quebrou:

* `customers.csv` não tem coluna `name` nem `signup\_date` (que eu tinha assumido) -
o nome vem em `company\_name` e não existe data de cadastro nesse dataset. O módulo
contratado está em `main\_product`. Com o código antigo, o chunk saía assim:
`"Cliente CUST001: , estado MG, módulo contratado , cliente desde , situação Ativo."` - com os campos vazios, o que ia direto pro embedding como ruído.
* `products.json` e `stores.json` não são listas na raiz do JSON - são objetos com
as chaves `"products"` e `"network\_stores"` guardando a lista de verdade. O código
antigo tentava iterar a raiz direto e estourava `AttributeError: 'str' object has no attribute 'get'`.
* Os tickets já vêm com `state` e `module` no JSONL, mas eu não estava puxando isso
pros metadados. Como a Etapa 2 vai precisar filtrar por estado e por módulo,
ajustei pra capturar esses dois campos desde já.

Corrigi os três loaders, reingeri os dados reais pra confirmar e bateu os 5.715
chunks acima, sem nenhum campo vazio ou erro.

### Decisões técnicas

* **`sale` como `doc\_type` extra:** o dataset trouxe um `sales.csv` que não está na
lista original de fontes do desafio. Decidi indexar mesmo assim, como
`doc\_type="sale"`, porque é contexto de negócio real (faturamento por loja/produto)
que pode ser útil nas perguntas das próximas etapas.
* **Não indexar a política em dois formatos:** `reembolso` e `seguranca\_lgpd`
existem em `.md` e `.pdf` no dataset. Uso só a versão PDF pra essas duas e ignoro
o `.md` correspondente, pra não ter dois chunks quase idênticos competindo no
top-k da busca.
* **Sensibilidade sempre fixada na ingestão**, nunca decidida em tempo de resposta.

### Próximo passo

Encontro 2: busca híbrida (embeddings + BM25) e filtro por metadado (`state`,
`module`, `customer\_id`) usando o índice que já está pronto.

### Como rodar

```bash
pip install -r requirements.txt
python src/ingest.py          # gera e salva o índice FAISS em ./faiss\_index
python src/sanity\_check.py    # imprime totais, distribuição e top-5 pra 3 perguntas de teste
```

\---

## Etapa 3 - Síntese estruturada, evidência e guardrails de LGPD

**Status:** itens 1 (schema Pydantic), 2 (citação de evidência) e 3 (LGPD) concluídos.

### Item 1 - Saída validada por Pydantic (`src/schema.py`)

`RAGResponse` e `SourceEvidence` usam `Literal` para `confidence\_level` e
`refusal\_reason`, e um `model\_validator` garante a consistência entre
`is\_refusal`, `sources\_used` e `confidence\_level` (ver `src/test\_schema.py`).

### Itens 2 e 3 - Citação de evidência + LGPD (`src/lgpd\_policy.py`, `src/generate.py`)

**Política de LGPD com três níveis**, implementada em `src/lgpd\_policy.py`:

|Nível|Como decidimos|Exemplo|
|-|-|-|
|**Recusar**|`classify\_question()` casa a pergunta normalizada contra padrões de salário/remuneração, CPF, dados bancários/PIX, credenciais e dados de saúde - inclusive formas indiretas ("quanto a folha custa por pessoa"). Como segunda camada, `has\_only\_restricted\_docs()` recusa mesmo sem casar nenhum padrão de texto, se todos os chunks recuperados tiverem `sensitivity="restrito"`.|"Qual o salário do funcionário X?"|
|**Mascarar**|`classify\_question()` casa contra padrões de e-mail/telefone/endereço/cartão; a resposta final e as citações passam por `mask\_pii()` antes de voltar pro usuário.|"Qual o e-mail do cliente CUST001?"|
|**Responder**|Nenhum padrão de recusa/mascaramento casa.|"Qual a política de reembolso?"|

Estendemos a lista mínima do enunciado com padrões indiretos de salário (ver
"Dicas para não travar" do guia, item 5) para não deixar o guardrail furar
com fraseado adversarial.

A decisão de recusar/mascarar acontece **antes** de chamar o LLM sempre que
possível (recusa nunca chama o LLM; mascaramento chama o LLM normalmente e
só ofusca o texto depois) - seguindo a recomendação do guia de classificar
por metadado, não delegar pro modelo.

**Fora de escopo:** `is\_out\_of\_scope()` compara a distância do chunk mais
similar contra `OUT\_OF\_SCOPE\_SCORE\_THRESHOLD` (calibrar em `.env`/`config.py`
rodando perguntas reais - ver bloco de teste em `src/generate.py`).

**Citação de evidência (item 2):** todo prompt de síntese exige que o LLM
devolva `sources\_used` com `filepath` + `chunk\_id` idênticos ao contexto
recuperado, e `quotation` como trecho literal (não parafraseado). A saída é
validada por `RAGResponse.model\_validate()`; se inválida, o erro de validação
é devolvido ao próprio modelo pedindo correção, até `MAX\_RETRIES` tentativas
(sem `except: pass`).

### Configuração

```bash
cp .env.example .env      # preencha OPENAI\_API\_KEY com sua chave
python src/test\_lgpd\_policy.py   # testes de sanidade, não precisa de API key
python src/generate.py           # roda o pipeline completo com 8 perguntas de teste
```



> \*\*Limitação conhecida, documentada após teste real com o índice:\*\* rodamos

> 8 perguntas de calibração (4 dentro do domínio, 4 fora) contra o índice

> real e medimos a distância L2 do chunk mais próximo (e também a média dos

> 3 mais próximos). Em nenhum dos dois casos existe um único valor de limiar

> que separe os dois grupos sem erro - "Quem descobriu o Brasil?" (fora de

> escopo) fica com score melhor (mais "parecido") que "Como funciona a

> sincronização de estoque entre lojas?" (dentro de escopo), porque a

> distância de embedding mede parecença textual com o chunk mais próximo, não

> pertencimento ao domínio - uma pergunta legítima mas fraseada de forma

> incomum pode não bater bem com nenhum chunk específico, e uma pergunta

> genérica pode coincidir por acaso com a estrutura de algum chunk qualquer.

> Com `OUT\_OF\_SCOPE\_SCORE\_THRESHOLD=0.9` (o padrão), o erro mínimo alcançável

> nesse teste foi 2 em 8 perguntas. Mitigação futura considerada e \*\*não\*\*

> implementada por decisão do time: combinar a distância com uma lista de

> palavras-chave do domínio (mesma lógica do `lgpd\_policy.py`), que resolveria

> o caso de falso positivo ("sincronização de estoque") sem depender só do

> embedding.

### Decisões técnicas / trade-offs

* **Recuperação por caso:** se o Query Analyzer extrai algum filtro
(`state`, `module`, etc.), usamos `FilteredVectorSearch` (busca densa + filtro
de metadado, Etapa 2 item 3); senão usamos `HybridRetriever` (denso + BM25 +
RRF, Etapa 2 item 2). Integrar os dois no mesmo fluxo (híbrido *e* filtrado
ao mesmo tempo) ainda é uma pendência registrada no `ACOMPANHAMENTO.md`.
* **Classificação de LGPD por regras, não por LLM:** mais barato, determinístico
e testável sem API key (`src/test\_lgpd\_policy.py`). Trade-off: cobertura
depende da lista de padrões declarada - qualquer extensão deve ser
justificada aqui, como pede o guia.

\---

*Ver `ACOMPANHAMENTO.md` para o relato dos encontros e uso de IA.*

