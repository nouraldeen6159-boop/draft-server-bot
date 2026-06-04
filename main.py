import requests, math, re, pandas as pd, numpy as np
from fastapi import FastAPI, Request

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
ADMIN_ID = 8684618304
user_sessions = {}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    if "message" not in data: return {"status": "ok"}
    
    msg = data["message"]
    user_id = msg["from"]["id"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    # 1. أوامر البداية
    if text == "/start":
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id, 
            "text": "⚓ أهلاً قبطان، نظام Chief Mate Pro جاهز.\nارفع ملف الجداول (CSV/Excel) للبدء."
        })
    
    # 2. استقبال الملفات
    elif "document" in msg:
        doc = msg["document"]
        file_info = requests.get(f"{BASE_URL}/getFile?file_id={doc['file_id']}").json()
        file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info['result']['file_path']}"
        try:
            df = pd.read_csv(file_url) if doc["file_name"].endswith('.csv') else pd.read_excel(file_url)
            user_sessions[user_id] = {"tables": df.dropna()}
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "✅ تم تحميل الجدول.\nأرسل الآن: `[Fwd] [Mid] [Aft] [Breadth] [Angle] [Dir]`"})
        except Exception as e:
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"❌ خطأ في القراءة: {str(e)}"})

    # 3. الحسابات الرياضية
    elif user_id in user_sessions and len(text.split()) == 6:
        try:
            f, m, a, b, ang, d = [float(x) for x in text.split()]
            corr = (b / 2) * math.tan(math.radians(ang))
            m_sea = m - corr if d == 1 else m + corr
            m_quay = m + corr if d == 1 else m - corr
            mom = (f + a + (6 * ((m_sea + m_quay) / 2))) / 8
            user_sessions[user_id].update({"mom": mom})
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"🌊 الرصيف: {m_quay:.2f} | البحر: {m_sea:.2f}\n📊 الغاطس النهائي: {mom:.3f}\n📥 أرسل الآن: [المخصومات] [الكثافة]"})
        except:
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "❌ تأكد من إدخال 6 أرقام مفصولة بمسافات."})

    elif user_id in user_sessions and len(text.split()) == 2:
        try:
            ded, dens = [float(x) for x in text.split()]
            df = user_sessions[user_id]["tables"]
            raw = np.interp(user_sessions[user_id]["mom"], df['Draft'], df['Displacement'])
            net = (raw * (dens / 1.025)) - ded
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"🏁 الوزن الصافي النهائي: {net:.2f} طن."})
        except:
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "❌ تأكد من إدخال المخصومات والكثافة."})
            
    return {"status": "ok"}
