"""
Budget Mensuel Intelligent — Streamlit v4 Premium
Ajout rapide · Édition/suppression · Dépenses récurrentes · Import CSV
Prévision · Tendances · Filtres · Export CSV
"""

import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
from pathlib import Path


CATEGORIES = [
    "🍔 Alimentation", "🚗 Transport", "🏠 Logement / Factures",
    "💊 Santé", "🎮 Loisirs", "👗 Vêtements", "📱 Abonnements",
    "🍽️ Restaurant", "✈️ Voyage", "🎁 Cadeaux", "📦 Autres",
]

MOIS_FR = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]

DATA_FILE = Path("budget_data.json")
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

PLOTLY_COLORS = ["#4F8EFF", "#A855F7", "#22C55E", "#F59E0B", "#F43F5E",
                 "#06B6D4", "#EC4899", "#84CC16", "#FB923C", "#A78BFA", "#34D399"]

PREMIUM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,300;0,14..32,400;0,14..32,500;0,14..32,600;0,14..32,700;0,14..32,800;0,14..32,900&display=swap');

/* ═══════════════════════════════════════════════
   VARIABLES
═══════════════════════════════════════════════ */
:root {
    --bg:        #05091A;
    --bg2:       #080E25;
    --card:      rgba(255,255,255,0.035);
    --card-h:    rgba(255,255,255,0.065);
    --border:    rgba(79,142,255,0.13);
    --border-h:  rgba(79,142,255,0.32);
    --blue:      #4F8EFF;
    --purple:    #A855F7;
    --grad:      linear-gradient(135deg,#4F8EFF,#A855F7);
    --grad-r:    linear-gradient(135deg,#A855F7,#4F8EFF);
    --success:   #22C55E;
    --warning:   #F59E0B;
    --danger:    #F43F5E;
    --text:      #F1F5F9;
    --text2:     #94A3B8;
    --text3:     #64748B;
    --font:      'Inter',-apple-system,BlinkMacSystemFont,sans-serif;
    --r:         14px;
    --r-sm:      10px;
    --r-xs:      7px;
    --trans:     0.25s cubic-bezier(0.4,0,0.2,1);
}

/* ═══════════════════════════════════════════════
   BASE
═══════════════════════════════════════════════ */
html, body { font-family: var(--font) !important; }

.stApp {
    background:
        radial-gradient(ellipse 90% 55% at 50% -5%, rgba(79,142,255,0.11) 0%, transparent 55%),
        radial-gradient(ellipse 55% 45% at 85% 55%, rgba(168,85,247,0.07) 0%, transparent 55%),
        #05091A !important;
    font-family: var(--font) !important;
    color: var(--text) !important;
}

.main .block-container {
    padding-top: 2rem !important;
    padding-bottom: 4rem !important;
    max-width: 1380px !important;
}

* { font-family: var(--font) !important; }

/* ═══════════════════════════════════════════════
   SIDEBAR
═══════════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#08102A 0%,#050A1C 100%) !important;
    border-right: 1px solid var(--border) !important;
    box-shadow: 4px 0 30px rgba(0,0,0,0.35) !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div { color: var(--text) !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: var(--text) !important; font-weight:700 !important; }
[data-testid="stSidebar"] .block-container { padding: 1.5rem 1rem !important; }

/* ═══════════════════════════════════════════════
   TYPOGRAPHY
═══════════════════════════════════════════════ */
h1,h2,h3,h4,h5,h6 {
    font-family: var(--font) !important;
    color: var(--text) !important;
    letter-spacing: -0.025em !important;
}
p, li, td, th { color: var(--text2) !important; }

/* ═══════════════════════════════════════════════
   METRICS
═══════════════════════════════════════════════ */
[data-testid="stMetric"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
    padding: 1.1rem 1rem !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    transition: all var(--trans) !important;
    position: relative !important;
    overflow: hidden !important;
}
[data-testid="stMetric"]::after {
    content:'';
    position:absolute;
    top:0;left:0;right:0;
    height:2px;
    background: var(--grad);
    opacity:0;
    transition: opacity var(--trans);
}
[data-testid="stMetric"]:hover {
    background: var(--card-h) !important;
    border-color: var(--border-h) !important;
    transform: translateY(-3px) !important;
    box-shadow: 0 14px 40px rgba(79,142,255,0.13) !important;
}
[data-testid="stMetric"]:hover::after { opacity:1; }
[data-testid="stMetricLabel"] p,
[data-testid="stMetricLabel"] div {
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: var(--text3) !important;
}
[data-testid="stMetricValue"] div,
[data-testid="stMetricValue"] {
    font-size: 1.45rem !important;
    font-weight: 800 !important;
    color: var(--text) !important;
    line-height: 1.15 !important;
}
[data-testid="stMetricDelta"] div { font-size: 0.78rem !important; font-weight:600 !important; }

/* ═══════════════════════════════════════════════
   BUTTONS
═══════════════════════════════════════════════ */
.stButton > button {
    background: var(--grad) !important;
    color: #fff !important;
    border: none !important;
    border-radius: var(--r-sm) !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    padding: 0.52rem 1.1rem !important;
    transition: all var(--trans) !important;
    box-shadow: 0 4px 18px rgba(79,142,255,0.32) !important;
    letter-spacing: 0.01em !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 28px rgba(79,142,255,0.52) !important;
    filter: brightness(1.08) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

.stDownloadButton > button {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid var(--border-h) !important;
    color: var(--blue) !important;
    border-radius: var(--r-sm) !important;
    font-weight: 600 !important;
    transition: all var(--trans) !important;
    box-shadow: none !important;
}
.stDownloadButton > button:hover {
    background: rgba(79,142,255,0.1) !important;
    border-color: var(--blue) !important;
    transform: translateY(-1px) !important;
}
[data-testid="stFormSubmitButton"] > button {
    background: var(--grad) !important;
    color: #fff !important;
    border: none !important;
    border-radius: var(--r-sm) !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 18px rgba(79,142,255,0.32) !important;
    transition: all var(--trans) !important;
}
[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 28px rgba(79,142,255,0.52) !important;
    filter: brightness(1.08) !important;
}

/* ═══════════════════════════════════════════════
   INPUTS
═══════════════════════════════════════════════ */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea > div > div > textarea {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    color: var(--text) !important;
    font-size: 0.9rem !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--blue) !important;
    box-shadow: 0 0 0 3px rgba(79,142,255,0.13) !important;
    background: rgba(79,142,255,0.04) !important;
}
.stTextInput label, .stNumberInput label, .stSelectbox label,
.stDateInput label, .stTextArea label, .stFileUploader label,
.stMultiSelect label {
    font-weight: 600 !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: var(--text3) !important;
}
.stSelectbox > div > div,
[data-testid="stSelectbox"] > div > div {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    color: var(--text) !important;
}
.stDateInput > div > div > input {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    color: var(--text) !important;
}
[data-testid="stNumberInput"] button {
    background: rgba(255,255,255,0.06) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
    border-radius: 6px !important;
    box-shadow: none !important;
    transition: background var(--trans) !important;
}
[data-testid="stNumberInput"] button:hover {
    background: rgba(79,142,255,0.15) !important;
    transform: none !important;
    box-shadow: none !important;
}
[data-testid="stMultiSelect"] > div {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
}
[data-testid="stFileUploader"] {
    background: rgba(255,255,255,0.02) !important;
    border: 2px dashed var(--border) !important;
    border-radius: var(--r) !important;
    transition: border-color 0.2s ease !important;
}
[data-testid="stFileUploader"]:hover { border-color: var(--blue) !important; }

/* ═══════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════ */
[data-testid="stTabs"] [role="tablist"],
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.03) !important;
    border-radius: 12px !important;
    padding: 5px !important;
    border: 1px solid var(--border) !important;
    gap: 3px !important;
}
[data-testid="stTabs"] [role="tab"],
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    color: var(--text2) !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    transition: all var(--trans) !important;
    border: none !important;
    padding: 0.48rem 1rem !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"],
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: var(--grad) !important;
    color: #fff !important;
    box-shadow: 0 4px 14px rgba(79,142,255,0.4) !important;
    font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-highlight"] { display:none !important; }

