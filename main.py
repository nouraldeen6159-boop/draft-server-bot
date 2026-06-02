import math, requests, pandas as pd, numpy as np
from fastapi import FastAPI, Request
from io import BytesIO

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
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
    
    # 1. معالجة الملف
    if "document" in msg:
        doc = msg["document"]
        file_info = requests.get(f"{BASE_URL}/getFile?file_id={doc['file_id']}").json()
        file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info['result']['file_path']}"
        try:
            df = pd.read_csv(file_url)
            df.columns = df.columns.str.strip()
            user_sessions[user_id] = {"tables": df, "state": "AWAITING_DRAFTS"}
            send_message(chat_id, "✅ تم حفظ الجدول. أرسل الآن الغواطس الستة (مسافات فقط):")
        except: send_message(chat_id, "❌ خطأ في الملف.")
        return {"status": "ok"}

    # 2. المعالجة النصية
    if "text" in msg:
        # تنظيف النص من أي فواصل غير المسافات
        txt = msg["text"].strip().replace(',', ' ').replace('  ', ' ')
        sess = user_sessions.get(user_id)
        if not sess: return {"status": "ok"}
        
        try:
            parts = [float(x) for x in txt.split()]
            
            # حالة الغواطس
            if sess["state"] == "AWAITING_DRAFTS" and len(parts) == 6:
                f, m, a, b, ang, direct = parts
                # تصحيح الميل
                corr = (b / 2) * math.tan(math.radians(ang))
                m_sea = m - corr if direct == 1 else m + corr
                
                # حساب الـ Hogging/Sagging
                mid_theory = (f + a) / 2
                diff = m_sea - mid_theory
                status = f"{'Hogging' if diff > 0 else 'Sagging'} ({abs(diff*100):.1f} cm)" if abs(diff) > 0.02 else "Neutral"
                
                mom = (f + a + (6 * ((m + m_sea) / 2))) / 8
                sess.update({"mom": mom, "state": "DEDUCTS", "status": status})
                send_message(chat_id, f"📊 الغاطس: {mom:.3f}\n🏗 الوضع: {status}\n📥 أرسل: [المخصومات] [الكثافة]")
                
            # حالة المخصومات
            elif sess["state"] == "DEDUCTS" and len(parts) == 2:
                deduct, dens = parts
                df = sess["tables"]
                raw = float(np.interp(sess["mom"], df['Draft'], df['Displacement']))
                net = (raw * (dens / 1.025)) - deduct
                send_message(chat_id, f"🏁 **التقرير**\nالغاطس: {sess['mom']:.3f}\nالوضع: {sess['status']}\nالصافي: {net:.2f} طن.")
                sess["state"] = "AWAITING_DRAFTS"
            else:
                send_message(chat_id, f"⚠️ عدد القيم غير صحيح: {len(parts)} (المطلوب 6 للغواطس أو 2 للمخصومات).")
        except: 
            send_message(chat_id, "⚠️ خطأ في الصيغة! تأكد من إرسال أرقام فقط.")
            
    return {"status": "ok"}

