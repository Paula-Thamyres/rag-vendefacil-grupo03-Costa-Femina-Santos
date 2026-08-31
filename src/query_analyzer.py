import re
import unicodedata
from pydantic import BaseModel
from query_index import load_index


class QueryFilters(BaseModel):
    doc_type: str | None = None
    state: str | None = None
    module: str | None = None
    customer_id: str | None = None
    priority: str | None = None
    status: str | None = None

    def to_dict(self):
        return self.model_dump(exclude_none=True)


def normalize(text: str) -> str:
    """Normaliza caixa, acentos e espaços."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().strip().split())


STATE_ALIASES = {
    "acre": "AC",
    "alagoas": "AL",
    "amapa": "AP",
    "amazonas": "AM",
    "bahia": "BA",
    "ceara": "CE",
    "distrito federal": "DF",
    "espirito santo": "ES",
    "goias": "GO",
    "maranhao": "MA",
    "mato grosso": "MT",
    "mato grosso do sul": "MS",
    "minas gerais": "MG",
    "para": "PA",
    "paraiba": "PB",
    "parana": "PR",
    "pernambuco": "PE",
    "piaui": "PI",
    "rio de janeiro": "RJ",
    "rio grande do norte": "RN",
    "rio grande do sul": "RS",
    "rondonia": "RO",
    "roraima": "RR",
    "santa catarina": "SC",
    "sao paulo": "SP",
    "sergipe": "SE",
    "tocantins": "TO",
}


DOC_TYPE_ALIASES = {
    "ticket": ["ticket", "tickets", "chamado", "chamados"],
    "customer": ["cliente", "clientes"],
    "employee": ["funcionario", "funcionarios", "colaborador", "colaboradores"],
    "product": ["produto", "produtos"],
    "store": ["loja", "lojas"],
    "log": ["log", "logs"],
    "manual": ["manual", "manuais"],
    "ata": ["ata", "atas"],
    "policy": ["politica", "politicas"],
    "email": ["email", "emails"],
    "sale": ["venda", "vendas"],
}


def contains(query: str, value: str) -> bool:
    """Evita encontrar palavras apenas por coincidência parcial."""
    return re.search(rf"\b{re.escape(value)}\b", query) is not None


class QueryAnalyzer:

    FIELDS = [
        "doc_type",
        "state",
        "module",
        "customer_id",
        "priority",
        "status",
    ]

    def __init__(self, vectorstore):
        self.valid_values = self._load_valid_values(vectorstore)

    def _load_valid_values(self, vectorstore):
        """
        Descobre quais valores realmente existem nos metadados
        do índice FAISS.
        """
        values = {field: {} for field in self.FIELDS}

        for doc_id in vectorstore.index_to_docstore_id.values():
            doc = vectorstore.docstore.search(doc_id)

            if not hasattr(doc, "metadata"):
                continue

            for field in self.FIELDS:
                value = doc.metadata.get(field)

                if value is not None and str(value).strip():
                    values[field][normalize(str(value))] = str(value)

        return values

    def _validated_value(self, field: str, value: str):
        """Só devolve o valor se ele existir no índice."""
        return self.valid_values[field].get(normalize(value))

    def analyze(self, question: str) -> QueryFilters:
        query = normalize(question)

        filters = QueryFilters()

        # Tipo do documento
        for doc_type, aliases in DOC_TYPE_ALIASES.items():
            if any(contains(query, normalize(alias)) for alias in aliases):
                value = self._validated_value("doc_type", doc_type)

                if value:
                    filters.doc_type = value
                    break

        # Estado por nome completo
        for state_name, acronym in STATE_ALIASES.items():
            if contains(query, state_name):
                value = self._validated_value("state", acronym)

                if value:
                    filters.state = value
                    break

        # Estado informado diretamente como UF
        if not filters.state:
            for acronym in STATE_ALIASES.values():
                if contains(query, acronym.lower()):
                    value = self._validated_value("state", acronym)

                    if value:
                        filters.state = value
                        break

        # Módulo
        module_matches = []

        for normalized_value, original_value in self.valid_values["module"].items():

            clean_value = normalized_value.replace("vendefacil", "").strip()

            # Prioridade maior quando o valor real aparece diretamente na pergunta.
            if contains(query, normalized_value):
                module_matches.append((3, normalized_value, original_value))

            # Ex.: "VendeFácil Estoque" -> "estoque"
            elif clean_value and contains(query, clean_value):
                module_matches.append((2, normalized_value, original_value))

            # Fallback por palavras relevantes
            else:
                words = [
                    word
                    for word in normalized_value.split()
                    if len(word) >= 4 and word != "vendefacil"
                ]

                if any(contains(query, word) for word in words):
                    module_matches.append((1, normalized_value, original_value))

        if module_matches:
            # Maior prioridade primeiro.
            module_matches.sort(key=lambda item: item[0], reverse=True)
            filters.module = module_matches[0][2]

        # Customer ID, prioridade e status
        for field in ["customer_id", "priority", "status"]:
            for normalized_value, original_value in self.valid_values[field].items():

                if contains(query, normalized_value):
                    setattr(filters, field, original_value)
                    break

        return filters


if __name__ == "__main__":

    vectorstore = load_index()
    analyzer = QueryAnalyzer(vectorstore)

    questions = [
        "Quais tickets de clientes de Minas Gerais estão relacionados ao módulo de estoque?",
        "Mostre os chamados de São Paulo",
        "Quais tickets possuem prioridade alta?",
        "Mostre os tickets de Wakanda do módulo abacaxi",
    ]

    for question in questions:
        filters = analyzer.analyze(question)

        print(f"\nPergunta: {question}")
        print("Filtros:", filters.to_dict())