/* ═══════════════════════════════════════════════
   EXPANDERS
═══════════════════════════════════════════════ */
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
    background: rgba(255,255,255,0.02) !important;
    overflow: hidden !important;
    transition: border-color var(--trans) !important;
}
[data-testid="stExpander"]:hover { border-color: var(--border-h) !important; }
[data-testid="stExpander"] summary {
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    color: var(--text) !important;
    padding: 0.85rem 1rem !important;
}

/* ═══════════════════════════════════════════════
   DATA EDITOR / DATAFRAME
═══════════════════════════════════════════════ */
[data-testid="stDataFrame"],
[data-testid="stDataEditor"] {
    border-radius: var(--r) !important;
    overflow: hidden !important;
    border: 1px solid var(--border) !important;
}

/* ═══════════════════════════════════════════════
   ALERTS
═══════════════════════════════════════════════ */
[data-testid="stAlert"] {
    border-radius: var(--r) !important;
    font-size: 0.88rem !important;
    backdrop-filter: blur(10px) !important;
}
div[data-testid="stSuccess"] > div { background: rgba(34,197,94,0.1) !important; border: 1px solid rgba(34,197,94,0.3) !important; border-radius: var(--r) !important; }
div[data-testid="stError"]   > div { background: rgba(244,63,94,0.1) !important;  border: 1px solid rgba(244,63,94,0.3) !important;  border-radius: var(--r) !important; }
div[data-testid="stWarning"] > div { background: rgba(245,158,11,0.1) !important; border: 1px solid rgba(245,158,11,0.3) !important; border-radius: var(--r) !important; }
div[data-testid="stInfo"]    > div { background: rgba(79,142,255,0.1) !important; border: 1px solid rgba(79,142,255,0.3) !important;  border-radius: var(--r) !important; }

