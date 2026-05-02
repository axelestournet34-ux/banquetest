"""
Budget Mensuel Intelligent — Streamlit v4
Mobile-first · Tabs · Top marchands · Évolution 6 mois · Mode sombre
"""

import hashlib
import json
import os
import smtplib
import time
from collections import defaultdict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import redis
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime

SESSION_KEY = "budget_session"

@st.cache_resource
def _redis():
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)

CATEGORIES = [
    "🍔 Alimentation", "🚗 Transport", "🏠 Logement / Factures",
    "💊 Santé", "🎮 Loisirs", "👗 Vêtements", "📱 Abonnements",
    "🍽️ Restaurant", "✈️ Voyage", "🎁 Cadeaux", "📦 Autres",
]

INCOME_CATEGORIES = [
    "💰 Salaire", "🏦 Virement", "💼 Freelance / Side income",
    "📈 Remboursement", "🎁 Cadeau reçu", "💸 Autre revenu",
]

NEEDS_CATS  = {"🍔 Alimentation", "🚗 Transport", "🏠 Logement / Factures", "💊 Santé"}
WANTS_CATS  = {"🍽️ Restaurant", "🎮 Loisirs", "👗 Vêtements", "✈️ Voyage", "🎁 Cadeaux", "📱 Abonnements", "📦 Autres"}

THEMES = {
    "Indigo": "#6366F1", "Violet": "#8B5CF6", "Rose": "#F43F5E",
    "Orange": "#F59E0B", "Vert": "#10B981", "Bleu": "#3B82F6",
    "Cyan": "#06B6D4",
}

def get_categories() -> list:
    raw = _redis().get(f"categories:{st.session_state.username}")
    extras = json.loads(raw) if raw else []
    return CATEGORIES + [c for c in extras if c not in CATEGORIES]

def save_extra_categories(extras: list) -> None:
    _redis().set(f"categories:{st.session_state.username}", json.dumps(extras, ensure_ascii=False))

def get_theme() -> str:
    return st.session_state.data.get("settings", {}).get("theme", "#6366F1")

MOIS_FR = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]

DATE_FORMATS = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d.%m.%Y"]

CURRENCIES = {
    "EUR": "€ Euro",
    "CHF": "Fr. Franc suisse",
    "USD": "$ Dollar US",
    "GBP": "£ Livre sterling",
    "CAD": "$ Dollar canadien",
    "JPY": "¥ Yen japonais",
}

CURRENCY_SYMBOLS = {
    "EUR": "€", "CHF": "Fr.", "USD": "$", "GBP": "£", "CAD": "CA$", "JPY": "¥",
}


# ── Authentification ──────────────────────────────────────────────────────────
def _hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def load_users() -> dict:
    raw = _redis().get("users")
    return json.loads(raw) if raw else {}

def save_users(users: dict) -> None:
    _redis().set("users", json.dumps(users, ensure_ascii=False))

def register_user(username: str, password: str) -> str | None:
    username = username.strip().lower()
    if not username or not password:
        return "Nom d'utilisateur et mot de passe requis."
    if len(username) < 3:
        return "Le nom d'utilisateur doit avoir au moins 3 caractères."
    if len(password) < 4:
        return "Le mot de passe doit avoir au moins 4 caractères."
    users = load_users()
    if username in users:
        return "Ce nom d'utilisateur est déjà pris."
    users[username] = _hash(password)
    save_users(users)
    return None

def verify_user(username: str, password: str) -> bool:
    users = load_users()
    return users.get(username.strip().lower()) == _hash(password)

