# main.py
import os, json, requests
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

app = FastAPI()

# --- Config via environment variables ---
VERIFY_TOKEN     = os.getenv("VERIFY_TOKEN", "CHANGE_ME")
WHATSAPP_TOKEN   = os.getenv("WHATSAPP_TOKEN", "")          # paste after approval
PHONE_NUMBER_ID  = os.getenv("PHONE_NUMBER_ID", "")         # paste after approval

GRAPH_BASE = "https://graph.facebook.com/v20.0"

@app.get("/health")
def health():
    return {"status": "ok"}

# --- Webhook verification (Meta calls GET first) ---
@app.get("/whatsapp")
def verify(request: Request):
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(p.get("hub.challenge", ""))
    return PlainTextResponse("forbidden", status_code=403)

# --- WhatsApp sender helper ---
def send_whatsapp_text(to_number: str, text: str) -> dict:
    if not (WHATSAPP_TOKEN and PHONE_NUMBER_ID):
        # If creds not set yet, just no-op safely
        return {"sent": False, "reason": "missing_credentials"}
    url = f"{GRAPH_BASE}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text[:4096]},
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"error": "non-json", "status_code": r.status_code, "text": r.text}
    return {"status_code": r.status_code, "data": data}

# --- Incoming webhook (Meta posts here on new messages) ---
@app.post("/whatsapp")
async def incoming(req: Request):
    payload = await req.json()
    # Basic log to Render logs
    print("INCOMING:", json.dumps(payload, ensure_ascii=False)[:1000])

    # Try to parse a text message
    try:
        entry = payload["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages", [])
        if not messages:
            return {"ok": True}  # ignore non-message webhooks

        msg = messages[0]
        from_num = msg["from"]                # sender's phone (as string, with country code)
        txt = msg.get("text", {}).get("body", "").strip()

        # Simple echo for now (proves full loop works)
        reply = f"👋 Hi! You said: {txt or '[no text]'}"
        result = send_whatsapp_text(from_num, reply)
        print("OUTGOING:", json.dumps(result, ensure_ascii=False)[:1000])

    except Exception as e:
        print("PARSE_ERROR:", repr(e))

    return {"ok": True}