/* ═══════════════════════════════════════════════
   TABLES (markdown)
═══════════════════════════════════════════════ */
table { width:100% !important; border-collapse:collapse !important; font-size:0.875rem !important; }
th {
    background: rgba(79,142,255,0.08) !important;
    color: var(--text3) !important;
    font-size: 0.7rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.09em !important;
    padding: 0.65rem 0.85rem !important;
    border-bottom: 1px solid var(--border) !important;
    font-weight: 700 !important;
}
td { padding: 0.58rem 0.85rem !important; border-bottom: 1px solid var(--border) !important; color: var(--text2) !important; }
tr:last-child td { border-bottom: none !important; }
tr:hover td { background: rgba(79,142,255,0.04) !important; }

/* ═══════════════════════════════════════════════
   MISC
═══════════════════════════════════════════════ */
hr { border:none !important; border-top: 1px solid var(--border) !important; margin: 1.75rem 0 !important; }
.stCaption, [data-testid="stCaptionContainer"] { color: var(--text3) !important; font-size:0.78rem !important; }
code { background: rgba(79,142,255,0.12) !important; color: var(--blue) !important; border-radius:5px !important; padding: 0.1em 0.4em !important; }
[data-testid="stHeader"] { background: transparent !important; }
::selection { background: rgba(79,142,255,0.3); color:#fff; }
::-webkit-scrollbar { width:5px; height:5px; }
::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); }
::-webkit-scrollbar-thumb { background: rgba(79,142,255,0.3); border-radius:10px; }
::-webkit-scrollbar-thumb:hover { background: rgba(79,142,255,0.55); }

/* Sidebar form */
[data-testid="stSidebar"] [data-testid="stForm"] {
    background: rgba(255,255,255,0.02) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
    padding: 0.6rem !important;
}

/* ═══════════════════════════════════════════════
   CUSTOM COMPONENTS
═══════════════════════════════════════════════ */

/* — Page header — */
.page-header {
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border);
}
.header-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(79,142,255,0.1);
    border: 1px solid rgba(79,142,255,0.25);
    color: var(--blue);
    font-size: 0.67rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    padding: 0.28rem 0.75rem;
    border-radius: 100px;
    margin-bottom: 0.75rem;
}
.gradient-title {
    font-size: 2.6rem !important;
    font-weight: 900 !important;
    letter-spacing: -0.035em !important;
    line-height: 1.08 !important;
    margin: 0 0 0.45rem 0 !important;
    background: linear-gradient(135deg,#F1F5F9 0%,#94A3B8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.gradient-title .accent {
    background: var(--grad);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.header-subtitle {
    color: var(--text3) !important;
    font-size: 0.97rem !important;
    font-weight: 400 !important;
    margin: 0 !important;
}

/* — Sidebar logo — */
.sidebar-logo {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding-bottom: 1.4rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1.4rem;
}
.sidebar-logo-icon { font-size: 1.75rem; }
.sidebar-logo-name {
    font-size: 1.05rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em !important;
    background: var(--grad);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1.1;
}
.sidebar-logo-sub {
    font-size: 0.68rem !important;
    color: var(--text3) !important;
    font-weight: 400 !important;
    line-height: 1.2;
}

/* — Section headers — */
.sh {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    margin: 0.25rem 0 1rem 0;
}
.sh-title {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text) !important;
    letter-spacing: -0.015em;
    white-space: nowrap;
}
.sh-line {
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, var(--border), transparent);
}

/* — Quick add bar — */
.qa-wrap {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 1rem 1.2rem 0.6rem 1.2rem;
    margin-bottom: 0.75rem;
    transition: border-color var(--trans);
}
.qa-wrap:hover { border-color: var(--border-h); }
.qa-label {
    font-size: 0.67rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text3);
    margin-bottom: 0.55rem;
}