def render_auth_page() -> None:
    st.title("💶 Budget Mensuel")
    tab_login, tab_register = st.tabs(["🔑 Se connecter", "📝 Créer un compte"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Nom d'utilisateur")
            password = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Connexion", use_container_width=True, type="primary"):
                if verify_user(username, password):
                    uname = username.strip().lower()
                    st.session_state.logged_in = True
                    st.session_state.username = uname
                    token = hashlib.sha256(f"{uname}{time.time()}".encode()).hexdigest()[:16]
                    _redis().setex(f"session:{token}", 60 * 60 * 24 * 365, uname)
                    st.query_params[SESSION_KEY] = token
                    st.rerun()
                else:
                    st.error("Nom d'utilisateur ou mot de passe incorrect.")

    with tab_register:
        with st.form("register_form"):
            new_user = st.text_input("Nom d'utilisateur")
            new_pass = st.text_input("Mot de passe", type="password")
            confirm  = st.text_input("Confirmer le mot de passe", type="password")
            if st.form_submit_button("Créer le compte", use_container_width=True, type="primary"):
                if new_pass != confirm:
                    st.error("Les mots de passe ne correspondent pas.")
                else:
                    err = register_user(new_user, new_pass)
                    if err:
                        st.error(err)
                    else:
                        st.info("Compte créé ! Connectez-vous dans l'onglet ci-contre.")


# ── Persistance ───────────────────────────────────────────────────────────────
def load_data() -> dict:
    raw = _redis().get(f"budget:{st.session_state.username}")
    return json.loads(raw) if raw else {}

def save_data() -> None:
    r = _redis()
    r.set(f"budget:{st.session_state.username}", json.dumps(st.session_state.data, ensure_ascii=False))
    r.set(f"mtime:{st.session_state.username}", str(time.time()))
    check_budget_alert()

def get_month_keys() -> list:
    return sorted([k for k in st.session_state.data if k not in ("recurring", "settings")], reverse=True)

def get_recurring() -> list:
    return st.session_state.data.get("recurring", [])

def get_currency() -> str:
    return st.session_state.data.get("settings", {}).get("currency", "EUR")

def set_currency(code: str) -> None:
    if "settings" not in st.session_state.data:
        st.session_state.data["settings"] = {}
    st.session_state.data["settings"]["currency"] = code
    save_data()

def fmt(amount: float) -> str:
    sym = CURRENCY_SYMBOLS.get(get_currency(), "€")
    if get_currency() == "JPY":
        return f"{sym}{int(amount):,}"
    return f"{amount:.2f} {sym}"


# ── Helpers ───────────────────────────────────────────────────────────────────
def current_month_key() -> str:
    return date.today().strftime("%Y-%m")

def month_label(key: str) -> str:
    try:
        y, m = int(key[:4]), int(key[5:])
        return f"{MOIS_FR[m - 1]} {y}"
    except Exception:
        return key

def parse_date(raw: str) -> str:
    raw = str(raw).strip()
    for fmt_str in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt_str).date().isoformat()
        except ValueError:
            continue
    return date.today().isoformat()

def ensure_month(key: str) -> None:
    if key not in st.session_state.data:
        st.session_state.data[key] = {
            "config": {
                "monthly_budget": 900.0,
                "days_in_month": 30,
                "current_day": date.today().day,
            },
            "category_budgets": {cat: 0.0 for cat in CATEGORIES},
            "expenses": [],
        }
        _apply_recurring(key)
        save_data()

def _apply_recurring(month_key: str) -> None:
    y, m = int(month_key[:4]), int(month_key[5:])
    first_day = date(y, m, 1).isoformat()
    for rec in get_recurring():
        st.session_state.data[month_key]["expenses"].append({
            "date": first_day,
            "amount": float(rec["amount"]),
            "category": rec["category"],
            "description": f"[Récurrent] {rec['description']}",
        })


# ── Session state ─────────────────────────────────────────────────────────────
def _data_mtime() -> float:
    val = _redis().get(f"mtime:{st.session_state.username}")
    return float(val) if val else 0.0

def init_state() -> None:
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ""
        token = st.query_params.get(SESSION_KEY)
        if token:
            saved = _redis().get(f"session:{token}")
            if saved and saved in load_users():
                st.session_state.logged_in = True
                st.session_state.username = saved
    if not st.session_state.logged_in:
        return
    if "data" not in st.session_state:
        st.session_state.data = load_data()
        st.session_state.file_mtime = _data_mtime()
    if "active_month" not in st.session_state:
        st.session_state.active_month = current_month_key()
    ensure_month(st.session_state.active_month)
    check_weekly_alerts()
    check_monthly_report()
    check_payment_reminders()
    current_mtime = _data_mtime()
    if current_mtime > st.session_state.get("file_mtime", 0):
        st.session_state.data = load_data()
        st.session_state.file_mtime = current_mtime


# ── Accesseurs ────────────────────────────────────────────────────────────────
def active_config() -> dict:
    return st.session_state.data[st.session_state.active_month]["config"]

def active_expenses() -> list:
    return st.session_state.data[st.session_state.active_month]["expenses"]

def active_cat_budgets() -> dict:
    return st.session_state.data[st.session_state.active_month]["category_budgets"]

def build_df() -> pd.DataFrame:
    expenses = active_expenses()
    if not expenses:
        return pd.DataFrame(columns=["date", "amount", "category", "description", "type"])
    df = pd.DataFrame(expenses)
    df["amount"] = df["amount"].astype(float)
    if "type" not in df.columns:
        df["type"] = "expense"
    return df

def expense_df(df: pd.DataFrame) -> pd.DataFrame:
    if "type" in df.columns:
        return df[df["type"] == "expense"]
    return df

def income_df(df: pd.DataFrame) -> pd.DataFrame:
    if "type" in df.columns:
        return df[df["type"] == "income"]
    return pd.DataFrame(columns=df.columns)


# ── Logique métier ────────────────────────────────────────────────────────────
def get_historical_daily_avg() -> float:
    current = current_month_key()
    past = [m for m in get_month_keys() if m != current][:3]
    if not past:
        return 0.0
    avgs = []
    for mk in past:
        md   = st.session_state.data[mk]
        days = int(md.get("config", {}).get("days_in_month", 30))
        tot  = sum(float(e["amount"]) for e in md.get("expenses", []) if e.get("type", "expense") == "expense")
        if tot > 0 and days > 0:
            avgs.append(tot / days)
    return sum(avgs) / len(avgs) if avgs else 0.0

def compute_summary(config: dict, df: pd.DataFrame) -> dict:
    budget = float(config["monthly_budget"])
    total_days = int(config["days_in_month"])
    current_day = int(config["current_day"])

    exp = expense_df(df)
    inc = income_df(df)
    total_income = float(inc["amount"].sum()) if not inc.empty else 0.0
    total_spent = float(exp["amount"].sum()) if not exp.empty else 0.0
    initial_daily = budget / total_days if total_days > 0 else 0.0
    days_elapsed = min(current_day, total_days)
    days_remaining = max(total_days - days_elapsed, 0)
    budget_remaining = budget - total_spent
    daily_remaining = budget_remaining / days_remaining if days_remaining > 0 else 0.0
    avg_daily = total_spent / days_elapsed if days_elapsed > 0 else 0.0
    hist_avg  = get_historical_daily_avg()
    if days_elapsed <= 3 and hist_avg > 0:
        forecast_base = hist_avg
    elif hist_avg > 0:
        forecast_base = (avg_daily * 0.7 + hist_avg * 0.3)
    else:
        forecast_base = avg_daily
    forecast_total = forecast_base * total_days
    ideal_spent = initial_daily * days_elapsed
    difference = ideal_spent - total_spent

    return {
        "budget": budget, "total_spent": total_spent, "total_income": total_income,
        "budget_remaining": budget_remaining, "initial_daily": initial_daily,
        "daily_remaining": daily_remaining, "days_remaining": days_remaining,
        "days_elapsed": days_elapsed, "ideal_spent": ideal_spent,
        "difference": difference, "total_days": total_days,
        "forecast_total": forecast_total, "avg_daily": avg_daily,
    }

def get_status(difference: float) -> tuple:
    if difference > 5:
        return "green", "✅ Tu es en dessous de ton rythme de dépense. Continue comme ça !"
    elif difference >= -5:
        return "orange", "⚠️ Tu es dans la zone de vigilance. Surveille tes prochaines dépenses."
    else:
        return "red", "🔴 Tu dépenses trop vite pour le reste du mois. Ralentis !"

def get_category_alerts(df: pd.DataFrame, cat_budgets: dict) -> dict:
    if df.empty:
        return {}
    by_cat = df.groupby("category")["amount"].sum()
    alerts = {}
    for cat, limit in cat_budgets.items():
        if limit > 0 and cat in by_cat.index:
            spent = float(by_cat[cat])
            pct = spent / limit
            if pct >= 1.0:
                alerts[cat] = ("red", spent, limit, pct)
            elif pct >= 0.8:
                alerts[cat] = ("orange", spent, limit, pct)
    return alerts


# ── Sidebar minimale (mois + déconnexion) ────────────────────────────────────
def render_sidebar() -> None:
    st.sidebar.markdown(f"👤 **{st.session_state.username}**")
    if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
        token = st.query_params.get(SESSION_KEY)
        if token:
            _redis().delete(f"session:{token}")
            st.query_params.clear()
        for key in ["logged_in", "username", "data", "active_month"]:
            st.session_state.pop(key, None)
        st.rerun()
    st.sidebar.markdown("---")

    all_months = get_month_keys()
    cur = current_month_key()
    if cur not in all_months:
        all_months.insert(0, cur)
    active = st.session_state.active_month
    idx = all_months.index(active) if active in all_months else 0

    selected = st.sidebar.selectbox(
        "📅 Mois affiché", options=all_months, index=idx, format_func=month_label,
    )
    if selected != st.session_state.active_month:
        st.session_state.active_month = selected
        ensure_month(selected)
        st.rerun()

    with st.sidebar.expander("➕ Nouveau mois"):
        new_year = st.number_input("Année", min_value=2020, max_value=2030, value=date.today().year)
        new_month = st.number_input("Mois (1–12)", min_value=1, max_value=12, value=date.today().month)
        if st.button("Créer ce mois", use_container_width=True, key="create_month_btn"):
            new_key = f"{int(new_year):04d}-{int(new_month):02d}"
            ensure_month(new_key)
            st.session_state.active_month = new_key
            st.rerun()


# ── Fonctions sidebar settings (réutilisées dans l'onglet Réglages) ───────────
def _render_recurring_sidebar() -> None:
    st.caption("Ajoutées automatiquement à chaque nouveau mois.")
    recurring = get_recurring()
    for i, rec in enumerate(recurring):
        c1, c2 = st.columns([5, 1])
        c1.markdown(f"**{rec['description']}** — {rec['amount']:.0f} € · {rec['category']}")
        if c2.button("✕", key=f"del_rec_{i}"):
            recurring.pop(i)
            st.session_state.data["recurring"] = recurring
            save_data()
            st.rerun()
    with st.form("recurring_form"):
        r_desc = st.text_input("Description", placeholder="Loyer, Netflix…")
        r_amt = st.number_input("Montant (€)", min_value=0.01, value=50.0, step=5.0)
        r_cat = st.selectbox("Catégorie", CATEGORIES)
        if st.form_submit_button("➕ Ajouter", use_container_width=True) and r_desc.strip():
            recurring.append({"description": r_desc.strip(), "amount": float(r_amt), "category": r_cat})
            st.session_state.data["recurring"] = recurring
            save_data()
            st.rerun()


def _render_notif_sidebar() -> None:
    cfg = get_notif_cfg()
    st.caption("Recevez des alertes budget et un résumé hebdomadaire.")
    with st.form("notif_form"):
        email    = st.text_input("Votre email", value=cfg.get("email", ""))
        gmail    = st.text_input("Votre adresse Gmail (expéditeur)", value=cfg.get("gmail", ""))
        app_pwd  = st.text_input("Mot de passe d'application Google", value=cfg.get("app_password", ""), type="password",
                                  help="Compte Google → Sécurité → Mots de passe des applications")
        if st.form_submit_button("💾 Sauvegarder", use_container_width=True):
            save_notif_cfg({"email": email.strip(), "gmail": gmail.strip(), "app_password": app_pwd})
    if cfg.get("email"):
        if st.button("📨 Email test", use_container_width=True, key="test_email"):
            with st.spinner("Connexion à Gmail… (max 15 s)"):
                ok = send_email("✅ Test Budget App", "<h2>Ça fonctionne !</h2><p>Vos alertes email sont bien configurées.</p>")
            if ok:
                st.success("✅ Email envoyé !")
            else:
                st.error("❌ Échec. Vérifiez : adresse Gmail, mot de passe d'application (pas votre vrai mdp Google), et que la validation en 2 étapes est activée.")


def _render_auto_rules_sidebar() -> None:
    rules = get_auto_rules()
    st.caption("Mots-clés → catégorie automatique pour les dépenses Revolut.")
    for kw in list(rules.keys()):
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"`{kw}` → {rules[kw]}")
        if c2.button("✕", key=f"del_rule_{kw}"):
            del rules[kw]
            save_auto_rules(rules)
            st.rerun()
    with st.form("add_rule_form"):
        c1, c2 = st.columns(2)
        new_kw  = c1.text_input("Mot-clé", placeholder="starbucks")
        new_cat = c2.selectbox("Catégorie", CATEGORIES)
        if st.form_submit_button("➕ Ajouter", use_container_width=True) and new_kw.strip():
            rules[new_kw.strip().lower()] = new_cat
            save_auto_rules(rules)
            st.rerun()


def _render_savings_goal_sidebar() -> None:
    goal = get_savings_goal()
    with st.form("savings_form"):
        label  = st.text_input("Nom de l'objectif", value=goal.get("label", ""), placeholder="Vacances, voiture…")
        target = st.number_input("Montant cible (€)", min_value=0.0, value=float(goal.get("target", 0)), step=50.0)
        if st.form_submit_button("💾 Sauvegarder", use_container_width=True):
            if "settings" not in st.session_state.data:
                st.session_state.data["settings"] = {}
            st.session_state.data["settings"]["savings_goal"] = {"label": label, "target": target}
            save_data()


def _render_categories_sidebar() -> None:
    raw    = _redis().get(f"categories:{st.session_state.username}")
    extras = json.loads(raw) if raw else []
    st.caption("Ajoutez vos propres catégories en plus des catégories par défaut.")
    for i, cat in enumerate(extras):
        c1, c2 = st.columns([5, 1])
        c1.markdown(cat)
        if c2.button("✕", key=f"del_cat_{i}"):
            extras.pop(i)
            save_extra_categories(extras)
            st.rerun()
    with st.form("add_cat_form"):
        new_cat = st.text_input("Nouvelle catégorie", placeholder="🏋️ Sport")
        if st.form_submit_button("➕ Ajouter", use_container_width=True) and new_cat.strip():
            if new_cat.strip() not in CATEGORIES and new_cat.strip() not in extras:
                extras.append(new_cat.strip())
                save_extra_categories(extras)
                st.rerun()


def _render_theme_sidebar() -> None:
    current = get_theme()
    current_name = next((n for n, c in THEMES.items() if c == current), "Indigo")
    chosen = st.selectbox("Couleur principale", list(THEMES.keys()),
                          index=list(THEMES.keys()).index(current_name), key="theme_select")
    if st.button("💾 Appliquer", use_container_width=True, key="apply_theme"):
        if "settings" not in st.session_state.data:
            st.session_state.data["settings"] = {}
        st.session_state.data["settings"]["theme"] = THEMES[chosen]
        save_data()
        st.rerun()
    cols = st.columns(len(THEMES))
    for i, (name, color) in enumerate(THEMES.items()):
        cols[i].markdown(
            f'<div style="background:{color};border-radius:50%;width:24px;height:24px;margin:auto;'
            f'{"border:3px solid white;box-shadow:0 0 0 2px "+color if color==current else ""}"></div>',
            unsafe_allow_html=True,
        )


