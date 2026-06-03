import requests, os, pandas as pd, numpy as np, math, re
from fastapi import FastAPI, Request

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
ADMIN_ID = 8684618304
USERS_FILE = "allowed_users.txt"
user_sessions = {}

def get_allowed():
    allowed = {ADMIN_ID}
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            for line in f:
                if line.strip().isdigit(): allowed.add(int(line.strip()))
    return list(allowed)

def save_users(users_list):
    with open(USERS_FILE, "w") as f:
        for u in set(users_list): f.write(f"{u}\n")

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    
    # تحديد الهوية
    if "callback_query" in data:
        user_id = data["callback_query"]["from"]["id"]
        chat_id = data["callback_query"]["message"]["chat"]["id"]
    elif "message" in data:
        user_id = data["message"]["from"]["id"]
        chat_id = data["message"]["chat"]["id"]
    else: return {"status": "ok"}

    if user_id not in get_allowed():
        requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "⛔ غير مصرح لك."})
        return {"status": "ok"}

    # 1. معالجة الملفات
    if "message" in data and "document" in data["message"]:
        doc = data["message"]["document"]
        file_info = requests.get(f"{BASE_URL}/getFile?file_id={doc['file_id']}").json()
        file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info['result']['file_path']}"
        try:
            df = pd.read_csv(file_url) if doc["file_name"].endswith('.csv') else pd.read_excel(file_url)
            user_sessions[user_id] = {"tables": df.dropna()}
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "✅ تم تحميل الجدول. أرسل الآن: `[Fwd] [Mid] [Aft] [Breadth] [Angle] [Dir]`"})
        except Exception as e:
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"❌ خطأ: {str(e)}"})
        return {"status": "ok"}

    # 2. الأزرار
    if "callback_query" in data:
        cb = data["callback_query"]
        action = cb["data"]
        if action == "draft": text = "قم برفع ملف الـ CSV/Excel."
        elif action == "list_users": text = f"📋 المصرح لهم:\n`{get_allowed()}`"
        elif action == "add": text = "أرسل: /add [ID]"
        elif action == "del": text = "أرسل: /del [ID]"
        requests.post(f"{BASE_URL}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
        requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
        return {"status": "ok"}

    # 3. الرسائل والحسابات
    if "message" in data and "text" in data["message"]:
        text = data["message"]["text"]
        if text == "/start":
            is_admin = (user_id == ADMIN_ID)
            menu = {"inline_keyboard": [[{"text": "📊 درافت سيرفي", "callback_data": "draft"}]] + 
                    ([[{"text": "📋 القائمة", "callback_data": "list_users"}], [{"text": "➕ إضافة", "callback_data": "add"}, {"text": "➖ حذف", "callback_data": "del"}]] if is_admin else [])}
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": "أهلاً قبطان، اختر العملية:", "reply_markup": menu})
        
        elif re.match(r'^/add\s*\d+', text) and user_id == ADMIN_ID:
            new_id = int(re.findall(r'\d+', text)[0])
            users = get_allowed(); users.append(new_id); save_users(users)
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"✅ تمت إضافة {new_id}"})
            
        elif user_id in user_sessions and len(text.split()) == 6:
            f, m, a, b, ang, d = [float(x) for x in text.split()]
            corr = (b / 2) * math.tan(math.radians(ang))
            m_sea = m - corr if d == 1 else m + corr
            m_quay = m + corr if d == 1 else m - corr
            mom = (f + a + (6 * ((m_sea + m_quay) / 2))) / 8
            user_sessions[user_id].update({"mom": mom})
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"🌊 الرصيف: {m_quay:.2f} | البحر: {m_sea:.2f}\n📊 الغاطس النهائي: {mom:.3f}\n📥 أرسل: [المخصومات] [الكثافة]"})
            
        elif user_id in user_sessions and len(text.split()) == 2:
            ded, dens = [float(x) for x in text.split()]
            df = user_sessions[user_id]["tables"]
            raw = np.interp(user_sessions[user_id]["mom"], df['Draft'], df['Displacement'])
            net = (raw * (dens / 1.025)) - ded
            requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": f"🏁 الوزن الصافي: {net:.2f} طن."})
            
    return {"status": "ok"}

