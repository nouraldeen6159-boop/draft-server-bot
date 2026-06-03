import requests
from fastapi import FastAPI, Request

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
ADMIN_ID = 8684618304 # المعرف الذي زودتني به

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")

        # رسالة تفعيل الأدمين (تظهر دائماً للأدمين)
        if text == "/start":
            if user_id == ADMIN_ID:
                menu = {
                    "inline_keyboard": [
                        [{"text": "📊 درافت سيرفي", "callback_data": "draft"}],
                        [{"text": "➕ إضافة مستخدم", "callback_data": "add"}]
                    ]
                }
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id, 
                    "text": "مرحباً يا أدمين، البوت مفعل بالكامل. استخدم الأزرار أدناه:", 
                    "reply_markup": menu
                })
            else:
                # إذا لم يكن هو الأدمين، البوت سيعطيك الـ ID الصحيح للنسخ
                requests.post(f"{BASE_URL}/sendMessage", json={
                    "chat_id": chat_id, 
                    "text": f"⛔ غير مصرح.\nالـ ID الخاص بك هو: `{user_id}`\nانسخ هذا الرقم وحدث به كود الأدمين."
                })
    return {"status": "ok"}




