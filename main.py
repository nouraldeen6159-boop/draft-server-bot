import math, requests, pandas as pd, numpy as np
from io import BytesIO
from fastapi import FastAPI, Request

app = FastAPI()
TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
# تخزين مؤقت للجلسات والبيانات
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
    
    # معالجة النصوص
    if "text" in msg:
        txt = msg["text"].strip()
        if txt == "/start":
            sessions[user_id] = {"state": "LANG"}
            send_msg(chat_id, "أهلاً بك. أرسل /ar للعربية أو /en للإنجليزية")
        elif txt in ["/ar", "/en"]:
            sessions[user_id] = {"lang": txt, "state": "FILE"}
            send_msg(chat_id, "الآن، ارفع ملف CSV الخاص بالسفينة (Draft, Displacement)")
        elif "tables" in sessions.get(user_id, {}) and sessions[user_id]["state"] == "DRAFTS":
            try:
                # معالجة الغواطس: [مقدمة] [منتصف] [مؤخرة] [عرض] [زاوية] [اتجاه]
                vals = [float(x.replace(',', '.')) for x in txt.split()]
                f, m, a, b, ang, direct = vals
                corr = (b / 2) * math.tan(math.radians(ang))
                m_sea = m - corr if direct == 1 else m + corr
                mom = (f + a + (6 * (m + m_sea)/2)) / 8
                sessions[user_id].update({"mom": mom, "state": "DEDUCTS"})
                send_msg(chat_id, f"الغاطس المكافئ: {mom:.3f}\nالآن أرسل: [المخصومات] [الكثافة]")
            except: send_msg(chat_id, "خطأ في البيانات. أرسل الأرقام الستة مفصولة بمسافات.")
        elif sessions.get(user_id, {}).get("state") == "DEDUCTS":
            try:
                deduct, dens = [float(x.replace(',', '.')) for x in txt.split()]
                df = sessions[user_id]["tables"]
                raw = float(np.interp(sessions[user_id]["mom"], df['Draft'], df['Displacement']))
                net = (raw * (dens / 1.025)) - deduct
                send_msg(chat_id, f"الوزن الصافي للبضاعة: {net:.2f} طن.")
                sessions[user_id]["state"] = "DRAFTS"
            except: send_msg(chat_id, "خطأ في الصيغة. أرسل رقمين فقط.")
            
    # معالجة الملفات
    elif "document" in msg:
        if user_id in sessions:
            file_id = msg["document"]["file_id"]
            path = requests.get(f"https://api.telegram.org/bot{TOKEN}/getFile?file_id={file_id}").json()["result"]["file_path"]
            resp = requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{path}")
            sessions[user_id]["tables"] = pd.read_csv(BytesIO(resp.content))
            sessions[user_id]["state"] = "DRAFTS"
            send_msg(chat_id, "✅ تم حفظ الجدول! أرسل الآن الغواطس.")
            
    return {"status": "ok"}

