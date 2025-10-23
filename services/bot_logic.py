from openai import OpenAI
from config import OPENAI_API_KEY
from services.state import get_history, append_user_message, append_assistant_message
from services.tools_schema import query_catalogue_tool
from services.eventa_adapter import run_query_catalogue
import json
import logging

client = OpenAI(api_key=OPENAI_API_KEY)

# --- helpers: header + compact list (без картинок) ---
def _norm_minmax(val, default=("?", "?")):
    """Нормализует значение min–max: принимает список из 2 чисел или dict {min,max} или пару отдельных полей."""
    if isinstance(val, (list, tuple)) and len(val) == 2:
        return val[0], val[1]
    if isinstance(val, dict):
        lo = val.get("min")
        hi = val.get("max")
        if lo is not None and hi is not None:
            return lo, hi
    return default
    
def _has_name_like(d: dict) -> bool:
    if not isinstance(d, dict):
        return False
    for k in ("name", "title", "venue_name"):
        if k in d and d[k]:
            return True
    return False

def _best_list_of_venues(payload: dict) -> list:
    """
    Рекурсивно обходит JSON и ищет список словарей, где >=50% элементов
    выглядят как карточки площадок (есть поле name/title/venue_name).
    Если находит несколько — выбирает самый «плотный» и длинный.
    """
    best = []
    best_score = (0.0, 0)  # (доля с name-like, длина)

    def walk(node):
        nonlocal best, best_score
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list) and node:
            dicts = [x for x in node if isinstance(x, dict)]
            if dicts:
                score = sum(1 for x in dicts if _has_name_like(x)) / len(dicts)
                candidate = (score, len(dicts))
                if candidate > best_score:
                    best_score = candidate
                    best = dicts
            # продолжаем обход на случай вложенных структур
            for v in node:
                walk(v)

    walk(payload)
    return best
'''
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
def _make_header(filters: dict) -> str:
    guests = (filters or {}).get("guest_count")
    budget = (filters or {}).get("price_per_guest_max")
    district = (filters or {}).get("district") or "Баку"
    parts = ["Вот подходящие площадки для вашего мероприятия"]
    if district: parts.append(f"в {district}")
    if guests: parts.append(f"на {guests} гостей")
    if budget: parts.append(f"с бюджетом до {budget} манат на человека")
    return " ".join(parts).strip() + ":"
    
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

#--------------------------------------------------------------------------------------
'''
def _extract_items(payload: dict) -> list:
    """
    Сначала пробуем «типичные» места, потом — глубокий поиск.
    """
    if not isinstance(payload, dict):
        return []
    # быстрые кандидаты
    for c in [
        payload.get("items"),
        payload.get("venues"),
        payload.get("results"),
        (payload.get("data") or {}).get("items"),
        (payload.get("data") or {}).get("venues"),
    ]:
        if isinstance(c, list) and c:
            return c
    # глубокий поиск
    return _best_list_of_venues(payload)
'''
def _extract_items(payload: dict) -> list:
    """Сначала проверяем типичные поля, затем глубоко ищем. Важно: поддерживаем `shortlist`."""
    if not isinstance(payload, dict):
        return []
    # 1) Точные ключи нашего API
    if isinstance(payload.get("shortlist"), list) and payload["shortlist"]:
        return payload["shortlist"]
    # 2) Другие типичные варианты
    for c in [
        payload.get("items"),
        payload.get("venues"),
        payload.get("results"),
        (payload.get("data") or {}).get("items"),
        (payload.get("data") or {}).get("venues"),
    ]:
        if isinstance(c, list) and c:
            return c
    # 3) Глубокий поиск (на всякий случай)
    best = []
    best_score = (0.0, 0)
    def has_name_like(d):
        return isinstance(d, dict) and any(k in d and d[k] for k in ("name","title","venue_name"))
    def walk(node):
        nonlocal best, best_score
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list) and node:
            dicts = [x for x in node if isinstance(x, dict)]
            if dicts:
                score = sum(1 for x in dicts if has_name_like(x)) / len(dicts)
                cand = (score, len(dicts))
                if cand > best_score:
                    best_score = cand
                    best = dicts
            for v in node:
                walk(v)
    walk(payload)
    return best
    
'''
def _get(v: dict, *keys, default=None):
    for k in keys:
        if k in v and v[k] not in (None, ""):
            return v[k]
    return default
