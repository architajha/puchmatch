import os
from dotenv import load_dotenv
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from collections import deque

# Load .env file
load_dotenv()

AUTH_TOKEN = os.getenv("AUTH_TOKEN", "changeme")
OWNER_PHONE = os.getenv("OWNER_PHONE", "")

if AUTH_TOKEN == "changeme":
    print("⚠ WARNING: AUTH_TOKEN is still 'changeme'. Please set a secure token in your .env")
if not OWNER_PHONE:
    print("⚠ WARNING: OWNER_PHONE is not set in your .env file")

app = FastAPI(title="PuchMatch (MCP) Server")

# ----------------------
# In-memory storage
# ----------------------
waiting_queue = deque()
active_pairs: Dict[str, str] = {}
inbox: Dict[str, List[Dict]] = {}
meta: Dict[str, Dict] = {}

# ----------------------
# Pydantic models
# ----------------------
class ConnectPayload(BaseModel):
    user_id: str
    nickname: Optional[str] = None

class MessagePayload(BaseModel):
    user_id: str
    text: str

class SimplePayload(BaseModel):
    user_id: str

# ----------------------
# Middleware to check Bearer token for every request
# ----------------------
@app.middleware("http")
async def check_auth_middleware(request: Request, call_next):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Missing or invalid Authorization header"})
    token = auth_header.split("Bearer ")[1]
    if token != AUTH_TOKEN:
        return JSONResponse(status_code=403, content={"detail": "Invalid token"})
    return await call_next(request)

# ----------------------
# Helpers
# ----------------------
def make_user_if_missing(user_id: str, nickname: Optional[str] = None):
    if user_id not in inbox:
        inbox[user_id] = []
    if user_id not in meta:
        meta[user_id] = {"nickname": nickname or f"User-{user_id[-4:]}"}

def pair_two(user_a: str, user_b: str):
    active_pairs[user_a] = user_b
    active_pairs[user_b] = user_a
    make_user_if_missing(user_a)
    make_user_if_missing(user_b)

def unpair(user_id: str):
    partner = active_pairs.pop(user_id, None)
    if partner:
        active_pairs.pop(partner, None)
        inbox.setdefault(partner, []).append({"from": "system", "text": "Your partner disconnected."})

# ----------------------
# MCP / Puch required endpoints
# ----------------------
@app.get("/")
def root():
    return {"status": "ok", "service": "PuchMatch MCP server"}

@app.post("/validate")
def validate():
    if not OWNER_PHONE:
        return {"phone_number": "UNKNOWN", "message": "Set OWNER_PHONE env var to your phone"}
    return {"phone_number": OWNER_PHONE}

# ----------------------
# Matchmaking endpoints (now under /mcp)
# ----------------------
@app.post("/mcp/join_chat")
def join_chat(payload: ConnectPayload):
    user_id = payload.user_id
    nickname = payload.nickname
    make_user_if_missing(user_id, nickname)

    if user_id in active_pairs:
        partner = active_pairs[user_id]
        return {"status": "already_matched", "partner_id": partner, "icebreaker": "What's something you love talking about?"}

    if user_id in waiting_queue:
        return {"status": "waiting", "queue_position": list(waiting_queue).index(user_id)}

    if waiting_queue:
        partner = waiting_queue.popleft()
        if partner == user_id:
            waiting_queue.appendleft(partner)
            return {"status": "waiting"}
        pair_two(user_id, partner)
        icebreaker = "If you could have lunch with anyone (alive), who would it be?"
        return {"status": "matched", "partner_id": partner, "icebreaker": icebreaker}
    else:
        waiting_queue.append(user_id)
        return {"status": "waiting"}

@app.post("/mcp/send_message")
def send_message(payload: MessagePayload):
    user_id = payload.user_id
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty message")

    if user_id not in active_pairs:
        raise HTTPException(status_code=400, detail="You are not matched")

    partner = active_pairs[user_id]
    inbox.setdefault(partner, []).append({"from": user_id, "text": text})
    return {"status": "sent", "to": partner}

@app.get("/mcp/get_messages")
def get_messages(user_id: str):
    if user_id not in inbox:
        return {"messages": []}
    msgs = inbox.get(user_id, [])
    inbox[user_id] = []
    return {"messages": msgs}

@app.post("/mcp/skip")
def skip_user(payload: SimplePayload):
    user_id = payload.user_id
    if user_id in waiting_queue:
        return {"status": "waiting"}

    if user_id in active_pairs:
        partner = active_pairs.get(user_id)
        unpair(user_id)
        if partner:
            waiting_queue.appendleft(partner)

    make_user_if_missing(user_id)
    if user_id in waiting_queue:
        return {"status": "waiting"}
    if waiting_queue:
        partner = waiting_queue.popleft()
        if partner == user_id:
            waiting_queue.appendleft(partner)
            return {"status": "waiting"}
        pair_two(user_id, partner)
        return {"status": "matched", "partner_id": partner}
    else:
        waiting_queue.append(user_id)
        return {"status": "waiting"}

@app.post("/mcp/leave")
def leave(payload: SimplePayload):
    user_id = payload.user_id
    try:
        if user_id in waiting_queue:
            waiting_queue.remove(user_id)
    except ValueError:
        pass
    if user_id in active_pairs:
        unpair(user_id)
    inbox.pop(user_id, None)
    meta.pop(user_id, None)
    return {"status": "left"}

@app.get("/mcp/status")
def status(user_id: str):
    if user_id in active_pairs:
        return {"status": "matched", "partner_id": active_pairs[user_id]}
    elif user_id in waiting_queue:
        return {"status": "waiting", "queue_position": list(waiting_queue).index(user_id)}
    else:
        return {"status": "not_connected"}