/* — Premium budget card — */
.p-card {
    position: relative;
    border-radius: 20px;
    padding: 1.8rem 1.5rem 1.4rem;
    margin: 0.5rem 0 1.1rem 0;
    overflow: hidden;
    text-align: center;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(79,142,255,0.18);
}
.p-card::before {
    content:'';
    position:absolute;
    inset:0;
    border-radius:20px;
    padding:1px;
    background: var(--grad);
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    opacity:0.45;
    pointer-events:none;
}
.p-card-glow {
    position:absolute;
    top:-70px; left:50%;
    transform:translateX(-50%);
    width:220px; height:110px;
    border-radius:50%;
    filter:blur(35px);
    opacity:0.13;
    pointer-events:none;
}
.p-card-label {
    font-size: 0.7rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.12em !important;
    color: var(--text3) !important;
    margin: 0 0 0.4rem 0 !important;
}
.big-daily {
    font-size: 3rem !important;
    font-weight: 900 !important;
    line-height: 1.05 !important;
    letter-spacing: -0.04em !important;
    margin: 0 0 0.3rem 0 !important;
    text-align: center !important;
}
.p-card-sub {
    color: var(--text2) !important;
    font-size: 0.85rem !important;
    margin: 0 0 1rem 0 !important;
}
.p-card-sub strong { color: var(--text) !important; font-weight:700 !important; }
.prog-bar {
    background: rgba(255,255,255,0.07);
    border-radius: 100px;
    height: 5px;
    overflow: hidden;
    margin-bottom: 0.4rem;
}
.prog-fill {
    height:100%;
    border-radius:100px;
    transition: width 0.6s cubic-bezier(0.4,0,0.2,1);
}
.prog-label {
    font-size: 0.7rem !important;
    color: var(--text3) !important;
    text-align: center;
}

