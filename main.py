import requests
from fastapi import FastAPI, Request
import os

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
ADMIN_ID = 8684618304
USERS_FILE = "allowed_users.txt"

# دالة لقراءة المستخدمين
def get_allowed():
    allowed = {ADMIN_ID}
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            for line in f:
                if line.strip().isdigit(): allowed.add(int(line.strip()))
    return list(allowed)

# دالة لحفظ المستخدمين
def save_users(users_list):
    with open(USERS_FILE, "w") as f:
        for u in set(users_list): f.write(f"{u}\n")

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    
    # 1. التعامل مع الأزرار
    if "callback_query" in data:
        cb = data["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        action = cb["data"]
        
        if action == "draft":
            text = "قم برفع ملف الـ CSV/Excel الآن."
        elif action == "list_users":
            text = f"📋 قائمة المستخدمين المصرح لهم:\n`{get_allowed()}`"
        elif action == "add":
            text = "لإضافة مستخدم، أرسل: /add [ID]"
        elif action == "del":
            text = "لحذف مستخدم، أرسل: /del [ID]"
        else:
            text = "تم الضغط على: " + action
            
        requests.post(f"{BASE_URL}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
        requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
        return {"status": "ok"}

    # 2. التعامل مع الرسائل
    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")
        
        if text == "/start":
            menu = {
                "inline_keyboard": [
                    [{"text": "📊 درافت سيرفي", "callback_data": "draft"}],
                    [{"text": "📋 عرض المستخدمين", "callback_data": "list_users"}],
                    [{"text": "➕ إضافة", "callback_data": "add"}, {"text": "➖ حذف", "callback_data": "del"}]
                ]
            }
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id, 
                "text": "أهلاً يا قبطان، اختر العملية:", 
                "reply_markup": menu
            })
        
        # منطق الإضافة (يدعم /add [ID])
        elif text.startswith("/add "):
            new_id = int(text.split()[1])
            users = get_allowed()
            if new_id not in users:
                users.append(new_id)
                save_users(users)
                requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"✅ تمت إضافة {new_id}"})
                
        # منطق الحذف (يدعم /del [ID])
        elif text.startswith("/del "):
            del_id = int(text.split()[1])
            users = get_allowed()
            if del_id in users and del_id != ADMIN_ID:
                users.remove(del_id)
                save_users(users)
                requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"✅ تمت حذف {del_id}"})

    return {"status": "ok"}