def _render_reminders_sidebar() -> None:
    settings = st.session_state.data.get("settings", {})
    current_days = int(settings.get("reminder_days", 3))
    st.caption("Email de rappel avant le renouvellement des paiements récurrents.")
    with st.form("reminders_form"):
        days = st.number_input("Jours avant la fin du mois", min_value=1, max_value=15, value=current_days)
        if st.form_submit_button("💾 Sauvegarder", use_container_width=True):
            if "settings" not in st.session_state.data:
                st.session_state.data["settings"] = {}
            st.session_state.data["settings"]["reminder_days"] = int(days)
            save_data()


# ── Ajout rapide ──────────────────────────────────────────────────────────────
def render_quick_add() -> None:
    is_income = st.toggle("💰 Revenu (pas une dépense)", key="qa_is_income")
    c1, c2 = st.columns([3, 1])
    desc = c1.text_input("Description", placeholder="courses, café, salaire…",
                         label_visibility="collapsed", key="qa_desc")
    amt  = c2.number_input("€", min_value=0.01, value=10.0, step=1.0,
                           label_visibility="collapsed", key="qa_amt", format="%.2f")
    c3, c4 = st.columns([3, 1])
    cats = INCOME_CATEGORIES if is_income else get_categories()
    cat = c3.selectbox("Catégorie", cats, label_visibility="collapsed", key="qa_cat")
    if c4.button("➕ Ajouter", use_container_width=True, key="qa_btn", type="primary"):
        active_expenses().append({
            "date": date.today().isoformat(),
            "amount": float(amt),
            "category": cat,
            "description": desc.strip() or "—",
            "type": "income" if is_income else "expense",
        })
        save_data()
        st.rerun()


# ── Formulaire détaillé ───────────────────────────────────────────────────────
def render_expense_form() -> None:
    sym = CURRENCY_SYMBOLS.get(get_currency(), "€")
    st.subheader("➕ Ajouter une transaction")
    with st.form("expense_form", clear_on_submit=True):
        entry_type = st.radio("Type", ["💸 Dépense", "💰 Revenu"], horizontal=True)
        is_income  = entry_type == "💰 Revenu"
        c1, c2 = st.columns(2)
        with c1:
            exp_date = st.date_input("Date", value=date.today())
            amount = st.number_input(f"Montant ({sym})", min_value=0.01, value=1.0, step=0.5, format="%.2f")
        with c2:
            cats = INCOME_CATEGORIES if is_income else get_categories()
            category = st.selectbox("Catégorie", cats)
            description = st.text_input("Description (facultatif)")
        note = st.text_input("Note (facultatif)", placeholder="ex: déj avec Paul, promo -20%…")
        if st.form_submit_button("✅ Ajouter", use_container_width=True, type="primary") and amount > 0:
            entry = {
                "date": exp_date.isoformat(), "amount": float(amount),
                "category": category, "description": description.strip() or "—",
                "type": "income" if is_income else "expense",
            }
            if note.strip():
                entry["note"] = note.strip()
            active_expenses().append(entry)
            save_data()


# ── Import CSV ────────────────────────────────────────────────────────────────
def render_csv_import() -> None:
    with st.expander("📥 Importer depuis un CSV bancaire"):
        st.caption("Colonnes attendues : date, montant, description (noms flexibles)")
        uploaded = st.file_uploader("Fichier CSV", type=["csv"],
                                    label_visibility="collapsed", key="csv_uploader")
        if uploaded is None:
            return
        try:
            df_raw = pd.read_csv(uploaded, sep=None, engine="python", encoding_errors="replace")
        except Exception as e:
            st.error(f"Erreur lecture : {e}")
            return

        st.dataframe(df_raw.head(3), use_container_width=True)
        cols = list(df_raw.columns)
        c1, c2, c3 = st.columns(3)
        col_date = c1.selectbox("Colonne date", cols, key="csv_col_date")
        col_amt  = c2.selectbox("Colonne montant", cols, key="csv_col_amt")
        col_desc = c3.selectbox("Colonne description", ["— aucune —"] + cols, key="csv_col_desc")
        default_cat = st.selectbox("Catégorie par défaut", get_categories(), key="csv_default_cat")

        if st.button("✅ Importer", use_container_width=True, key="csv_do_import"):
            imported, skipped = 0, 0
            for _, row in df_raw.iterrows():
                try:
                    raw_amt = (str(row[col_amt])
                               .replace(",", ".").replace(" ", "")
                               .replace("€", "").replace("\xa0", ""))
                    amt = float(raw_amt)
                    if amt <= 0:
                        skipped += 1
                        continue
                    d = parse_date(str(row[col_date]))
                    desc = str(row[col_desc]).strip() if col_desc != "— aucune —" else "—"
                    active_expenses().append({
                        "date": d, "amount": amt,
                        "category": default_cat, "description": desc,
                    })
                    imported += 1
                except Exception:
                    skipped += 1
            save_data()
            st.success(f"✅ {imported} dépenses importées, {skipped} ignorées.")
            st.rerun()


# ── Métriques (2×2 mobile-friendly) ──────────────────────────────────────────
def render_metrics(summary: dict) -> None:
    c1, c2 = st.columns(2)
    c1.metric(
        "💸 Dépensé", fmt(summary["total_spent"]),
        delta=f"{summary['total_spent'] - summary['budget']:+.0f}",
        delta_color="inverse",
    )
    c2.metric(
        "🏦 Restant", fmt(summary["budget_remaining"]),
        delta=f"{summary['days_remaining']} j restants",
    )
    c3, c4 = st.columns(2)
    c3.metric(
        "🎯 Budget/jour", fmt(summary["daily_remaining"]),
        delta=f"{summary['daily_remaining'] - summary['initial_daily']:+.2f}",
        delta_color="normal",
    )
    forecast_delta = summary["forecast_total"] - summary["budget"]
    c4.metric(
        "🔮 Prévision", fmt(summary["forecast_total"]),
        delta=f"{forecast_delta:+.0f}",
        delta_color="inverse",
    )
    income = summary.get("total_income", 0)
    if income > 0:
        net = income - summary["total_spent"]
        c5, c6 = st.columns(2)
        c5.metric("💰 Revenus", fmt(income))
        c6.metric("📈 Solde net", fmt(net),
                  delta=f"{'+' if net >= 0 else ''}{net:.0f}", delta_color="normal")


# ── Carte de statut ───────────────────────────────────────────────────────────
def render_status_card(summary: dict, df: pd.DataFrame) -> None:
    st.subheader("📊 État du budget")
    status, message = get_status(summary["difference"])
    color_map = {"green": "#28a745", "orange": "#fd7e14", "red": "#dc3545"}
    color_hex = color_map[status]

    if status == "green":
        st.success(message)
    elif status == "orange":
        st.warning(message)
    else:
        st.error(message)

    st.markdown(f"""
    <div class="budget-card">
        <p class="card-label">Budget quotidien restant</p>
        <p class="big-daily" style="color:{color_hex};">{fmt(summary['daily_remaining'])}</p>
        <p class="card-label">pour les <strong>{summary['days_remaining']}</strong> jours restants</p>
    </div>
    """, unsafe_allow_html=True)

    diff = summary["difference"]
    sign = "+" if diff >= 0 else ""
    forecast_ok = summary["forecast_total"] <= summary["budget"]
    sym = CURRENCY_SYMBOLS.get(get_currency(), "€")
    st.markdown(f"""
| Indicateur | Valeur |
|---|---|
| Rythme idéal à ce jour | {fmt(summary['ideal_spent'])} |
| Réellement dépensé | {fmt(summary['total_spent'])} |
| Écart | **{sign}{diff:.2f} {sym}** |
| Moyenne/jour | {fmt(summary['avg_daily'])}/j |
| Prévision fin de mois | **{fmt(summary['forecast_total'])}** {'✅' if forecast_ok else '⚠️'} |
    """)

    alerts = get_category_alerts(df, active_cat_budgets())
    if alerts:
        st.markdown("**⚠️ Alertes enveloppes :**")
        for cat, (color, spent, limit, pct) in alerts.items():
            bg = "#fff3cd" if color == "orange" else "#f8d7da"
            border = "#fd7e14" if color == "orange" else "#dc3545"
            st.markdown(
                f'<div class="cat-pill" style="background:{bg};border-left:4px solid {border};">'
                f'{cat} — {fmt(spent)} / {fmt(limit)} ({pct*100:.0f}%)</div>',
                unsafe_allow_html=True,
            )


# ── Top 5 marchands ───────────────────────────────────────────────────────────
def render_top_merchants(df: pd.DataFrame) -> None:
    if df.empty:
        return
    desc_df = df[~df["description"].isin(["—", ""])].copy()
    if desc_df.empty or len(desc_df) < 3:
        return
    top = (desc_df.groupby("description")["amount"]
                  .sum()
                  .sort_values(ascending=False)
                  .head(5)
                  .reset_index())
    top.columns = ["Marchand", "Total"]
    theme = get_theme()
    st.markdown("**🏆 Top 5 marchands**")
    max_val = top["Total"].max()
    for _, row in top.iterrows():
        pct = row["Total"] / max_val if max_val > 0 else 0
        st.markdown(
            f'<div style="margin:.3rem 0;">'
            f'<div style="display:flex;justify-content:space-between;margin-bottom:4px;">'
            f'<span style="font-size:.9rem;font-weight:500">{row["Marchand"][:28]}</span>'
            f'<strong style="font-size:.9rem;color:{theme}">{fmt(row["Total"])}</strong></div>'
            f'<div style="background:#F0F0F8;border-radius:6px;height:6px;">'
            f'<div style="background:{theme};width:{pct*100:.0f}%;height:6px;border-radius:6px;'
            f'transition:width .3s ease;"></div></div></div>',
            unsafe_allow_html=True,
        )


