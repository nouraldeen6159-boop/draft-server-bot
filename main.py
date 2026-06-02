import math
import requests
import pandas as pd
import numpy as np
from fastapi import FastAPI, Request

app = FastAPI()

TELEGRAM_TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

user_sessions = {}

# قاموس الرسائل لدعم اللغتين
LANGUAGES = {
    "AR": {
        "welcome": "أهلاً بك في مساعد مسح الغاطس الذكي. اختر لغتك:",
        "lang_set": "تم اختيار العربية. يرجى رفع ملف جدول السفينة (CSV/Excel).",
        "file_success": "✅ تم حفظ الجدول! الآن أرسل الغواطس: [مقدمة] [منتصف] [مؤخرة] [عرض] [زاوية] [اتجاه]\n(اتجاه الميل: 1 للرصيف، 2 للبحر)",
        "result_drafts": "📊 نتائج الحسابات:\nغاطس المنتصف لجهة البحر: {mid_sea} م\nالغاطس النهائي (Mean of Means): {mean_of_means} م\n\nالآن أرسل: [إجمالي المخصومات] [الكثافة]",
        "final_report": "🏁 تقرير مسح الغاطس النهائي:\nالغاطس النهائي: {mom} م\nالإزاحة الكلية: {disp} طن\nالكثافة: {dens}\nالوزن الصافي النهائي: {net} طن",
        "error": "⚠️ خطأ في الإدخال، تأكد من الصيغة."
    },
    "EN": {
        "welcome": "Welcome to Draft Survey Bot. Choose your language:",
        "lang_set": "English selected. Please upload the Ship Table (CSV/Excel).",
        "file_success": "✅ Table saved! Now send drafts: [Fwd] [Mid] [Aft] [Breadth] [Angle] [Direction]\n(Direction: 1 for Dock, 2 for Sea)",
        "result_drafts": "📊 Calculation Results:\nMid Sea Draft: {mid_sea} m\nMean of Means: {mean_of_means} m\n\nNow send: [Total Deductions] [Density]",
        "final_report": "🏁 Final Draft Survey Report:\nMean of Means: {mom} m\nTotal Displacement: {disp} Tons\nDensity: {dens}\nNet Displacement: {net} Tons",
        "error": "⚠️ Input error, please check format."
    }
}

def send_message(chat_id, text, reply_markup=None):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "reply_markup": reply_markup}
    requests.post(url, json=payload)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    if "message" not in data and "callback_query" not in data: return {"status": "ok"}
    
    # معالجة الأزرار (اللغة)
    if "callback_query" in data:
        cb = data["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        user_id = cb["from"]["id"]
        lang = "AR" if cb["data"] == "LANG_AR" else "EN"
        user_sessions[user_id] = {"language": lang, "state": "AWAITING_FILE"}
        send_message(chat_id, LANGUAGES[lang]["lang_set"])
        return {"status": "ok"}

    # معالجة الرسائل النصية
    msg = data["message"]
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    
    if "text" in msg and msg["text"] == "/start":
        keyboard = {"inline_keyboard": [[{"text": "العربية 🇸🇦", "callback_data": "LANG_AR"}, {"text": "English 🇬🇧", "callback_data": "LANG_EN"}]]}
        send_message(chat_id, "مرحباً/Welcome. اختر لغتك:", keyboard)
        return {"status": "ok"}
    
    session = user_sessions.get(user_id)
    if not session: return {"status": "ok"}
    
    lang = session["language"]
    
    # معالجة الملفات
    if "document" in msg:
        file_id = msg["document"]["file_id"]
        file_path = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
        session["tables"] = pd.read_csv(file_url) if msg["document"]["file_name"].endswith('.csv') else pd.read_excel(file_url)
        session["state"] = "AWAITING_DRAFTS"
        send_message(chat_id, LANGUAGES[lang]["file_success"])
        
    # معالجة الحسابات
    elif "text" in msg:
        txt = msg["text"].split()
        if session["state"] == "AWAITING_DRAFTS":
            fwd, mid, aft, b, angle, direct = map(float, txt)
            list_corr = (b / 2) * math.tan(math.radians(angle))
            mid_sea = mid - list_corr if direct == 1 else mid + list_corr
            mom = (fwd + aft + (6 * (mid + mid_sea)/2)) / 8
            session.update({"mom": mom, "state": "AWAITING_DEDUCTIONS"})
            send_message(chat_id, LANGUAGES[lang]["result_drafts"].format(mid_sea=f"{mid_sea:.2f}", mean_of_means=f"{mom:.3f}"))
        
        elif session["state"] == "AWAITING_DEDUCTIONS":
            deduct, dens = map(float, txt)
            raw_disp = float(np.interp(session["mom"], session["tables"]['Draft'], session["tables"]['Displacement']))
            net = (raw_disp * (dens / 1.025)) - deduct
            send_message(chat_id, LANGUAGES[lang]["final_report"].format(mom=f"{session['mom']:.3f}", disp=f"{raw_disp:.2f}", dens=dens, net=f"{net:.2f}"))
            session["state"] = "AWAITING_DRAFTS"
            
    return {"status": "ok"}

