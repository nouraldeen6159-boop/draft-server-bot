import requests, math, pandas as pd, numpy as np, matplotlib.pyplot as plt, io
from fastapi import FastAPI, Request

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
ADMIN_ID = 8684618304
# نستخدم قاموساً لحفظ جلسات المستخدمين (بدون ملفات لتجنب مشاكل Vercel)
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
        user_sessions[user_id] = {"tables": None, "history": [], "mom": 0}
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id, 
            "text": "⚓ أهلاً قبطان.\n1. ارفع ملف الجداول (CSV/Excel) يحتوي على Draft و Displacement.\n2. أرسل البيانات: `[Fwd] [Mid] [Aft] [Breadth] [Angle] [Dir]`\n3. أرسل `/graph` لرؤية الرسم البياني."
        })

    # 2. الرسم البياني
    elif text == "/graph":
        if user_id in user_sessions and len(user_sessions[user_id]["history"]) > 0:
            plt.figure(figsize=(8, 4))
            plt.plot(user_sessions[user_id]["history"], marker='o', linestyle='-', color='b')
            plt.title("سجل الوزن الصافي خلال الرحلة")
            plt.ylabel("الوزن (طن)")
            buf = io.BytesIO()
            plt.savefig(buf, format='png'); buf.seek(0)
            requests.post(f"{BASE_URL}/sendPhoto", files={"photo": buf}, data={"chat_id": chat_id})
        else:
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "❌ لا توجد بيانات كافية للرسم."})

    # 3. استقبال الملفات
    elif "document" in msg:
        doc = msg["document"]
        file_info = requests.get(f"{BASE_URL}/getFile?file_id={doc['file_id']}").json()
        file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info['result']['file_path']}"
        try:
            df = pd.read_csv(file_url) if doc["file_name"].endswith('.csv') else pd.read_excel(file_url)
            user_sessions[user_id]["tables"] = df.dropna()
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "✅ تم تحميل الجدول بنجاح. ابدأ الحسابات."})
        except Exception as e:
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"❌ خطأ في قراءة الجدول: {str(e)}"})

    # 4. الحسابات الرياضية (6 أرقام للغاطس والميل)
    elif user_id in user_sessions and len(text.split()) == 6:
        try:
            f, m, a, b, ang, d = [float(x) for x in text.split()]
            corr = (b / 2) * math.tan(math.radians(ang))
            m_sea = m - corr if d == 1 else m + corr
            m_quay = m + corr if d == 1 else m - corr
            mom = (f + a + (6 * ((m_sea + m_quay) / 2))) / 8
            user_sessions[user_id]["mom"] = mom
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"📊 الغاطس النهائي: {mom:.3f}\n📥 أرسل الآن: [المخصومات] [الكثافة]"})
        except:
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "❌ تأكد من التنسيق: 6 أرقام مفصولة بمسافات."})

    # 5. الحساب النهائي (خصم المخصومات والكثافة)
    elif user_id in user_sessions and len(text.split()) == 2:
        try:
            ded, dens = [float(x) for x in text.split()]
            df = user_sessions[user_id]["tables"]
            raw = np.interp(user_sessions[user_id]["mom"], df['Draft'], df['Displacement'])
            net = (raw * (dens / 1.025)) - ded
            user_sessions[user_id]["history"].append(net)
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"🏁 الوزن الصافي النهائي: {net:.2f} طن.\n✅ تم حفظ العملية في الرسم البياني."})
        except:
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "❌ خطأ في حساب النتائج."})
            
    return {"status": "ok"}

