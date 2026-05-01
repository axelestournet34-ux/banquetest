"""
Budget Mensuel Intelligent — Streamlit v4
Ajout rapide · Édition/suppression · Dépenses récurrentes · Import CSV
Prévision · Tendances · Filtres · Export CSV
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
    """Retourne un message d'erreur ou None si succès."""
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
    st.title("💶 Budget Mensuel Intelligent")
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
                        st.success("Compte créé ! Connectez-vous dans l'onglet ci-contre.")


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
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
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
    # Recharge automatiquement si le webhook a écrit une nouvelle transaction
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
        return pd.DataFrame(columns=["date", "amount", "category", "description"])
    df = pd.DataFrame(expenses)
    df["amount"] = df["amount"].astype(float)
    return df


# ── Logique métier ────────────────────────────────────────────────────────────
def compute_summary(config: dict, df: pd.DataFrame) -> dict:
    budget = float(config["monthly_budget"])
    total_days = int(config["days_in_month"])
    current_day = int(config["current_day"])

    total_spent = float(df["amount"].sum()) if not df.empty else 0.0
    initial_daily = budget / total_days if total_days > 0 else 0.0
    days_elapsed = min(current_day, total_days)
    days_remaining = max(total_days - days_elapsed, 0)
    budget_remaining = budget - total_spent
    daily_remaining = budget_remaining / days_remaining if days_remaining > 0 else 0.0
    avg_daily = total_spent / days_elapsed if days_elapsed > 0 else 0.0
    forecast_total = avg_daily * total_days
    ideal_spent = initial_daily * days_elapsed
    difference = ideal_spent - total_spent

    return {
        "budget": budget, "total_spent": total_spent,
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


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar() -> None:
    st.sidebar.title("💶 Budget Mensuel v4")
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
        if st.button("Créer ce mois", use_container_width=True):
            new_key = f"{int(new_year):04d}-{int(new_month):02d}"
            ensure_month(new_key)
            st.session_state.active_month = new_key
            st.rerun()

    st.sidebar.markdown("---")

    # ── Devise ───────────────────────────────────────────────────────────────
    cur_code = get_currency()
    cur_idx = list(CURRENCIES.keys()).index(cur_code) if cur_code in CURRENCIES else 0
    chosen = st.sidebar.selectbox(
        "💱 Devise", options=list(CURRENCIES.keys()),
        format_func=lambda k: CURRENCIES[k], index=cur_idx,
    )
    if chosen != cur_code:
        set_currency(chosen)
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Configuration")
    cfg = active_config()

    with st.sidebar.form("config_form"):
        budget = st.number_input(
            "Budget mensuel (€)", min_value=1.0, max_value=100_000.0,
            value=float(cfg["monthly_budget"]), step=50.0, format="%.2f",
        )
        days = st.number_input("Jours dans le mois", min_value=1, max_value=31, value=int(cfg["days_in_month"]))
        current_day = st.number_input(
            "Jour actuel", min_value=1, max_value=31, value=int(cfg["current_day"]),
            help="Pour calculer les jours restants.",
        )
        if st.form_submit_button("💾 Sauvegarder", use_container_width=True, type="primary"):
            active_config().update({
                "monthly_budget": float(budget),
                "days_in_month": int(days),
                "current_day": int(current_day),
            })
            save_data()
            st.sidebar.success("✓ Configuration mise à jour !")

    daily = cfg["monthly_budget"] / cfg["days_in_month"] if cfg["days_in_month"] > 0 else 0
    st.sidebar.markdown(f"""
---
**Budget quotidien initial**
## {fmt(daily)}/j
*{fmt(cfg['monthly_budget'])} ÷ {cfg['days_in_month']} j*
    """)
    st.sidebar.markdown("---")

    with st.sidebar.expander("🏷️ Enveloppes par catégorie"):
        st.caption("Budget max par catégorie (0 = pas de limite)")
        cat_budgets = active_cat_budgets()
        with st.form("cat_budget_form"):
            new_budgets = {}
            for cat in CATEGORIES:
                new_budgets[cat] = st.number_input(
                    cat, min_value=0.0, value=float(cat_budgets.get(cat, 0.0)), step=10.0, format="%.0f",
                )
            if st.form_submit_button("💾 Sauvegarder", use_container_width=True):
                st.session_state.data[st.session_state.active_month]["category_budgets"] = new_budgets
                save_data()
                st.sidebar.success("✓ Enveloppes mises à jour !")

    with st.sidebar.expander("🔄 Dépenses récurrentes"):
        _render_recurring_sidebar()

    with st.sidebar.expander("📧 Notifications email"):
        _render_notif_sidebar()

    with st.sidebar.expander("🤖 Auto-catégorisation"):
        _render_auto_rules_sidebar()

    with st.sidebar.expander("🎯 Objectif d'épargne"):
        _render_savings_goal_sidebar()

    st.sidebar.markdown("---")
    if st.sidebar.button("🗑️ Réinitialiser les dépenses du mois", use_container_width=True):
        st.session_state.data[st.session_state.active_month]["expenses"] = []
        save_data()
        st.rerun()


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


# ── Sidebar : notifications email ────────────────────────────────────────────
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
            st.success("✓ Sauvegardé !")
    if cfg.get("email"):
        if st.button("📨 Email test", use_container_width=True, key="test_email"):
            ok = send_email("✅ Test Budget App", "<h2>Ça fonctionne !</h2><p>Vos alertes email sont bien configurées.</p>")
            st.success("Email envoyé !") if ok else st.error("Échec — vérifiez vos identifiants.")


# ── Sidebar : auto-catégorisation ─────────────────────────────────────────────
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


# ── Sidebar : objectif d'épargne ──────────────────────────────────────────────
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
            st.success("✓ Objectif mis à jour !")


# ── Ajout rapide ──────────────────────────────────────────────────────────────
def render_quick_add() -> None:
    st.markdown("**⚡ Ajout rapide**")
    c1, c2 = st.columns([3, 1])
    desc = c1.text_input("Description", placeholder="courses, essence…", label_visibility="collapsed", key="qa_desc")
    amt  = c2.number_input("€", min_value=0.01, value=10.0, step=1.0,
                           label_visibility="collapsed", key="qa_amt", format="%.2f")
    c3, c4 = st.columns([3, 1])
    cat = c3.selectbox("Catégorie", CATEGORIES, label_visibility="collapsed", key="qa_cat")
    if c4.button("➕ Ajouter", use_container_width=True, key="qa_btn"):
        active_expenses().append({
            "date": date.today().isoformat(),
            "amount": float(amt),
            "category": cat,
            "description": desc.strip() or "—",
        })
        save_data()
        st.success(f"✅ {amt:.2f} € ajouté — {cat}")
        st.rerun()


# ── Formulaire détaillé ───────────────────────────────────────────────────────
def render_expense_form() -> None:
    sym = CURRENCY_SYMBOLS.get(get_currency(), "€")
    st.subheader("➕ Ajouter une dépense")
    with st.form("expense_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            exp_date = st.date_input("Date", value=date.today())
            amount = st.number_input(f"Montant ({sym})", min_value=0.01, value=1.0, step=0.5, format="%.2f")
        with c2:
            category = st.selectbox("Catégorie", CATEGORIES)
            description = st.text_input("Description (facultatif)")
        if st.form_submit_button("✅ Ajouter", use_container_width=True, type="primary") and amount > 0:
            active_expenses().append({
                "date": exp_date.isoformat(), "amount": float(amount),
                "category": category, "description": description.strip() or "—",
            })
            save_data()
            st.success(f"**{fmt(amount)}** ajouté dans *{category}* !")


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
        default_cat = st.selectbox("Catégorie par défaut", CATEGORIES, key="csv_default_cat")

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


# ── Métriques ─────────────────────────────────────────────────────────────────
def render_metrics(summary: dict) -> None:
    sym = CURRENCY_SYMBOLS.get(get_currency(), "€")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Budget", fmt(summary["budget"]))
    c2.metric("💸 Dépensé", fmt(summary["total_spent"]))
    c3.metric("🏦 Restant", fmt(summary["budget_remaining"]))
    c4.metric("📅 Jours restants", f"{summary['days_remaining']} j")
    c5, c6, c7 = st.columns(3)
    c5.metric(f"📊 {sym}/j initial", fmt(summary["initial_daily"]))
    c6.metric(
        f"🎯 {sym}/j recalculé",
        fmt(summary["daily_remaining"]),
        delta=f"{summary['daily_remaining'] - summary['initial_daily']:+.2f}",
    )
    forecast_delta = summary["forecast_total"] - summary["budget"]
    c7.metric(
        "🔮 Prévision fin mois",
        fmt(summary["forecast_total"]),
        delta=f"{forecast_delta:+.2f}",
        delta_color="inverse",
    )


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


# ── Tableau des dépenses (éditable) ──────────────────────────────────────────
def render_expense_table(df: pd.DataFrame) -> None:
    st.subheader("📋 Historique des dépenses")

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

    edited = st.data_editor(
        edit_df,
        column_config={
            "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
            "amount": st.column_config.NumberColumn(f"Montant ({CURRENCY_SYMBOLS.get(get_currency(), '€')})", format="%.2f", min_value=0.01),
            "category": st.column_config.SelectboxColumn("Catégorie", options=CATEGORIES, required=True),
            "description": st.column_config.TextColumn("Description", max_chars=120),
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="expense_editor",
    )

    # Filtered stats (display only)
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
        st.success("✅ Modifications sauvegardées !")
        st.rerun()

    c_info.caption(
        f"**{len(view_df)}** dépense(s) affichées · "
        f"Total filtré : **{fmt(view_df['amount'].sum())}** · "
        f"Total mois : **{fmt(df['amount'].sum())}**"
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
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = gmail
        msg["To"] = to
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
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
        <p class="big-daily" style="color:{color};">{fmt(saved)} / {fmt(target)}</p>
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


# ── Puis-je me permettre ça ? ────────────────────────────────────────────────
def render_affordability(summary: dict) -> None:
    st.subheader("💬 Puis-je me permettre ça ?")
    amount = st.number_input("Montant de la dépense envisagée (€)", min_value=0.01, value=50.0, step=5.0, key="afford_amt")
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
        <p class="big-daily" style="color:{color};">{icon} {msg}</p>
        <p style="text-align:center">Cette dépense = <strong>{pct:.0f}%</strong> du budget restant
        · impact <strong>{days_impact:.1f} jours</strong></p>
    </div>""", unsafe_allow_html=True)


# ── Vue hebdomadaire ──────────────────────────────────────────────────────────
def render_weekly_view(df: pd.DataFrame, summary: dict) -> None:
    st.subheader("📅 Vue par semaine")
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

    for _, row in weekly.iterrows():
        over = row["Dépensé"] > weekly_budget
        delta = row["Dépensé"] - weekly_budget
        st.metric(row["Semaine"], f"{row['Dépensé']:.2f} €",
                  delta=f"{delta:+.2f} €", delta_color="inverse" if over else "normal")


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


# ── Analyse IA ────────────────────────────────────────────────────────────────
def render_ai_analysis(df: pd.DataFrame, summary: dict) -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        st.info("Ajoutez `ANTHROPIC_API_KEY` dans Render → Environment pour activer l'analyse IA.")
        return

    if st.button("🤖 Analyser mes dépenses avec l'IA", use_container_width=True, type="primary"):
        with st.spinner("Analyse en cours..."):
            try:
                import anthropic
                by_cat = df.groupby("category")["amount"].sum().sort_values(ascending=False).to_dict()
                client = anthropic.Anthropic(api_key=api_key)
                msg = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=600,
                    messages=[{"role": "user", "content": f"""Analyse ces dépenses mensuelles et donne 4 conseils pratiques et personnalisés en français. Sois direct, concis et bienveillant.

Budget : {summary['budget']:.0f}€ | Dépensé : {summary['total_spent']:.0f}€ ({summary['total_spent']/summary['budget']*100:.0f}%) | Jours restants : {summary['days_remaining']}

Dépenses par catégorie :
{chr(10).join(f"- {cat}: {amt:.2f}€" for cat, amt in by_cat.items())}

Format : 4 points avec emoji, chacun sur une ligne."""}]
                )
                st.markdown("### 🤖 Analyse de vos dépenses")
                st.markdown(msg.content[0].text)
            except Exception as e:
                st.error(f"Erreur IA : {e}")


# ── Comparaison multi-mois ────────────────────────────────────────────────────
def render_month_comparison() -> None:
    months = get_month_keys()
    if len(months) < 2:
        return
    st.subheader("📆 Comparaison multi-mois")
    rows = []
    for key in months:
        month_data = st.session_state.data[key]
        cfg = month_data.get("config", {})
        expenses = month_data.get("expenses", [])
        total = sum(float(e["amount"]) for e in expenses)
        budget = float(cfg.get("monthly_budget", 0))
        rows.append({"Mois": month_label(key), "Budget": budget,
                     "Dépensé": total, "Économisé": round(budget - total, 2)})
    df_comp = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Budget", x=df_comp["Mois"], y=df_comp["Budget"],
                          marker_color="#d1e7dd", opacity=0.85))
    fig.add_trace(go.Bar(name="Dépensé", x=df_comp["Mois"], y=df_comp["Dépensé"],
                          marker_color="#4A90D9"))
    fig.update_layout(barmode="overlay", title="Budget vs Dépenses par mois",
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df_comp, use_container_width=True, hide_index=True)


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    init_state()
    logged_in = st.session_state.get("logged_in", False)
    st.set_page_config(
        page_title="Budget Mensuel Intelligent",
        page_icon="💶",
        layout="centered" if not logged_in else "wide",
        initial_sidebar_state="expanded",
    )

    if not logged_in:
        render_auth_page()
        return

    st.markdown("""
<style>
    .big-daily { font-size:3.5rem; font-weight:800; text-align:center; margin:.3rem 0; line-height:1.1; }
    .card-label { text-align:center; color:#6c757d; font-size:.85rem; margin:0; }
    .budget-card { background:#f8f9fa; border-radius:14px; padding:1.5rem 1rem; margin:.5rem 0 1rem 0; }
    .cat-pill { padding:.35rem .8rem; border-radius:8px; margin:.2rem 0; font-size:.88rem; }
    <script>
    if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js');}
    var ml=document.createElement('link');ml.rel='manifest';ml.href='/manifest.json';document.head.appendChild(ml);
    var mt=document.createElement('meta');mt.name='theme-color';mt.content='#6366F1';document.head.appendChild(mt);
    </script>
    .js-plotly-plot { border-radius:16px !important; box-shadow:0 2px 16px rgba(0,0,0,0.07); padding:4px; background:white; }
    @media (max-width: 640px) {
        .big-daily { font-size:2.2rem; }
        div[data-testid="stMetric"] { padding:.3rem .2rem; }
        div[data-testid="stMetricValue"] { font-size:1rem !important; }
        div[data-testid="stMetricLabel"] { font-size:.7rem !important; }
        section[data-testid="stSidebar"] { width:85vw !important; }
        .js-plotly-plot .main-svg { touch-action: pan-y !important; }
    }
</style>
""", unsafe_allow_html=True)

    active_key = st.session_state.active_month
    st.title(f"💶 Budget Mensuel Intelligent — {month_label(active_key)}")
    st.markdown("Suivez vos dépenses au quotidien et adaptez votre rythme automatiquement.")

    render_sidebar()
    render_quick_add()
    st.markdown("---")

    df = build_df()
    summary = compute_summary(active_config(), df)
    render_metrics(summary)
    st.markdown("---")

    if df.empty:
        st.subheader("📊 État du budget")
        st.info("Ajoutez vos premières dépenses pour voir l'état de votre budget en temps réel.")
        cfg = active_config()
        st.markdown(f"""
        <div class="budget-card">
            <p class="card-label">Budget quotidien de départ</p>
            <p class="big-daily" style="color:#28a745;">{fmt(summary['initial_daily'])}</p>
            <p class="card-label">sur {cfg['days_in_month']} jours</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        render_status_card(summary, df)

    st.markdown("---")
    render_expense_form()
    render_csv_import()
    render_revolut_csv_import()

    st.markdown("---")
    render_expense_table(df)

    render_savings_goal(summary)

    st.markdown("---")
    with st.expander("💬 Puis-je me permettre ça ?", expanded=False):
        render_affordability(summary)

    if not df.empty:
        with st.expander("📅 Vue hebdomadaire", expanded=False):
            render_weekly_view(df, summary)
        with st.expander("📈 Graphiques", expanded=False):
            render_charts(df, summary)
        with st.expander("📆 Comparaison multi-mois", expanded=False):
            render_month_comparison()
        with st.expander("🤖 Analyse IA", expanded=False):
            render_ai_analysis(df, summary)
        subs = detect_subscriptions()
        if subs:
            with st.expander(f"🔁 Abonnements détectés ({len(subs)})", expanded=False):
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
                        st.success(f"'{s['description'].title()}' ajouté aux récurrents !")
                        st.rerun()


if __name__ == "__main__":
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    if get_script_run_ctx() is not None:
        main()
    else:
        import subprocess, sys
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])
