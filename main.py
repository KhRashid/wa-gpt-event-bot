# main.py
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import logging

# Загружаем .env локально (на Render переменные берутся из интерфейса)
load_dotenv()

# Наши модули
from transport import get_provider
from services.bot_logic import process_message_with_context
from services.state import (
    save_message,
    get_chat,
    upsert_chat,
    open_ticket,
    close_ticket,
)

# -------------------- Базовая инициализация --------------------

app = Flask(__name__)
provider = get_provider()

# Логирование в stdout (видно в Render → Logs)
logging.basicConfig(level=logging.INFO)
log = app.logger

# --- helper: отправка длинных сообщений частями ---
def chunk_and_send(send_fn, to: str, body: str, chunk_size: int = 1200):
    """
    Режем длинный текст на части, чтобы WhatsApp через Twilio не обрезал сообщение.
    send_fn: функция-отправитель (provider.send_message)
    to: chat_id (например, '+9945...@c.us')
    body: полный текст
    chunk_size: безопасная длина для одного сообщения (1200–1400)
    """
    if not body:
        return True

    parts = []
    current = []
    count = 0

    # режем по строкам — аккуратнее для списков
    for line in body.splitlines():
        # +1 на учёт '\n'
        if count + len(line) + 1 > chunk_size and current:
            parts.append("\n".join(current))
            current = [line]
            count = len(line) + 1
        else:
            current.append(line)
            count += len(line) + 1

    if current:
        parts.append("\n".join(current))

    # отправляем по порядку
    total = len(parts)
    ok_all = True
    for idx, part in enumerate(parts, 1):
        prefix = f"({idx}/{total})\n" if total > 1 else ""
        ok = send_fn(to, prefix + part)
        ok_all = ok_all and bool(ok)
    return ok_all


# -------------------- Вспомогательное --------------------

def detect_lang(text: str) -> str:
    """Очень простой детектор языка (AZ/RU). При желании заменишь на нормальный."""
    t = (text or "").lower()
    if any(w in t for w in ["salam", "necəsən", "xahiş", "bəli", "nə", "təşəkkür"]):
        return "az"
    if any(w in t for w in ["привет", "здравствуйте", "свадьба", "нужно", "спасибо"]):
        return "ru"
    return "az"

#ESCALATE_KEYWORDS = {"operator", "оператор", "менеджер", "человек", "специалист"}
ESCALATE_KEYWORDS = {"operator", "оператор"}

# -------------------- Роуты сервиса --------------------

@app.route("/", methods=["GET"])
def index():
    return "Bot is running!"

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/webhook", methods=["POST"])
def webhook():
    """Входящие сообщения: Twilio (form-urlencoded) и Green-API (JSON)."""
    try:
        # Twilio присылает form; Green — JSON. Берём form в приоритете.
        form = request.form.to_dict() if request.form else {}
        data = form or request.get_json(force=True, silent=True) or {}
        log.info("RAW IN: %s", data)

        message = provider.parse_incoming(data)
        log.info("PARSED: %s", message)

        if not message:
            return jsonify({"status": "ok"})

        chat_id = message["chat_id"]
        text = message.get("text", "")

        # язык + метаданные диалога
        lang = detect_lang(text)
        upsert_chat(chat_id, lang=lang)

        # уже эскалировано — только пишем входящее
        chat_meta = get_chat(chat_id) or {}
        if chat_meta.get("state") == "ESCALATED":
            save_message(chat_id, "user", text)
            return jsonify({"status": "ok"})

        # ключевые слова для эскалации
        if any(k in (text or "").lower() for k in ESCALATE_KEYWORDS):
            open_ticket(chat_id, reason="keyword")
            #provider.send_message(chat_id, "Переключаю вас на специалиста. Он скоро ответит 🙏")
            chunk_and_send(provider.send_message, chat_id, "Переключаю вас на специалиста. Он скоро ответит 🙏")
            return jsonify({"status": "ok"})

        # обычный режим: история → GPT → ответ
        save_message(chat_id, "user", text)
        reply = process_message_with_context(chat_id, text, lang=lang)
        log.info("REPLY: %s", reply)
        save_message(chat_id, "assistant", reply)

        #ok = provider.send_message(chat_id, reply)
        ok = chunk_and_send(provider.send_message, chat_id, reply, chunk_size=1200)
        log.info("SEND RESULT: %s", ok)

        return jsonify({"status": "ok"})
    except Exception as e:
        log.exception("WEBHOOK ERROR")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.post("/operator/reply")
def operator_reply():
    """
    Ручка для оператора: отправить ответ клиенту.
    Требует заголовок X-Operator-Secret = OPERATOR_SECRET из ENV.
    Body JSON: {"chatId":"<id@c.us>", "text":"...", "close": false}
    """
    secret = os.environ.get("OPERATOR_SECRET")
    if secret and request.headers.get("X-Operator-Secret") != secret:
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(force=True, silent=False)
    chat_id = data["chatId"]
    text = data["text"]
    close = bool(data.get("close", False))

    save_message(chat_id, "operator", text)
    #provider.send_message(chat_id, text)
    chunk_and_send(provider.send_message, chat_id, text)

    if close:
        close_ticket(chat_id, note="operator closed")
        #provider.send_message(chat_id, "Спасибо! Диалог закрыт. Если что — пишите.")
        chunk_and_send(provider.send_message, chat_id, "Спасибо! Диалог закрыт. Если что — пишите.")

    return jsonify({"ok": True})

# -------------------- Локальный запуск --------------------

if __name__ == "__main__":
    # Для локального запуска: python main.py
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
