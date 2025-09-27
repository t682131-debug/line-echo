import os, base64, hmac, hashlib
import httpx
from fastapi import FastAPI, Request, Header, HTTPException

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")  # 新增：讀取 secret

app = FastAPI()

@app.get("/healthz")
async def health():
    return {"status": "ok"}

def verify_signature(raw_body: bytes, x_line_signature: str) -> bool:
    """用 Channel secret 對原始 body 做 HMAC-SHA256，再 base64，比對 header"""
    mac = hmac.new(CHANNEL_SECRET.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode()
    return hmac.compare_digest(expected, x_line_signature or "")

@app.post("/webhook/line")
async def webhook(
    request: Request,
    x_line_signature: str = Header(default="")  # 讀取 X-Line-Signature
):
    raw = await request.body()

    # 1) 先驗簽，不通過就擋掉
    if not verify_signature(raw, x_line_signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # 2) 驗簽通過才處理事件
    body = await request.json()
    for event in body.get("events", []):
        if event.get("type") == "message" and event["message"]["type"] == "text":
            reply_token = event["replyToken"]
            text = event["message"]["text"]

            headers = {
                "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            }
            payload = {
                "replyToken": reply_token,
                "messages": [{"type": "text", "text": f"我收到了：{text}"}],
            }
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    "https://api.line.me/v2/bot/message/reply",
                    headers=headers, json=payload
                )
                r.raise_for_status()
    return "OK"

