import math, requests, os
import pandas as pd, numpy as np
from fastapi import FastAPI, Request

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
ADMIN_ID = 7101808941 
USERS_FILE = "allowed_users.txt"

# --- دوال إدارة المستخدمين ---
def get_allowed():
    if not os.path.exists(USERS_FILE): return [ADMIN_ID]
    with open(USERS_FILE, "r") as f: return [int(line.strip()) for line in f]

def save_users(users):
    with open(USERS_FILE, "w") as f: f.writelines([f"{u}\n" for u in set(users)])

# --- دالة الإرسال ---
def send_msg(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup: payload["reply_markup"] = reply_markup
    requests.post(f"{BASE_URL}/sendMessage", json=payload)

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    
    # 1. معالجة الضغط على الأزرار (Callback Query)
    if "callback_query" in data:
        cb = data["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        action = cb["data"]
        
        if action == "draft":
            send_msg(chat_id, "يرجى رفع ملف الـ CSV/Excel للبدء.")
        elif action == "add":
            send_msg(chat_id, "أرسل الآن: /add [ID] لإضافة مستخدم.")
        elif action == "del":
            send_msg(chat_id, "أرسل الآن: /del [ID] لحذف مستخدم.")
        return {"status": "ok"}

    # 2. معالجة الرسائل العادية
    if "message" in data:
        msg = data["message"]
        chat_id, user_id = msg["chat"]["id"], msg["from"]["id"]
        
        if user_id not in get_allowed():
            send_msg(chat_id, f"⛔ غير مصرح لك. الـ ID: `{user_id}`")
            return {"status": "ok"}
            
        text = msg.get("text", "")
        if text == "/start":
            menu = {"inline_keyboard": [
                [{"text": "📊 درافت سيرفي", "callback_data": "draft"}],
                [{"text": "➕ إضافة مستخدم", "callback_data": "add"}],
                [{"text": "➖ حذف مستخدم", "callback_data": "del"}]
            ]}
            send_msg(chat_id, "مرحباً يا قبطان، اختر العملية:", menu)
            
        elif text.startswith("/add "):
            users = get_allowed()
            users.append(int(text.split()[1]))
            save_users(users)
            send_msg(chat_id, "✅ تم الإضافة.")
            
        elif text.startswith("/del "):
            users = get_allowed()
            rem_id = int(text.split()[1])
            if rem_id in users:
                users.remove(rem_id)
                save_users(users)
                send_msg(chat_id, "✅ تم الحذف.")
                
    return {"status": "ok"}
