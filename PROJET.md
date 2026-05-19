# Budget Mensuel Intelligent — Documentation complète

## Vue d'ensemble

Application web de gestion de budget personnel, construite avec **Streamlit** (Python).
Stockage local en JSON, pas de base de données, pas de compte utilisateur.
Accessible depuis un navigateur via `localhost:8501`.

---

## Stack technique

| Composant | Technologie |
|---|---|
| Interface web | Streamlit |
| Graphiques | Plotly Express + Plotly Graph Objects |
| Données | Pandas + JSON local |
| Langage | Python 3.x |
| Environnement | `.venv` dans le dossier du projet |

### Dépendances (installées dans `.venv`)
- `streamlit`
- `pandas`
- `plotly`

---

## Structure des fichiers

```
test/
├── app.py                  ← Application principale (unique fichier Python)
├── budget_data.json        ← Données persistées (créé automatiquement)
├── PROJET.md               ← Ce fichier
├── .venv/                  ← Environnement virtuel Python
│   └── Scripts/
│       ├── python.exe
│       └── streamlit.exe
└── .vscode/
    └── launch.json         ← Config lancement VS Code (Run & Debug)
```

---

## Lancer l'application

```powershell
# Depuis un terminal PowerShell dans le dossier du projet
.venv\Scripts\python.exe -m streamlit run app.py
```

Ou via VS Code : `Ctrl+Shift+D` → sélectionner **"Streamlit: Run app.py"** → ▶

L'app s'ouvre automatiquement sur `http://localhost:8501`.

> **Note importante** : ne jamais lancer avec `python app.py` seul — le fichier
> contient un guard qui détecte ce cas et relance via Streamlit automatiquement,
> mais l'usage normal reste `streamlit run app.py`.

---

## Structure des données — `budget_data.json`

```json
{
  "settings": {
    "currency": "EUR"
  },
  "recurring": [
    {
      "description": "Loyer",
      "amount": 800.0,
      "category": "🏠 Logement / Factures"
    }
  ],
  "2026-04": {
    "config": {
      "monthly_budget": 900.0,
      "days_in_month": 30,
      "current_day": 15
    },
    "category_budgets": {
      "🍔 Alimentation": 200.0,
      "🚗 Transport": 0.0
    },
    "expenses": [
      {
        "date": "2026-04-15",
        "amount": 45.50,
        "category": "🍔 Alimentation",
        "description": "Courses Migros"
      }
    ]
  }
}
```

Clés spéciales au niveau racine : `settings`, `recurring`.
Toutes les autres clés sont des mois au format `YYYY-MM`.

---

## Catégories disponibles

```
🍔 Alimentation · 🚗 Transport · 🏠 Logement / Factures · 💊 Santé
🎮 Loisirs · 👗 Vêtements · 📱 Abonnements · 🍽️ Restaurant
✈️ Voyage · 🎁 Cadeaux · 📦 Autres
```

---

## Devises supportées

| Code | Symbole | Nom |
|---|---|---|
| EUR | € | Euro |
| CHF | Fr. | Franc suisse |
| USD | $ | Dollar US |
| GBP | £ | Livre sterling |
| CAD | CA$ | Dollar canadien |
| JPY | ¥ | Yen japonais |

Sélection dans la sidebar. Stockée dans `settings.currency`.

---

## Fonctionnalités — détail

### Sidebar (panneau gauche)
- **Sélecteur de mois** : navigue entre les mois existants
- **Créer un nouveau mois** : sélectionne année + mois → crée l'entrée JSON + applique les récurrences
- **Devise** : sélecteur parmi 6 devises, s'applique partout
- **Configuration du mois** : budget mensuel, nb de jours, jour actuel
- **Enveloppes par catégorie** : budget max par catégorie (0 = pas de limite)
- **Dépenses récurrentes** : liste + ajout/suppression. Appliquées au 1er du mois à la création
- **Réinitialiser le mois** : vide toutes les dépenses du mois actif

### Page principale

#### ⚡ Ajout rapide
Barre en haut : description + montant + catégorie + bouton ➕ sur une seule ligne.
Date = aujourd'hui automatiquement.

#### 7 métriques en haut
1. Budget mensuel
2. Total dépensé
3. Budget restant
4. Jours restants
5. Budget/jour initial (budget ÷ nb jours)
6. Budget/jour recalculé (restant ÷ jours restants) avec delta
7. **Prévision fin de mois** (moyenne/j actuelle × nb jours total) avec delta

#### Formulaire d'ajout détaillé
Date + montant + catégorie + description. Vide après soumission.

#### Import CSV bancaire (expander sous le formulaire)
- Upload d'un fichier `.csv`
- Aperçu des 3 premières lignes
- Sélection manuelle des colonnes date / montant / description
- Catégorie par défaut pour toutes les lignes importées
- Formats de date acceptés : `DD/MM/YYYY`, `YYYY-MM-DD`, `DD-MM-YYYY`, `MM/DD/YYYY`, `DD.MM.YYYY`
- Les montants négatifs et les lignes invalides sont ignorés

#### Carte de statut (colonne droite)
- Message vert/orange/rouge selon l'écart avec le rythme idéal
  - Vert : `idéal - réel > 5`
  - Orange : entre -5 et +5
  - Rouge : `idéal - réel < -5`
