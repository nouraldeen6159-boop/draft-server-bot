import os
import math
import requests
import pandas as pd
import numpy as np
from fastapi import FastAPI, Request

app = FastAPI()

TELEGRAM_TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

user_sessions = {}

def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:requests.post(url, json=payload)
    except Exception as e: print(f"Error: {e}")

def interpolate_displacement(draft, df_tables):
    df_sorted = df_tables.sort_values(by='Draft')
    return float(np.interp(draft, df_sorted['Draft'].values, df_sorted['Displacement'].values))

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    if "message" not in data: return {"status": "ignored"}
    
    message = data["message"]
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    
    # 1. استقبال الملف
    if "document" in message:
        doc = message["document"]
        if doc["file_name"].endswith(('.xlsx', '.csv')):
            file_id = doc["file_id"]
            file_info = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
            if "result" in file_info:
                file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info['result']['file_path']}"
                try:
                    df = pd.read_excel(file_url) if doc["file_name"].endswith('.xlsx') else pd.read_csv(file_url)
                    if 'Draft' not in df.columns or 'Displacement' not in df.columns:
                        send_message(chat_id, "❌ خطأ في الأعمدة! يجب أن تكون `Draft` و `Displacement`.")
                        return {"status": "ok"}
                    user_sessions[user_id] = {"tables": df, "state": "AWAITING_DRAFTS"}
                    send_message(chat_id, "✅ **تم حفظ جدول السفينة!**\n\nالرجاء إرسال الغواطس والميلان:\n`[غاطس_المقدمة] [غاطس_المنتصف] [غاطس_المؤخرة] [عرض_السفينة_B] [زاوية_الميلان] [جهة_الميل]`\n\n*(جهة الميل: 1 نحو الرصيف، 2 نحو البحر)*")
                except: send_message(chat_id, "❌ فشل في قراءة الملف.")
            return {"status": "ok"}

    # 2. المعالجة الحسابية
    if "text" in message:
        text = message["text"].strip()
        if text == "/start":
            send_message(chat_id, "⚓️ **مرحباً بك في مساعد مسح الغاطس الذكي.**\n\nيرجى رفع ملف جدول السفينة (Draft & Displacement) أولاً.")
            return {"status": "ok"}
            
        session = user_sessions.get(user_id)
        if not session:
            send_message(chat_id, "⚠️ يرجى إرسال `/start` ورفع الملف أولاً.")
            return {"status": "ok"}
            
        if session["state"] == "AWAITING_DRAFTS":
            try:
                parts = text.split()
                if len(parts) != 6: raise ValueError
                
                fwd_dock = float(parts[0])
                mid_dock = float(parts[1])
                aft_dock = float(parts[2])
                breadth = float(parts[3])
                list_angle = float(parts[4])
                direction = int(parts[5])
                
                # حساب تصحيح الميل الجانبي (List Correction) المعتمد هندسياً للمنتصف
                list_corr = (breadth / 2) * math.tan(math.radians(list_angle))
                
                # تصحيح غاطس المنتصف فقط لجهة البحر
                if direction == 1: # مائلة نحو الرصيف -> جهة البحر أعلى
                    mid_sea = mid_dock - list_corr
                elif direction == 2: # مائلة نحو البحر -> جهة البحر أسفل
                    mid_sea = mid_dock + list_corr
                else: raise ValueError
                
                # غواطس المقدمة والمؤخرة المعتمدة هي قراءات الرصيف (أو متوسطة هندسياً)
                mean_fwd = fwd_dock
                mean_aft = aft_dock
                mean_mid = (mid_dock + mid_sea) / 2
                
                # معادلة ربع المتوسطات الدولية (Mean of Means)
                mean_of_means = (mean_fwd + mean_aft + (6 * mean_mid)) / 8
                
                session["mean_of_means"] = mean_of_means
                session["state"] = "AWAITING_DEDUCTIONS_AND_DENSITY"
                
                response_text = (
                    f"📊 **نتائج الحسابات المنطقية المصححة:**\n\n"
                    f"🌊 غاطس المنتصف لجهة البحر (Mid Sea): `{mid_sea:.2f} m`\n"
                    f"🌓 متوسط المنتصف المصحح (Mean Mid): `{mean_mid:.2f} m`\n\n"
                    f"🧮 **الغاطس النهائي المعتمد (Mean of Means):** `{mean_of_means:.3f} m`\n\n"
                    f"📥 **الخطوة التالية:** أرسل إجمالي المخصومات (بالطن) متبوعاً بكثافة المياه المقاسة وبينهما مسافة:\n"
                    f"`[المخصومات] [الكثافة]`\n"
                    f"💡 *مثال:* `1420 1.018`"
                )
                send_message(chat_id, response_text)
            except ValueError:
                send_message(chat_id, "⚠️ صيغة خاطئة! يرجى إدخال القيم الستة بشكل صحيح كالمثال.")
            return {"status": "ok"}
            
        if session["state"] == "AWAITING_DEDUCTIONS_AND_DENSITY":
            try:
                parts = text.split()
                if len(parts) != 2: raise ValueError
                total_deductions = float(parts[0])
                measured_density = float(parts[1])
                
                mean_of_means = session["mean_of_means"]
                df_tables = session["tables"]
                
                raw_displacement = interpolate_displacement(mean_of_means, df_tables)
                corrected_by_density = raw_displacement * (measured_density / 1.025)
                final_net_displacement = corrected_by_density - total_deductions
                
                final_report = (
                    f"🏁 **تقرير مسح الغاطس النهائي الشامل (Draft Survey)**\n\n"
                    f"📏 الغاطس النهائي المصحح: `{mean_of_means:.3f} m`\n"
                    f"⚓️ الإزاحة من الجدول القياسي: `{raw_displacement:.2f} Tons`\n"
                    f"🧪 الكثافة المقاسة: `{measured_density:.3f}`\n"
                    f"⚖️ الإزاحة المصححة بالكثافة: `{corrected_by_density:.2f} Tons`\n"
                    f"📉 الأوزان المطروحة: `{total_deductions:.2f} Tons`\n"
                    f"──────────────────────\n"
                    f"📦 **الوزن الصافي المعدل النهائي (Net Displacement):**\n"
                    f"`{final_net_displacement:.2f} Tons`\n\n"
                    f"🔄 لمسح جديد أرسل الأرقام مباشرة."
                )
                send_message(chat_id, final_report)
                session["state"] = "AWAITING_DRAFTS"
            except:
                send_message(chat_id, "⚠️ يرجى إدخال المخصومات ثم الكثافة بشكل صحيح.")
            return {"status": "ok"}
            
    return {"status": "ok"}

