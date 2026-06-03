import math, requests, os, pandas as pd, numpy as np
from fastapi import FastAPI, Request

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
ADMIN_ID = 7101808941
USERS_FILE = "allowed_users.txt"
user_sessions = {}

# --- دوال الإدارة ---
def get_allowed():
    if not os.path.exists(USERS_FILE): return [ADMIN_ID]
    with open(USERS_FILE, "r") as f: return [int(line.strip()) for line in f]

def save_users(users):
    with open(USERS_FILE, "w") as f: f.writelines([f"{u}\n" for u in set(users)])

def send_msg(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup: payload["reply_markup"] = reply_markup
    requests.post(f"{BASE_URL}/sendMessage", json=payload)

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    if "callback_query" in data:
        cb = data["callback_query"]
        chat_id, action = cb["message"]["chat"]["id"], cb["data"]
        if action == "draft": send_msg(chat_id, "يرجى رفع ملف الـ CSV/Excel.")
        elif action == "add": send_msg(chat_id, "أرسل: /add [ID]")
        elif action == "del": send_msg(chat_id, "أرسل: /del [ID]")
        return {"status": "ok"}

    if "message" in data:
        msg = data["message"]
        chat_id, user_id = msg["chat"]["id"], msg["from"]["id"]
        
        # حماية
        if user_id not in get_allowed():
            send_msg(chat_id, f"⛔ غير مصرح. ID الخاص بك: `{user_id}`")
            return {"status": "ok"}
        
        # معالجة الملف
        if "document" in msg:
            file_info = requests.get(f"{BASE_URL}/getFile?file_id={msg['document']['file_id']}").json()
            file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info['result']['file_path']}"
            df = pd.read_csv(file_url) if msg["document"]["file_name"].endswith('.csv') else pd.read_excel(file_url)
            user_sessions[user_id] = {"tables": df.dropna()}
            send_msg(chat_id, "✅ تم الحفظ. أرسل الآن: `[Fwd] [Mid] [Aft] [Breadth] [Angle] [Dir]`")
            return {"status": "ok"}

        # معالجة النصوص
        text = msg.get("text", "")
        if text == "/start":
            menu = {"inline_keyboard": [[{"text": "📊 درافت سيرفي", "callback_data": "draft"}],
                                        [{"text": "➕ إضافة مستخدم", "callback_data": "add"}],
                                        [{"text": "➖ حذف مستخدم", "callback_data": "del"}]]}
            send_msg(chat_id, "أهلاً يا قبطان:", menu)
        elif text.startswith("/add "):
            users = get_allowed(); users.append(int(text.split()[1])); save_users(users); send_msg(chat_id, "✅ تمت الإضافة.")
        elif text.startswith("/del "):
            users = get_allowed(); users.remove(int(text.split()[1])); save_users(users); send_msg(chat_id, "✅ تمت الحذف.")
        
        elif user_id in user_sessions and len(text.split()) == 6:
            f, m, a, b, ang, d = [float(x) for x in text.split()]
            # تصحيح الميل
            corr = (b / 2) * math.tan(math.radians(ang))
            m_sea = m - corr if d == 1 else m + corr
            m_quay = m + corr if d == 1 else m - corr
            
            mid_theory = (f + a) / 2
            diff = m_sea - mid_theory
            status = f"{'Hogging' if diff > 0 else 'Sagging'} ({abs(diff*100):.1f}cm)" if abs(diff) > 0.02 else "Neutral"
            
            mom = (f + a + (6 * ((m_sea + m_quay) / 2))) / 8
            user_sessions[user_id].update({"mom": mom, "status": status})
            send_msg(chat_id, f"🌊 الرصيف: {m_quay:.2f} | البحر: {m_sea:.2f}\n"
                             f"📊 الغاطس النهائي: {mom:.3f}\n"
                             f"🏗 الوضع: {status}\n📥 أرسل: [المخصومات] [الكثافة]")
        
        elif user_id in user_sessions and len(text.split()) == 2:
            ded, dens = [float(x) for x in text.split()]
            df = user_sessions[user_id]["tables"]
            raw = np.interp(user_sessions[user_id]["mom"], df['Draft'], df['Displacement'])
            net = (raw * (dens / 1.025)) - ded
            send_msg(chat_id, f"🏁 **الوزن الصافي: {net:.2f} طن.**\n(الوضع: {user_sessions[user_id]['status']})")
            
    return {"status": "ok"}

