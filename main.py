import os, hmac, hashlib, base64
import httpx
from fastapi import FastAPI, Request, Header, HTTPException

app = FastAPI()

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")

def verify_signature(body: bytes, signature: str) -> bool:
    mac = hmac.new(CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature or "")

# ====== 假資料：今天/明天/本週 可選時段 ======
FAKE_SLOTS = {
    "今天": ["09:00–10:00", "12:00–13:00", "19:00–20:00"],
    "明天": ["08:00–09:00", "13:00–14:00", "20:00–21:00"],
    "本週": ["週三 18:30–19:30", "週五 07:30–08:30", "週六 10:00–11:00"],
}

def build_slots_flex(day_label: str, slots: list[str]) -> dict:
    """把時段清單做成 Flex 卡片（carousel）"""
    bubbles = []
    for s in slots:
        bubbles.append({
            "type": "bubble",
            "size": "micro",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": f"{day_label}", "weight": "bold", "size": "sm"},
                    {"type": "text", "text": s, "size": "lg", "weight": "bold"},
                    {"type": "text", "text": "剩餘名額：3", "size": "xs", "color": "#888888"}
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "height": "sm",
                        # 簡化：用 message action，點了會送出「預約_選_時段」
                        "action": {
                            "type": "message",
                            "label": "選擇這個時段",
                            "text": f"預約_選_{s}"
                        }
                    }
                ],
                "flex": 0
            }
        })
    return {
        "type": "flex",
        "altText": f"{day_label} 可預約時段",
        "contents": {"type": "carousel", "contents": bubbles}
    }

@app.get("/healthz")
async def health():
    return {"status": "ok"}

@app.post("/webhook/line")
async def webhook(request: Request, x_line_signature: str = Header(default="")):
    raw = await request.body()
    if not verify_signature(raw, x_line_signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    body = await request.json()
    for event in body.get("events", []):
        etype = event.get("type")

        # 只處理文字訊息
        if etype == "message" and event["message"]["type"] == "text":
            reply_token = event["replyToken"]
            text = event["message"]["text"].strip()

            headers = {
                "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            }

            # 使用者輸入「預約」→ 給 Quick Reply
            if text in ["預約", "約", "book"]:
                payload = {
                    "replyToken": reply_token,
                    "messages": [
                        {
                            "type": "text",
                            "text": "請選擇預約區間 👇",
                            "quickReply": {
                                "items": [
                                    {"type": "action", "action": {"type": "message", "label": "今天", "text": "預約_今天"}},
                                    {"type": "action", "action": {"type": "message", "label": "明天", "text": "預約_明天"}},
                                    {"type": "action", "action": {"type": "message", "label": "本週", "text": "預約_本週"}},
                                ]
                            }
                        }
                    ]
                }

            # 使用者選了日期（例如 預約_今天）
            elif text.startswith("預約_"):
                day = text.split("_", 1)[1]
                slots = FAKE_SLOTS.get(day)
                if slots:
                    payload = {
                        "replyToken": reply_token,
                        "messages": [build_slots_flex(day, slots)]
                    }
                else:
                    payload = {
                        "replyToken": reply_token,
                        "messages": [{"type": "text", "text": f"目前「{day}」沒有可預約時段，換個區間試試～"}]
                    }

            # 使用者從卡片點了「選擇這個時段」→ 會送出 預約_選_時段文字
            elif text.startswith("預約_選_"):
                slot_label = text.replace("預約_選_", "")
                payload = {
                    "replyToken": reply_token,
                    "messages": [
                        {"type": "text", "text": f"收到，你選了「{slot_label}」。\n（下一步我們會把它接成『建立預約』喔）"}
                    ]
                }

            # 其他 → Echo
            else:
                payload = {
                    "replyToken": reply_token,
                    "messages": [{"type": "text", "text": f"我收到了：「{text}」 ✅"}],
                }

            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post("https://api.line.me/v2/bot/message/reply",
                                      headers=headers, json=payload)
                r.raise_for_status()
    return "OK"
