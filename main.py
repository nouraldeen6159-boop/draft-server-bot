import math, requests, os, pandas as pd, numpy as np, re
from fastapi import FastAPI, Request

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
ADMIN_ID = 8684618304
USERS_FILE = "allowed_users.txt"
user_sessions = {}

def get_allowed():
    # نستخدم قائمة ثابتة + الملف لضمان عمل الأدمين دائماً
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
    
    # معالجة الضغط على الأزرار
    if "callback_query" in data:
        cb = data["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        action = cb["data"]
        
        if action == "draft": 
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "يرجى رفع ملف الـ CSV/Excel."})
        elif action == "list_users": 
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"📋 المصرح لهم:\n`{get_allowed()}`", "parse_mode": "Markdown"})
        elif action == "add": 
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "أرسل: /add [ID]"})
        elif action == "del": 
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "أرسل: /del [ID]"})
        return {"status": "ok"}

    # معالجة الرسائل
    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")
        
        # حماية
        if user_id not in get_allowed():
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"⛔ غير مصرح. ID الخاص بك: `{user_id}`", "parse_mode": "Markdown"})
            return {"status": "ok"}
            
        if text == "/start":
            menu = {"inline_keyboard": [
                [{"text": "📊 درافت سيرفي", "callback_data": "draft"}],
                [{"text": "📋 قائمة المعرفات", "callback_data": "list_users"}],
                [{"text": "➕ إضافة", "callback_data": "add"}, {"text": "➖ حذف", "callback_data": "del"}]
            ]}
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "أهلاً يا قبطان:", "reply_markup": menu})
        
        elif re.match(r'^/add\s*\d+', text):
            new_id = int(re.findall(r'\d+', text)[0])
            users = get_allowed()
            if new_id not in users:
                users.append(new_id)
                save_users(users)
                requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"✅ تمت إضافة {new_id}"})
    return {"status": "ok"}



