import requests, os, re
from fastapi import FastAPI, Request

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
ADMIN_ID = 8684618304
USERS_FILE = "allowed_users.txt"

def get_allowed():
    allowed = {ADMIN_ID}
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            for line in f:
                if line.strip().isdigit(): allowed.add(int(line.strip()))
    return list(allowed)

def save_users(users_list):
    with open(USERS_FILE, "w") as f:
        for u in set(users_list): f.write(f"{u}\n")

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    
    # تحديد المستخدم
    if "callback_query" in data:
        user_id = data["callback_query"]["from"]["id"]
        chat_id = data["callback_query"]["message"]["chat"]["id"]
    elif "message" in data:
        user_id = data["message"]["from"]["id"]
        chat_id = data["message"]["chat"]["id"]
    else:
        return {"status": "ok"}

    # 1. الحماية: التأكد من الصلاحية
    if user_id not in get_allowed():
        requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "⛔ غير مصرح لك باستخدام البوت."})
        return {"status": "ok"}

    # 2. التعامل مع الأزرار
    if "callback_query" in data:
        cb = data["callback_query"]
        action = cb["data"]
        
        if action == "draft": text = "يرجى رفع ملف الـ CSV/Excel."
        elif action == "list_users": text = f"📋 المصرح لهم:\n`{get_allowed()}`"
        elif action == "add": text = "أرسل: /add [ID]"
        elif action == "del": text = "أرسل: /del [ID]"
        else: text = "تمت العملية."
        
        requests.post(f"{BASE_URL}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
        requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
        return {"status": "ok"}

    # 3. التعامل مع الرسائل
    if "message" in data:
        text = data["message"].get("text", "")
        
        if text == "/start":
            menu = {"inline_keyboard": [
                [{"text": "📊 درافت سيرفي", "callback_data": "draft"}],
                [{"text": "📋 قائمة المستخدمين", "callback_data": "list_users"}],
                [{"text": "➕ إضافة", "callback_data": "add"}, {"text": "➖ حذف", "callback_data": "del"}]
            ]}
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "أهلاً قبطان:", "reply_markup": menu})
        
        elif text.startswith("/add "):
            new_id = int(text.split()[1])
            users = get_allowed()
            if new_id not in users:
                users.append(new_id)
                save_users(users)
                requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"✅ تمت إضافة {new_id}"})
                
        elif text.startswith("/del "):
            del_id = int(text.split()[1])
            users = get_allowed()
            if del_id in users and del_id != ADMIN_ID:
                users.remove(del_id)
                save_users(users)
                requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"✅ تمت حذف {del_id}"})

    return {"status": "ok"}


