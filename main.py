import httpx
from fastapi import FastAPI, Request

app = FastAPI()

# رابط السيرفر السحابي الخاص بك على Render
BASE_URL = "https://bot-factory-wsro.onrender.com"
MAIN_BOT_TOKEN = "8560690505:AAH-qPNGKqNWwPW0ARCkTVtveMnO_I2Q-oM"

# قاعدة بيانات تخزين مؤقتة للبوتات وإعداداتها
# الهيكل: {bot_token: {"owner_id": 123, "admins": [], "welcome_msg": "...", "modules": {...}}}
bots_db = {
    MAIN_BOT_TOKEN: {
        "owner_id": None,
        "admins": [],
        "welcome_msg": "أهلاً بك في بوت المصنع الرئيسي! أنشئ وأدر بوتاتك بكل سهولة.",
        "modules": {"media": True, "groups": True, "business": True, "ai": True},
    }
}

async def send_telegram(token: str, method: str, data: dict):
    """إرسال طلب مباشر لتيليجرام API"""
    url = f"https://api.telegram.org/bot{token}/{method}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=data)
            return response.json()
        except Exception as e:
            print(f"Error calling Telegram: {e}")
            return None

def build_settings_keyboard():
    """بناء أزرار لوحة التحكم الرئيسية"""
    return {
        "inline_keyboard": [
            [
                {"text": "✏️ تعديل رسالة الترحيب", "callback_data": "edit_welcome"},
                {"text": "👥 إدارة الصلاحيات", "callback_data": "manage_admins"}
            ],
            [
                {"text": "🎬 أدوات الوسائط", "callback_data": "mod_media"},
                {"text": "🛡 حماية المجموعات", "callback_data": "mod_groups"}
            ],
            [
                {"text": "💼 المتجر والدعم", "callback_data": "mod_business"},
                {"text": "🤖 الذكاء الاصطناعي", "callback_data": "mod_ai"}
            ],
            [
                {"text": "🔄 تحديث الإعدادات", "callback_data": "refresh_panel"}
            ]
        ]
    }

