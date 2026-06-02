import os
import math
import requests
import pandas as pd
import numpy as np
from fastapi import FastAPI, Request

app = FastAPI()

# توكن البوت الخاص بك
TELEGRAM_TOKEN = "8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU"
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ذاكرة مؤفتة لتخزين جلسات المستخدمين
user_sessions = {}

def send_message(chat_id, text):
    """دالة مساعدة لإرسال الرسائل عبر تليجرام"""
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending message: {e}")

def interpolate_displacement(draft, df_tables):
    """البحث في جدول السفينة وجلب الإزاحة عبر الاستيفاء الخطي (Linear Interpolation)"""
    df_sorted = df_tables.sort_values(by='Draft')
    drafts = df_sorted['Draft'].values
    displacements = df_sorted['Displacement'].values
    return float(np.interp(draft, drafts, displacements))

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    
    if "message" not in data:
        return {"status": "ignored"}
        
    message = data["message"]
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    
    # 1. استقبال ملف جدول السفينة (Excel / CSV)
    if "document" in message:
        doc = message["document"]
        if doc["file_name"].endswith(('.xlsx', '.csv')):
            file_id = doc["file_id"]
            
            file_info = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
            if "result" in file_info:
                file_path = file_info["result"]["file_path"]
                file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
                
                try:
                    if doc["file_name"].endswith('.xlsx'):
                        df = pd.read_excel(file_url)
                    else:
                        df = pd.read_csv(file_url)
                        
                    if 'Draft' not in df.columns or 'Displacement' not in df.columns:
                        send_message(chat_id, "❌ خطأ في الملف! تأكد من أن أسماء الأعمدة في الجدول هي تماماً: `Draft` و `Displacement`.")
                        return {"status": "ok"}
                    
                    user_sessions[user_id] = {"tables": df, "state": "AWAITING_DRAFTS"}
                    send_message(chat_id, "✅ **تم حفظ جدول السفينة الهيدروستاتيكي بنجاح!**\n\nالآن، الرجاء إرسال الغواطس الثلاثة لجهة الرصيف، تفاصيل السفينة، والميلان بالشكل التالي:\n\n`[غاطس_المقدمة] [غاطس_المنتصف] [غاطس_المؤخرة] [عرض_السفينة_B] [زاوية_الميلان] [جهة_الميل]`\n\n✍️ **ملاحظة للجهة:** اكتب `1` إذا كان الميلان نحو الرصيف، أو `2` إذا كان الميلان عكس الرصيف (نحو البحر).\n\n💡 *مثال:* `6.20 6.50 6.80 32 1.5 1`")
                except Exception as e:
                    send_message(chat_id, "❌ فشل في قراءة الملف. تأكد من صيغته وسلامة البيانات داخله.")
            return {"status": "ok"}

    # 2. استقبال النصوص والأوامر والمراحل الحسابية
    if "text" in message:
        text = message["text"].strip()
        
        if text == "/start":
            send_message(chat_id, "⚓️ **مرحباً بك في مساعد مسح الغاطس الذكي (Draft Survey Bot).**\n\nخطوتنا الأولى هي رفع ملف الإكسيل أو CSV الخاص بجدول سفينتك المائي.\n\n⚠️ *ملاحظة:* تأكد أن الجدول يحتوي على عمودين رئيسيين بالإنجليزية باسم:\n1. `Draft` (للغاطس)\n2. `Displacement` (للإزاحة)")
            return {"status": "ok"}
            
        session = user_sessions.get(user_id)
        if not session:
            send_message(chat_id, "⚠️ ليس لديك جلسة نشطة. الرجاء إرسال `/start` وإعادة رفع ملف جدول السفينة أولاً.")
            return {"status": "ok"}
            
        # المرحلة الأولى: حساب الغواطس والوصول للـ Mean of Means
        if session["state"] == "AWAITING_DRAFTS":
            try:
                parts = text.split()
                if len(parts) != 6:
                    raise ValueError
                    
                fwd_dock = float(parts[0])
                mid_dock = float(parts[1])
                aft_dock = float(parts[2])
                breadth = float(parts[3])
                list_angle = float(parts[4])
                direction = int(parts[5])
                
                list_corr = (breadth / 2) * math.tan(math.radians(list_angle))
                
                if direction == 1:
                    mid_sea = mid_dock - (2 * list_corr)
                    fwd_sea = fwd_dock - (2 * list_corr)
                    aft_sea = aft_dock - (2 * list_corr)
                elif direction == 2:
                    mid_sea = mid_dock + (2 * list_corr)
                    fwd_sea = fwd_dock + (2 * list_corr)
                    aft_sea = aft_dock + (2 * list_corr)
                else:
                    raise ValueError
                
                mean_fwd = (fwd_dock + fwd_sea) / 2
                mean_mid = (mid_dock + mid_sea) / 2
                mean_aft = (aft_dock + aft_sea) / 2
                
                mean_of_means = (mean_fwd + mean_aft + (6 * mean_mid)) / 8
                
                session["mean_of_means"] = mean_of_means
                session["state"] = "AWAITING_DEDUCTIONS_AND_DENSITY"
                
                response_text = (
                    f"📊 **نتائج حساب الغواطس لجهة البحر المجهولة:**\n\n"
                    f"🌊 **غواطس جهة البحر (المحسوبة آلياً):**\n"
                    f" ├ المقدمة (Fwd Sea): `{fwd_sea:.2f} m`\n"
                    f" ├ المنتصف (Mid Sea): `{mid_sea:.2f} m`\n"
                    f" └ المؤخرة (Aft Sea): `{aft_sea:.2f} m`\n\n"
                    f"🧮 **الغاطس النهائي (Mean of Means):** `{mean_of_means:.3f} m`\n\n"
                    f"📥 **الخطوة التالية (الأوزان والكثافة):** الرجاء إرسال إجمالي المخصومات (بالطن) متبوعاً بكثافة المياه المقاسة يفصلهما مسافة كالتالي:\n"
                    f"`[إجمالي_المخصومات] [كثافة_المياه]`\n\n"
                    f"💡 *مثال:* `1420 1.018`"
                )
                send_message(chat_id, response_text)
                
            except ValueError:
                send_message(chat_id, "⚠️ صيغة الإدخال خاطئة! الرجاء إرسال 6 قيم تفصل بينها مسافات تماماً كالمثال:\n`6.20 6.50 6.80 32 1.5 1`")
            return {"status": "ok"}
            
        # المرحلة الثانية المتطورة: استقبال المخصومات والكثافة وحساب تصحيح الكثافة والوزن الصافي
        if session["state"] == "AWAITING_DEDUCTIONS_AND_DENSITY":
            try:
                parts = text.split()
                if len(parts) != 2:
                    raise ValueError
                    
                total_deductions = float(parts[0])
                measured_density = float(parts[1])
                
                mean_of_means = session["mean_of_means"]
                df_tables = session["tables"]
                
                # 1. استخراج الإزاحة المبدئية من الجدول
                raw_displacement = interpolate_displacement(mean_of_means, df_tables)
                
                # 2. تطبيق معادلة تصحيح الكثافة المعتمدة بحرياً (المقارنة مع الكثافة القياسية 1.025)
                corrected_by_density = raw_displacement * (measured_density / 1.025)
                
                # 3. حساب الإزاحة الصافية النهائية بعد طرح المخصومات
                final_net_displacement = corrected_by_density - total_deductions
                
                final_report = (
                    f"🏁 **تقرير مسح الغاطس النهائي الشامل (Draft Survey Report)**\n\n"
                    f"📏 الغاطس الحسابي المعتمد: `{mean_of_means:.3f} m`\n"
                    f"⚓️ الإزاحة الكلية (من الجدول الافتراضي): `{raw_displacement:.2f} Tons`\n"
                    f"🧪 كثافة المياه المقاسة: `{measured_density:.3f} mt/m³`\n"
                    f"⚖️ **الإزاحة المصححة بناءً على الكثافة:** `{corrected_by_density:.2f} Tons`\n"
                    f"📉 إجمالي الأوزان المطروحة (Deductions): `{total_deductions:.2f} Tons`\n"
                    f"──────────────────────\n"
                    f"📦 **الوزن الصافي المعدل النهائي (Net Displacement):**\n"
                    f"`{final_net_displacement:.2f} Tons`\n\n"
                    f"🔄 للقيام بمسح جديد على نفس السفينة، أرسل الغواطس مباشرة. لتغيير السفينة، ارفع ملف إكسيل جديد."
                )
                send_message(chat_id, final_report)
                
                # العودة للمرحلة الأولى لاستقبال غواطس جديدة لنفس السفينة عند الحاجة
                session["state"] = "AWAITING_DRAFTS"
                
            except Exception as e:
                send_message(chat_id, "⚠️ صيغة الإدخال خاطئة! الرجاء إرسال قيمتين (المخصومات ثم الكثافة) تفصل بينهما مسافة كالمثال:\n`1420 1.018`")
            return {"status": "ok"}

    return {"status": "ok"}