- Affiche le budget/jour restant en grand
- Tableau : rythme idéal, réel, écart, moyenne/j, prévision fin mois
- Alertes enveloppes : orange si ≥ 80%, rouge si ≥ 100% du budget catégorie

#### Tableau des dépenses (éditable)
- **`st.data_editor`** avec `num_rows="dynamic"`
- Édition inline de toutes les cellules (date, montant, catégorie, description)
- Suppression : sélectionner une ligne → touche `Suppr`
- Ajout de ligne : bouton `+` en bas du tableau
- Bouton **Sauvegarder** pour valider les changements
- Barre de filtres : recherche texte libre + filtre par catégorie (stats affichées dessous)
- Export CSV du mois complet

#### Graphiques (4 onglets)
1. **Par jour** : barres des dépenses journalières, couleur selon montant
2. **Par catégorie** : camembert (donut) + comparatif dépensé vs enveloppe si budgets définis
3. **Progression** : courbe cumulée réelle vs rythme idéal (tirets verts) + prévision (pointillés orange)
4. **Tendances** : courbes multi-mois par catégorie (nécessite ≥ 2 mois de données), multiselect des catégories

#### Comparaison multi-mois (bas de page)
Visible à partir de 2 mois. Graphique barres budget vs dépensé + tableau récapitulatif avec économies.

---

## Architecture du code — `app.py`

```
CONSTANTES
  CATEGORIES, MOIS_FR, DATA_FILE, DATE_FORMATS, CURRENCIES, CURRENCY_SYMBOLS

PERSISTANCE
  load_data()          → charge budget_data.json
  save_data()          → écrit budget_data.json
  get_month_keys()     → liste des clés YYYY-MM (exclut "recurring", "settings")
  get_recurring()      → liste des dépenses récurrentes
  get_currency()       → code devise actuel ("EUR" par défaut)
  set_currency(code)   → sauvegarde la devise
  fmt(amount)          → formate un montant avec le bon symbole

HELPERS
  current_month_key()      → "YYYY-MM" du jour
  month_label(key)         → "Avril 2026"
  parse_date(raw)          → convertit n'importe quel format en "YYYY-MM-DD"
  ensure_month(key)        → crée le mois s'il n'existe pas + applique récurrences
  _apply_recurring(key)    → injecte les récurrences au 1er du mois

SESSION STATE
  init_state()         → initialise data + active_month au démarrage

ACCESSEURS MOIS ACTIF
  active_config()          → dict config du mois actif
  active_expenses()        → liste des dépenses du mois actif
  active_cat_budgets()     → dict des enveloppes du mois actif
  build_df()               → DataFrame des dépenses du mois actif

LOGIQUE MÉTIER
  compute_summary(config, df)      → dict de toutes les métriques calculées
  get_status(difference)           → tuple (couleur, message)
  get_category_alerts(df, budgets) → dict des catégories en alerte

RENDU UI
  render_sidebar()             → tout le panneau latéral
  _render_recurring_sidebar()  → sous-section des récurrences
  render_quick_add()           → barre d'ajout rapide
  render_expense_form()        → formulaire détaillé
  render_csv_import()          → import CSV (expander)
  render_metrics(summary)      → 7 métriques en colonnes
  render_status_card(summary, df)  → carte état + alertes
  render_expense_table(df)     → tableau éditable + filtres + export
  render_charts(df, summary)   → 4 onglets de graphiques
  render_month_comparison()    → comparaison multi-mois

POINT D'ENTRÉE
  main()               → set_page_config + CSS + init + rendu complet
  if __name__          → guard : lance streamlit si exécuté avec python directement
```

---

## Fonctionnalités prévues / non encore implémentées

### Connexion bancaire automatique
**Objectif** : enregistrer chaque dépense CB automatiquement.

**Contrainte principale** : nécessite que l'app soit déployée **en ligne** (pas en localhost) pour recevoir les callbacks OAuth des banques.

**Option 1 — Notifications téléphone (Android)**
- App Tasker intercepte les notifications push de la banque
- Envoie une requête HTTP à l'app déployée
- Setup : ~1h, gratuit
- Avantage : aucun accès aux données bancaires côté serveur

**Option 2 — Open Banking PSD2 (Europe)**
- API Nordigen/GoCardless (gratuit, couvre banques FR + CH)
- Authentification OAuth → lecture seule des transactions
- Voit solde + transactions (on n'utilise que les transactions)
- Nécessite déploiement en ligne + enregistrement développeur

**Étape préalable obligatoire** : déployer sur Streamlit Cloud (gratuit)
avant d'implémenter l'une ou l'autre option.

---

## Points techniques importants

- `st.set_page_config()` doit être le **premier appel Streamlit** → placé en tête de `main()`
- Le `if __name__ == "__main__"` vérifie `get_script_run_ctx()` pour éviter une boucle infinie de sous-processus Streamlit
- Les mois sont créés à la demande (`ensure_month`), jamais en avance
- Le JSON est sauvegardé à chaque modification (pas de "session perdue")
- `st.data_editor` avec `num_rows="dynamic"` gère nativement ajout/édition/suppression de lignes
- Filtres du tableau = affichage uniquement, la sauvegarde porte toujours sur le dataset complet du mois
