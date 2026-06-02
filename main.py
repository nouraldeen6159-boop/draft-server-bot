import os
import math
import requests
import pandas as pd
import numpy as np
from fastapi import FastAPI, Request

app = FastAPI()

# جلب التوكن السري من إعدادات البيئة (Environment Variables)
TELEGRAM_TOKEN = os.getenv("8884546097:AAFDZnjOh35NQNgTKlQ1FjqxdlmJGl6n8VU")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ذاكرة مؤقتة لتخزين بيانات السفن (للإنتاج التجاري يفضل ربطها بقاعدة بيانات كـ Supabase)
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
    # ترتيب الجدول بناءً على الغاطس لضمان دقة الحساب
    df_sorted = df_tables.sort_values(by='Draft')
    drafts = df_sorted['Draft'].values
    displacements = df_sorted['Displacement'].values
    
    # حساب القيمة الدقيقة المقابلة للكسور
    return float(np.interp(draft, drafts, displacements))

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    
    if "message" not in data:
        return {"status": "ignored"}
        
    message = data["message"]
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    
    # ---------------------------------------------------------------
    # 1. استقبال ملف جدول السفينة (Excel / CSV)
    # ---------------------------------------------------------------
    if "document" in message:
        doc = message["document"]
        if doc["file_name"].endswith(('.xlsx', '.csv')):
            file_id = doc["file_id"]
            
            # جلب رابط تحميل الملف من خوادم تليجرام
            file_info = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
            if "result" in file_info:
                file_path = file_info["result"]["file_path"]
                file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
                
                try:
                    # قراءة الجدول وحفظه في جلسة المستخدم وتحويل الحالة لانتظار الغواطس
                    if doc["file_name"].endswith('.xlsx'):
                        df = pd.read_excel(file_url)
                    else:
                        df = pd.read_csv(file_url)
                        
                    # التحقق من وجود الأعمدة المطلوبة
                    if 'Draft' not in df.columns or 'Displacement' not in df.columns:
                        send_message(chat_id, "❌ خطأ في الملف! تأكد من أن أسماء الأعمدة في الجدول هي تماماً: `Draft` و `Displacement`.")
                        return {"status": "ok"}
                    
                    user_sessions[user_id] = {"tables": df, "state": "AWAITING_DRAFTS"}
                    send_message(chat_id, "✅ **تم حفظ جدول السفينة الهيدروستاتيكي بنجاح!**\n\nالآن، الرجاء إرسال الغواطس الثلاثة لجهة الرصيف، تفاصيل السفينة، والميلان بالشكل التالي:\n\n`[غاطس_المقدمة] [غاطس_المنتصف] [غاطس_المؤخرة] [عرض_السفينة_B] [زاوية_الميلان] [جهة_الميل]`\n\n✍️ **ملاحظة للجهة:** اكتب `1` إذا كان الميلان نحو الرصيف، أو `2` إذا كان الميلان عكس الرصيف (نحو البحر).\n\n💡 *مثال:* `6.20 6.50 6.80 32 1.5 1`")
                except Exception as e:
                    send_message(chat_id, "❌ فشل في قراءة الملف. تأكد من صيغته وسلامة البيانات داخله.")
            return {"status": "ok"}

    # ---------------------------------------------------------------
    # 2. استقبال النصوص والأوامر والمراحل الحسابية
    # ---------------------------------------------------------------
    if "text" in message:
        text = message["text"].strip()
        
        # أمر البداية
        if text == "/start":
            send_message(chat_id, "⚓️ **مرحباً بك في مساعد مسح الغاطس الذكي (Draft Survey Bot).**\n\nخطوتنا الأولى هي رفع ملف الإكسيل أو CSV الخاص بجدول سفينتك المائي.\n\n⚠️ *ملاحظة:* تأكد أن الجدول يحتوي على عمودين رئيسيين بالإنجليزية باسم:\n1. `Draft` (للغاطس)\n2. `Displacement` (للإزاحة)")
            return {"status": "ok"}
            
        session = user_sessions.get(user_id)
        if not session:
            send_message(chat_id, "⚠️ ليس لديك جلسة نشطة. الرجاء إرسال `/start` وإعادة رفع ملف جدول السفينة أولاً.")
            return {"status": "ok"}
            
        # المرحلة الأولى: استقبال الغواطس وحساب الجهة الأخرى والمتوسط الحسابي
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
                direction = int(parts[5]) # 1 = نحو الرصيف، 2 = نحو البحر
                
                # حساب مقدار التعديل بسبب زاوية الميلان (List Correction)
                list_corr = (breadth / 2) * math.tan(math.radians(list_angle))
                
                # تحديد إشارة الحساب لجهة البحر بناءً على اتجاه الميلان
                if direction == 1:
                    # السفينة تميل نحو الرصيف -> جهة البحر مرتفعة (الغاطس أقل)
                    mid_sea = mid_dock - (2 * list_corr)
                    fwd_sea = fwd_dock - (2 * list_corr) # افتراض تأثير الميل الموحد هندسياً
                    aft_sea = aft_dock - (2 * list_corr)
                elif direction == 2:
                    # السفينة تميل نحو البحر -> جهة البحر منخفضة (الغاطس أكبر)
                    mid_sea = mid_dock + (2 * list_corr)
                    fwd_sea = fwd_dock + (2 * list_corr)
                    aft_sea = aft_dock + (2 * list_corr)
                else:
                    raise ValueError
                
                # حساب المتوسطات الحسابية الدقيقة للجهتين (Mean Drafts)
                mean_fwd = (fwd_dock + fwd_sea) / 2
                mean_mid = (mid_dock + mid_sea) / 2
                mean_aft = (aft_dock + aft_sea) / 2
                
                # حساب الغاطس النهائي المعتمد بحرياً معادلة ربع المتوسطات (Mean of Means)
                mean_of_means = (mean_fwd + mean_aft + (6 * mean_mid)) / 8
                
                # حفظ قيمة الـ Mean of Means في الجلسة ونقل الحالة للمرحلة الأخيرة
                session["mean_of_means"] = mean_of_means
                session["state"] = "AWAITING_DEDUCTIONS"
                
                response_text = (
                    f"📊 **نتائج حساب الغواطس لجهة البحر المجهولة:**\n\n"
                    f"🌊 **غواطس جهة البحر (المحسوبة آلياً):**\n"
                    f" ├ المقدمة (Fwd Sea): `{fwd_sea:.2f} m`\n"
                    f" ├ المنتصف (Mid Sea): `{mid_sea:.2f} m`\n"
                    f" └ المؤخرة (Aft Sea): `{aft_sea:.2f} m`\n\n"
                    f"🧮 **الغاطس النهائي (Mean of Means):** `{mean_of_means:.3f} m`\n\n"
                    f"📥 **الخطوة الأخيرة:** الرجاء إرسال إجمالي الأوزان المراد طرحها بالطن (مجموع: المياه العذبة + البالاست + الوقود والزيوت... إلخ).\n"
                    f" *مثال: 1420*"
                )
                send_message(chat_id, response_text)
                
            except ValueError:
                send_message(chat_id, "⚠️ صيغة الإدخال خاطئة! الرجاء إرسال 6 قيم تفصل بينها مسافات تماماً كالمثال:\n`6.20 6.50 6.80 32 1.5 1`")
            return {"status": "ok"}
            
        # المرحلة الثانية: استقبال المخصومات وحساب الوزن الصافي النهائي
        if session["state"] == "AWAITING_DEDUCTIONS":
            try:
                total_deductions = float(text)
                mean_of_means = session["mean_of_means"]
                df_tables = session["tables"]
                
                # استخراج الإزاحة الكلية من جدول الإكسيل عبر دالة الاستيفاء الخطي
                displacement = interpolate_displacement(mean_of_means, df_tables)
                
                # حساب الإزاحة الصافية المصححة (Corrected Displacement)
                corrected_displacement = displacement - total_deductions
                
                final_report = (
                    f"🏁 **تقرير مسح الغاطس النهائي (Draft Survey Report)**\n\n"
                    f"📏 الغاطس الحسابي المعتمد: `{mean_of_means:.3f} m`\n"
                    f"⚓️ الإزاحة الإجمالية (من الجدول): `{displacement:.2f} Tons`\n"
                    f"📉 إجمالي الأوزان المطروحة: `{total_deductions:.2f} Tons`\n"
                    f"──────────────────────\n"
                    f"⚖️ **الوزن الصافي المعدل (Corrected Displacement):**\n"
                    f"`{corrected_displacement:.2f} Tons`\n\n"
                    f"🔄 للقيام بمسح جديد على نفس السفينة، أرسل الغواطس مباشرة. لتغيير السفينة، أرفع ملف إكسيل جديد."
                )
                send_message(chat_id, final_report)
                
                # إعادة الحالة لاستقبال غواطس جديدة لنفس السفينة المرفوعة دون الحاجة لرفع الإكسيل مجدداً
                session["state"] = "AWAITING_DRAFTS"
                
            except Exception as e:
                send_message(chat_id, "⚠️ خطأ! الرجاء إرسال قيمة عددية صحيحة لإجمالي الأوزان المراد طرحها.")
            return {"status": "ok"}

    return {"status": "ok"}
