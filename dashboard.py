"""
Tableau de bord — Crypto Scanner (v3)
--------------------------------------------------------------
Corrige le bug d'affichage HTML (indentation) et le conflit de theme
clair/sombre. Design : degrade sombre/vert, boutons "liquid glass".
Le theme sombre est fige via .streamlit/config.toml (pas seulement du CSS).
"""

import streamlit as st
import pandas as pd
import os
import glob
import json
from datetime import datetime, timedelta

st.set_page_config(page_title="Crypto Scanner", page_icon="📊", layout="wide")

# ============================================================
# STYLE — degrade vert sombre + boutons "liquid glass"
# ============================================================

CSS = """
<style>
.stApp {
    background: radial-gradient(circle at 20% 0%, #0f1f12 0%, #05070a 55%, #030405 100%);
}
.carte-actif {
    background: rgba(20, 30, 22, 0.55);
    border: 1px solid rgba(83, 252, 24, 0.25);
    border-radius: 16px;
    padding: 18px 22px;
    margin-bottom: 12px;
    backdrop-filter: blur(18px) saturate(160%);
    -webkit-backdrop-filter: blur(18px) saturate(160%);
    box-shadow: 0 0 24px rgba(83, 252, 24, 0.06), inset 0 1px 0 rgba(255,255,255,0.06);
}
.badge-acheter {
    background: rgba(83, 252, 24, 0.18);
    color: #7dff4f;
    border: 1px solid rgba(83, 252, 24, 0.5);
    padding: 3px 12px; border-radius: 20px; font-size: 12px; font-weight: 700;
    text-shadow: 0 0 8px rgba(83,252,24,0.5);
}
.badge-surveiller {
    background: rgba(251, 191, 36, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.4);
    padding: 3px 12px; border-radius: 20px; font-size: 12px; font-weight: 700;
}
.badge-nouveau {
    background: rgba(239, 68, 68, 0.18);
    color: #ff8080;
    border: 1px solid rgba(255, 128, 128, 0.4);
    padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: 700;
    margin-left: 6px;
}
.nom-actif { font-size: 19px; font-weight: 800; color: #f0fff2; letter-spacing: 0.3px; }
.info-secondaire { color: #7fa085; font-size: 13px; }

/* Boutons style verre "Kick" : vert neon plus marque, glow visible */
div[data-testid="stLinkButton"] a, div.stButton > button {
    background: linear-gradient(135deg, rgba(83,252,24,0.28), rgba(255,255,255,0.05)) !important;
    backdrop-filter: blur(16px) saturate(180%) !important;
    -webkit-backdrop-filter: blur(16px) saturate(180%) !important;
    border: 1px solid rgba(83,252,24,0.45) !important;
    border-radius: 12px !important;
    color: #eaffe6 !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 20px rgba(83,252,24,0.12), inset 0 1px 0 rgba(255,255,255,0.15) !important;
    transition: all 0.2s ease;
}
div[data-testid="stLinkButton"] a:hover, div.stButton > button:hover {
    background: linear-gradient(135deg, rgba(83,252,24,0.5), rgba(255,255,255,0.1)) !important;
    border: 1px solid rgba(83,252,24,0.8) !important;
    box-shadow: 0 4px 26px rgba(83,252,24,0.3), inset 0 1px 0 rgba(255,255,255,0.2) !important;
    transform: translateY(-1px);
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

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

FICHIER_NOTIF_LUES = "notifications_lues.json"


def charger_notifs_lues():
    if os.path.exists(FICHIER_NOTIF_LUES):
        with open(FICHIER_NOTIF_LUES) as f:
            return set(json.load(f))
    return set()


def sauvegarder_notifs_lues(lues):
    with open(FICHIER_NOTIF_LUES, "w") as f:
        json.dump(list(lues), f)


notifs_supprimees = charger_notifs_lues()

# On construit une notification par scan recent (les 10 derniers), sauf celles deja supprimees
notifications = []
for d in dates_disponibles[:10]:
    if d in notifs_supprimees:
        continue
    df_n = pd.read_csv(f"resultats/resultats_{d}.csv")
    nb_acheter = int((df_n['statut'] == 'A ACHETER').sum())
    nb_surveiller = int((df_n['statut'] == 'A SURVEILLER').sum())
    notifications.append({
        'date': d,
        'texte': f"Scan du {d} — {nb_acheter} à acheter, {nb_surveiller} à surveiller",
    })

col_titre, col_cloche = st.columns([6, 1])
with col_titre:
    st.title("📊 Crypto Scanner")
    st.caption(f"Dernier scan : {date_derniere_maj}")
with col_cloche:
    label_cloche = "🔔 🔴" if notifications else "🔔"
    with st.popover(label_cloche, use_container_width=True):
        st.markdown("**Notifications**")
        if not notifications:
            st.caption("Aucune nouvelle notification.")
        else:
            for notif in notifications:
                col_texte, col_croix = st.columns([5, 1])
                col_texte.write(notif['texte'])
                if col_croix.button("✕", key=f"suppr_{notif['date']}"):
                    notifs_supprimees.add(notif['date'])
                    sauvegarder_notifs_lues(notifs_supprimees)
                    st.rerun()

st.divider()

# ============================================================
# SELECTION DE LA DATE + CHARGEMENT
# ============================================================

date_choisie = st.selectbox("Date du scan", dates_disponibles)
df = pd.read_csv(f"resultats/resultats_{date_choisie}.csv")

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
# Important : le HTML est construit SANS indentation en debut de ligne,
# sinon Streamlit/Markdown l'interprete comme un bloc de code brut.
# ============================================================


def construire_carte_html(actif, badge_class, badge_texte, badge_nouveau_html, exchanges, prix):
    lignes = [
        '<div class="carte-actif">',
        f'<span class="nom-actif">{actif}</span> ',
        f'<span class="{badge_class}">{badge_texte}</span>{badge_nouveau_html}',
        f'<br><span class="info-secondaire">{exchanges} · {prix:.6g} $</span>',
        '</div>',
    ]
    return "".join(lignes)


def afficher_cartes(dataframe, badge_class, badge_texte):
    if dataframe.empty:
        st.info("Aucun actif dans cette catégorie.")
        return
    for _, row in dataframe.iterrows():
        actif = row['actif']
        est_nouveau = actif in actifs_nouveaux
        verifie = est_verifie(actif)
        badge_nouveau_html = ' <span class="badge-nouveau">NOUVEAU</span>' if est_nouveau else ''

        col_info, col_action = st.columns([5, 1])
        with col_info:
            html = construire_carte_html(actif, badge_class, badge_texte, badge_nouveau_html, row['exchanges'], row['prix_moyen'])
            st.markdown(html, unsafe_allow_html=True)
        with col_action:
            st.link_button("📈 Graphique", lien_tradingview(actif, row['exchanges']), width="stretch")
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
