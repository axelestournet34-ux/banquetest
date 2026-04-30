"""
server.py — Point d'entrée unique pour Render.com
Lance Streamlit en arrière-plan (port 8501) et expose :
  - /expense  /revolut  /health  → webhook FastAPI
  - tout le reste                → proxy vers Streamlit (HTTP + WebSocket)
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import httpx
import websockets
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

PORT    = int(os.getenv("PORT", 8000))
ST_PORT = 8501
ST_HTTP = f"http://127.0.0.1:{ST_PORT}"
ST_WS   = f"ws://127.0.0.1:{ST_PORT}"

WEBHOOK_TOKEN      = os.getenv("WEBHOOK_TOKEN", "mon-budget-secret")
CATEGORIES_DEFAULT = "📦 Autres"

app = FastAPI(title="Budget App")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Helpers fichiers ──────────────────────────────────────────────────────────
DATA_DIR = Path(os.getenv("DATA_DIR", "."))
DATA_DIR.mkdir(parents=True, exist_ok=True)

def _data_file(username: str) -> Path:
    return DATA_DIR / f"budget_{username}.json"

def _load(username: str) -> dict:
    f = _data_file(username)
    if not f.exists():
        raise HTTPException(status_code=404, detail=f"Utilisateur '{username}' introuvable.")
    with open(f, "r", encoding="utf-8") as fp:
        return json.load(fp)

def _save(username: str, data: dict) -> None:
    with open(_data_file(username), "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)

def _ensure_month(data: dict, month_key: str) -> None:
    if month_key not in data:
        data[month_key] = {
            "config": {"monthly_budget": 900.0, "days_in_month": 30, "current_day": date.today().day},
            "category_budgets": {},
            "expenses": [],
        }


# ── Routes webhook ────────────────────────────────────────────────────────────
class ExpensePayload(BaseModel):
    token: str
    username: str
    amount: float
    description: str = "Revolut"
    category: str = CATEGORIES_DEFAULT
    date: str = ""

@app.post("/expense")
async def add_expense(payload: ExpensePayload):
    if payload.token != WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Token invalide.")
    expense_date = payload.date or date.today().isoformat()
    month_key    = expense_date[:7]
    data = _load(payload.username)
    _ensure_month(data, month_key)
    data[month_key]["expenses"].append({
        "date": expense_date,
        "amount": round(float(payload.amount), 2),
        "category": payload.category,
        "description": payload.description[:80],
    })
    _save(payload.username, data)
    return {"status": "ok", "message": f"{payload.amount}€ ajouté — {payload.description}"}

@app.post("/revolut")
async def revolut_notification(request: Request):
    body = await request.json()
    if body.get("token") != WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Token invalide.")
    username = body.get("username", "")
    notif    = body.get("notif", "")
    amount, desc = _parse_revolut(notif)
    if amount is None:
        raise HTTPException(status_code=422, detail=f"Impossible de parser : {notif!r}")
    expense_date = date.today().isoformat()
    data = _load(username)
    _ensure_month(data, expense_date[:7])
    data[expense_date[:7]]["expenses"].append({
        "date": expense_date, "amount": amount,
        "category": CATEGORIES_DEFAULT, "description": desc[:80],
    })
    _save(username, data)
    return {"status": "ok", "amount": amount, "description": desc}

@app.get("/health")
async def health():
    return {"status": "ok"}

def _parse_revolut(text: str):
    text = text.strip()
    patterns = [
        r"pay[eé]\s+([\d\s,\.]+)\s*(?:€|EUR|eur)(?:\s*[·@]\s*|\s+chez\s+|\s+à\s+|\s+at\s+)(.+)",
        r"paid\s+(?:€|EUR)?\s*([\d,\.]+)\s*(?:€|EUR)?\s+(?:at|to|chez|à)\s+(.+)",
        r"payment of\s+([\d,\.]+)\s*(?:€|EUR)\s+to\s+(.+)",
        r"([\d,\.]+)\s*(?:€|EUR)\s+(.+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return round(float(m.group(1).replace(" ", "").replace(",", ".")), 2), m.group(2).strip().rstrip(".")
            except ValueError:
                continue
    return None, None


# ── Proxy WebSocket → Streamlit ───────────────────────────────────────────────
@app.websocket("/{path:path}")
async def proxy_ws(websocket: WebSocket, path: str = ""):
    # Transmettre les sous-protocoles demandés par le navigateur (ex: "streamlit")
    proto_header = websocket.headers.get("sec-websocket-protocol", "")
    subprotocols = [s.strip() for s in proto_header.split(",") if s.strip()]

    if subprotocols:
        await websocket.accept(subprotocol=subprotocols[0])
    else:
        await websocket.accept()

    qs     = websocket.url.query
    ws_url = f"{ST_WS}/{path}" + (f"?{qs}" if qs else "")

    try:
        async with websockets.connect(
            ws_url,
            subprotocols=subprotocols or None,
            ping_interval=20,
            ping_timeout=20,
        ) as upstream:
            async def c2u():
                try:
                    while True:
                        msg = await websocket.receive()
                        if msg.get("bytes"):
                            await upstream.send(msg["bytes"])
                        elif msg.get("text"):
                            await upstream.send(msg["text"])
                except Exception:
                    pass

            async def u2c():
                try:
                    async for msg in upstream:
                        if isinstance(msg, bytes):
                            await websocket.send_bytes(msg)
                        else:
                            await websocket.send_text(msg)
                except Exception:
                    pass

            await asyncio.gather(c2u(), u2c())
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


# ── Proxy HTTP → Streamlit ────────────────────────────────────────────────────
_SKIP = {"host", "transfer-encoding", "content-encoding", "content-length"}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def proxy_http(request: Request, path: str = ""):
    url = f"{ST_HTTP}/{path}"
    qs  = request.url.query
    if qs:
        url += f"?{qs}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in _SKIP}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            rp = await client.request(
                method=request.method, url=url,
                headers=headers, content=await request.body(),
                follow_redirects=True,
            )
            out_headers = {k: v for k, v in rp.headers.items() if k.lower() not in _SKIP}
            return Response(content=rp.content, status_code=rp.status_code, headers=out_headers)
        except httpx.ConnectError:
            return Response(
                content=b"<html><body><p>Demarrage en cours, rechargez dans 10 secondes...</p>"
                        b"<script>setTimeout(()=>location.reload(),8000)</script></body></html>",
                status_code=503,
                media_type="text/html",
            )


# ── Démarrage Streamlit ───────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    cmd = [
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", str(ST_PORT),
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false",
    ]
    subprocess.Popen(cmd)
    print(f"[server] Streamlit lancé sur le port {ST_PORT}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=PORT)