'''
def _get(v: dict, *keys, default=None):
    for k in keys:
        if isinstance(v, dict) and k in v and v[k] not in (None, ""):
            return v[k]
    return default

'''
def _format_compact_list(data: dict, max_items: int | None = None) -> str:
    items = _extract_items(data) or []
    if max_items:
        items = items[:max_items]

    filters_used = data.get("filters_used", {}) or {}
    lines = [_make_header(filters_used)]

    if not items:
        # Явно покажем, что ничего не найдено (это лучше, чем пустая секция)
        lines.append("Пока подходящих площадок не найдено по этим параметрам.")
    else:
        for i, v in enumerate(items, 1):
            name = _get(v, "name", "title", "venue_name", default="?")
            district = _get(v, "district", "area", "location", default="?")

            # Вместимость
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
'''
def _format_compact_list(data: dict, max_items: int | None = None) -> str:
    """Основной формат вывода: 1 строка на площадку, без картинок + ссылка в конце."""
    items = _extract_items(data) or []
    if max_items:
        items = items[:max_items]

    filters_used = data.get("filters_used", {}) or {}
    lines = [_make_header(filters_used)]

    if items:
        for i, v in enumerate(items, 1):
            name = _get(v, "name", "title", "venue_name", default="?")
            district = _get(v, "district", "area", "location", default="?")

            # Вместимость
            cap_pair = _get(v, "capacity", default=None)
            cap_min, cap_max = _norm_minmax(cap_pair, default=(
                _get(v, "capacity_min", "min_capacity", "capacityMin", default="?"),
                _get(v, "capacity_max", "max_capacity", "capacityMax", default="?"),
            ))

            # Цена/гость
            ppg_pair = _get(v, "price_per_guest", default=None)
            price_min, price_max = _norm_minmax(ppg_pair, default=(
                _get(v, "price_per_guest_min", "ppg_min", "priceMin", default="?"),
                _get(v, "price_per_guest_max", "ppg_max", "priceMax", default="?"),
            ))

            lines.append(f"{i}. {name} — {district} — {cap_min}–{cap_max} мест — ~{price_min}–{price_max} AZN/гость")
    else:
        # Если карточек нет, но API прислал готовый текст (reply) — используем его
        reply_text = data.get("reply")
        if reply_text:
            lines.append(reply_text.strip())
        else:
            lines.append("Пока подходящих площадок не найдено по этим параметрам.")

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
    #   FIXME: в твоём main.py ПЕРЕД вызовом этой функции уже делается save_message(chat_id, "user", text).
    #   Чтобы не было дублирования сообщений в истории, лучше ИЛИ убрать ту запись в main.py,
    #   ИЛИ закомментировать следующую строку:
    # append_user_message(chat_id, user_text)

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
                cnt_shortlist = len(data.get("shortlist", []) or [])
            except Exception:
                #cnt_items = cnt_venues = cnt_results = -1
                cnt_items = cnt_venues = cnt_results = cnt_shortlist = -1
            #print(f"[EventaAPI] keys=[{log_keys}] counts: items={cnt_items}, venues={cnt_venues}, results={cnt_results}")
            print(f"[EventaAPI] keys=[{log_keys}] counts: items={cnt_items}, venues={cnt_venues}, results={cnt_results}, shortlist={cnt_shortlist}")
        except Exception:
            text = (
                "Кажется, возникла техническая задержка при поиске площадок. "
                "Попробуйте изменить параметры или повторить запрос чуть позже."
            )
            #   FIXME: аналогично, в main.py ПОСЛЕ вызова этой функции ты уже делаешь save_message(..., 'assistant', reply)
            #   Чтобы не было дублей — либо оставь append_* здесь и убери сохранение в main.py,
            #   либо наоборот: закомментируй append_* здесь.
            #append_assistant_message(chat_id, text)
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
        
        #   FIXME: см. комментарий выше про дубли. Либо сохраняем здесь и убираем в main.py,
        #   либо комментируем эти две строки и сохраняем только в main.py.
        append_assistant_message(chat_id, final)
        
        return final

    # Инструмент не вызывался — вернём обычный текст
    final = (first.choices[0].message.content or "").strip() or \
            "Уточните, пожалуйста, параметры поиска (гостей, бюджет/гость, район)."
    #   FIXME: тот же комментарий про дублирование сохранения ответа.
    #append_assistant_message(chat_id, final)
    
    return final
