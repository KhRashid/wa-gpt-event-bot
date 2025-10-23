from openai import OpenAI
from config import OPENAI_API_KEY
from services.state import get_history, append_user_message, append_assistant_message
from services.tools_schema import query_catalogue_tool
from services.eventa_adapter import run_query_catalogue
import json

client = OpenAI(api_key=OPENAI_API_KEY)

# --- helpers: header + compact list (без картинок) ---
def _make_header(filters: dict) -> str:
    guests = filters.get("guest_count")
    budget = filters.get("price_per_guest_max")
    district = filters.get("district") or "Баку"
    parts = ["Вот подходящие площадки для вашего мероприятия"]
    if district:
        parts.append(f"в {district}")
    if guests:
        parts.append(f"на {guests} гостей")
    if budget:
        parts.append(f"с бюджетом до {budget} манат на человека")
    return " ".join(parts).strip() + ":"
'''
def _format_compact_list(data: dict, max_items: int | None = None) -> str:
    items = data.get("items", []) or []
    if max_items:
        items = items[:max_items]

    filters_used = data.get("filters_used", {}) or {}
    lines = [_make_header(filters_used)]

    for i, v in enumerate(items, 1):
        name = v.get("name", "?")
        district = v.get("district", "?")
        cap_min = v.get("capacity_min", "?")
        cap_max = v.get("capacity_max", "?")
        price_min = v.get("price_per_guest_min", "?")
        price_max = v.get("price_per_guest_max", "?")
        lines.append(f"{i}. {name} — {district} — {cap_min}–{cap_max} мест — ~{price_min}–{price_max} AZN/гость")

    # единая ссылка на каталог/шортлист (кликается как голый URL)
    link = data.get("shortlist_url") or data.get("link") or ""
    if link:
        lines.append("")
        lines.append("Для просмотра каталога выбранных площадок, пожалуйста, перейдите по ссылке:")
        lines.append(link)

    return "\n".join(lines)

'''
SYSTEM_PROMPT = {
    "az": "Sən tədbir təşkilatı üzrə köməkçisən. Qısa, dəqiq və nəzakətli cavablar yaz.",
    "ru": "Ты ассистент по организации мероприятий. Пиши кратко, вежливо и по делу.",
    "en": "You are an event-planning assistant. Be concise and helpful.",
}
'''
SYSTEM_PROMPT = {
    "ru": (
        "Ты — ассистент Eventa. Помогаешь подобрать площадки для мероприятий в Баку/Азербайджане.\n"
        "Если пользователь дает параметры поиска (кол-во гостей, бюджет/гость, район, дата) — "
        "вызывай инструмент query_catalogue. Если параметров не хватает — спроси ровно то, чего не хватает.\n"
        "В ответе выводи 3–7 лучших вариантов: Название — Район — Вместимость — ~AZN/гость — URL. "
        "В конце добавь 'Фильтры: …' и, если пришло от API, 'Shortlist: <url>'."
    ),
    "az": (
        "Sən Eventa köməkçisisən. Bakı/Azərbaycanda məkan seçiminə kömək edirsən. "
        "İstifadəçi axtarış parametrləri veribsə (qonaq sayı, büdcə/qonaq, rayon, tarix) — "
        "query_catalogue alətini çağır. Parametrlər çatmırsa, yalnız çatmayanları soruş. "
        "Cavabda 3–7 ən uyğun variantı göstər: Ad — Rayon — Tutum — ~AZN/qonaq — URL. "
        "Sonda 'Filtrlər: …' və (əgər API-dən gəlibsə) 'Shortlist: <url>' əlavə et."
    )
}
'''

#--------------------------------------------------------------------------------------
def _extract_items(payload: dict) -> list:
    """Пытаемся найти список карточек в разных типичных местах ответа."""
    if not isinstance(payload, dict):
        return []
    candidates = [
        payload.get("items"),
        payload.get("venues"),
        payload.get("results"),
        (payload.get("data") or {}).get("items"),
        (payload.get("data") or {}).get("venues"),
    ]
    for c in candidates:
        if isinstance(c, list) and len(c) > 0:
            return c
    return []

def _get(v: dict, *keys, default=None):
    for k in keys:
        if k in v and v[k] not in (None, ""):
            return v[k]
    return default

def _format_compact_list(data: dict, max_items: int | None = None) -> str:
    items = _extract_items(data)
    if max_items:
        items = items[:max_items]

    filters_used = data.get("filters_used", {}) or {}
    lines = [_make_header(filters_used)]

    for i, v in enumerate(items, 1):
        name = _get(v, "name", "title", default="?")
        district = _get(v, "district", "area", "location", default="?")

        # Вместимость: пытаемся собрать min–max из разных схем
        cap_min = _get(v, "capacity_min", "min_capacity", "capacityMin",
                          default=_get(v.get("capacity", {}) if isinstance(v.get("capacity"), dict) else {}, "min", default="?"))
        cap_max = _get(v, "capacity_max", "max_capacity", "capacityMax",
                          default=_get(v.get("capacity", {}) if isinstance(v.get("capacity"), dict) else {}, "max", default="?"))

        # Цена/гость
        price_min = _get(v, "price_per_guest_min", "ppg_min", "priceMin",
                            default=_get(v.get("price_per_guest", {}) if isinstance(v.get("price_per_guest"), dict) else {}, "min", default="?"))
        price_max = _get(v, "price_per_guest_max", "ppg_max", "priceMax",
                            default=_get(v.get("price_per_guest", {}) if isinstance(v.get("price_per_guest"), dict) else {}, "max", default="?"))

        lines.append(f"{i}. {name} — {district} — {cap_min}–{cap_max} мест — ~{price_min}–{price_max} AZN/гость")

    link = data.get("shortlist_url") or data.get("link") or ""
    if link:
        lines.append("")
        lines.append("Для просмотра каталога выбранных площадок, пожалуйста, перейдите по ссылке:")
        lines.append(link)

    return "\n".join(lines)
