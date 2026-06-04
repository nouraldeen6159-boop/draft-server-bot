import requests, os, sqlite3, pandas as pd, numpy as np, math, re
from fastapi import FastAPI, Request

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
ADMIN_ID = 8684618304
user_sessions = {}

# --- إعداد قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect("maritime_data.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, user_id INTEGER, result REAL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()

init_db()

def is_allowed(user_id):
    if user_id == ADMIN_ID: return True
    conn = sqlite3.connect("maritime_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    
    if "message" in data:
        msg = data["message"]
        user_id = msg["from"]["id"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")

        # 1. الحماية
        if not is_allowed(user_id):
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "⛔ غير مصرح لك."})
            return {"status": "ok"}

        # 2. رفع الملفات
        if "document" in msg:
            doc = msg["document"]
            file_info = requests.get(f"{BASE_URL}/getFile?file_id={doc['file_id']}").json()
            file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info['result']['file_path']}"
            try:
                df = pd.read_csv(file_url) if doc["file_name"].endswith('.csv') else pd.read_excel(file_url)
                user_sessions[user_id] = {"tables": df.dropna()}
                requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "✅ تم تحميل الجدول. أرسل الآن القيم: `[Fwd] [Mid] [Aft] [Breadth] [Angle] [Dir]`"})
            except Exception as e:
                requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"❌ خطأ: {str(e)}"})

        # 3. الأوامر والحسابات
        elif text == "/start":
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "⚓ أهلاً يا قبطان، نظام Chief Mate Pro جاهز. ارفع ملف الجداول للبدء."})
        
        elif text.startswith("/add ") and user_id == ADMIN_ID:
            new_id = int(text.split()[1])
            conn = sqlite3.connect("maritime_data.db")
            conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (new_id,))
            conn.commit(); conn.close()
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"✅ تمت إضافة المستخدم {new_id} بنجاح."})

        # الحسابات الرياضية
        elif user_id in user_sessions and len(text.split()) == 6:
            f, m, a, b, ang, d = [float(x) for x in text.split()]
            corr = (b / 2) * math.tan(math.radians(ang))
            m_sea = m - corr if d == 1 else m + corr
            m_quay = m + corr if d == 1 else m - corr
            mom = (f + a + (6 * ((m_sea + m_quay) / 2))) / 8
            user_sessions[user_id].update({"mom": mom})
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"🌊 الرصيف: {m_quay:.2f} | البحر: {m_sea:.2f}\n📊 الغاطس النهائي: {mom:.3f}\n📥 أرسل الآن: [المخصومات] [الكثافة]"})
            
        elif user_id in user_sessions and len(text.split()) == 2:
            ded, dens = [float(x) for x in text.split()]
            df = user_sessions[user_id]["tables"]
            raw = np.interp(user_sessions[user_id]["mom"], df['Draft'], df['Displacement'])
            net = (raw * (dens / 1.025)) - ded
            
            # حفظ العملية في قاعدة البيانات
            conn = sqlite3.connect("maritime_data.db")
            conn.execute("INSERT INTO logs (user_id, result) VALUES (?, ?)", (user_id, float(net)))
            conn.commit(); conn.close()
            
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"🏁 الوزن الصافي النهائي: {net:.2f} طن.\n✅ تم حفظ العملية في السجل."})

    return {"status": "ok"}
