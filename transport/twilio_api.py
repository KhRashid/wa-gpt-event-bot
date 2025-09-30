# Заглушка для будущей миграции на Twilio
class TwilioAPI:
    def parse_incoming(self, data):
        return None

    def send_message(self, chat_id, message):
        pass