# ── Tableau des dépenses (éditable) ──────────────────────────────────────────
def render_expense_table(df: pd.DataFrame) -> None:
    st.subheader("📋 Historique")

    c1, c2 = st.columns([3, 1])
    search = c1.text_input("🔍 Rechercher", placeholder="description ou catégorie…",
                           label_visibility="collapsed", key="tbl_search")
    cat_filter = c2.selectbox("Catégorie", ["Toutes"] + CATEGORIES,
                              label_visibility="collapsed", key="tbl_cat")

    if df.empty:
        st.info("💡 Aucune dépense enregistrée. Ajoutez votre première dépense ci-dessus !")
        return

    edit_df = df.copy()
    edit_df["date"] = pd.to_datetime(edit_df["date"]).dt.date
    edit_df = edit_df.sort_values("date", ascending=False).reset_index(drop=True)

    col_cfg = {
        "date":        st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
        "amount":      st.column_config.NumberColumn(f"Montant ({CURRENCY_SYMBOLS.get(get_currency(), '€')})", format="%.2f", min_value=0.01),
        "category":    st.column_config.SelectboxColumn("Catégorie", options=CATEGORIES, required=True),
        "description": st.column_config.TextColumn("Description", max_chars=120),
    }
    if "type" in edit_df.columns:
        col_cfg["type"] = st.column_config.SelectboxColumn("Type", options=["expense", "income"])

    edited = st.data_editor(
        edit_df,
        column_config=col_cfg,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="expense_editor",
    )

    view_df = df.copy()
    if search:
        mask = (view_df["description"].str.contains(search, case=False, na=False) |
                view_df["category"].str.contains(search, case=False, na=False))
        view_df = view_df[mask]
    if cat_filter != "Toutes":
        view_df = view_df[view_df["category"] == cat_filter]

    c_save, c_info, c_export = st.columns([1, 2, 1])

    if c_save.button("💾 Sauvegarder", use_container_width=True, type="primary", key="save_edits"):
        edited["date"] = pd.to_datetime(edited["date"], errors="coerce")
        edited = edited.dropna(subset=["date", "amount"])
        edited["date"] = edited["date"].dt.strftime("%Y-%m-%d")
        edited["amount"] = edited["amount"].astype(float)
        st.session_state.data[st.session_state.active_month]["expenses"] = edited.to_dict("records")
        save_data()
        st.rerun()

    c_info.caption(
        f"**{len(view_df)}** transaction(s) · "
        f"Total filtré : **{fmt(view_df['amount'].sum())}**"
    )
    c_export.download_button(
        label="⬇️ CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"budget_{st.session_state.active_month}.csv",
        mime="text/csv",
        use_container_width=True,
    )


# ── Graphiques ────────────────────────────────────────────────────────────────
_PALETTE = ["#6366F1","#22D3EE","#F59E0B","#10B981","#F43F5E","#A78BFA","#FB923C","#34D399","#60A5FA","#E879F9","#FBBF24"]
_CFG     = {"scrollZoom": False, "displayModeBar": False, "doubleClick": False}
_LAYOUT  = dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter,system-ui,sans-serif", size=13, color="#374151"),
    margin=dict(l=8, r=8, t=44, b=8),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font_size=12),
    hoverlabel=dict(bgcolor="white", font_size=13, bordercolor="#E5E7EB"),
)

def _base_layout(**kw):
    d = dict(_LAYOUT)
    d.update(kw)
    return d

def render_charts(df: pd.DataFrame, summary: dict) -> None:
    tab1, tab2, tab3, tab4 = st.tabs(["📅 Par jour", "🏷️ Catégories", "📈 Progression", "📆 Tendances"])

    with tab1:
        daily = df.groupby("date")["amount"].sum().reset_index().sort_values("date")
        daily.columns = ["Date", "Montant"]
        fig = px.bar(
            daily, x="Date", y="Montant",
            color="Montant", color_continuous_scale=[[0,"#C7D2FE"],[1,"#4F46E5"]],
            text_auto=".0f",
        )
        fig.update_traces(
            marker_line_width=0,
            textfont_size=11, textposition="outside",
            hovertemplate="<b>%{x}</b><br>%{y:.2f} €<extra></extra>",
        )
        fig.update_layout(_base_layout(
            title=dict(text="Dépenses par jour", font_size=15, x=0.5, xanchor="center"),
            coloraxis_showscale=False,
            yaxis=dict(showgrid=True, gridcolor="#F3F4F6", zeroline=False),
            xaxis=dict(showgrid=False),
        ))
        st.plotly_chart(fig, use_container_width=True, config=_CFG)

    with tab2:
        by_cat = df.groupby("category")["amount"].sum().reset_index().sort_values("amount", ascending=False)
        by_cat.columns = ["Catégorie", "Montant"]
        fig = go.Figure(go.Pie(
            labels=by_cat["Catégorie"], values=by_cat["Montant"],
            hole=0.55,
            marker=dict(colors=_PALETTE, line=dict(color="white", width=2)),
            textinfo="percent", textposition="outside",
            hovertemplate="<b>%{label}</b><br>%{value:.2f} €  ·  %{percent}<extra></extra>",
            pull=[0.05] + [0] * (len(by_cat) - 1),
        ))
        total = by_cat["Montant"].sum()
        fig.add_annotation(text=f"<b>{total:.0f} €</b>", x=0.5, y=0.5,
                           font=dict(size=18, color="#111827"), showarrow=False)
        fig.update_layout(_base_layout(
            title=dict(text="Répartition des dépenses", font_size=15, x=0.5, xanchor="center"),
            showlegend=True,
        ))
        st.plotly_chart(fig, use_container_width=True, config=_CFG)

        cat_budgets = active_cat_budgets()
        limits = {cat: lim for cat, lim in cat_budgets.items() if lim > 0}
        if limits:
            spent_map = by_cat.set_index("Catégorie")["Montant"].to_dict()
            rows = [{"Catégorie": cat, "Dépensé": spent_map.get(cat, 0.0), "Budget": lim}
                    for cat, lim in limits.items()]
            df_lim = pd.DataFrame(rows).sort_values("Dépensé", ascending=True)
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                name="Budget", y=df_lim["Catégorie"], x=df_lim["Budget"],
                orientation="h", marker_color="#E0E7FF", marker_line_width=0,
            ))
            fig2.add_trace(go.Bar(
                name="Dépensé", y=df_lim["Catégorie"], x=df_lim["Dépensé"],
                orientation="h", marker_color="#6366F1", marker_line_width=0,
                hovertemplate="<b>%{y}</b><br>Dépensé : %{x:.2f} €<extra></extra>",
            ))
            fig2.update_layout(_base_layout(
                title=dict(text="Budget vs Dépenses par catégorie", font_size=15, x=0.5, xanchor="center"),
                barmode="overlay",
                xaxis=dict(showgrid=True, gridcolor="#F3F4F6"),
                yaxis=dict(showgrid=False),
                height=max(250, len(limits) * 42),
            ))
            st.plotly_chart(fig2, use_container_width=True, config=_CFG)

    with tab3:
        total_days    = summary["total_days"]
        initial_daily = summary["initial_daily"]
        ideal_x = list(range(0, total_days + 1))
        ideal_y = [initial_daily * d for d in ideal_x]

        daily_cum = df.groupby("date")["amount"].sum().reset_index().sort_values("date")
        daily_cum["cumsum"] = daily_cum["amount"].cumsum()
        try:
            key       = st.session_state.active_month
            first_day = date(int(key[:4]), int(key[5:]), 1)
            days_nums = [(date.fromisoformat(d) - first_day).days + 1 for d in daily_cum["date"]]
        except Exception:
            days_nums = list(range(1, len(daily_cum) + 1))

        days_elapsed = summary["days_elapsed"]
        avg_daily    = summary["avg_daily"]
        forecast_x   = list(range(days_elapsed, total_days + 1))
        forecast_y   = [summary["total_spent"] + avg_daily * (d - days_elapsed) for d in forecast_x]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=ideal_x, y=ideal_y, mode="lines", name="Rythme idéal",
            line=dict(color="#10B981", dash="dash", width=2),
            hovertemplate="Jour %{x} — idéal : %{y:.2f} €<extra></extra>",
        ))
        if not daily_cum.empty:
            fig.add_trace(go.Scatter(
                x=days_nums, y=daily_cum["cumsum"].tolist(),
                mode="lines+markers", name="Réel",
                line=dict(color="#6366F1", width=3),
                marker=dict(size=7, color="#6366F1", line=dict(color="white", width=2)),
                fill="tozeroy", fillcolor="rgba(99,102,241,0.08)",
                hovertemplate="Jour %{x} — %{y:.2f} €<extra></extra>",
            ))
        if len(forecast_x) > 1:
            fig.add_trace(go.Scatter(
                x=forecast_x, y=forecast_y, mode="lines", name="Prévision",
                line=dict(color="#F59E0B", dash="dot", width=2),
                hovertemplate="Jour %{x} — prévision : %{y:.2f} €<extra></extra>",
            ))
        fig.update_layout(_base_layout(
            title=dict(text="Progression cumulée", font_size=15, x=0.5, xanchor="center"),
            xaxis=dict(title="Jour du mois", showgrid=False),
            yaxis=dict(title="€ cumulés", showgrid=True, gridcolor="#F3F4F6", zeroline=False),
        ))
        st.plotly_chart(fig, use_container_width=True, config=_CFG)

    with tab4:
        months = get_month_keys()
        if len(months) < 2:
            st.info("Il faut au moins 2 mois de données pour afficher les tendances.")
        else:
            rows = []
            for key in months:
                expenses = st.session_state.data[key].get("expenses", [])
                if not expenses:
                    continue
                df_m = pd.DataFrame(expenses)
                df_m["amount"] = df_m["amount"].astype(float)
                for cat, total in df_m.groupby("category")["amount"].sum().items():
                    rows.append({"Mois": month_label(key), "Catégorie": cat, "Montant": total})
            if rows:
                df_trends   = pd.DataFrame(rows)
                all_cats    = df_trends["Catégorie"].unique().tolist()
                selected_cats = st.multiselect(
                    "Catégories à afficher", all_cats,
                    default=all_cats[:min(5, len(all_cats))], key="trend_cats",
                )
                if selected_cats:
                    df_f = df_trends[df_trends["Catégorie"].isin(selected_cats)]
                    fig  = px.line(
                        df_f, x="Mois", y="Montant", color="Catégorie",
                        markers=True, color_discrete_sequence=_PALETTE,
                    )
                    fig.update_traces(
                        line_width=2.5, marker_size=8,
                        marker=dict(line=dict(color="white", width=2)),
                    )
                    fig.update_layout(_base_layout(
                        title=dict(text="Tendances mensuelles", font_size=15, x=0.5, xanchor="center"),
                        xaxis=dict(showgrid=False),
                        yaxis=dict(showgrid=True, gridcolor="#F3F4F6", zeroline=False),
                    ))
                    st.plotly_chart(fig, use_container_width=True, config=_CFG)