/* — Status badge — */
.sbadge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 0.42rem 1rem;
    border-radius: 100px;
    font-size: 0.8rem;
    font-weight: 600;
    margin-bottom: 1rem;
}
.sbadge.green  { background:rgba(34,197,94,0.1);  border:1px solid rgba(34,197,94,0.3);  color:#86efac; }
.sbadge.orange { background:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.3); color:#fcd34d; }
.sbadge.red    { background:rgba(244,63,94,0.1);  border:1px solid rgba(244,63,94,0.3);  color:#fca5a5; }

/* — Budget detail table — */
.b-table { width:100%; border-collapse:collapse; margin-top:1rem; font-size:0.85rem; }
.b-table td { padding: 0.55rem 0.5rem; border-bottom:1px solid var(--border); }
.b-table td:first-child { color: var(--text3) !important; }
.b-table td:last-child  { text-align:right; color:var(--text) !important; font-weight:600; }
.b-table tr:last-child td { border-bottom:none; }

/* — Category pill — */
.cat-pill {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.55rem 0.9rem;
    border-radius: 10px;
    margin: 0.3rem 0;
    font-size: 0.83rem;
    transition: transform var(--trans);
}
.cat-pill:hover { transform: translateX(4px); }
.cat-pill.orange { background:rgba(245,158,11,0.09); border-left:3px solid #F59E0B; color:#fcd34d; }
.cat-pill.red    { background:rgba(244,63,94,0.09);  border-left:3px solid #F43F5E; color:#fca5a5; }
.cat-pill-pct {
    font-size:0.7rem;
    background:rgba(255,255,255,0.1);
    padding: 0.12rem 0.45rem;
    border-radius:100px;
}
.cat-alerts-title {
    font-size:0.67rem;
    font-weight:800;
    text-transform:uppercase;
    letter-spacing:0.12em;
    color:var(--text3);
    margin:1rem 0 0.35rem 0;
}
</style>
"""


# ── Persistance ───────────────────────────────────────────────────────────────
def load_data() -> dict:
    if not DATA_FILE.exists():
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data() -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.data, f, ensure_ascii=False, indent=2)

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
def init_state() -> None:
    if "data" not in st.session_state:
        st.session_state.data = load_data()
    if "active_month" not in st.session_state:
        st.session_state.active_month = current_month_key()
    ensure_month(st.session_state.active_month)


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
        return "green", "En dessous du rythme idéal — continue comme ça !"
    elif difference >= -5:
        return "orange", "Zone de vigilance — surveille tes prochaines dépenses."
    else:
        return "red", "Tu dépenses trop vite — ralentis pour finir le mois !"

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


# ── Plotly theme helper ───────────────────────────────────────────────────────
def plotly_layout(**kwargs) -> dict:
    base = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#94A3B8", size=12),
        title_font=dict(family="Inter, sans-serif", color="#F1F5F9", size=15, weight="bold" if False else None),
        xaxis=dict(
            gridcolor="rgba(79,142,255,0.08)",
            zerolinecolor="rgba(79,142,255,0.12)",
            tickfont=dict(color="#64748B", size=11),
            linecolor="rgba(79,142,255,0.15)",
        ),
        yaxis=dict(
            gridcolor="rgba(79,142,255,0.08)",
            zerolinecolor="rgba(79,142,255,0.12)",
            tickfont=dict(color="#64748B", size=11),
            linecolor="rgba(79,142,255,0.15)",
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(79,142,255,0.15)",
            borderwidth=1,
            font=dict(color="#94A3B8", size=11),
        ),
        margin=dict(t=50, b=20, l=10, r=10),
        hoverlabel=dict(
            bgcolor="#0D1635",
            bordercolor="rgba(79,142,255,0.3)",
            font=dict(color="#F1F5F9", family="Inter"),
        ),
    )
    base.update(kwargs)
    return base


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar() -> None:
    st.sidebar.markdown("""
<div class="sidebar-logo">
    <span class="sidebar-logo-icon">💶</span>
    <div>
        <div class="sidebar-logo-name">BudgetApp</div>
        <div class="sidebar-logo-sub">Gestion financière intelligente</div>
    </div>
</div>
""", unsafe_allow_html=True)

    all_months = get_month_keys()
    cur = current_month_key()
    if cur not in all_months:
        all_months.insert(0, cur)
    active = st.session_state.active_month
    idx = all_months.index(active) if active in all_months else 0

    selected = st.sidebar.selectbox(
        "Mois affiché", options=all_months, index=idx, format_func=month_label,
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

    cur_code = get_currency()
    cur_idx = list(CURRENCIES.keys()).index(cur_code) if cur_code in CURRENCIES else 0
    chosen = st.sidebar.selectbox(
        "Devise", options=list(CURRENCIES.keys()),
        format_func=lambda k: CURRENCIES[k], index=cur_idx,
    )
    if chosen != cur_code:
        set_currency(chosen)
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown('<p style="font-size:0.72rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;color:#64748B;margin-bottom:0.6rem;">⚙️ Configuration</p>', unsafe_allow_html=True)
    cfg = active_config()

    with st.sidebar.form("config_form"):
        budget = st.number_input(
            "Budget mensuel", min_value=1.0, max_value=100_000.0,
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
            st.sidebar.success("Configuration mise à jour !")

    daily = cfg["monthly_budget"] / cfg["days_in_month"] if cfg["days_in_month"] > 0 else 0
    st.sidebar.markdown(f"""
<div style="background:rgba(79,142,255,0.07);border:1px solid rgba(79,142,255,0.18);border-radius:12px;padding:0.9rem 1rem;margin:1rem 0;text-align:center;">
    <div style="font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;color:#64748B;margin-bottom:0.3rem;">Budget quotidien initial</div>
    <div style="font-size:1.6rem;font-weight:900;letter-spacing:-0.03em;background:linear-gradient(135deg,#4F8EFF,#A855F7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">{fmt(daily)}</div>
    <div style="font-size:0.72rem;color:#64748B;margin-top:0.2rem;">{fmt(cfg['monthly_budget'])} ÷ {cfg['days_in_month']} jours</div>
</div>
---
""", unsafe_allow_html=True)

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
                st.sidebar.success("Enveloppes mises à jour !")

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
        c1.markdown(f"**{rec['description']}** — {rec['amount']:.0f} · {rec['category']}")
        if c2.button("✕", key=f"del_rec_{i}"):
            recurring.pop(i)
            st.session_state.data["recurring"] = recurring
            save_data()
            st.rerun()
    with st.form("recurring_form"):
        r_desc = st.text_input("Description", placeholder="Loyer, Netflix…")
        r_amt  = st.number_input("Montant", min_value=0.01, value=50.0, step=5.0)
        r_cat  = st.selectbox("Catégorie", CATEGORIES)
        if st.form_submit_button("➕ Ajouter", use_container_width=True) and r_desc.strip():
            recurring.append({"description": r_desc.strip(), "amount": float(r_amt), "category": r_cat})
            st.session_state.data["recurring"] = recurring
            save_data()
            st.rerun()


# ── Ajout rapide ──────────────────────────────────────────────────────────────
def render_quick_add() -> None:
    st.markdown("""
<div class="qa-wrap">
    <div class="qa-label">⚡ Ajout rapide</div>
""", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([3, 1.2, 2.5, 1])
    desc = c1.text_input("Description", placeholder="courses, essence…",
                         label_visibility="collapsed", key="qa_desc")
    amt  = c2.number_input("Montant", min_value=0.01, value=10.0, step=1.0,
                           label_visibility="collapsed", key="qa_amt", format="%.2f")
    cat  = c3.selectbox("Catégorie", CATEGORIES, label_visibility="collapsed", key="qa_cat")
    if c4.button("➕", use_container_width=True, key="qa_btn"):
        active_expenses().append({
            "date": date.today().isoformat(),
            "amount": float(amt),
            "category": cat,
            "description": desc.strip() or "—",
        })
        save_data()
        st.success(f"✅ {fmt(amt)} ajouté — {cat}")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ── Formulaire détaillé ───────────────────────────────────────────────────────
def render_expense_form() -> None:
    sym = CURRENCY_SYMBOLS.get(get_currency(), "€")
    st.markdown('<div class="sh"><span class="sh-title">➕ Ajouter une dépense</span><div class="sh-line"></div></div>', unsafe_allow_html=True)
    with st.form("expense_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            exp_date = st.date_input("Date", value=date.today())
            amount = st.number_input(f"Montant ({sym})", min_value=0.01, value=1.0, step=0.5, format="%.2f")
        with c2:
            category    = st.selectbox("Catégorie", CATEGORIES)
            description = st.text_input("Description (facultatif)")
        if st.form_submit_button("✅ Ajouter la dépense", use_container_width=True, type="primary") and amount > 0:
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
        col_date    = c1.selectbox("Colonne date", cols, key="csv_col_date")
        col_amt     = c2.selectbox("Colonne montant", cols, key="csv_col_amt")
        col_desc    = c3.selectbox("Colonne description", ["— aucune —"] + cols, key="csv_col_desc")
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
                    d    = parse_date(str(row[col_date]))
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
    c1.metric("💰 Budget total",         fmt(summary["budget"]))
    c2.metric("💸 Dépensé",              fmt(summary["total_spent"]))
    c3.metric("🏦 Restant",              fmt(summary["budget_remaining"]))
    c4.metric("📅 Jours restants",       f"{summary['days_remaining']} j")
    c5.metric(f"📊 {sym}/j initial",     fmt(summary["initial_daily"]))
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
    st.markdown('<div class="sh"><span class="sh-title">📊 État du budget</span><div class="sh-line"></div></div>', unsafe_allow_html=True)

    status, message = get_status(summary["difference"])
    icon_map   = {"green": "✅", "orange": "⚠️", "red": "🔴"}
    color_map  = {"green": "#22C55E", "orange": "#F59E0B", "red": "#F43F5E"}
    color_hex  = color_map[status]

    budget_pct = min(summary["total_spent"] / summary["budget"] * 100 if summary["budget"] > 0 else 0, 100)
    diff       = summary["difference"]
    sign       = "+" if diff >= 0 else ""
    forecast_ok = summary["forecast_total"] <= summary["budget"]
    sym        = CURRENCY_SYMBOLS.get(get_currency(), "€")

    st.markdown(f"""
<div style="text-align:center;margin-bottom:0.75rem;">
    <span class="sbadge {status}">{icon_map[status]} {message}</span>
</div>

<div class="p-card">
    <div class="p-card-glow" style="background:{color_hex};"></div>
    <p class="p-card-label">Budget quotidien restant</p>
    <p class="big-daily" style="color:{color_hex};">{fmt(summary['daily_remaining'])}</p>
    <p class="p-card-sub">pour les <strong>{summary['days_remaining']}</strong> jours restants</p>
    <div class="prog-bar">
        <div class="prog-fill" style="width:{budget_pct:.1f}%;background:{color_hex};"></div>
    </div>
    <p class="prog-label">{budget_pct:.1f}% du budget mensuel utilisé</p>
</div>

<table class="b-table">
    <tr><td>Rythme idéal à ce jour</td><td>{fmt(summary['ideal_spent'])}</td></tr>
    <tr><td>Réellement dépensé</td>
        <td style="color:{'#22C55E' if diff >= 0 else '#F43F5E'} !important;">{fmt(summary['total_spent'])}</td></tr>
    <tr><td>Écart</td>
        <td style="color:{'#22C55E' if diff >= 0 else '#F43F5E'} !important;font-size:1rem;">{sign}{diff:.2f} {sym}</td></tr>
    <tr><td>Moyenne / jour</td><td>{fmt(summary['avg_daily'])}/j</td></tr>
    <tr><td>Prévision fin de mois</td>
        <td>{'✅' if forecast_ok else '⚠️'} <strong>{fmt(summary['forecast_total'])}</strong></td></tr>
</table>
""", unsafe_allow_html=True)

    alerts = get_category_alerts(df, active_cat_budgets())
    if alerts:
        st.markdown('<p class="cat-alerts-title">⚠️ Alertes enveloppes</p>', unsafe_allow_html=True)
        for cat, (color, spent, limit, pct) in alerts.items():
            st.markdown(f"""
<div class="cat-pill {color}">
    <span>{cat}</span>
    <div style="display:flex;align-items:center;gap:0.45rem;">
        <span>{fmt(spent)} / {fmt(limit)}</span>
        <span class="cat-pill-pct">{pct*100:.0f}%</span>
    </div>
</div>""", unsafe_allow_html=True)


# ── Tableau des dépenses ──────────────────────────────────────────────────────
def render_expense_table(df: pd.DataFrame) -> None:
    st.markdown('<div class="sh"><span class="sh-title">📋 Historique des dépenses</span><div class="sh-line"></div></div>', unsafe_allow_html=True)

    c1, c2 = st.columns([3, 1])
    search     = c1.text_input("🔍 Rechercher", placeholder="description ou catégorie…",
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
            "date":        st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
            "amount":      st.column_config.NumberColumn(f"Montant ({CURRENCY_SYMBOLS.get(get_currency(), '€')})", format="%.2f", min_value=0.01),
            "category":    st.column_config.SelectboxColumn("Catégorie", options=CATEGORIES, required=True),
            "description": st.column_config.TextColumn("Description", max_chars=120),
        },
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
        st.success("✅ Modifications sauvegardées !")
        st.rerun()

    c_info.caption(
        f"**{len(view_df)}** dépense(s) · "
        f"Filtré : **{fmt(view_df['amount'].sum())}** · "
        f"Total mois : **{fmt(df['amount'].sum())}**"
    )
    c_export.download_button(
        label="⬇️ Exporter CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"budget_{st.session_state.active_month}.csv",
        mime="text/csv",
        use_container_width=True,
    )


# ── Graphiques ────────────────────────────────────────────────────────────────
def render_charts(df: pd.DataFrame, summary: dict) -> None:
    st.markdown('<div class="sh"><span class="sh-title">📈 Visualisations</span><div class="sh-line"></div></div>', unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["📅 Par jour", "🏷️ Par catégorie", "📈 Progression", "📆 Tendances"])

    with tab1:
        daily = df.groupby("date")["amount"].sum().reset_index().sort_values("date")
        daily.columns = ["Date", "Montant"]
        fig = px.bar(
            daily, x="Date", y="Montant",
            title="Dépenses journalières",
            color="Montant",
            color_continuous_scale=[[0, "#1e3a6e"], [0.5, "#4F8EFF"], [1, "#A855F7"]],
            text_auto=".2f",
        )
        fig.update_traces(textposition="outside", textfont=dict(color="#94A3B8", size=10))
        fig.update_layout(**plotly_layout(coloraxis_showscale=False))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        by_cat = df.groupby("category")["amount"].sum().reset_index()
        by_cat.columns = ["Catégorie", "Montant"]
        fig = px.pie(
            by_cat, names="Catégorie", values="Montant",
            title="Répartition par catégorie", hole=0.52,
            color_discrete_sequence=PLOTLY_COLORS,
        )
        fig.update_traces(
            textposition="outside", textinfo="label+percent",
            textfont=dict(color="#94A3B8", size=11),
            marker=dict(line=dict(color="#05091A", width=2)),
        )
        fig.update_layout(**plotly_layout())
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
                                  marker_color="rgba(79,142,255,0.2)", marker_line=dict(color="rgba(79,142,255,0.5)", width=1)))
            fig2.add_trace(go.Bar(name="Dépensé", x=df_lim["Catégorie"], y=df_lim["Dépensé"],
                                  marker_color="#4F8EFF", marker_line=dict(color="#A855F7", width=1)))
            fig2.update_layout(barmode="overlay", title="Dépensé vs Enveloppe", **plotly_layout())
            st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        total_days   = summary["total_days"]
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
        avg_daily    = summary["avg_daily"]
        forecast_x   = list(range(days_elapsed, total_days + 1))
        forecast_y   = [summary["total_spent"] + avg_daily * (d - days_elapsed) for d in forecast_x]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=ideal_x, y=ideal_y, mode="lines", name="Rythme idéal",
            line=dict(color="#22C55E", dash="dash", width=2),
            fill="tozeroy", fillcolor="rgba(34,197,94,0.04)",
        ))
        if not daily_cum.empty:
            fig.add_trace(go.Scatter(
                x=days_nums, y=daily_cum["cumsum"].tolist(),
                mode="lines+markers", name="Dépenses réelles",
                line=dict(color="#4F8EFF", width=2.5),
                marker=dict(size=6, color="#4F8EFF", line=dict(color="#A855F7", width=1.5)),
                fill="tozeroy", fillcolor="rgba(79,142,255,0.06)",
            ))
        if len(forecast_x) > 1:
            fig.add_trace(go.Scatter(
                x=forecast_x, y=forecast_y, mode="lines", name="Prévision",
                line=dict(color="#F59E0B", dash="dot", width=2),
            ))
        fig.update_layout(
            title="Progression cumulée vs rythme idéal",
            xaxis_title="Jour du mois", yaxis_title=f"Montant cumulé ({CURRENCY_SYMBOLS.get(get_currency(),'€')})",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            **plotly_layout(),
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
                        title="Tendances par catégorie", markers=True,
                        color_discrete_sequence=PLOTLY_COLORS,
                    )
                    fig.update_traces(line=dict(width=2.5), marker=dict(size=7))
                    fig.update_layout(
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                        **plotly_layout(),
                    )
                    st.plotly_chart(fig, use_container_width=True)


# ── Comparaison multi-mois ────────────────────────────────────────────────────
def render_month_comparison() -> None:
    months = get_month_keys()
    if len(months) < 2:
        return
    st.markdown('<div class="sh"><span class="sh-title">📆 Comparaison multi-mois</span><div class="sh-line"></div></div>', unsafe_allow_html=True)
    rows = []
    for key in months:
        month_data = st.session_state.data[key]
        cfg        = month_data.get("config", {})
        expenses   = month_data.get("expenses", [])
        total      = sum(float(e["amount"]) for e in expenses)
        budget     = float(cfg.get("monthly_budget", 0))
        rows.append({"Mois": month_label(key), "Budget": budget,
                     "Dépensé": total, "Économisé": round(budget - total, 2)})
    df_comp = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Budget", x=df_comp["Mois"], y=df_comp["Budget"],
        marker_color="rgba(79,142,255,0.18)",
        marker_line=dict(color="rgba(79,142,255,0.4)", width=1),
    ))
    fig.add_trace(go.Bar(
        name="Dépensé", x=df_comp["Mois"], y=df_comp["Dépensé"],
        marker=dict(color=df_comp["Dépensé"].apply(
            lambda v: "#22C55E" if v <= df_comp["Budget"].mean() else "#F43F5E"
        ).tolist()),
    ))
    fig.update_layout(barmode="overlay", title="Budget vs Dépenses par mois", **plotly_layout())
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df_comp, use_container_width=True, hide_index=True)


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    st.set_page_config(
        page_title="Budget Mensuel Intelligent",
        page_icon="💶",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(PREMIUM_CSS, unsafe_allow_html=True)

    init_state()
    active_key = st.session_state.active_month

    # ── Premium page header ──
    st.markdown(f"""
<div class="page-header">
    <div class="header-badge">💶 BUDGET MENSUEL INTELLIGENT</div>
    <h1 class="gradient-title">Tableau de bord <span class="accent">{month_label(active_key)}</span></h1>
    <p class="header-subtitle">Suivez vos dépenses en temps réel · Pilotez votre budget avec précision.</p>
</div>
""", unsafe_allow_html=True)

    render_sidebar()
    render_quick_add()
    st.markdown("---")

    df      = build_df()
    summary = compute_summary(active_config(), df)

    render_metrics(summary)
    st.markdown("---")

    col_form, col_status = st.columns([1, 1], gap="large")
    with col_form:
        render_expense_form()
        render_csv_import()
    with col_status:
        if df.empty:
            st.markdown('<div class="sh"><span class="sh-title">📊 État du budget</span><div class="sh-line"></div></div>', unsafe_allow_html=True)
            st.info("Ajoutez vos premières dépenses pour voir l'état de votre budget en temps réel.")
            cfg = active_config()
            daily_v = cfg["monthly_budget"] / cfg["days_in_month"] if cfg["days_in_month"] > 0 else 0
            st.markdown(f"""
<div class="p-card">
    <div class="p-card-glow" style="background:#22C55E;"></div>
    <p class="p-card-label">Budget quotidien de départ</p>
    <p class="big-daily" style="color:#22C55E;">{fmt(daily_v)}</p>
    <p class="p-card-sub">sur <strong>{cfg['days_in_month']}</strong> jours</p>
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

    # Footer
    st.markdown("""
<div style="text-align:center;padding:2rem 0 1rem;border-top:1px solid rgba(79,142,255,0.1);margin-top:2rem;">
    <span style="font-size:0.72rem;color:#334155;letter-spacing:0.08em;">
        BUDGET MENSUEL INTELLIGENT · Données stockées localement · 100% privé
    </span>
</div>
""", unsafe_allow_html=True)


if __name__ == "__main__":
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    if get_script_run_ctx() is not None:
        main()
    else:
        import subprocess, sys
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])