#--------------------------------------------------------------------------------------

def build_messages(chat_id: str, user_text: str, lang: str = "az", max_turns: int = 10):
    history = get_history(chat_id, limit=max_turns)
    system = {"role": "system", "content": SYSTEM_PROMPT.get(lang, SYSTEM_PROMPT["az"])}
    return [system, *history, {"role": "user", "content": user_text}]

def _extract_first_tool_call(resp):
    # Works with Chat Completions tool_calls format
    for choice in resp.choices:
        tool_calls = getattr(choice.message, "tool_calls", None) or []
        if tool_calls:
            return tool_calls[0]
    return None

def _join_text(resp):
    # For Chat Completions: single message content
    try:
        return resp.choices[0].message.content or ""
    except Exception:
        return ""

def process_message_with_context(chat_id: str, user_text: str, lang: str = "az") -> str:
    append_user_message(chat_id, user_text)

    # 1) Первый проход: объявляем инструмент, даём модели решить
    msgs = build_messages(chat_id, user_text, lang=lang)
    first = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=msgs,
        tools=[query_catalogue_tool],
        tool_choice="auto",
        temperature=0.3,
        max_tokens=400,
    )

    # Если модель решила вызвать инструмент
    assistant_msg = first.choices[0].message
    tool_calls = getattr(assistant_msg, "tool_calls", None) or []
    if tool_calls and tool_calls[0].function and tool_calls[0].function.name == "query_catalogue":
        call = tool_calls[0]

        # 2) Исполнить инструмент (ваш Eventa-API)
        try:
            args = json.loads(call.function.arguments or "{}")
        except Exception:
            args = {}
        try:
            data = run_query_catalogue(args)

            log_keys = ", ".join(list(data.keys())[:10]) if isinstance(data, dict) else type(data).__name__
            try:
                cnt_items = len(data.get("items", []) or [])
                cnt_venues = len(data.get("venues", []) or [])
                cnt_results = len(data.get("results", []) or [])
            except Exception:
                cnt_items = cnt_venues = cnt_results = -1
            print(f"[EventaAPI] keys=[{log_keys}] counts: items={cnt_items}, venues={cnt_venues}, results={cnt_results}")
        except Exception:
            text = (
                "Кажется, возникла техническая задержка при поиске площадок. "
                "Попробуйте изменить параметры или повторить запрос чуть позже."
            )
            append_assistant_message(chat_id, text)
            return text

        '''
        # 3) ВТОРОЙ ПРОХОД — ПРАВИЛЬНАЯ СЦЕПКА assistant(tool_calls) → tool(tool_call_id)
        msgs2 = msgs + [
            {
                "role": "assistant",
                "content": assistant_msg.content,  # может быть None
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,  # строка как есть
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": call.id,
                "name": call.function.name,
                "content": json.dumps(data, ensure_ascii=False),
            },
        ]

        second = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=msgs2,
            temperature=0.2,
            max_tokens=700,
        )
        final = (second.choices[0].message.content or "").strip()

        if not final:
            # редкий fallback — красиво отформатируем сами
            items = data.get("items", [])
            lines = []
            for i, v in enumerate(items[:7], 1):
                cap = f"{v.get('capacity_min','?')}–{v.get('capacity_max','?')} мест"
                ppg = f"~{v.get('price_per_guest_min','?')}–{v.get('price_per_guest_max','?')} AZN/гость"
                lines.append(f"{i}) {v.get('name','?')} — {v.get('district','?')} — {cap} — {ppg}\n{v.get('url','')}")
            flt = data.get("filters_used", {})
            sl = data.get("shortlist_url")
            tail = f"\nФильтры: {json.dumps(flt, ensure_ascii=False)}"
            if sl:
                tail += f"\nShortlist: {sl}"
            final = ("\n".join(lines) + tail).strip()

        '''        
        
        # 3) Формируем компактный ответ БЕЗ второго вызова модели
        final = _format_compact_list(data)  # показываем все объекты, без картинок
        
        append_assistant_message(chat_id, final)
        return final

    # Инструмент не вызывался — вернём обычный текст
    final = (first.choices[0].message.content or "").strip() or \
            "Уточните, пожалуйста, параметры поиска (гостей, бюджет/гость, район)."
    append_assistant_message(chat_id, final)
    return final
