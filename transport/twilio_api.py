# transport/twilio_api.py
import os
from twilio.rest import Client

class TwilioAPI:
    def __init__(self):
        self.sid = os.environ["TWILIO_ACCOUNT_SID"]
        self.token = os.environ["TWILIO_AUTH_TOKEN"]
        self.from_ = os.environ["TWILIO_WHATSAPP_FROM"]  # формат: 'whatsapp:+14155238886'
        self.client = Client(self.sid, self.token)

    # Twilio шлёт form-urlencoded. Flask даёт request.form; мы передаём "сырые" данные сюда.
    def parse_incoming(self, form_dict):
        try:
            # Пример входящих полей: From='whatsapp:+99455...', Body='Привет'
            text = form_dict.get("Body", "")
            from_ = form_dict.get("From")  # 'whatsapp:+99455...'
            if not (text and from_ and from_.startswith("whatsapp:")):
                return None
            chat_id = from_.replace("whatsapp:", "") + "@c.us"  # унифицируем формат, как в Green
            return {"text": text, "chat_id": chat_id}
        except Exception:
            return None

    def send_message(self, chat_id, message: str):
        # chat_id у нас вида '+99455...@c.us' → для Twilio нужно 'whatsapp:+99455...'
        to = "whatsapp:" + chat_id.replace("@c.us", "")
        msg = self.client.messages.create(
            from_=self.from_,
            to=to,
            body=message[:1000]  # на всякий случай ограничим длину
        )
        # вернём True/False по статусу запроса
        return msg.sid is not None
