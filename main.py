import math, requests, pandas as pd, numpy as np
from fastapi import FastAPI, Request
from io import BytesIO

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
user_sessions = {}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    if "message" not in data: return {"status": "ok"}
    msg = data["message"]
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    
    # معالجة الملف
    if "document" in msg:
        file_id = msg["document"]["file_id"]
        file_info = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
        file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info['result']['file_path']}"
        df = pd.read_csv(file_url)
        df.columns = df.columns.str.strip()
        user_sessions[user_id] = {"tables": df, "state": "DRAFTS"}
        requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "✅ الجدول جاهز. أرسل الآن: 6 أرقام (غواطس)"})
        return {"status": "ok"}
        
    # معالجة النص
    if "text" in msg:
        txt = msg["text"].strip().replace(',', ' ')
        if txt == "/start":
            user_sessions[user_id] = {}
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "أهلاً. ارفع ملف CSV."})
            return {"status": "ok"}
            
        sess = user_sessions.get(user_id)
        if not sess or "tables" not in sess: return {"status": "ok"}
        
        parts = [float(x) for x in txt.split()]
        if len(parts) == 6:
            f, m, a, b, ang, d = parts
            corr = (b/2) * math.tan(math.radians(ang))
            m_sea = m - corr if d == 1 else m + corr
            mid_theory = (f + a) / 2
            diff = m_sea - mid_theory
            status = f"{'Hogging' if diff > 0 else 'Sagging'} ({abs(diff*100):.1f}cm)" if abs(diff) > 0.02 else "Neutral"
            mom = (f + a + (6 * ((m + m_sea) / 2))) / 8
            sess.update({"mom": mom, "state": "DEDUCTS", "status": status})
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"الغاطس: {mom:.3f}\nالوضع: {status}\nأرسل الآن: [المخصومات] [الكثافة]"})
        elif len(parts) == 2:
            deduct, dens = parts
            raw = float(np.interp(sess["mom"], sess["tables"]['Draft'], sess["tables"]['Displacement']))
            net = (raw * (dens / 1.025)) - deduct
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"الوزن الصافي: {net:.2f} طن."})
            
    return {"status": "ok"}

        except: 
            send_message(chat_id, "⚠️ خطأ في الصيغة! تأكد من إرسال أرقام فقط.")
            
    return {"status": "ok"}