# ── Auto-catégorisation ───────────────────────────────────────────────────────
DEFAULT_AUTO_RULES = {
    "mcdonald": "🍽️ Restaurant", "burger": "🍽️ Restaurant", "pizza": "🍽️ Restaurant",
    "kebab": "🍽️ Restaurant", "sushi": "🍽️ Restaurant", "boulangerie": "🍔 Alimentation",
    "netflix": "📱 Abonnements", "spotify": "📱 Abonnements", "disney": "📱 Abonnements",
    "amazon prime": "📱 Abonnements", "apple": "📱 Abonnements", "sfr": "📱 Abonnements",
    "orange": "📱 Abonnements", "bouygues": "📱 Abonnements", "free": "📱 Abonnements",
    "uber": "🚗 Transport", "sncf": "🚗 Transport", "blablacar": "🚗 Transport",
    "essence": "🚗 Transport", "total": "🚗 Transport", "bp ": "🚗 Transport",
    "carrefour": "🍔 Alimentation", "leclerc": "🍔 Alimentation", "lidl": "🍔 Alimentation",
    "aldi": "🍔 Alimentation", "monoprix": "🍔 Alimentation", "intermarché": "🍔 Alimentation",
    "pharmacie": "💊 Santé", "médecin": "💊 Santé", "docteur": "💊 Santé",
    "cinema": "🎮 Loisirs", "cinéma": "🎮 Loisirs", "steam": "🎮 Loisirs",
    "zara": "👗 Vêtements", "h&m": "👗 Vêtements", "decathlon": "👗 Vêtements",
    "loyer": "🏠 Logement / Factures", "edf": "🏠 Logement / Factures",
}

def get_auto_rules() -> dict:
    raw = _redis().get(f"auto_rules:{st.session_state.username}")
    return json.loads(raw) if raw else dict(DEFAULT_AUTO_RULES)

def save_auto_rules(rules: dict) -> None:
    _redis().set(f"auto_rules:{st.session_state.username}", json.dumps(rules, ensure_ascii=False))

def auto_categorize(description: str) -> str:
    desc = description.lower()
    for kw, cat in get_auto_rules().items():
        if kw in desc:
            return cat
    return CATEGORIES[-1]


# ── Notifications email ───────────────────────────────────────────────────────
def get_notif_cfg() -> dict:
    return st.session_state.data.get("settings", {}).get("notifications", {})

def save_notif_cfg(cfg: dict) -> None:
    if "settings" not in st.session_state.data:
        st.session_state.data["settings"] = {}
    st.session_state.data["settings"]["notifications"] = cfg
    save_data()

def send_email(subject: str, html: str) -> bool:
    cfg = get_notif_cfg()
    to, gmail, pwd = cfg.get("email", ""), cfg.get("gmail", ""), cfg.get("app_password", "")
    if not all([to, gmail, pwd]):
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = gmail
    msg["To"]      = to
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as s:
            s.login(gmail, pwd)
            s.sendmail(gmail, to, msg.as_string())
        return True
    except Exception:
        pass
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as s:
            s.ehlo()
            s.starttls()
            s.login(gmail, pwd)
            s.sendmail(gmail, to, msg.as_string())
        return True
    except Exception:
        return False

def check_budget_alert() -> None:
    if not get_notif_cfg().get("email"):
        return
    df = build_df()
    if df.empty:
        return
    summary = compute_summary(active_config(), df)
    pct = summary["total_spent"] / summary["budget"] if summary["budget"] > 0 else 0
    month, user = st.session_state.active_month, st.session_state.username
    for threshold, label, color, icon in [
        (1.0, "100", "#dc3545", "🔴"), (0.8, "80", "#fd7e14", "⚠️")
    ]:
        if pct >= threshold:
            key = f"alert:{user}:{month}:{label}"
            if not _redis().get(key):
                _redis().setex(key, 60 * 60 * 24 * 35, "1")
                send_email(
                    f"{icon} Budget {label}% — {month_label(month)}",
                    f"""<div style="font-family:sans-serif;max-width:480px;margin:auto">
                    <h2 style="color:{color}">{icon} Budget {label}% atteint</h2>
                    <p>Dépensé : <strong>{fmt(summary['total_spent'])}</strong> / {fmt(summary['budget'])} ({pct*100:.0f}%)</p>
                    <p>Restant : <strong>{fmt(summary['budget_remaining'])}</strong> pour {summary['days_remaining']} jours</p>
                    <p>Budget quotidien recalculé : <strong>{fmt(summary['daily_remaining'])}/j</strong></p>
                    </div>"""
                )
            break
    # Alertes catégories dépassées
    exp = expense_df(df)
    alerts = get_category_alerts(exp, active_cat_budgets())
    for cat, (color, spent, limit, cat_pct) in alerts.items():
        if cat_pct >= 1.0:
            cat_key = f"cat_alert:{user}:{month}:{cat}"
            if not _redis().get(cat_key):
                _redis().setex(cat_key, 60 * 60 * 24 * 35, "1")
                send_email(
                    f"⚠️ Enveloppe {cat} dépassée",
                    f"""<div style="font-family:sans-serif;max-width:480px;margin:auto">
                    <h2 style="color:#dc3545">⚠️ Enveloppe dépassée</h2>
                    <p>Catégorie : <strong>{cat}</strong></p>
                    <p>Dépensé : <strong>{fmt(spent)}</strong> / Budget : {fmt(limit)} ({cat_pct*100:.0f}%)</p>
                    </div>"""
                )

def check_weekly_alerts() -> None:
    if not get_notif_cfg().get("email"):
        return
    user = st.session_state.username
    last = _redis().get(f"weekly:{user}")
    if last and (time.time() - float(last)) < 7 * 24 * 3600:
        return
    _redis().set(f"weekly:{user}", str(time.time()))
    df = build_df()
    if df.empty:
        return
    today = date.today()
    df_dates = df.copy()
    df_dates["date"] = pd.to_datetime(df_dates["date"])
    w0 = pd.Timestamp(today) - pd.Timedelta(days=7)
    w1 = w0 - pd.Timedelta(days=7)
    this_week = df_dates[df_dates["date"] >= w0]["amount"].sum()
    prev_week = df_dates[(df_dates["date"] >= w1) & (df_dates["date"] < w0)]["amount"].sum()
    diff = this_week - prev_week
    color = "#dc3545" if diff > 0 else "#22C55E"
    sign = "+" if diff > 0 else ""
    summary = compute_summary(active_config(), df)
    by_cat = df_dates[df_dates["date"] >= w0].groupby("category")["amount"].sum().sort_values(ascending=False).head(3)
    cats_html = "".join(f"<tr><td>{c}</td><td><b>{a:.2f} €</b></td></tr>" for c, a in by_cat.items())
    title = "⚠️ Dépenses en hausse cette semaine" if diff > summary["initial_daily"] else "📊 Résumé hebdomadaire"
    send_email(title, f"""<div style="font-family:sans-serif;max-width:480px;margin:auto">
        <h2>{title}</h2>
        <p>Semaine du {(today - pd.Timedelta(days=7)).strftime('%d/%m')} au {today.strftime('%d/%m')}</p>
        <p>Cette semaine : <strong>{this_week:.2f} €</strong></p>
        <p>Vs semaine précédente : <span style="color:{color}"><strong>{sign}{diff:.2f} €</strong></span></p>
        <h3>Top catégories :</h3><table>{cats_html}</table><hr>
        <p>Budget restant : <strong>{fmt(summary['budget_remaining'])}</strong> · {summary['days_remaining']} jours</p>
        </div>""")


# ── Objectif d'épargne ────────────────────────────────────────────────────────
def get_savings_goal() -> dict:
    return st.session_state.data.get("settings", {}).get("savings_goal", {})

def render_savings_goal(summary: dict) -> None:
    goal = get_savings_goal()
    if not goal or not goal.get("target"):
        return
    saved  = max(0.0, summary["budget_remaining"])
    target = float(goal["target"])
    label  = goal.get("label", "Objectif")
    pct    = min(1.0, saved / target) if target > 0 else 0
    color  = "#22C55E" if pct >= 1.0 else "#6366F1"
    st.markdown(f"""
    <div class="budget-card">
        <p class="card-label">🎯 {label}</p>
        <p class="big-daily" style="color:{color};font-size:2rem;">{fmt(saved)} / {fmt(target)}</p>
        <div style="background:#E5E7EB;border-radius:99px;height:10px;margin:.5rem 0;">
            <div style="background:{color};width:{pct*100:.1f}%;height:10px;border-radius:99px;"></div>
        </div>
        <p class="card-label">{'🎉 Objectif atteint !' if pct >= 1.0 else f'{pct*100:.0f}% atteint'}</p>
    </div>""", unsafe_allow_html=True)


