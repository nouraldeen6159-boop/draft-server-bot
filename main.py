import math
import requests
import pandas as pd
import numpy as np
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
        
        # 1. أمر البدء
        if txt == "/start":
            send_message(chat_id, "أهلاً بك. اختر لغتك بكتابة: /ar للعربية أو /en للإنجليزية")
            return {"status": "ok"}
        
        # 2. اختيار اللغة (بديل الأزرار)
        if txt in ["/ar", "/en"]:
            lang = "AR" if txt == "/ar" else "EN"
            user_sessions[user_id] = {"language": lang, "state": "AWAITING_FILE"}
            msg_set = "تم اختيار العربية. يرجى الآن رفع ملف جدول السفينة (CSV)." if lang == "AR" else "English selected. Please upload the Ship Table (CSV)."
            send_message(chat_id, msg_set)
            return {"status": "ok"}
            
        # 3. معالجة الملفات والحسابات
        session = user_sessions.get(user_id)
        if not session: 
            send_message(chat_id, "يرجى البدء بـ /start")
            return {"status": "ok"}
            
        if "document" in msg:
            file_id = msg["document"]["file_id"]
            path = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()["result"]["file_path"]
            url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{path}"
            session["tables"] = pd.read_csv(url)
            session["state"] = "AWAITING_DRAFTS"
            send_message(chat_id, "✅ تم حفظ الجدول. أرسل الآن: [مقدمة] [منتصف] [مؤخرة] [عرض] [زاوية] [اتجاه]")
            
        elif session["state"] == "AWAITING_DRAFTS":
            try:
                f, m, a, b, ang, direct = map(float, txt.split())
                corr = (b / 2) * math.tan(math.radians(ang))
                m_sea = m - corr if direct == 1 else m + corr
                mom = (f + a + (6 * (m + m_sea)/2)) / 8
                session.update({"mom": mom, "state": "AWAITING_DEDUCTIONS"})
                send_message(chat_id, f"الغاطس النهائي: {mom:.3f}. أرسل الآن [المخصومات] [الكثافة]")
            except: send_message(chat_id, "خطأ في الصيغة. جرب مجدداً.")
            
        elif session["state"] == "AWAITING_DEDUCTIONS":
            try:
                deduct, dens = map(float, txt.split())
                raw = float(np.interp(session["mom"], session["tables"]['Draft'], session["tables"]['Displacement']))
                net = (raw * (dens / 1.025)) - deduct
                send_message(chat_id, f"الوزن الصافي: {net:.2f} طن. لمسح جديد أرسل الغواطس.")
                session["state"] = "AWAITING_DRAFTS"
            except: send_message(chat_id, "خطأ في الصيغة.")
            
    return {"status": "ok"}