@app.post("/webhook/{token}")
async def telegram_webhook(token: str, request: Request):
    payload = await request.json()

    # 1. معالجة نقرات الأزرار التفاعلية (Callback Query)
    if "callback_query" in payload:
        callback = payload["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        message_id = callback["message"]["message_id"]
        data = callback["data"]
        user_id = callback["from"]["id"]

        bot_data = bots_db.get(token, {})
        # التحقق من الصلاحية (المالك أو المشرفين)
        is_authorized = (bot_data.get("owner_id") == user_id) or (user_id in bot_data.get("admins", []))

        if not is_authorized and bot_data.get("owner_id") is not None:
            await send_telegram(token, "answerCallbackQuery", {
                "callback_query_id": callback["id"],
                "text": "⚠️ عذراً، لا تملك صلاحية تعديل هذا البوت.",
                "show_alert": True
            })
            return {"ok": True}

        # الردود التفاعلية لكل زر في اللوحة
        response_text = "⚙️ **لوحة التحكم**\nاختر الإجراء المطلوب:"
        if data == "edit_welcome":
            response_text = "✏️ **تعديل الترحيب:** لتغيير الرسالة، أرسل الأمر:\n`/setwelcome نص الرسالة الجديد`"
        elif data == "manage_admins":
            admins_list = ", ".join(map(str, bot_data.get("admins", []))) or "لا يوجد مشرفين حالياً"
            response_text = f"👥 **إدارة الصلاحيات:**\nالمشرفين: `{admins_list}`\n\nلإضافة مشرف أرسل:\n`/addadmin آيدي_المستخدم`"
        elif data == "mod_media":
            response_text = "🎬 **قسم الوسائط والملفات:**\nجاهز للعمل (تنزيل مقاطع، تحويل صيغ، إزالة خلفية)."
        elif data == "mod_groups":
            response_text = "🛡 **قسم المجموعات والقنوات:**\nمفعل (حماية، كابتشا، ردود تلقائية)."
        elif data == "mod_business":
            response_text = "💼 **قسم الأعمال والدعم:**\nمفعل (استقبال الطلبات، بوت التواصل بدون كشف هويتك)."
        elif data == "mod_ai":
            response_text = "🤖 **قسم الذكاء الاصطناعي:**\nمفعل (مساعد المحادثة، تلخيص النصوص والمحتوى)."
        elif data == "refresh_panel":
            response_text = "✅ تم تحديث لوحة التحكم."

        await send_telegram(token, "editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": response_text,
            "parse_mode": "Markdown",
            "reply_markup": build_settings_keyboard()
        })
        await send_telegram(token, "answerCallbackQuery", {"callback_query_id": callback["id"]})
        return {"ok": True}

    # 2. معالجة الرسائل النصية العادية
    if "message" in payload:
        msg = payload["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")

        # تسجيل أول مستخدم كمالك للبوت إذا لم يتم تسجيله مسبقاً
        if token not in bots_db:
            bots_db[token] = {
                "owner_id": user_id,
                "admins": [],
                "welcome_msg": "أهلاً بك في بوتر الخاص! يمكنك التحكم بي عبر /settings",
                "modules": {"media": True, "groups": True, "business": True, "ai": True},
            }
        elif bots_db[token]["owner_id"] is None:
            bots_db[token]["owner_id"] = user_id

        bot_info = bots_db[token]
        is_owner = (bot_info["owner_id"] == user_id)

        # أمر البدء
        if text.startswith("/start"):
            welcome = bot_info.get("welcome_msg", "أهلاً بك!")
            reply_markup = build_settings_keyboard() if is_owner else None
            await send_telegram(token, "sendMessage", {
                "chat_id": chat_id,
                "text": f"{welcome}\n\n⚙️ أرسل /settings لفتح لوحة التحكم." if is_owner else welcome,
                "reply_markup": reply_markup
            })

        # فتح لوحة التحكم
        elif text.startswith("/settings"):
            if is_owner or user_id in bot_info.get("admins", []):
                await send_telegram(token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "🎛 **أهلاً بك في لوحة تحكم البوت:**\nتحكم بالإعدادات والصلاحيات عبر الأزرار أدناه:",
                    "parse_mode": "Markdown",
                    "reply_markup": build_settings_keyboard()
                })
            else:
                await send_telegram(token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": "⛔️ عذراً، هذا الأمر مخصص لمالك البوت ومشرفيه فقط."
                })

        # تعديل رسالة الترحيب: /setwelcome نص
        elif text.startswith("/setwelcome "):
            if is_owner:
                new_msg = text.replace("/setwelcome ", "").strip()
                bot_info["welcome_msg"] = new_msg
                await send_telegram(token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": f"✅ تم حفظ رسالة الترحيب الجديدة:\n\n{new_msg}"
                })

        # إضافة مشرف: /addadmin 123456789
        elif text.startswith("/addadmin "):
            if is_owner:
                new_admin = text.replace("/addadmin ", "").strip()
                if new_admin.isdigit():
                    admin_id = int(new_admin)
                    if admin_id not in bot_info["admins"]:
                        bot_info["admins"].append(admin_id)
                        await send_telegram(token, "sendMessage", {
                            "chat_id": chat_id,
                            "text": f"✅ تم بنجاح إضافة المستخدم `{admin_id}` كمشرف في البوت.",
                            "parse_mode": "Markdown"
                        })
                    else:
                        await send_telegram(token, "sendMessage", {
                            "chat_id": chat_id,
                            "text": "المستخدم مضاف كمشرف بالفعل."
                        })
                else:
                    await send_telegram(token, "sendMessage", {
                        "chat_id": chat_id,
                        "text": "الرجاء إرسال ID صالح (أرقام فقط)."
                    })

        # استقبال الروابط وتحميل الميديا كمثال للميزة
        elif any(domain in text for domain in ["tiktok.com", "instagram.com", "youtube.com", "youtu.be", "twitter.com", "x.com"]):
            await send_telegram(token, "sendMessage", {
                "chat_id": chat_id,
                "text": "📥 تم التقاط الرابط بنجاح! جاري معالجة واستخراج الفيديو بدون علامة مائية..."
            })

    return {"ok": True}
