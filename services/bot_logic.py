import openai import OpenAI
from config import OPENAI_API_KEY

#openai.api_key = OPENAI_API_KEY
client = OpenAI(api_key=OPENAI_API_KEY)

def process_message(text):
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
