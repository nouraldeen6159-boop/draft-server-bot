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
    requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    if "message" not in data: return {"status": "ok"}
    msg = data["message"]
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    
    if "text" in msg:
        txt = msg["text"].strip().replace(',', '.') # استبدال أي فاصلة بنقطة تلقائياً
        
        if txt == "/start":
            user_sessions[user_id] = {}
            send_message(chat_id, "أرسل /ar للعربية أو /en للإنجليزية")
            return {"status": "ok"}
            
        if txt in ["/ar", "/en"]:
            user_sessions[user_id] = {"lang": "AR" if txt == "/ar" else "EN", "state": "FILE"}
            send_message(chat_id, "يرجى رفع ملف الـ CSV الآن.")
            return {"status": "ok"}
            
        session = user_sessions.get(user_id)
        if not session: return {"status": "ok"}

        try:
            parts = [float(x) for x in txt.split()]
            
            if session["state"] == "DRAFTS" and len(parts) == 6:
                f, m, a, b, ang, direct = parts
                corr = (b / 2) * math.tan(math.radians(ang))
                m_sea = m - corr if direct == 1 else m + corr
                mom = (f + a + (6 * (m + m_sea)/2)) / 8
                session.update({"mom": mom, "state": "DEDUCTIONS"})
                send_message(chat_id, f"الغاطس النهائي: {mom:.3f}. أرسل الآن [المخصومات] [الكثافة]")
                
            elif session["state"] == "DEDUCTIONS" and len(parts) == 2:
                deduct, dens = parts
                raw = float(np.interp(session["mom"], session["tables"]['Draft'], session["tables"]['Displacement']))
                net = (raw * (dens / 1.025)) - deduct
                send_message(chat_id, f"الوزن الصافي: {net:.2f} طن.")
                session["state"] = "DRAFTS"
        except:
            send_message(chat_id, "⚠️ خطأ! أرسل الأرقام فقط (مثال: 940.3 1.010)")
            
    elif "document" in msg:
        session = user_sessions.get(user_id)
        if session:
            file_id = msg["document"]["file_id"]
            path = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()["result"]["file_path"]
            resp = requests.get(f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{path}")
            session["tables"] = pd.read_csv(BytesIO(resp.content))
            session["state"] = "DRAFTS"
            send_message(chat_id, "✅ تم حفظ الجدول. أرسل الآن الغواطس 6 أرقام.")
            
    return {"status": "ok"}
