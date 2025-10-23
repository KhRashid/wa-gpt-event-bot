# services/tools_schema.py
# JSON-schema definition for the LLM tool that proxies to your Eventa-APIwithCatalogue /search

query_catalogue_tool = {
    "type": "function",
    "function": {
        "name": "query_catalogue",
        "description": "Поиск площадок через Eventa-APIwithCatalogue (/search). Ничего не изменяет, только читает.",
        "parameters": {
            "type": "object",
            "properties": {
                "guest_count": {"type": "integer", "minimum": 1, "description": "Количество гостей (обязательно)"},
                "price_per_guest_max": {"type": "number", "minimum": 0, "description": "Макс. бюджет на гостя, AZN"},
                "district": {"type": "string", "description": "Район/локация (необязательно)"},
                "date": {"type": "string", "format": "date", "description": "Дата события YYYY-MM-DD (необязательно)"},
                "sort": {"type": "string", "enum": ["price_asc","capacity_desc","rating_desc"], "description": "Сортировка (необязательно)"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 7, "description": "Сколько позиций вернуть (1..50)"}
            },
            "required": ["guest_count"]
        }
    }
}
