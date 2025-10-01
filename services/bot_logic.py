'''
from openai import OpenAI
from config import OPENAI_API_KEY

#openai.api_key = OPENAI_API_KEY
client = OpenAI(api_key=OPENAI_API_KEY)

#def process_message(text):
def process_message(text: str) -> str:
    try:
        #response = openai.ChatCompletion.create(
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты — помощник по организации мероприятий."},
                {"role": "user", "content": text}
            ]
        )
        ##return response['choices'][0]['message']['content']
        #return response.choices[0].message["content"]
        return resp.choices[0].message.content
    except Exception as e:
        return f"Ошибка при обращении к GPT: {e}"
'''

from openai import OpenAI
from config import OPENAI_API_KEY
from .state import get_history

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = {
    "az": "Sən tədbir təşkilatı üzrə köməkçisən. Qısa, dəqiq və nəzakətli cavablar yaz.",
    "ru": "Ты ассистент по организации мероприятий. Пиши кратко, вежливо и по делу.",
    "en": "You are an event-planning assistant. Be concise and helpful.",
}

def build_messages(chat_id: str, user_text: str, lang: str = "az", max_turns: int = 10):
    history = get_history(chat_id, limit=max_turns)
    system = {"role": "system", "content": SYSTEM_PROMPT.get(lang, SYSTEM_PROMPT["az"])}
    return [system, *history, {"role": "user", "content": user_text}]

def process_message_with_context(chat_id: str, user_text: str, lang: str = "az") -> str:
    msgs = build_messages(chat_id, user_text, lang=lang, max_turns=10)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=msgs,
        temperature=0.3,
        max_tokens=300,
    )
    return resp.choices[0].message.content
