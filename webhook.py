"""
Serveur webhook — reçoit les transactions Revolut depuis Tasker
et les ajoute automatiquement au budget de l'utilisateur.

Démarrage : uvicorn webhook:app --host 0.0.0.0 --port 8000
"""

import json
import os
import re
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Budget Webhook")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Token secret — changez cette valeur et mettez la même dans Tasker
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "mon-budget-secret")

CATEGORIES_DEFAULT = "📦 Autres"


class ExpensePayload(BaseModel):
    token: str
    username: str
    amount: float
    description: str = "Revolut"
    category: str = CATEGORIES_DEFAULT
    date: str = ""


def data_file(username: str) -> Path:
    return Path(f"budget_{username}.json")


def load_user_data(username: str) -> dict:
    f = data_file(username)
    if not f.exists():
        raise HTTPException(status_code=404, detail=f"Utilisateur '{username}' introuvable.")
    with open(f, "r", encoding="utf-8") as fp:
        return json.load(fp)


def save_user_data(username: str, data: dict) -> None:
    with open(data_file(username), "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)


def ensure_month(data: dict, month_key: str) -> None:
    if month_key not in data:
        y, m = int(month_key[:4]), int(month_key[5:])
        data[month_key] = {
            "config": {
                "monthly_budget": 900.0,
                "days_in_month": 30,
                "current_day": date.today().day,
            },
            "category_budgets": {},
            "expenses": [],
        }


# ── Endpoint principal ────────────────────────────────────────────────────────
@app.post("/expense")
async def add_expense(payload: ExpensePayload):
    if payload.token != WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Token invalide.")

    expense_date = payload.date or date.today().isoformat()
    month_key = expense_date[:7]

    data = load_user_data(payload.username)
    ensure_month(data, month_key)

    data[month_key]["expenses"].append({
        "date": expense_date,
        "amount": round(float(payload.amount), 2),
        "category": payload.category,
        "description": payload.description[:80],
    })

    save_user_data(payload.username, data)
    return {"status": "ok", "message": f"{payload.amount}€ ajouté — {payload.description}"}


# ── Endpoint Tasker (texte brut de la notif Revolut) ─────────────────────────
@app.post("/revolut")
async def revolut_notification(request: Request):
    """
    Tasker envoie le texte brut de la notification Revolut.
    Format attendu (corps JSON) :
      { "token": "...", "username": "...", "notif": "Vous avez payé 12,50 € chez McDonald's" }
    """
    body = await request.json()

    if body.get("token") != WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Token invalide.")

    username = body.get("username", "")
    notif    = body.get("notif", "")

    # Parse la notification Revolut (français et anglais)
    amount, desc = _parse_revolut_notif(notif)
    if amount is None:
        raise HTTPException(status_code=422, detail=f"Impossible de parser la notification : {notif!r}")

    expense_date = date.today().isoformat()
    month_key    = expense_date[:7]

    data = load_user_data(username)
    ensure_month(data, month_key)

    data[month_key]["expenses"].append({
        "date":        expense_date,
        "amount":      amount,
        "category":    CATEGORIES_DEFAULT,
        "description": desc[:80],
    })

    save_user_data(username, data)
    return {"status": "ok", "amount": amount, "description": desc}


def _parse_revolut_notif(text: str):
    """
    Extrait montant et description depuis une notification Revolut.
    Exemples reconnus :
      "Vous avez payé 12,50 € chez McDonald's"
      "Payé 8.99€ · Netflix"
      "You paid €12.50 at Starbucks"
      "Payment of 5,00 EUR to Amazon"
    Retourne (float, str) ou (None, None) si non reconnu.
    """
    text = text.strip()

    patterns = [
        # FR : "payé 12,50 € chez Merchant" ou "payé 12,50€ · Merchant"
        r"pay[eé]\s+([\d\s,\.]+)\s*(?:€|EUR|eur)(?:\s*[·@]\s*|\s+chez\s+|\s+à\s+|\s+at\s+)(.+)",
        # EN : "You paid €12.50 at Merchant" ou "paid €12.50 to Merchant"
        r"paid\s+(?:€|EUR)?\s*([\d,\.]+)\s*(?:€|EUR)?\s+(?:at|to|chez|à)\s+(.+)",
        # "Payment of 12,50 EUR to Merchant"
        r"payment of\s+([\d,\.]+)\s*(?:€|EUR)\s+to\s+(.+)",
        # Fallback : "12,50 € Merchant" ou "12.50€ Merchant"
        r"([\d,\.]+)\s*(?:€|EUR)\s+(.+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            raw_amount = m.group(1).replace(" ", "").replace(",", ".")
            desc       = m.group(2).strip().rstrip(".")
            try:
                return round(float(raw_amount), 2), desc
            except ValueError:
                continue

    return None, None


# ── Santé ─────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}
