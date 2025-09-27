import os
import httpx
from fastapi import FastAPI, Request

# 從環境變數讀取 Access Token（等會在雲端填）
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")

app = FastAPI()

@app.get("/healthz")
async def health():
    return {"status": "ok"}

@app.post("/webhook/line")
async def webhook(req: Request):
    body = await req.json()
    # 逐筆處理事件
    for event in body.get("events", []):
        if event.get("type") == "message" and event["message"]["type"] == "text":
            reply_token = event["replyToken"]
            text = event["message"]["text"]
            # 呼叫 LINE Reply API 回話
            headers = {
                "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            }
            payload = {
                "replyToken": reply_token,
                "messages": [{"type": "text", "text": f"我收到了：{text}"}],
            }
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post("https://api.line.me/v2/bot/message/reply",
                                       headers=headers, json=payload)
                r.raise_for_status()
    return "OK"
