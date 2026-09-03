"""
Tableau de bord — Crypto Scanner (v2, design pro)
--------------------------------------------------------------
Interface web privee complete : design soigne, cloche de notification,
liens directs TradingView, recherche/tri, badge "nouveau", historique
des scans, et suivi des actifs deja verifies.
"""

import streamlit as st
import pandas as pd
import os
import glob
import json
from datetime import datetime, timedelta

st.set_page_config(page_title="Crypto Scanner", page_icon="📊", layout="wide")

# ============================================================
# STYLE — theme sombre pro
# ============================================================

st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .carte-actif {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 10px;
    }
    .badge-acheter {
        background-color: #1a4d2e; color: #4ade80;
        padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600;
    }
    .badge-surveiller {
        background-color: #4d3b1a; color: #fbbf24;
        padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600;
    }
    .badge-nouveau {
        background-color: #7f1d1d; color: #fca5a5;
        padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: 600;
        margin-left: 6px;
    }
    .nom-actif { font-size: 18px; font-weight: 700; color: #f0f6fc; }
    .info-secondaire { color: #8b949e; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# CHARGEMENT DES DONNEES
# ============================================================

FICHIER_SUIVI = "actifs_verifies.json"

def charger_suivi():
    if os.path.exists(FICHIER_SUIVI):
        with open(FICHIER_SUIVI) as f:
            return json.load(f)
    return {}

def sauvegarder_suivi(suivi):
    with open(FICHIER_SUIVI, "w") as f:
        json.dump(suivi, f)

fichiers = sorted(glob.glob("resultats/resultats_*.csv"), reverse=True)

if not fichiers:
    st.warning("Aucun résultat disponible pour l'instant. Le premier scan n'a peut-être pas encore tourné.")
    st.stop()

dates_disponibles = [
    os.path.basename(f).replace("resultats_", "").replace(".csv", "")
    for f in fichiers
]

# ============================================================
# EN-TETE avec cloche de notification
# ============================================================

date_derniere_maj = dates_disponibles[0]
try:
    date_obj = datetime.strptime(date_derniere_maj, "%Y-%m-%d")
    scan_recent = (datetime.now() - date_obj) < timedelta(hours=36)
except Exception:
    scan_recent = False

col_titre, col_cloche = st.columns([6, 1])
with col_titre:
    st.title("📊 Crypto Scanner")
    st.caption(f"Dernier scan : {date_derniere_maj}")
with col_cloche:
    if scan_recent:
        st.markdown(
            "<div style='text-align:right; font-size:32px;'>🔔<span style='color:#ef4444; font-size:14px;'>●</span></div>",
            unsafe_allow_html=True,
        )
        st.caption("Nouveau scan")
    else:
        st.markdown("<div style='text-align:right; font-size:32px; opacity:0.4;'>🔔</div>", unsafe_allow_html=True)

st.divider()

# ============================================================
# SELECTION DE LA DATE + CHARGEMENT
# ============================================================

date_choisie = st.selectbox("Date du scan", dates_disponibles)
df = pd.read_csv(f"resultats/resultats_{date_choisie}.csv")

# Comparaison avec le scan precedent pour le badge "nouveau"
idx_actuel = dates_disponibles.index(date_choisie)
actifs_nouveaux = set()
if idx_actuel + 1 < len(dates_disponibles):
    df_precedent = pd.read_csv(f"resultats/resultats_{dates_disponibles[idx_actuel + 1]}.csv")
    actifs_nouveaux = set(df['actif']) - set(df_precedent['actif'])

# ============================================================
# METRIQUES
# ============================================================

df_acheter = df[df['statut'] == 'A ACHETER'].sort_values('actif')
df_surveiller = df[df['statut'] == 'A SURVEILLER'].sort_values('actif')

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total analysé", len(df))
c2.metric("✅ À acheter", len(df_acheter))
c3.metric("👀 À surveiller", len(df_surveiller))
c4.metric("🆕 Nouveaux", len(actifs_nouveaux))

st.divider()

# ============================================================
# RECHERCHE ET TRI
# ============================================================

col_recherche, col_tri = st.columns([3, 1])
with col_recherche:
    recherche = st.text_input("🔍 Rechercher un actif", "")
with col_tri:
    tri = st.selectbox("Trier par", ["Alphabétique", "Prix", "Nombre d'exchanges"])

def appliquer_tri(dataframe):
    if tri == "Prix":
        return dataframe.sort_values('prix_moyen', ascending=False)
    elif tri == "Nombre d'exchanges":
        dataframe = dataframe.copy()
        dataframe['nb_exch'] = dataframe['exchanges'].str.count(',') + 1
        return dataframe.sort_values('nb_exch', ascending=False)
    return dataframe.sort_values('actif')

if recherche:
    df_acheter = df_acheter[df_acheter['actif'].str.contains(recherche, case=False, na=False)]
    df_surveiller = df_surveiller[df_surveiller['actif'].str.contains(recherche, case=False, na=False)]

df_acheter = appliquer_tri(df_acheter)
df_surveiller = appliquer_tri(df_surveiller)

# ============================================================
# LIEN TRADINGVIEW
# ============================================================

PREFIXES_TV = {"OKX": "OKX", "Kraken": "KRAKEN", "Gate.io": "GATEIO"}

def lien_tradingview(actif, exchanges):
    premier_exchange = exchanges.split(",")[0].strip()
    prefixe = PREFIXES_TV.get(premier_exchange)
    if prefixe:
        return f"https://www.tradingview.com/chart/?symbol={prefixe}%3A{actif}USDT"
    return f"https://www.tradingview.com/symbols/{actif}USDT/"

# ============================================================
# SUIVI DES ACTIFS DEJA VERIFIES
# ============================================================

suivi = charger_suivi()
cle_jour = date_choisie

def est_verifie(actif):
    return suivi.get(cle_jour, {}).get(actif, False)

def basculer_verifie(actif):
    suivi.setdefault(cle_jour, {})
    suivi[cle_jour][actif] = not suivi[cle_jour].get(actif, False)
    sauvegarder_suivi(suivi)

# ============================================================
# AFFICHAGE DES CARTES
# ============================================================

def afficher_cartes(dataframe, badge_class, badge_texte):
    if dataframe.empty:
        st.info("Aucun actif dans cette catégorie.")
        return
    for _, row in dataframe.iterrows():
        actif = row['actif']
        est_nouveau = actif in actifs_nouveaux
        verifie = est_verifie(actif)

        col_info, col_action = st.columns([5, 1])
        with col_info:
            badge_nouveau_html = '<span class="badge-nouveau">NOUVEAU</span>' if est_nouveau else ''
            st.markdown(f"""
            <div class="carte-actif">
                <span class="nom-actif">{actif}</span>
                <span class="{badge_class}">{badge_texte}</span>
                {badge_nouveau_html}
                <br>
                <span class="info-secondaire">{row['exchanges']} · {row['prix_moyen']:.6g} $</span>
            </div>
            """, unsafe_allow_html=True)
        with col_action:
            st.link_button("📈 Graphique", lien_tradingview(actif, row['exchanges']), use_container_width=True)
            st.checkbox("Vérifié", value=verifie, key=f"check_{cle_jour}_{actif}",
                        on_change=basculer_verifie, args=(actif,))

onglet_acheter, onglet_surveiller, onglet_historique = st.tabs(
    ["✅ À acheter", "👀 À surveiller", "📈 Historique"]
)

with onglet_acheter:
    afficher_cartes(df_acheter, "badge-acheter", "À ACHETER")

with onglet_surveiller:
    afficher_cartes(df_surveiller, "badge-surveiller", "À SURVEILLER")

with onglet_historique:
    st.subheader("Évolution du nombre de signaux dans le temps")
    lignes_historique = []
    for f in sorted(fichiers):
        d = os.path.basename(f).replace("resultats_", "").replace(".csv", "")
        df_h = pd.read_csv(f)
        lignes_historique.append({
            'date': d,
            'A ACHETER': (df_h['statut'] == 'A ACHETER').sum(),
            'A SURVEILLER': (df_h['statut'] == 'A SURVEILLER').sum(),
        })
    df_historique = pd.DataFrame(lignes_historique).set_index('date')
    st.line_chart(df_historique)
