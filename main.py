from transport import get_provider
from services.bot_logic import process_message
from flask import Flask, request, jsonify

app = Flask(__name__)
provider = get_provider()

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    message = provider.parse_incoming(data)
    if message:
        response = process_message(message['text'])
        provider.send_message(message['chat_id'], response)
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(port=5000)
