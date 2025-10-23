from openai import OpenAI
from config import OPENAI_API_KEY
from services.state import get_history, append_user_message, append_assistant_message
from services.tools_schema import query_catalogue_tool
from services.eventa_adapter import run_query_catalogue
import json

client = OpenAI(api_key=OPENAI_API_KEY)
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
'''
def process_message_with_context(chat_id: str, user_text: str, lang: str = "az") -> str:
    # keep history coherent
    append_user_message(chat_id, user_text)
    
    # 1) First pass: announce the tool, let the model decide
    msgs = build_messages(chat_id, user_text, lang=lang)
    first = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=msgs,
        tools=[query_catalogue_tool],
        tool_choice="auto",
        temperature=0.3,
        max_tokens=400,
    )

    #call = _extract_first_tool_call(first)

    if call and call.function and call.function.name == "query_catalogue":
        # Parse tool args
        args = {}
        try:
            args = json.loads(call.function.arguments or "{}")
        except Exception:
            pass

        # 2) Execute tool (proxy to Eventa-API /search)
        try:
            data = run_query_catalogue(args)
        except Exception as e:
            # graceful degrade
            text = (
                "Кажется, возникла техническая задержка при поиске площадок. "
                "Попробуйте изменить параметры или повторить запрос чуть позже."
            )
            append_assistant_message(chat_id, text)
            return text

        # 3) Second pass: return tool result to the model to craft final wording
        msgs2 = msgs + [{
            "role": "tool",
            "tool_call_id": call.id,
            "name": "query_catalogue",
            "content": json.dumps(data, ensure_ascii=False),
        }]

        second = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=msgs2,
            temperature=0.2,
            max_tokens=700,
        )
        final = _join_text(second).strip()
        if not final:
            # fallback formatting on backend (very rare)
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

        append_assistant_message(chat_id, final)
        return final

    # If tool isn't called, return model's text as is
    final = _join_text(first).strip() or "Уточните, пожалуйста, параметры поиска (гостей, бюджет/гость, район)."
    append_assistant_message(chat_id, final)
    return final
'''

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
        except Exception:
            text = (
                "Кажется, возникла техническая задержка при поиске площадок. "
                "Попробуйте изменить параметры или повторить запрос чуть позже."
            )
            append_assistant_message(chat_id, text)
            return text

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

        append_assistant_message(chat_id, final)
        return final

    # Инструмент не вызывался — вернём обычный текст
    final = (first.choices[0].message.content or "").strip() or \
            "Уточните, пожалуйста, параметры поиска (гостей, бюджет/гость, район)."
    append_assistant_message(chat_id, final)
    return final