# ── Détection des abonnements ─────────────────────────────────────────────────
def detect_subscriptions() -> list:
    months = get_month_keys()
    if len(months) < 2:
        return []
    desc_months  = defaultdict(set)
    desc_amounts = defaultdict(list)
    for month in months:
        for e in st.session_state.data[month].get("expenses", []):
            desc = e.get("description", "").strip()
            if desc and desc != "—" and not desc.startswith("[Récurrent]"):
                desc_months[desc].add(month)
                desc_amounts[desc].append(float(e["amount"]))
    subs = []
    for desc, mset in desc_months.items():
        if len(mset) >= 2:
            amounts = desc_amounts[desc]
            avg = sum(amounts) / len(amounts)
            if avg > 0 and all(abs(a - avg) / avg < 0.25 for a in amounts):
                subs.append({"description": desc, "avg_amount": avg, "months": len(mset)})
    return sorted(subs, key=lambda x: x["avg_amount"], reverse=True)


# ── Règle 50/30/20 ───────────────────────────────────────────────────────────
def render_budget_5030(summary: dict, df: pd.DataFrame) -> None:
    income = summary.get("total_income", 0)
    base   = income if income > 0 else summary["budget"]
    label  = "vos revenus" if income > 0 else "votre budget"
    st.caption(f"Basé sur {label} : **{fmt(base)}**")
    exp = expense_df(df)
    needs = float(exp[exp["category"].isin(NEEDS_CATS)]["amount"].sum()) if not exp.empty else 0
    wants = float(exp[exp["category"].isin(WANTS_CATS)]["amount"].sum()) if not exp.empty else 0
    savings = max(0.0, summary["budget_remaining"])
    for emoji, lbl, pct_rec, spent in [
        ("🏠", "Besoins", 0.50, needs),
        ("🎮", "Envies",  0.30, wants),
        ("🏦", "Épargne", 0.20, savings),
    ]:
        rec  = base * pct_rec
        pct  = min(1.0, spent / rec) if rec > 0 else 0
        over = spent > rec
        icon = "⚠️" if over else "✅"
        st.markdown(f"**{icon} {emoji} {lbl} ({int(pct_rec*100)}%)** — {fmt(spent)} / {fmt(rec)} recommandé")
        st.progress(pct)


# ── Rappels de paiement ───────────────────────────────────────────────────────
def check_payment_reminders() -> None:
    if not get_notif_cfg().get("email"):
        return
    recurring = get_recurring()
    if not recurring:
        return
    reminder_days = int(st.session_state.data.get("settings", {}).get("reminder_days", 3))
    today = date.today()
    cfg   = active_config()
    days_left = int(cfg.get("days_in_month", 30)) - today.day
    if days_left > reminder_days:
        return
    user = st.session_state.username
    key  = f"reminder:{user}:{today.strftime('%Y-%m')}"
    if _redis().get(key):
        return
    _redis().setex(key, 60 * 60 * 24 * 35, "1")
    rows = "".join(
        f"<tr><td style='padding:4px 8px'>{r['description']}</td>"
        f"<td style='padding:4px 8px'><b>{r['amount']:.2f}€</b></td>"
        f"<td style='padding:4px 8px;color:#6B7280'>{r['category']}</td></tr>"
        for r in recurring
    )
    total_rec = sum(r["amount"] for r in recurring)
    send_email(
        f"🔔 {len(recurring)} paiements récurrents dans {days_left} jour(s)",
        f"""<div style="font-family:sans-serif;max-width:520px;margin:auto;padding:20px">
        <h2 style="color:#6366F1">🔔 Paiements à venir</h2>
        <p>Dans <strong>{days_left} jour(s)</strong>, les paiements suivants seront prélevés :</p>
        <table style="width:100%;border-collapse:collapse;background:#F9FAFB">{rows}</table>
        <p><b>Total : {total_rec:.2f}€</b></p>
        </div>""",
    )


# ── Vue calendrier ────────────────────────────────────────────────────────────
def render_calendar(df: pd.DataFrame) -> None:
    import calendar as cal_mod
    month_key = st.session_state.active_month
    y, m = int(month_key[:4]), int(month_key[5:])
    daily = {}
    if not df.empty:
        dc = df.copy()
        dc["day"] = pd.to_datetime(dc["date"]).dt.day
        for d, amt in dc.groupby("day")["amount"].sum().items():
            daily[int(d)] = float(amt)
    max_amt = max(daily.values()) if daily else 1
    weeks   = cal_mod.monthcalendar(y, m)
    today_d = date.today().day if month_key == date.today().strftime("%Y-%m") else -1
    theme   = get_theme()

    html = '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:3px;">'
    for dn in ["L","M","M","J","V","S","D"]:
        html += f'<div style="text-align:center;font-size:11px;color:#9CA3AF;padding:3px">{dn}</div>'
    for week in weeks:
        for day in week:
            if day == 0:
                html += "<div></div>"
                continue
            amt = daily.get(day, 0)
            intensity = (amt / max_amt) ** 0.6 if max_amt > 0 and amt > 0 else 0
            r, g, b = int(99 + (99-99)*intensity), int(102 - 102*intensity), int(241 - 200*intensity)
            bg = f"rgba({r},{g},{b},{intensity*0.85:.2f})" if amt > 0 else "#F9FAFB"
            tc = "white" if intensity > 0.45 else "#374151"
            bd = f"2px solid {theme}" if day == today_d else "1px solid #E5E7EB"
            amt_html = f'<div style="font-size:9px">{amt:.0f}€</div>' if amt > 0 else ""
            html += (f'<div style="background:{bg};color:{tc};border:{bd};border-radius:8px;'
                     f'padding:5px 2px;text-align:center;min-height:44px;">'
                     f'<div style="font-size:11px;font-weight:600">{day}</div>'
                     f'{amt_html}'
                     f"</div>")
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ── Budget annuel ─────────────────────────────────────────────────────────────
def render_annual_view() -> None:
    year = st.selectbox("Année", [date.today().year, date.today().year - 1], key="annual_year")
    months_keys = [f"{year:04d}-{m:02d}" for m in range(1, 13)]
    rows = []
    for mk in months_keys:
        if mk in st.session_state.data:
            md  = st.session_state.data[mk]
            exp = md.get("expenses", [])
            tot = sum(float(e["amount"]) for e in exp)
            bgt = float(md.get("config", {}).get("monthly_budget", 0))
            rows.append({"Mois": MOIS_FR[int(mk[5:])-1], "Budget": bgt, "Dépensé": tot, "Économisé": max(0, bgt-tot)})
    if not rows:
        st.info("Aucune donnée pour cette année.")
        return
    df_y = pd.DataFrame(rows)
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Budget annuel",  f"{df_y['Budget'].sum():.0f} €")
    c2.metric("💸 Total dépensé",  f"{df_y['Dépensé'].sum():.0f} €")
    c3.metric("🏦 Total économisé",f"{df_y['Économisé'].sum():.0f} €")
    fig = go.Figure()
    theme = get_theme()
    fig.add_trace(go.Bar(name="Budget",  x=df_y["Mois"], y=df_y["Budget"],  marker_color="#E0E7FF", marker_line_width=0))
    fig.add_trace(go.Bar(name="Dépensé", x=df_y["Mois"], y=df_y["Dépensé"], marker_color=theme,      marker_line_width=0))
    fig.update_layout(_base_layout(
        title=dict(text=f"Budget vs Dépenses {year}", font_size=15, x=0.5, xanchor="center"),
        barmode="overlay",
    ))
    st.plotly_chart(fig, use_container_width=True, config=_CFG)


# ── Rapport mensuel automatique ───────────────────────────────────────────────
def check_monthly_report() -> None:
    if not get_notif_cfg().get("email") or date.today().day != 1:
        return
    user  = st.session_state.username
    today = date.today()
    key   = f"monthly_report:{user}:{today.strftime('%Y-%m')}"
    if _redis().get(key):
        return
    _redis().setex(key, 60 * 60 * 24 * 35, "1")
    m = today.month - 1 or 12
    y = today.year if today.month > 1 else today.year - 1
    mk = f"{y:04d}-{m:02d}"
    if mk not in st.session_state.data:
        return
    md  = st.session_state.data[mk]
    exp = md.get("expenses", [])
    if not exp:
        return
    df_m  = pd.DataFrame(exp)
    df_m["amount"] = df_m["amount"].astype(float)
    total  = df_m["amount"].sum()
    budget = float(md.get("config", {}).get("monthly_budget", 0))
    saved  = budget - total
    by_cat = df_m.groupby("category")["amount"].sum().sort_values(ascending=False)
    rows_h = "".join(f"<tr><td style='padding:4px 8px'>{c}</td><td style='padding:4px 8px'><b>{a:.2f}€</b></td><td style='padding:4px 8px;color:#6B7280'>{a/total*100:.0f}%</td></tr>"
                     for c, a in by_cat.items())
    status = ("✅ Mois sous budget" if saved > 0 else "❌ Dépassement de budget")
    send_email(
        f"📊 Rapport {month_label(mk)}",
        f"""<div style="font-family:sans-serif;max-width:520px;margin:auto;padding:20px">
        <h1 style="color:#6366F1">📊 Rapport {month_label(mk)}</h1>
        <h2>{status}</h2>
        <table style="width:100%;border-collapse:collapse">
        <tr><td>Budget</td><td><b>{budget:.2f}€</b></td></tr>
        <tr><td>Dépensé</td><td><b>{total:.2f}€</b></td></tr>
        <tr><td>{'Économisé' if saved>0 else 'Dépassement'}</td><td><b style="color:{'#22C55E' if saved>0 else '#EF4444'}">{abs(saved):.2f}€</b></td></tr>
        </table><br>
        <h3>Détail par catégorie</h3>
        <table style="width:100%;border-collapse:collapse;background:#F9FAFB">{rows_h}</table>
        </div>""",
    )


