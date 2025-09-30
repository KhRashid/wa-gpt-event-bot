# services/state.py
from google.cloud import firestore
db = firestore.Client()

def save_message(user, role, text):
    db.collection("chats").document(user).collection("messages").add({
        "role": role, "text": text, "ts": firestore.SERVER_TIMESTAMP
    })

def get_history(user, limit=10):
    docs = db.collection("chats").document(user).collection("messages")\
             .order_by("ts", direction=firestore.Query.DESCENDING).limit(limit).stream()
    items = [{"role": d.to_dict()["role"], "content": d.to_dict()["text"]} for d in docs]
    return list(reversed(items))
