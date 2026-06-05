import requests, math, pandas as pd, numpy as np, matplotlib.pyplot as plt, io
from fastapi import FastAPI, Request

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
user_sessions = {}

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        if "message" not in data: return {"status": "ok"}
        
        msg = data["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")

        # معالجة بدء البوت
        if text == "/start":
            user_sessions[user_id] = {"tables": None, "history": []}
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "⚓ تم تفعيل النظام. ارفع ملف الجداول (CSV أو Excel) للبدء."})
            
        # معالجة الملفات
        elif "document" in msg:
            doc = msg["document"]
            file_info = requests.get(f"{BASE_URL}/getFile?file_id={doc['file_id']}").json()
            file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info['result']['file_path']}"
            df = pd.read_csv(file_url) if doc["file_name"].endswith('.csv') else pd.read_excel(file_url)
            user_sessions[user_id] = {"tables": df.dropna(), "history": []}
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "✅ تم تحميل الجدول بنجاح. أرسل القيم الآن: [Fwd] [Mid] [Aft] [Breadth] [Angle] [Dir]"})

        # معالجة الأرقام
        elif user_id in user_sessions and len(text.split()) == 6:
            vals = [float(x) for x in text.split()]
            # منطق الحساب
            corr = (vals[3] / 2) * math.tan(math.radians(vals[4]))
            mom = (vals[0] + vals[2] + (6 * (vals[1] - corr if vals[5] == 1 else vals[1] + corr))) / 8
            user_sessions[user_id]["last_mom"] = mom
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"📊 الغاطس النهائي: {mom:.3f}\nأرسل الآن: [المخصومات] [الكثافة]"})

        # الحساب النهائي
        elif user_id in user_sessions and len(text.split()) == 2:
            ded, dens = [float(x) for x in text.split()]
            df = user_sessions[user_id]["tables"]
            raw = np.interp(user_sessions[user_id]["last_mom"], df['Draft'], df['Displacement'])
            net = (raw * (dens / 1.025)) - ded
            user_sessions[user_id]["history"].append(net)
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"🏁 الوزن الصافي: {net:.2f} طن."})

    except Exception as e:
        requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"❌ حدث خطأ تقني: {str(e)}"})
            
    return {"status": "ok"}