# ── Puis-je me permettre ça ? ────────────────────────────────────────────────
def render_affordability(summary: dict) -> None:
    amount = st.number_input("Montant de la dépense envisagée", min_value=0.01, value=50.0, step=5.0, key="afford_amt")
    remaining = summary["budget_remaining"]
    daily = summary["daily_remaining"]
    days_impact = amount / daily if daily > 0 else 999

    if amount <= remaining * 0.2:
        color, icon, msg = "#22C55E", "✅", "Oui, sans problème !"
    elif amount <= remaining * 0.5:
        color, icon, msg = "#F59E0B", "⚠️", "Oui, mais surveillez la suite."
    elif amount <= remaining:
        color, icon, msg = "#F97316", "😬", "Possible, mais ça va serrer."
    else:
        color, icon, msg = "#EF4444", "❌", "Non — ça dépasse votre budget restant."

    pct = (amount / remaining * 100) if remaining > 0 else 999
    st.markdown(f"""
    <div class="budget-card" style="border-left:4px solid {color};">
        <p class="big-daily" style="color:{color};font-size:2rem;">{icon} {msg}</p>
        <p style="text-align:center">Cette dépense = <strong>{pct:.0f}%</strong> du budget restant
        · impact <strong>{days_impact:.1f} jours</strong></p>
    </div>""", unsafe_allow_html=True)


# ── Vue hebdomadaire ──────────────────────────────────────────────────────────
def render_weekly_view(df: pd.DataFrame, summary: dict) -> None:
    df_w = df.copy()
    df_w["date"] = pd.to_datetime(df_w["date"])
    df_w["semaine"] = df_w["date"].apply(lambda d: f"Sem. {(d.day - 1) // 7 + 1}")
    weekly = df_w.groupby("semaine")["amount"].sum().reset_index().sort_values("semaine")
    weekly.columns = ["Semaine", "Dépensé"]
    weekly_budget = summary["budget"] / 4.33

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=weekly["Semaine"], y=weekly["Dépensé"],
        marker_color=[("#EF4444" if v > weekly_budget else "#6366F1") for v in weekly["Dépensé"]],
        marker_line_width=0,
        hovertemplate="<b>%{x}</b><br>%{y:.2f} €<extra></extra>",
    ))
    fig.add_hline(y=weekly_budget, line_dash="dash", line_color="#10B981",
                  annotation_text=f"Budget/sem : {weekly_budget:.0f} €",
                  annotation_position="top right")
    fig.update_layout(_base_layout(
        title=dict(text="Dépenses par semaine", font_size=15, x=0.5, xanchor="center"),
        yaxis=dict(showgrid=True, gridcolor="#F3F4F6", zeroline=False),
        xaxis=dict(showgrid=False),
    ))
    st.plotly_chart(fig, use_container_width=True, config=_CFG)

    c1, c2, c3, c4 = st.columns(4)
    for col, (_, row) in zip([c1, c2, c3, c4], weekly.iterrows()):
        delta = row["Dépensé"] - weekly_budget
        col.metric(row["Semaine"], f"{row['Dépensé']:.0f} €",
                   delta=f"{delta:+.0f} €", delta_color="inverse")


# ── Import CSV Revolut ────────────────────────────────────────────────────────
def render_revolut_csv_import() -> None:
    with st.expander("📥 Importer historique Revolut (CSV)"):
        st.caption("Revolut App → Profil → Relevés → Exporter CSV")
        uploaded = st.file_uploader("Fichier CSV Revolut", type=["csv"], key="revolut_csv_up")
        if uploaded is None:
            return
        try:
            df_raw = pd.read_csv(uploaded, encoding_errors="replace")
        except Exception as e:
            st.error(f"Erreur : {e}")
            return

        revolut_cols = {"Completed Date", "Description", "Amount"}
        if not revolut_cols.issubset(set(df_raw.columns)):
            st.error("Ce fichier ne ressemble pas à un export Revolut. Colonnes attendues : Completed Date, Description, Amount.")
            return

        df_exp = df_raw.copy()
        if "State" in df_exp.columns:
            df_exp = df_exp[df_exp["State"] == "COMPLETED"]
        df_exp = df_exp[pd.to_numeric(df_exp["Amount"], errors="coerce") < 0].copy()
        df_exp["amount"]      = pd.to_numeric(df_exp["Amount"]).abs()
        df_exp["date"]        = pd.to_datetime(df_exp["Completed Date"], errors="coerce").dt.strftime("%Y-%m-%d")
        df_exp["description"] = df_exp["Description"].astype(str).str[:80]
        df_exp["category"]    = df_exp["description"].apply(auto_categorize)
        df_exp = df_exp.dropna(subset=["date", "amount"])

        st.dataframe(df_exp[["date","description","amount","category"]].head(10), use_container_width=True)
        st.caption(f"{len(df_exp)} transactions détectées")

        if st.button("✅ Importer tout", use_container_width=True, key="do_revolut_import", type="primary"):
            imported = 0
            for _, row in df_exp.iterrows():
                mk = row["date"][:7]
                ensure_month(mk)
                st.session_state.data[mk]["expenses"].append({
                    "date": row["date"], "amount": float(row["amount"]),
                    "category": row["category"], "description": row["description"],
                })
                imported += 1
            save_data()
            st.success(f"✅ {imported} transactions importées !")
            st.rerun()


# ── Évolution 6 mois ──────────────────────────────────────────────────────────
def render_6month_trend() -> None:
    all_keys = get_month_keys()
    months = sorted(all_keys)[-6:]
    if len(months) < 2:
        return
    rows = []
    for mk in months:
        md    = st.session_state.data.get(mk, {})
        exps  = [e for e in md.get("expenses", []) if e.get("type", "expense") == "expense"]
        total = sum(float(e["amount"]) for e in exps)
        bgt   = float(md.get("config", {}).get("monthly_budget", 0))
        rows.append({"Mois": month_label(mk), "Dépensé": round(total, 2), "Budget": round(bgt, 2)})
    df_t  = pd.DataFrame(rows)
    theme = get_theme()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_t["Mois"], y=df_t["Budget"],
        name="Budget", marker_color="#E0E7FF", marker_line_width=0,
        hovertemplate="%{x}<br>Budget : %{y:.0f} €<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=df_t["Mois"], y=df_t["Dépensé"],
        name="Dépensé", marker_color=theme, marker_line_width=0,
        hovertemplate="%{x}<br>Dépensé : %{y:.0f} €<extra></extra>",
    ))
    fig.update_layout(_base_layout(
        title=dict(text="Évolution sur 6 mois", font_size=15, x=0.5, xanchor="center"),
        barmode="overlay",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#F3F4F6", zeroline=False),
        height=220,
    ))
    st.plotly_chart(fig, use_container_width=True, config=_CFG)


# ── Comparaison mois précédent ────────────────────────────────────────────────
def render_month_comparison() -> None:
    months = get_month_keys()
    if len(months) < 2:
        st.info("Il faut au moins 2 mois de données.")
        return
    rows = []
    for key in months:
        month_data = st.session_state.data[key]
        cfg = month_data.get("config", {})
        expenses = [e for e in month_data.get("expenses", []) if e.get("type", "expense") == "expense"]
        total = sum(float(e["amount"]) for e in expenses)
        budget = float(cfg.get("monthly_budget", 0))
        rows.append({
            "Mois": month_label(key),
            "Budget": budget,
            "Dépensé": round(total, 2),
            "Économisé": round(max(0, budget - total), 2),
            "Dépassement": round(max(0, total - budget), 2),
        })
    df_comp = pd.DataFrame(rows)

    # Delta vs mois précédent
    if len(rows) >= 2:
        delta = rows[0]["Dépensé"] - rows[1]["Dépensé"]
        sign = "+" if delta > 0 else ""
        c1, c2, c3 = st.columns(3)
        c1.metric("Ce mois", fmt(rows[0]["Dépensé"]))
        c2.metric("Mois précédent", fmt(rows[1]["Dépensé"]))
        c3.metric("Différence", f"{sign}{delta:.0f} €",
                  delta=f"{sign}{delta:.0f}", delta_color="inverse")

    theme = get_theme()
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Budget",  x=df_comp["Mois"], y=df_comp["Budget"],
                          marker_color="#E0E7FF", marker_line_width=0))
    fig.add_trace(go.Bar(name="Dépensé", x=df_comp["Mois"], y=df_comp["Dépensé"],
                          marker_color=theme, marker_line_width=0))
    fig.update_layout(_base_layout(
        title=dict(text="Budget vs Dépenses par mois", font_size=15, x=0.5, xanchor="center"),
        barmode="overlay",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#F3F4F6", zeroline=False),
    ))
    st.plotly_chart(fig, use_container_width=True, config=_CFG)
    st.dataframe(df_comp, use_container_width=True, hide_index=True)


