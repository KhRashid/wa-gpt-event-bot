import requests
from config import GREEN_API_INSTANCE_ID, GREEN_API_TOKEN

class GreenAPI:
    def parse_incoming(self, data):
        try:
            msg = data['messageData']['textMessageData']['textMessage']
            chat_id = data['senderData']['chatId']
            return {'text': msg, 'chat_id': chat_id}
        except:
            return None

    def send_message(self, chat_id, message):
        url = f'https://api.green-api.com/waInstance{GREEN_API_INSTANCE_ID}/sendMessage/{GREEN_API_TOKEN}'
        payload = {
            "chatId": chat_id,
            "message": message
        }
        requests.post(url, json=payload)
