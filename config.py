"""
Configuração centralizada do projeto (credenciais e parâmetros).

Lê tudo de variáveis de ambiente (via `.env`, que NUNCA deve ser commitado -
veja `.gitignore` e `.env.example`), conforme exigido na seção 6 do guia do
desafio ("config.py - credenciais e parâmetros centralizados").
"""

import os

from dotenv import load_dotenv

load_dotenv()

# --- LLM de síntese (src/generate.py) --------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GENERATION_MODEL = os.getenv("GENERATION_MODEL", "gpt-4o-mini")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
# Endereço da API. Deixe em branco/removido para usar a OpenAI normal
# (https://api.openai.com/v1). Para usar um provedor compatível com a API da
# OpenAI (ex: Groq), defina OPENAI_BASE_URL no .env - ex:
# OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or None

# --- Heurística de "fora de escopo" (src/generate.py) -----------------------
# Distância L2 máxima aceitável entre a pergunta e o chunk mais parecido do
# índice. Precisa ser calibrado empiricamente com perguntas reais (ver
# `if __name__ == "__main__"` em src/generate.py) - o valor abaixo é um
# ponto de partida, não um número validado contra o índice de vocês.
OUT_OF_SCOPE_SCORE_THRESHOLD = float(os.getenv("OUT_OF_SCOPE_SCORE_THRESHOLD", "0.9"))
