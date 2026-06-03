import requests
from fastapi import FastAPI, Request

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
ADMIN_ID = 8684618304

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    
    # 1. التعامل مع الضغط على الأزرار (Callback Query)
    if "callback_query" in data:
        cb = data["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        action = cb["data"]
        
        if action == "draft":
            text = "قم برفع ملف الـ CSV/Excel الآن."
        elif action == "list_users":
            text = f"الأدمين الحالي هو: `{ADMIN_ID}`"
        elif action == "del":
            text = "لحذف مستخدم، أرسل: /del [ID]"
        else:
            text = "تم الضغط على: " + action
            
        requests.post(f"{BASE_URL}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
        requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
        return {"status": "ok"}

    # 2. التعامل مع الرسائل النصية والأوامر
    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")
        
        if text == "/start":
            menu = {
                "inline_keyboard": [
                    [{"text": "📊 درافت سيرفي", "callback_data": "draft"}],
                    [{"text": "📋 عرض المستخدمين", "callback_data": "list_users"}],
                    [{"text": "➖ حذف مستخدم", "callback_data": "del"}]
                ]
            }
            requests.post(f"{BASE_URL}/sendMessage", json={
                "chat_id": chat_id, 
                "text": "مرحباً يا أدمين، إليك لوحة التحكم:", 
                "reply_markup": menu
            })
            
    return {"status": "ok"}





