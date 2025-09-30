from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os

load_dotenv()

from transport import get_provider
from services.bot_logic import process_message

app = Flask(__name__)
provider = get_provider()

@app.route("/", methods=["GET"])
def index():
    return "Bot is running!"
    
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        #data = request.json
        data = request.get_json(force=True, silent=True)  # надежнее
        print("RAW IN:", data)   

        message = provider.parse_incoming(data)
        print("PARSED:", message)                         # <— лог результата парсинга

        if message:
            reply = process_message(message['text'])
            print("REPLY:", reply)                        # <— лог ответа GPT
            
            #provider.send_message(message['chat_id'], reply)
            ok = provider.send_message(message['chat_id'], reply)
            print("SEND RESULT:", ok)                     # <— лог результата отправки
            
        return jsonify({'status': 'ok'})
    except Exception as e:
        print("WEBHOOK ERROR:", e)
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
