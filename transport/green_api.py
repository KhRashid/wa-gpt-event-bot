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

#    def send_message(self, chat_id, message):
#        url = f'https://api.green-api.com/waInstance{GREEN_API_INSTANCE_ID}/sendMessage/{GREEN_API_TOKEN}'
#        payload = {
#            "chatId": chat_id,
#            "message": message
#        }
#        print("SEND PAYLOAD:", payload)  # <=== лог
#        requests.post(url, json=payload)
#        print("RESPONSE:", response.status_code, response.text)  # <=== лог

    def send_message(self, chat_id, message):
        url = f'https://api.green-api.com/waInstance{GREEN_API_INSTANCE_ID}/sendMessage/{GREEN_API_TOKEN}'
        payload = {
            "chatId": chat_id,
            "message": message
        }
        try:
            print("SEND PAYLOAD:", payload)                 # лог
            resp = requests.post(url, json=payload, timeout=15)
            print("RESPONSE:", resp.status_code, resp.text) # лог
            resp.raise_for_status()
            return True
        except Exception as e:
            print("SEND ERROR:", e)
            return False
