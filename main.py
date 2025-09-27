import os
import hmac
import hashlib
import base64
import httpx
from fastapi import FastAPI, Request, Header, HTTPException

app = FastAPI()

# 從環境變數讀取
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")

def verify_signature(body: bytes, signature: str) -> bool:
    """驗證 LINE 傳來的簽章"""
    mac = hmac.new(CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    expected_signature = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected_signature, signature)

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/webhook/line")
async def webhook(request: Request, x_line_signature: str = Header(default="")):
    raw = await request.body()

    # 驗證簽章，確保請求來自 LINE
    if not verify_signature(raw, x_line_signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    body = await request.json()
    for event in body.get("events", []):
        if event.get("type") == "message" and event["message"]["type"] == "text":
            reply_token = event["replyToken"]
            text = event["message"]["text"].strip()

            headers = {
                "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            }

            # 當使用者輸入「預約」時 → 回傳 Quick Reply
            if text in ["預約", "約", "book"]:
                payload = {
                    "replyToken": reply_token,
                    "messages": [
                        {
                            "type": "text",
                            "text": "請選擇預約區間 👇",
                            "quickReply": {
                                "items": [
                                    {
                                        "type": "action",
                                        "action": {
                                            "type": "message",
                                            "label": "今天",
                                            "text": "預約_今天"
                                        }
                                    },
                                    {
                                        "type": "action",
                                        "action": {
                                            "type": "message",
                                            "label": "明天",
                                            "text": "預約_明天"
                                        }
                                    },
                                    {
                                        "type": "action",
                                        "action": {
                                            "type": "message",
                                            "label": "本週",
                                            "text": "預約_本週"
                                        }
                                    }
                                ]
                            }
                        }
                    ],
                }
            else:
                # 其餘訊息 → 原樣回覆
                payload = {
                    "replyToken": reply_token,
                    "messages": [{"type": "text", "text": f"我收到了：「{text}」 ✅"}],
                }

            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    "https://api.line.me/v2/bot/message/reply",
                    headers=headers,
                    json=payload,
                )
                r.raise_for_status()
    return "OK"
