"""
Tableau de bord — Crypto Scanner
--------------------------------------------------------------
Interface web privee pour consulter les resultats du scan quotidien
(fichiers resultats/resultats_AAAA-MM-JJ.csv produits par run_scan.py).
"""

import streamlit as st
import pandas as pd
import os
import glob

st.set_page_config(page_title="Crypto Scanner", page_icon="📊", layout="wide")

st.title("📊 Crypto Scanner — Résultats du scan")

fichiers = sorted(glob.glob("resultats/resultats_*.csv"), reverse=True)

if not fichiers:
    st.warning("Aucun résultat disponible pour l'instant. Le premier scan n'a peut-être pas encore tourné.")
else:
    dates_disponibles = [
        os.path.basename(f).replace("resultats_", "").replace(".csv", "")
        for f in fichiers
    ]

    date_choisie = st.selectbox("Choisir une date de scan", dates_disponibles)
    chemin = f"resultats/resultats_{date_choisie}.csv"
    df = pd.read_csv(chemin)

    df_acheter = df[df['statut'] == 'A ACHETER'].sort_values('actif')
    df_surveiller = df[df['statut'] == 'A SURVEILLER'].sort_values('actif')

    col1, col2, col3 = st.columns(3)
    col1.metric("Total analysé", len(df))
    col2.metric("✅ À acheter", len(df_acheter))
    col3.metric("👀 À surveiller", len(df_surveiller))

    st.divider()

    colonne_gauche, colonne_droite = st.columns(2)

    with colonne_gauche:
        st.subheader("✅ À ACHETER")
        if df_acheter.empty:
            st.info("Aucun actif dans cette catégorie aujourd'hui.")
        else:
            st.dataframe(
                df_acheter[['actif', 'exchanges', 'prix_moyen']],
                use_container_width=True,
                hide_index=True,
            )

    with colonne_droite:
        st.subheader("👀 À SURVEILLER")
        if df_surveiller.empty:
            st.info("Aucun actif dans cette catégorie aujourd'hui.")
        else:
            st.dataframe(
                df_surveiller[['actif', 'exchanges', 'prix_moyen']],
                use_container_width=True,
                hide_index=True,
            )