# ── Onglet Réglages ───────────────────────────────────────────────────────────
def render_settings_tab() -> None:
    st.subheader("⚙️ Configuration du budget")
    cfg = active_config()
    with st.form("config_form_tab"):
        budget = st.number_input("Budget mensuel", min_value=1.0, max_value=100_000.0,
                                 value=float(cfg["monthly_budget"]), step=50.0, format="%.2f")
        c1, c2 = st.columns(2)
        days        = c1.number_input("Jours dans le mois", min_value=1, max_value=31, value=int(cfg["days_in_month"]))
        current_day = c2.number_input("Jour actuel", min_value=1, max_value=31, value=int(cfg["current_day"]))
        if st.form_submit_button("💾 Sauvegarder la configuration", use_container_width=True, type="primary"):
            active_config().update({
                "monthly_budget": float(budget),
                "days_in_month": int(days),
                "current_day": int(current_day),
            })
            save_data()
            st.rerun()

    # Devise
    cur_code = get_currency()
    cur_idx  = list(CURRENCIES.keys()).index(cur_code) if cur_code in CURRENCIES else 0
    chosen   = st.selectbox("💱 Devise", options=list(CURRENCIES.keys()),
                            format_func=lambda k: CURRENCIES[k], index=cur_idx, key="settings_currency")
    if chosen != cur_code:
        set_currency(chosen)
        st.rerun()

    st.markdown("---")

    with st.expander("🏷️ Enveloppes par catégorie"):
        st.caption("Budget max par catégorie (0 = pas de limite)")
        cat_budgets = active_cat_budgets()
        with st.form("cat_budget_form_tab"):
            new_budgets = {}
            for cat in get_categories():
                new_budgets[cat] = st.number_input(
                    cat, min_value=0.0, value=float(cat_budgets.get(cat, 0.0)),
                    step=10.0, format="%.0f", key=f"cbt_{cat}")
            if st.form_submit_button("💾 Sauvegarder", use_container_width=True):
                st.session_state.data[st.session_state.active_month]["category_budgets"] = new_budgets
                save_data()
                st.rerun()

    with st.expander("🔄 Dépenses récurrentes"):
        _render_recurring_sidebar()

    with st.expander("📧 Notifications email"):
        _render_notif_sidebar()

    with st.expander("🤖 Auto-catégorisation"):
        _render_auto_rules_sidebar()

    with st.expander("🎯 Objectif d'épargne"):
        _render_savings_goal_sidebar()

    with st.expander("🗂️ Catégories personnalisées"):
        _render_categories_sidebar()

    with st.expander("🎨 Thème"):
        _render_theme_sidebar()

    with st.expander("🔔 Rappels paiements"):
        _render_reminders_sidebar()

    with st.expander("⚡ Tasker : ajout automatique depuis Revolut"):
        uname = st.session_state.username
        st.markdown(f"""
**Tasker → Notif Revolut** — envoyez title + texte :
```
{{"token":"caca","username":"{uname}","notif":"%evtprm2","title":"%evtprm1"}}
```
URL : `https://banquetest.onrender.com/revolut`

**Tasker → Raccourci manuel** :
```
{{"token":"caca","username":"{uname}","amount":5.00,"description":"Café","category":"🍽️ Restaurant"}}
```
URL : `https://banquetest.onrender.com/expense`
""")
        raw = _redis().get(f"last_revolut:{uname}")
        if raw:
            log = json.loads(raw)
            ts  = datetime.fromtimestamp(float(log.get("time", 0))).strftime("%d/%m %H:%M")
            st.caption(f"Dernier webhook reçu : {ts}")
            st.code(f"title : {log.get('title','(vide)')}\nnotif : {log.get('notif','(vide)')}", language="text")
        else:
            st.caption("Aucun webhook reçu pour l'instant.")

    st.markdown("---")
    if st.button("🗑️ Réinitialiser les dépenses du mois", use_container_width=True):
        st.session_state.data[st.session_state.active_month]["expenses"] = []
        save_data()
        st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    init_state()
    logged_in = st.session_state.get("logged_in", False)
    st.set_page_config(
        page_title="Budget Mensuel",
        page_icon="💶",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    if not logged_in:
        render_auth_page()
        return

    theme_color = get_theme()
    active_key  = st.session_state.active_month

    st.markdown(f"""
<style>
#MainMenu, footer {{ visibility:hidden; }}
.stDeployButton {{ display:none !important; }}

/* Container principal */
.main .block-container {{
    padding-top:.75rem !important;
    padding-bottom:3rem !important;
}}

/* Métriques */
div[data-testid="stMetric"] {{
    border-radius:14px;
    padding:10px 12px !important;
    box-shadow:0 2px 8px rgba(0,0,0,0.06);
    border:1px solid #EBEBF5;
}}
div[data-testid="stMetricValue"] {{ font-size:1rem !important; font-weight:700 !important; }}
div[data-testid="stMetricLabel"] {{ font-size:.65rem !important; }}

/* Boutons */
.stButton > button {{
    border-radius:12px !important;
    min-height:44px !important;
    font-size:.9rem !important;
}}
.stButton > button[kind="primary"] {{
    background:linear-gradient(135deg,{theme_color},{theme_color}BB) !important;
    border:none !important;
    color:white !important;
    font-weight:600 !important;
    box-shadow:0 3px 12px {theme_color}44 !important;
}}

/* Expanders */
div[data-testid="stExpander"] {{
    border-radius:14px !important;
    border:1px solid #EBEBF5 !important;
    box-shadow:0 1px 4px rgba(0,0,0,0.04) !important;
    margin-bottom:6px !important;
    overflow:hidden !important;
}}

/* Barre de progression */
div[data-testid="stProgress"] > div > div {{ background:{theme_color} !important; }}

/* Graphiques */
.js-plotly-plot {{
    border-radius:14px !important;
    overflow:hidden;
    box-shadow:0 2px 10px rgba(0,0,0,0.06) !important;
}}

/* Sidebar */
section[data-testid="stSidebar"] {{ box-shadow:2px 0 12px rgba(0,0,0,0.06) !important; }}

/* Cartes custom */
.budget-card {{
    background:white;
    border-radius:18px;
    padding:1.2rem 1rem;
    margin:.5rem 0 .8rem;
    box-shadow:0 2px 10px rgba(0,0,0,0.06);
    border:1px solid #F0F0F8;
}}
.big-daily  {{ font-size:2.8rem; font-weight:800; text-align:center; margin:.2rem 0; line-height:1.1; }}
.card-label {{ text-align:center; color:#6B7280; font-size:.82rem; margin:0; }}
.cat-pill   {{ padding:.3rem .7rem; border-radius:8px; margin:.15rem 0; font-size:.85rem; }}

/* En-tête */
.app-header {{
    background:linear-gradient(135deg,{theme_color} 0%,{theme_color}88 100%);
    border-radius:16px;
    padding:16px 18px;
    margin:0 0 .8rem;
    color:white;
    box-shadow:0 4px 20px {theme_color}44;
}}
.app-header h2 {{ font-size:1.15rem; font-weight:700; margin:0 0 2px; color:white !important; }}
.app-header p  {{ font-size:.75rem; opacity:.9; margin:0; color:rgba(255,255,255,0.85) !important; }}

/* Mode sombre (OS) */
@media (prefers-color-scheme: dark) {{
    .budget-card {{ background:#1E2635 !important; border-color:#2D3748 !important; }}
    .app-header  {{ box-shadow:0 4px 20px rgba(0,0,0,0.4) !important; }}
}}

/* Mobile */
@media (max-width:640px) {{
    .main .block-container {{ padding-left:.4rem !important; padding-right:.4rem !important; }}
    .app-header {{ padding:12px 14px; border-radius:12px; }}
    .big-daily  {{ font-size:2.2rem; }}
    div[data-testid="stMetricValue"] {{ font-size:.88rem !important; }}
    section[data-testid="stSidebar"] {{ width:88vw !important; }}
}}
</style>
<div class="app-header">
  <h2>💶 Budget · {month_label(active_key)}</h2>
  <p>Bonjour {st.session_state.username} · Jour {date.today().day} du mois</p>
</div>
""", unsafe_allow_html=True)

    render_sidebar()

    df      = build_df()
    exp     = expense_df(df)
    summary = compute_summary(active_config(), df)

    tab_budget, tab_tx, tab_analyse, tab_reglages = st.tabs([
        "💰 Budget", "📋 Transactions", "📊 Analyse", "⚙️ Réglages"
    ])

    # ── Onglet Budget ────────────────────────────────────────────────────────
    with tab_budget:
        with st.expander("⚡ Ajout rapide", expanded=True):
            render_quick_add()

        st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
        render_metrics(summary)
        st.markdown("---")

        if exp.empty:
            cfg_now = active_config()
            st.markdown(f"""
            <div class="budget-card">
                <p class="card-label">Budget quotidien de départ</p>
                <p class="big-daily" style="color:#22C55E;">{fmt(summary['initial_daily'])}</p>
                <p class="card-label">sur {cfg_now['days_in_month']} jours · {fmt(summary['budget'])} ce mois</p>
            </div>""", unsafe_allow_html=True)
            st.info("Ajoutez vos premières dépenses pour voir votre budget en temps réel.")
        else:
            render_status_card(summary, exp)
            st.markdown("---")
            render_top_merchants(exp)

        render_savings_goal(summary)
        st.markdown("---")
        with st.expander("💬 Puis-je me permettre ça ?"):
            render_affordability(summary)

    # ── Onglet Transactions ──────────────────────────────────────────────────
    with tab_tx:
        render_expense_form()
        st.markdown("---")
        render_expense_table(df)
        render_csv_import()
        render_revolut_csv_import()

    # ── Onglet Analyse ───────────────────────────────────────────────────────
    with tab_analyse:
        if exp.empty:
            st.info("Pas encore de données à analyser.")
        else:
            render_6month_trend()
            st.markdown("---")
            with st.expander("📊 Graphiques détaillés", expanded=True):
                render_charts(exp, summary)
            with st.expander("📆 Comparaison multi-mois"):
                render_month_comparison()
            with st.expander("⚖️ Règle 50/30/20"):
                render_budget_5030(summary, exp)
            with st.expander("📅 Calendrier"):
                render_calendar(exp)
            with st.expander("📅 Vue hebdomadaire"):
                render_weekly_view(exp, summary)
            with st.expander("📊 Budget annuel"):
                render_annual_view()
            subs = detect_subscriptions()
            if subs:
                with st.expander(f"🔁 Abonnements détectés ({len(subs)})"):
                    st.caption("Dépenses répétées chaque mois avec un montant similaire.")
                    for s in subs:
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.markdown(f"**{s['description'].title()}**")
                        c2.markdown(f"{s['avg_amount']:.2f} €/mois")
                        if c3.button("➕ Récurrent", key=f"sub_{s['description']}"):
                            cat = auto_categorize(s["description"])
                            recurring = st.session_state.data.get("recurring", [])
                            recurring.append({"description": s["description"].title(),
                                              "amount": s["avg_amount"], "category": cat})
                            st.session_state.data["recurring"] = recurring
                            save_data()
                            st.rerun()

    # ── Onglet Réglages ──────────────────────────────────────────────────────
    with tab_reglages:
        render_settings_tab()


if __name__ == "__main__":
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    if get_script_run_ctx() is not None:
        main()
    else:
        import subprocess, sys
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])
