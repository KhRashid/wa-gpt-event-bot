# WhatsApp GPT Bot

Flask-приложение для обработки сообщений WhatsApp через Green-API и ответа с помощью GPT.

## Как запустить

1. Установите зависимости:
```
pip install -r requirements.txt
```

2. Создайте файл `.env` и укажите:
```
USE_PROVIDER=green
GREEN_API_INSTANCE_ID=your_instance_id
GREEN_API_TOKEN=your_token
OPENAI_API_KEY=your_openai_key
```

3. Запуск:
```
python main.py
```
