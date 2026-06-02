import math, requests, pandas as pd, numpy as np
from io import BytesIO
from fastapi import FastAPI, Request

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
sessions = {}

def send_msg(chat_id, text):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    if "message" not in data: return {"status": "ok"}
    msg = data["message"]
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    
    if "text" in msg:
        txt = msg["text"].strip()
        
        # 1. نظام البدء
        if txt == "/start":
            sessions[user_id] = {"state": "LANG"}
            send_msg(chat_id, "أهلاً بك. أرسل /ar للعربية أو /en للإنجليزية\nWelcome. Send /ar or /en")
            return {"status": "ok"}
        
        if txt in ["/ar", "/en"]:
            sessions[user_id] = {"lang": txt, "state": "FILE"}
            res = "تم اختيار العربية. يرجى رفع ملف CSV." if txt == "/ar" else "English selected. Please upload CSV."
            send_msg(chat_id, res)
            return {"status": "ok"}
            
        # 2. معالجة الحسابات
        sess = sessions.get(user_id)
        if not sess or "tables" not in sess: return {"status": "ok"}
        
        try:
            txt_clean = txt.replace(',', '.')
            vals = [float(x) for x in txt_clean.split()]
            
            if sess["state"] == "DRAFTS" and len(vals) == 6:
                f, m, a, b, ang, direct = vals
                corr = (b / 2) * math.tan(math.radians(ang))
                m_sea = m - corr if direct == 1 else m + corr
                
                # كشف الـ Hogging / Sagging
                theory = (f + a) / 2
                diff = m_sea - theory
                status = "Neutral"
                if abs(diff) > 0.05: status = "Hogging" if diff > 0 else "Sagging"
                
                mom = (f + a + (6 * (m + m_sea)/2)) / 8
                sess.update({"mom": mom, "state": "DEDUCTS", "status": status})
                
                if sess["lang"] == "/ar":
                    send_msg(chat_id, f"الغاطس المكافئ: {mom:.3f}\nالوضع الإنشائي: {status}\nأرسل [المخصومات] [الكثافة]")
                else:
                    send_msg(chat_id, f"Mean of Means: {mom:.3f}\nShip Status: {status}\nSend [Deductions] [Density]")
                
            elif sess["state"] == "DEDUCTS" and len(vals) == 2:
                deduct, dens = vals
                raw = float(np.interp(sess["mom"], sess["tables"]['Draft'], sess["tables"]['Displacement']))
                net = (raw * (dens / 1.025)) - deduct
                
                res = f"الوزن الصافي: {net:.2f} طن." if sess["lang"] == "/ar" else f"Net Cargo: {net:.2f} Tons."
                send_msg(chat_id, res)
                sess["state"] = "DRAFTS"
        except:
            send_msg(chat_id, "⚠️ خطأ في البيانات!")
            
    # 3. معالجة الملف
    elif "document" in msg:
        sess = sessions.get(user_id)
        if sess:
            file_id = msg["document"]["file_id"]
            path = requests.get(f"https://api.telegram.org/bot{TOKEN}/getFile?file_id={file_id}").json()["result"]["file_path"]
            resp = requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{path}")
            df = pd.read_csv(BytesIO(resp.content))
            df.columns = df.columns.str.strip()
            sess.update({"tables": df, "state": "DRAFTS"})
            send_msg(chat_id, "✅ تم حفظ الجدول. أرسل الآن الغواطس.")
            
    return {"status": "ok"}
