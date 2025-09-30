from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os

load_dotenv()

from transport import get_provider
from services.bot_logic import process_message

app = Flask(__name__)
provider = get_provider()

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        message = provider.parse_incoming(data)
        if message:
            response = process_message(message['text'])
            provider.send_message(message['chat_id'], response)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
