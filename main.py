from fastapi import FastAPI, Request
import httpx

app = FastAPI()

MAIN_BOT_TOKEN = "8560690505:AAH-qPNGKqNWwPW0ARCkTVtveMnO_I2Q-oM"
BASE_URL = "https://letter-crown-uphill.ngrok-free.dev"
TELEGRAM_API = "https://api.telegram.org"

# تخزين البوتات المسجلة في الذاكرة مؤقتاً
registered_bots = {}

async def send_message(token: str, chat_id: int, text: str):
    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})

async def register_webhook(token: str) -> bool:
    webhook_url = f"{BASE_URL}/webhook/{token}"
    url = f"{TELEGRAM_API}/bot{token}/setWebhook"
    async with httpx.AsyncClient() as client:
        res = await client.post(url, json={"url": webhook_url})
        return res.status_code == 200 and res.json().get("ok", False)

@app.post("/webhook/{token}")
async def telegram_webhook(token: str, request: Request):
    data = await request.json()
    if "message" not in data or "text" not in data["message"]:
        return {"status": "ignored"}

    chat_id = data["message"]["chat"]["id"]
    text = data["message"]["text"].strip()

    # إذا كانت الرسالة واردة للبوت الرئيسي (المصنع)
    if token == MAIN_BOT_TOKEN:
        if text.startswith("/start"):
            msg = "أهلاً بك في صانع البوتات! 🤖\nأرسل توكن بوتك المستخرج من @BotFather لتفعيله فوراً."
            await send_message(token, chat_id, msg)
        else:
            # افتراض أن المستخدم أرسل توكن لإنشاء بوت
            sub_token = text
            success = await register_webhook(sub_token)
            if success:
                registered_bots[sub_token] = chat_id
                msg = f"تم تفعيل بوتك بنجاح! 🎉\nيمكنك الآن الدخول إليه والبدء باستخدامه."
            else:
                msg = "فشل تفعيل البوت. تأكد من إرسال توكن صحيح مستخرج من @BotFather."
            await send_message(token, chat_id, msg)
    else:
        # إذا كانت الرسالة واردة لأحد البوتات الفرعية المصنوعة
        msg = f"مرحباً! أنا بوت فرعي تم إنشاؤك عبر المصنع. رسالتك كانت: {text}"
        await send_message(token, chat_id, msg)

    return {"status": "ok"}