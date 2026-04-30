"""
Budget Mensuel Intelligent — Streamlit v4
Ajout rapide · Édition/suppression · Dépenses récurrentes · Import CSV
Prévision · Tendances · Filtres · Export CSV
"""

import hashlib
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
from pathlib import Path


USERS_FILE = Path("users.json")

CATEGORIES = [
    "🍔 Alimentation", "🚗 Transport", "🏠 Logement / Factures",
    "💊 Santé", "🎮 Loisirs", "👗 Vêtements", "📱 Abonnements",
    "🍽️ Restaurant", "✈️ Voyage", "🎁 Cadeaux", "📦 Autres",
]

MOIS_FR = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]

def data_file_for(username: str) -> Path:
    return Path(f"budget_{username}.json")
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
    if not USERS_FILE.exists():
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users: dict) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

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
                    st.session_state.logged_in = True
                    st.session_state.username = username.strip().lower()
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
    f = data_file_for(st.session_state.username)
    if not f.exists():
        return {}
    with open(f, "r", encoding="utf-8") as fp:
        return json.load(fp)

def save_data() -> None:
    f = data_file_for(st.session_state.username)
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(st.session_state.data, fp, ensure_ascii=False, indent=2)

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
    f = data_file_for(st.session_state.username)
    return f.stat().st_mtime if f.exists() else 0.0

def init_state() -> None:
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ""
    if not st.session_state.logged_in:
        return
    if "data" not in st.session_state:
        st.session_state.data = load_data()
        st.session_state.file_mtime = _data_mtime()
    if "active_month" not in st.session_state:
        st.session_state.active_month = current_month_key()
    ensure_month(st.session_state.active_month)
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


# ── Ajout rapide ──────────────────────────────────────────────────────────────
def render_quick_add() -> None:
    st.markdown("**⚡ Ajout rapide**")
    c1, c2, c3, c4 = st.columns([3, 1.2, 2.5, 1])
    desc = c1.text_input("Desc", placeholder="courses, essence…", label_visibility="collapsed", key="qa_desc")
    amt = c2.number_input("€", min_value=0.01, value=10.0, step=1.0,
                          label_visibility="collapsed", key="qa_amt", format="%.2f")
    cat = c3.selectbox("Cat", CATEGORIES, label_visibility="collapsed", key="qa_cat")
    if c4.button("➕", use_container_width=True, key="qa_btn"):
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
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("💰 Budget", fmt(summary["budget"]))
    c2.metric("💸 Dépensé", fmt(summary["total_spent"]))
    c3.metric("🏦 Restant", fmt(summary["budget_remaining"]))
    c4.metric("📅 Jours restants", f"{summary['days_remaining']} j")
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
def render_charts(df: pd.DataFrame, summary: dict) -> None:
    st.subheader("📈 Visualisations")
    tab1, tab2, tab3, tab4 = st.tabs(["📅 Par jour", "🏷️ Par catégorie", "📈 Progression", "📆 Tendances"])

    with tab1:
        daily = df.groupby("date")["amount"].sum().reset_index().sort_values("date")
        daily.columns = ["Date", "Montant"]
        fig = px.bar(daily, x="Date", y="Montant", title="Dépenses journalières (€)",
                     color="Montant", color_continuous_scale="Reds", text_auto=".2f")
        fig.update_layout(coloraxis_showscale=False,
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        by_cat = df.groupby("category")["amount"].sum().reset_index()
        by_cat.columns = ["Catégorie", "Montant"]
        fig = px.pie(by_cat, names="Catégorie", values="Montant",
                     title="Répartition par catégorie", hole=0.45,
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_traces(textposition="outside", textinfo="label+percent")
        st.plotly_chart(fig, use_container_width=True)

        cat_budgets = active_cat_budgets()
        limits = {cat: lim for cat, lim in cat_budgets.items() if lim > 0}
        if limits:
            spent_map = by_cat.set_index("Catégorie")["Montant"].to_dict()
            rows = [{"Catégorie": cat, "Dépensé": spent_map.get(cat, 0.0), "Budget max": lim}
                    for cat, lim in limits.items()]
            df_lim = pd.DataFrame(rows)
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(name="Budget max", x=df_lim["Catégorie"], y=df_lim["Budget max"],
                                   marker_color="#d1e7dd", opacity=0.9))
            fig2.add_trace(go.Bar(name="Dépensé", x=df_lim["Catégorie"], y=df_lim["Dépensé"],
                                   marker_color="#4A90D9"))
            fig2.update_layout(barmode="overlay", title="Dépensé vs Enveloppe",
                                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        total_days = summary["total_days"]
        initial_daily = summary["initial_daily"]
        ideal_x = list(range(0, total_days + 1))
        ideal_y = [initial_daily * d for d in ideal_x]

        daily_cum = df.groupby("date")["amount"].sum().reset_index().sort_values("date")
        daily_cum["cumsum"] = daily_cum["amount"].cumsum()
        try:
            key = st.session_state.active_month
            first_day = date(int(key[:4]), int(key[5:]), 1)
            days_nums = [(date.fromisoformat(d) - first_day).days + 1 for d in daily_cum["date"]]
        except Exception:
            days_nums = list(range(1, len(daily_cum) + 1))

        days_elapsed = summary["days_elapsed"]
        avg_daily = summary["avg_daily"]
        forecast_x = list(range(days_elapsed, total_days + 1))
        forecast_y = [summary["total_spent"] + avg_daily * (d - days_elapsed) for d in forecast_x]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ideal_x, y=ideal_y, mode="lines", name="Rythme idéal",
                                  line=dict(color="#28a745", dash="dash", width=2)))
        if not daily_cum.empty:
            fig.add_trace(go.Scatter(x=days_nums, y=daily_cum["cumsum"].tolist(),
                                      mode="lines+markers", name="Dépenses réelles",
                                      line=dict(color="#dc3545", width=2), marker=dict(size=6)))
        if len(forecast_x) > 1:
            fig.add_trace(go.Scatter(x=forecast_x, y=forecast_y, mode="lines", name="Prévision",
                                      line=dict(color="#fd7e14", dash="dot", width=2)))
        fig.update_layout(
            title="Progression cumulée vs rythme idéal + prévision",
            xaxis_title="Jour du mois", yaxis_title="Montant cumulé (€)",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

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
                df_trends = pd.DataFrame(rows)
                all_cats = df_trends["Catégorie"].unique().tolist()
                selected_cats = st.multiselect(
                    "Catégories à afficher", all_cats,
                    default=all_cats[:min(5, len(all_cats))], key="trend_cats",
                )
                if selected_cats:
                    df_f = df_trends[df_trends["Catégorie"].isin(selected_cats)]
                    fig = px.line(df_f, x="Mois", y="Montant", color="Catégorie",
                                  title="Tendances par catégorie (multi-mois)", markers=True,
                                  color_discrete_sequence=px.colors.qualitative.Set2)
                    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
                    st.plotly_chart(fig, use_container_width=True)


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

    col_form, col_status = st.columns([1, 1], gap="large")
    with col_form:
        render_expense_form()
        render_csv_import()
    with col_status:
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
    render_expense_table(df)

    if not df.empty:
        st.markdown("---")
        render_charts(df, summary)

    st.markdown("---")
    render_month_comparison()


if __name__ == "__main__":
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    if get_script_run_ctx() is not None:
        main()
    else:
        import subprocess, sys
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])
