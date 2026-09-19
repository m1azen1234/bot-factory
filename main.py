import sqlite3
from fastapi import FastAPI, Request
import httpx

app = FastAPI()

# إعدادات المصنع ورابط ngrok
MAIN_BOT_TOKEN = "8560690505:AAH-qPNGKqNWwPW0ARCkTVtveMnO_I2Q-oM"
BASE_URL = "https://letter-crown-uphill.ngrok-free.dev"

# ----------------- تجهيز قاعدة البيانات -----------------
def init_db():
    conn = sqlite3.connect("factory.db")
    cursor = conn.cursor()
    # جدول لتخزين البوتات المنشأة
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bots (
            token TEXT PRIMARY KEY,
            owner_id INTEGER,
            bot_type TEXT,
            custom_welcome TEXT,
            admins TEXT
        )
    """)
    # جدول مؤقت لحفظ اختيار المستخدم قبل إرسال التوكن
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_states (
            user_id INTEGER PRIMARY KEY,
            selected_type TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ----------------- وظائف تيليجرام -----------------
async def send_message(token: str, chat_id: int, text: str, reply_markup: dict = None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)

async def set_webhook(token: str):
    webhook_url = f"{BASE_URL}/webhook/{token}"
    url = f"https://api.telegram.org/bot{token}/setWebhook?url={webhook_url}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        return res.json().get("ok", False)

# ----------------- معالجة رسائل وأزرار بوت المصنع -----------------
async def handle_factory_update(data: dict):
    # التعامل مع ضغط الأزرار (Callback Queries)
    if "callback_query" in data:
        cb = data["callback_query"]
        user_id = cb["from"]["id"]
        chat_id = cb["message"]["chat"]["id"]
        bot_choice = cb["data"]

        types_map = {
            "media": "📥 تنزيل الوسائط والسوشل ميديا",
            "protect": "🛡 حماية المجموعات والردود",
            "shop": "🛍 المتجر الرقمي والخدمات",
            "ai": "🤖 المساعد الذكي والملخصات"
        }
        choice_name = types_map.get(bot_choice, "خدمة غير معروفة")

        # حفظ اختيار المستخدم في قاعدة البيانات
        conn = sqlite3.connect("factory.db")
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO user_states (user_id, selected_type) VALUES (?, ?)", (user_id, bot_choice))
        conn.commit()
        conn.close()

        msg = (
            f"تم اختيار: **{choice_name}**\n\n"
            "الخطوة التالية:\n"
            "1. اذهب إلى @BotFather\n"
            "2. أرسل الأمر `/newbot` واتبع التعليمات لإنشاء اسم ومعرف للبوت.\n"
            "3. انسخ الـ **Token** وأرسله هنا مباشرة في الشات."
        )
        await send_message(MAIN_BOT_TOKEN, chat_id, msg)
        return

    # التعامل مع الرسائل النصية
    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "").strip()

        if text == "/start":
            # عرض قائمة الأزرار الشفافة
            buttons = {
                "inline_keyboard": [
                    [{"text": "📥 بوت تنزيل من السوشل ميديا", "callback_data": "media"}],
                    [{"text": "🛡 بوت حماية المجموعات والترحيب", "callback_data": "protect"}],
                    [{"text": "🛍 بوت المتجر وطلب الخدمات", "callback_data": "shop"}],
                    [{"text": "🤖 بوت الذكاء الاصطناعي والمحتوى", "callback_data": "ai"}]
                ]
            }
            await send_message(
                MAIN_BOT_TOKEN, 
                chat_id, 
                "مرحباً بك في مصنع البوتات 🚀\nاختر نوع البوت الذي تريد إنشاءه من الأزرار بالأسفل:", 
                reply_markup=buttons
            )
            return

        # فحص ما إذا كان النص المرسل عبارة عن توكن
        if ":" in text and len(text) > 30:
            token = text
            conn = sqlite3.connect("factory.db")
            cur = conn.cursor()
            cur.execute("SELECT selected_type FROM user_states WHERE user_id = ?", (chat_id,))
            row = cur.fetchone()
            selected_type = row[0] if row else "media"

            await send_message(MAIN_BOT_TOKEN, chat_id, "⏳ جاري فحص التوكن وربط البوت بالسيرفر...")
            ok = await set_webhook(token)
            if ok:
                cur.execute(
                    "INSERT OR REPLACE INTO bots (token, owner_id, bot_type, custom_welcome, admins) VALUES (?, ?, ?, ?, ?)",
                    (token, chat_id, selected_type, "أهلاً بك في البوت!", str(chat_id))
                )
                conn.commit()
                conn.close()
                await send_message(MAIN_BOT_TOKEN, chat_id, "✅ تم تفعيل وتشغيل بوك الجديد بنجاح!\nادخل عليه الآن وأرسل /start لتجربته والتحكم فيه.")
            else:
                conn.close()
                await send_message(MAIN_BOT_TOKEN, chat_id, "❌ فشل الربط! تأكد أن التوكن صحيح وغير مستخدم في مكان آخر.")

# ----------------- معالجة البوتات الفرعية المُنشأة -----------------
async def handle_sub_bot_update(token: str, data: dict):
    if "message" not in data:
        return
    msg = data["message"]
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    text = msg.get("text", "").strip()

    conn = sqlite3.connect("factory.db")
    cur = conn.cursor()
    cur.execute("SELECT owner_id, bot_type, custom_welcome, admins FROM bots WHERE token = ?", (token,))
    bot_info = cur.fetchone()
    conn.close()

    if not bot_info:
        return

    owner_id, bot_type, welcome_msg, admins_str = bot_info
    admins = [int(a) for a in admins_str.split(",") if a]

    # لوحة تحكم المالك والمشرفين
    if text == "/settings" and user_id in admins:
        settings_markup = {
            "inline_keyboard": [
                [{"text": "✏️ تعديل رسالة الترحيب", "callback_data": "edit_welcome"}],
                [{"text": "👥 إدارة المشرفين والصلاحيات", "callback_data": "manage_admins"}],
                [{"text": "📊 إحصائيات البوت", "callback_data": "bot_stats"}]
            ]
        }
        await send_message(token, chat_id, "⚙️ مرحباً بك في لوحة تحكم البوت:\nيمكنك تعديل إعداداتك من هنا:", reply_markup=settings_markup)
        return

    # الرد على أوامر البوت العادية بحسب نوعه
    if text == "/start":
        await send_message(token, chat_id, f"{welcome_msg}\n\nنوع الخدمة: {bot_type}\n(إذا كنت مالك البوت أرسل /settings لإدارته)")
    else:
        # استجابة مبدئية بحسب اختصاص البوت
        if bot_type == "media":
            await send_message(token, chat_id, "📥 أرسل رابط الفيديو (تيك توك، إنستغرام، يوتيوب) وسأقوم بتحميله لك فوراً.")
        else:
            await send_message(token, chat_id, f"تم استلام رسالتك: {text}")

# ----------------- مسار الاستقبال (FastAPI) -----------------
@app.post("/webhook/{token}")
async def receive_webhook(token: str, request: Request):
    data = await request.json()
    if token == MAIN_BOT_TOKEN:
        await handle_factory_update(data)
    else:
        await handle_sub_bot_update(token, data)
    return {"status": "ok"}
