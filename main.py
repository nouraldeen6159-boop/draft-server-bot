import math
import requests
import pandas as pd
import numpy as np
from io import BytesIO
from fastapi import FastAPI, Request

app = FastAPI()

TELEGRAM_TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

user_sessions = {}

def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    if "message" not in data: return {"status": "ok"}
    
    msg = data["message"]
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    
    if "text" in msg:
        txt = msg["text"].strip()
        
        # أمر البدء
        if txt == "/start":
            send_message(chat_id, "أهلاً بك. اختر لغتك بكتابة: /ar للعربية أو /en للإنجليزية")
            return {"status": "ok"}
        
        # اختيار اللغة
        if txt in ["/ar", "/en"]:
            lang = "AR" if txt == "/ar" else "EN"
            user_sessions[user_id] = {"language": lang, "state": "AWAITING_FILE"}
            res = "تم اختيار العربية. يرجى رفع ملف CSV الآن." if lang == "AR" else "English selected. Please upload CSV now."
            send_message(chat_id, res)
            return {"status": "ok"}
            
        session = user_sessions.get(user_id)
        if not session: 
            send_message(chat_id, "يرجى البدء بـ /start")
            return {"status": "ok"}
            
        # الحسابات
        try:
            f, m, a, b, ang, direct = map(float, txt.split())
            corr = (b / 2) * math.tan(math.radians(ang))
            m_sea = m - corr if direct == 1 else m + corr
            mom = (f + a + (6 * (m + m_sea)/2)) / 8
            session.update({"mom": mom, "state": "AWAITING_DEDUCTIONS"})
            res = f"الغاطس النهائي: {mom:.3f}. أرسل [المخصومات] [الكثافة]" if session["language"]=="AR" else f"Mean of Means: {mom:.3f}. Send [Deductions] [Density]"
            send_message(chat_id, res)
        except:
            send_message(chat_id, "خطأ في الصيغة / Input error")
            
    elif "document" in msg:
        session = user_sessions.get(user_id)
        if not session: return {"status": "ok"}
        
        file_id = msg["document"]["file_id"]
        path = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()["result"]["file_path"]
        url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{path}"
        
        # قراءة الملف بطريقة ثابتة
        response = requests.get(url)
        session["tables"] = pd.read_csv(BytesIO(response.content))
        session["state"] = "AWAITING_DRAFTS"
        res = "✅ تم حفظ الجدول. أرسل الآن: [مقدمة] [منتصف] [مؤخرة] [عرض] [زاوية] [اتجاه]" if session["language"]=="AR" else "✅ Table saved. Send: [Fwd] [Mid] [Aft] [Breadth] [Angle] [Direction]"
        send_message(chat_id, res)
        
    return {"status": "ok"}

