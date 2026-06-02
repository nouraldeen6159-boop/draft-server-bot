import math, requests, pandas as pd, numpy as np
from fastapi import FastAPI, Request
from io import BytesIO

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
    
    # استقبال الملف
    if "document" in msg:
        doc = msg["document"]
        file_info = requests.get(f"{BASE_URL}/getFile?file_id={doc['file_id']}").json()
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info['result']['file_path']}"
        try:
            df = pd.read_csv(file_url) if doc["file_name"].endswith('.csv') else pd.read_excel(file_url)
            df.columns = df.columns.str.strip()
            user_sessions[user_id] = {"tables": df, "state": "AWAITING_DRAFTS"}
            send_message(chat_id, "✅ تم حفظ الجدول. أرسل الآن:\n`[Fwd] [Mid] [Aft] [Breadth] [Angle] [Direction]`")
        except: send_message(chat_id, "❌ خطأ في قراءة الملف.")
        return {"status": "ok"}

    # المعالجة النصية
    if "text" in msg:
        text = msg["text"].strip().replace(',', '.')
        if text == "/start":
            user_sessions[user_id] = {}
            send_message(chat_id, "⚓️ أهلاً بك. ارفع ملف CSV/Excel الخاص بجدول السفينة.")
            return {"status": "ok"}
            
        sess = user_sessions.get(user_id)
        if not sess or "tables" not in sess: return {"status": "ok"}
        
        try:
            parts = [float(x) for x in text.split()]
            if sess["state"] == "AWAITING_DRAFTS" and len(parts) == 6:
                f, m, a, b, ang, direct = parts
                m_sea = m - ((b/2)*math.tan(math.radians(ang))) if direct == 1 else m + ((b/2)*math.tan(math.radians(ang)))
                
                mid_theory = (f + a) / 2
                diff = m_sea - mid_theory
                status = "Neutral" if abs(diff) <= 0.02 else ("Hogging" if diff > 0 else "Sagging")
                
                mom = (f + a + (6 * ((m + m_sea) / 2))) / 8
                sess.update({"mom": mom, "state": "DEDUCTS", "status": status})
                send_message(chat_id, f"📊 الغاطس النهائي: {mom:.3f}\n🏗 الوضع: {status}\n📥 أرسل [المخصومات] [الكثافة]")
                
            elif sess["state"] == "DEDUCTS" and len(parts) == 2:
                deduct, dens = parts
                df = sess["tables"]
                raw = float(np.interp(sess["mom"], df['Draft'], df['Displacement']))
                net = (raw * (dens / 1.025)) - deduct
                send_message(chat_id, f"🏁 **التقرير النهائي**\nالغاطس: {sess['mom']:.3f}\nالوضع: {sess['status']}\nالوزن الصافي: {net:.2f} طن.")
                sess["state"] = "AWAITING_DRAFTS"
        except: send_message(chat_id, "⚠️ خطأ في الصيغة!")
            
    return {"status": "ok"}
