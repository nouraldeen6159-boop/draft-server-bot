import math, requests, os
import pandas as pd, numpy as np
from fastapi import FastAPI, Request
from io import BytesIO

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
ADMIN_ID = 7101808941 

# ملف لحفظ المستخدمين (ملاحظة: هذا الملف يمسح عند إعادة تشغيل Vercel، 
# للحل الدائم يفضل استخدام قاعدة بيانات سحابية)
USERS_FILE = "allowed_users.txt"

def get_allowed():
    if not os.path.exists(USERS_FILE): return [ADMIN_ID]
    with open(USERS_FILE, "r") as f: return [int(line.strip()) for line in f]

def save_users(users):
    with open(USERS_FILE, "w") as f: f.writelines([f"{u}\n" for u in set(users)])

user_sessions = {}

def send_msg(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup: payload["reply_markup"] = reply_markup
    requests.post(f"{BASE_URL}/sendMessage", json=payload)

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    if "message" not in data: return {"status": "ok"}
    msg = data["message"]
    chat_id, user_id = msg["chat"]["id"], msg["from"]["id"]
    
    # 1. نظام الحماية
    allowed = get_allowed()
    if user_id not in allowed:
        send_msg(chat_id, f"⛔ غير مصرح لك.\nالـ ID الخاص بك: `{user_id}`")
        return {"status": "ok"}

    # 2. الأوامر
    text = msg.get("text", "")
    if text == "/start":
        menu = {"inline_keyboard": [[{"text": "📊 درافت سيرفي", "callback_data": "draft"}],
                                    [{"text": "➕ إضافة مستخدم", "callback_data": "add"}],
                                    [{"text": "➖ حذف مستخدم", "callback_data": "del"}]]}
        send_msg(chat_id, "أهلاً قبطان، اختر العملية:", menu)
    
    elif text.startswith("/add "):
        if user_id == ADMIN_ID:
            new_id = int(text.split()[1])
            users = get_allowed()
            users.append(new_id)
            save_users(users)
            send_msg(chat_id, f"✅ تم إضافة {new_id}")
            
    elif text.startswith("/del "):
        if user_id == ADMIN_ID:
            rem_id = int(text.split()[1])
            users = get_allowed()
            if rem_id in users: users.remove(rem_id)
            save_users(users)
            send_msg(chat_id, f"✅ تم حذف {rem_id}")

    # 3. معالجة الملفات والحسابات (كما صممناها سابقاً)
    # [هنا تضع منطق حساب الدرافت سيرفي الذي صممناه سابقاً]
    
    return {"status": "ok"}
