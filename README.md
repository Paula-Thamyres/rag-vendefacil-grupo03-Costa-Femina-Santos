# Mini Desafio RAG - VendeFácil

**Autor:** [Seu Nome] - [@seu-usuario-github](https://github.com/seu-usuario-github)
**Repositório base:** [mini-desafio-rag-vendefacil](https://github.com/feliperafael/mini-desafio-rag-vendefacil)

Assistente RAG Corporativo para a VendeFácil Tecnologia Ltda., empresa fictícia de
automação comercial. O objetivo é consultar seis fontes de dados diferentes
(cadastros, catálogo, chamados, logs, manuais, políticas e e-mails), aplicar filtros
por metadado e responder com citação de evidência, respeitando a LGPD.

---

## Etapa 1 - Ingestão heterogênea, metadados e indexação vetorial

**Data:** 27/08/2026
**Status:** concluída

### O que eu fiz

Implementei um leitor para cada um dos seis formatos que a VendeFácil usa
(`customers.csv`, `employees.csv`, `products.json`, `stores.json`, `tickets.jsonl`,
`system_logs.csv`, manuais e atas em `.md`, políticas em `.pdf` e e-mails em `.txt`),
cada um com sua própria estratégia de chunking - não dava pra tratar tudo como texto
corrido:

- **CSV/JSON tabular:** 1 registro = 1 chunk, sempre serializado em frase, nunca
  partido ao meio. Testei bastante isso porque o primeiro instinto é jogar a linha
  crua do CSV pro embedding, mas isso não funciona bem - o modelo não separa campo
  de valor numa string tipo `"CUST001,Boa Compra,MG,estoque"`. Virou:
  `"Cliente CUST001: Supermercado Boa Compra (Supermercado), CNPJ ..., localizado em
  Belo Horizonte/MG, plano Enterprise, produto principal VendeFácil Estoque, MRR de
  R$ 2450.0, situação Ativo, contato gerencia@boacompra.com.br."`
- **JSONL (tickets):** 1 ticket = 1 chunk. Quando o corpo (descrição + resolução)
  passa de 1000 caracteres, split recursivo, mas o cabeçalho (ticket, cliente,
  estado, módulo, prioridade, status) fica replicado em cada pedaço, senão perde o
  contexto.
- **Markdown (manuais, atas, políticas):** split por cabeçalho
  (`MarkdownHeaderTextSplitter`), com fallback por tamanho pras seções que passam de
  1200 caracteres.
- **PDF (`reembolso.pdf`, `seguranca_lgpd.pdf`):** split recursivo respeitando
  quebra de parágrafo, com overlap de 120 caracteres.
- **TXT (e-mails):** conferi os 43 arquivos de e-mail do dataset e nenhum tem mais
  de uma mensagem por arquivo, então cada arquivo já é a unidade semântica mínima -
  1 arquivo = 1 chunk direto, sem precisar quebrar por marcador de thread.

Todo chunk carrega o schema mínimo (`source_file`, `doc_type`, `chunk_id`,
`sensitivity`) via um `BaseModel` do Pydantic, mais os campos condicionais
(`customer_id`, `state`, `module`, `priority`, `status`, `date`, `section`) quando
fazem sentido pra fonte.

**Sensibilidade classificada já na ingestão** (não deixei pro LLM decidir depois,
porque filtrar por metadado é determinístico e barato, e isso é o que vai sustentar
os guardrails de LGPD na Etapa 3):

| `sensitivity` | Onde |
| --- | --- |
| `restrito` | folha de funcionários (`employees.csv`, tem salário), e-mails (alguns trazem senha/chave de API), código de conduta, política de segurança/LGPD |
| `interno` | clientes, tickets, logs, manuais, atas, demais políticas |
| `publico` | catálogo de produtos, cadastro de lojas |

Depois de gerar os chunks, vetorizei com `sentence-transformers/all-MiniLM-L6-v2`
via `HuggingFaceEmbeddings` e indexei no FAISS, salvando com `save_local` em
`faiss_index/`. `query_index.py` recarrega com `load_local` sem reindexar do zero.

### Números reais do índice (rodando `sanity_check.py`)

| `doc_type` | chunks |
| --- | --- |
| customer | 2000 |
| sale | 3000 |
| log | 450 |
| ticket | 75 |
| ata | 38 |
| manual | 24 |
| store | 50 |
| policy | 18 |
| email | 45 |
| employee | 10 |
| product | 5 |
| **Total** | **5715** |

Zero chunks sem `doc_type` ou `sensitivity` - confirmei isso rodando um filtro em
cima de todos os documentos indexados, não só olhando por cima.

**As 3 perguntas de teste do `sanity_check.py`:**
1. Qual é a política de reembolso da empresa?
2. Como funciona a sincronização de estoque entre lojas?
3. O que fazer em caso de vazamento de dados segundo a política de segurança e LGPD?

### Onde travei e o que corrigi

Escrevi a primeira versão dos loaders de `customers.csv`, `products.json` e
`stores.json` olhando só pro exemplo de serialização do enunciado - e quando rodei
contra o dataset de verdade, quebrou:

- `customers.csv` não tem coluna `name` nem `signup_date` (que eu tinha assumido) -
  o nome vem em `company_name` e não existe data de cadastro nesse dataset. O módulo
  contratado está em `main_product`. Com o código antigo, o chunk saía assim:
  `"Cliente CUST001: , estado MG, módulo contratado , cliente desde , situação
  Ativo."` - com os campos vazios, o que ia direto pro embedding como ruído.
- `products.json` e `stores.json` não são listas na raiz do JSON - são objetos com
  as chaves `"products"` e `"network_stores"` guardando a lista de verdade. O código
  antigo tentava iterar a raiz direto e estourava `AttributeError: 'str' object has
  no attribute 'get'`.
- Os tickets já vêm com `state` e `module` no JSONL, mas eu não estava puxando isso
  pros metadados. Como a Etapa 2 vai precisar filtrar por estado e por módulo,
  ajustei pra capturar esses dois campos desde já.

Corrigi os três loaders, reingeri os dados reais pra confirmar e bateu os 5.715
chunks acima, sem nenhum campo vazio ou erro.

### Decisões técnicas

- **`sale` como `doc_type` extra:** o dataset trouxe um `sales.csv` que não está na
  lista original de fontes do desafio. Decidi indexar mesmo assim, como
  `doc_type="sale"`, porque é contexto de negócio real (faturamento por loja/produto)
  que pode ser útil nas perguntas das próximas etapas.
- **Não indexar a política em dois formatos:** `reembolso` e `seguranca_lgpd`
  existem em `.md` e `.pdf` no dataset. Uso só a versão PDF pra essas duas e ignoro
  o `.md` correspondente, pra não ter dois chunks quase idênticos competindo no
  top-k da busca.
- **Sensibilidade sempre fixada na ingestão**, nunca decidida em tempo de resposta.

### Próximo passo

Encontro 2: busca híbrida (embeddings + BM25) e filtro por metadado (`state`,
`module`, `customer_id`) usando o índice que já está pronto.

### Como rodar

```bash
pip install -r requirements.txt
python src/ingest.py          # gera e salva o índice FAISS em ./faiss_index
python src/sanity_check.py    # imprime totais, distribuição e top-5 pra 3 perguntas de teste
```

---

*Ver `ACOMPANHAMENTO.md` para o relato do encontro e uso de IA.*
