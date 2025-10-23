# services/state.py
from google.cloud import firestore
from .db import db

def upsert_chat(chat_id: str, **fields):
    db.collection("chats").document(chat_id).set(
        {**fields, "updatedAt": firestore.SERVER_TIMESTAMP},
        merge=True,
    )

def get_chat(chat_id: str):
    doc = db.collection("chats").document(chat_id).get()
    return doc.to_dict() if doc.exists else None

def save_message(chat_id: str, role: str, text: str):
    # role: user | assistant | operator
    db.collection("chats").document(chat_id).collection("messages").add({
        "role": role,
        "text": text,
        "ts": firestore.SERVER_TIMESTAMP,
    })
    upsert_chat(chat_id)  # touch

def get_history(chat_id: str, limit: int = 10):
    q = (db.collection("chats").document(chat_id).collection("messages")
         .order_by("ts", direction=firestore.Query.DESCENDING)
         .limit(limit))
    items = []
    for d in q.stream():
        m = d.to_dict()
        if m.get("role") not in ("user", "assistant"):
            continue  # пропустим operator для LLM
        items.append({"role": m["role"], "content": m["text"]})
    return list(reversed(items))

def open_ticket(chat_id: str, reason="keyword", assignee=None):
    db.collection("tickets").document(chat_id).set({
        "status": "OPEN",
        "reason": reason,
        "assignee": assignee,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "updatedAt": firestore.SERVER_TIMESTAMP,
    })
    upsert_chat(chat_id, state="ESCALATED")

def close_ticket(chat_id: str, note=None):
    db.collection("tickets").document(chat_id).set({
        "status": "CLOSED",
        "note": note,
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }, merge=True)
    upsert_chat(chat_id, state="BOT")

# === thin wrappers for bot_logic compatibility ===

def append_user_message(chat_id: str, content: str) -> None:
    """Compatibility wrapper: store user message."""
    save_message(chat_id, role="user", text=content)

def append_assistant_message(chat_id: str, content: str) -> None:
    """Compatibility wrapper: store assistant message."""
    save_message(chat_id, role="assistant", text=content)
