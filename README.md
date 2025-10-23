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


# Eventa Tool Integration (query_catalogue)

Этот набор файлов добавляет к боту поддержку tool-calling и проксирует запросы в **Eventa-APIwithCatalogue**.

## Что добавлено
- `services/tools_schema.py` — описание инструмента `query_catalogue` (JSON-schema).
- `services/eventa_adapter.py` — тонкий адаптер к `EVENTA_API_URL` (`/search`).
- `services/bot_logic.py` — drop-in замена: теперь бот умеет вызывать инструмент, сходить в Eventa-API и красиво оформить ответ.

## Переменные окружения
```
OPENAI_API_KEY=sk-...
EVENTA_API_URL=https://<ваш-cloud-run>/search
EVENTA_API_KEY=<опционально, если требуется Bearer>
```

## Требуемые зависимости
- `openai>=1.40.0`
- `httpx>=0.27.0`
- (остальные — как в проекте)

## Быстрый тест (локально)
1. Пропишите переменные окружения ( `.env` либо в панели хостинга ).
2. Запустите `python main.py` и отправьте тестовое сообщение через Twilio/GreenAPI.
3. Пример запроса пользователя: _"Нужен зал на 80 гостей до 50 AZN, Насими"_.

## Как это работает
1. Модель получает ваш текст + объявленный инструмент `query_catalogue`.
2. Если нужен поиск — модель вернёт `tool_call`.
3. Бэкенд выполнит `run_query_catalogue(args)` → `GET EVENTA_API_URL?guest_count=...`.
4. Результат вернём модели как `tool`-сообщение → сформируется финальный ответ.
5. Бот отправит ответ пользователю.

## Частые ошибки
- **401/403 к Eventa-API** — проверьте `EVENTA_API_KEY` и заголовок Authorization.
- **TIMEOUT** — увеличьте таймаут в `eventa_adapter.py` или проверьте сеть/индексы.
- **Пустая выдача** — это не ошибка; модель вежливо попросит ослабить фильтры.
