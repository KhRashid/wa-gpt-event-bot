import openai
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def process_message(text):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "Ты — помощник по организации мероприятий."},
                {"role": "user", "content": text}
            ]
        )
        #return response['choices'][0]['message']['content']
        return response.choices[0].message["content"]
    except Exception as e:
        return f"Ошибка при обращении к GPT: {e}"
