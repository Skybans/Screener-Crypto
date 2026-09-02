"""
Scan quotidien complet — Pipeline unique
--------------------------------------------------------------
Fait tout en un seul passage par actif (plus efficace que des scripts
separes) :
  1. Filtres de preselection (Spot / EMA5>EMA10 / RSI<=60)
  2. Exclusions (stablecoins / jetons a effet de levier / actions tokenisees)
  3. Filtre d'age (max 2 ans d'historique)
  4. Detection du pattern en W (grand + niche, avec fraicheur de validation)
  5. Deduplication par actif (across exchanges)
  6. Envoi des resultats sur Telegram
  7. Sauvegarde d'un historique CSV

Variables d'environnement necessaires (a definir en local ou en secrets
GitHub Actions) :
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

import ccxt
import pandas as pd
import re
import os
import time
import requests
from datetime import datetime
from indicateurs import passe_filtres
from detect_w_v2 import analyser_df

# ============================================================
# CONFIGURATION
# ============================================================

AGE_MAX_JOURS = 730          # 2 ans
RECENCY_MAX_JOURS = 30       # une validation de W niche doit dater de < 30 jours
LIMIT_BOUGIES = 800          # historique recupere par actif (couvre l'age + le lookback)

STABLECOINS = {
    "USDT", "USDC", "USDS", "TUSD", "PYUSD", "GHO", "RLUSD", "GUSD",
    "USDP", "DAI", "BUSD", "FDUSD", "USDD", "FRAX", "USDE", "USD1",
}

PATTERN_LEVIER = re.compile(r"\d+[LS]$")

RACINES_ACTIONS_TOKENISEES = {
    "TSLA", "MSTR", "NVDA", "HOOD", "MSFT", "ADBE", "CRCL", "COIN",
    "SNDK", "SKHY", "CRWD", "BMNR", "MU", "XLE", "GME", "SPCX", "APP",
    "GOLD", "SILVER", "XAU", "XAG", "XPT", "UNH", "EEM", "IEMG",
    "HSBC", "QCOM", "AVGO", "JPM", "WMT", "MA", "SGOV", "NVO",
}
SUFFIXES_ACTIONS = ("X", "B", "G", "ON")


def ressemble_a_action_tokenisee(base):
    if base.startswith("X") and base[1:] in RACINES_ACTIONS_TOKENISEES:
        return True
    for racine in RACINES_ACTIONS_TOKENISEES:
        if base == racine:
            return True
        for suffixe in SUFFIXES_ACTIONS:
            if base == racine + suffixe:
                return True
    return False


def est_actif_valide(symbole, marche, nom_exchange):
    base = symbole.split("/")[0]
    if base in STABLECOINS:
        return False
    if PATTERN_LEVIER.search(base):
        return False
    if nom_exchange == "OKX":
        if marche.get('info', {}).get('instCategory') != "1":
            return False
    if nom_exchange == "Gate.io":
        base_name = marche.get('info', {}).get('base_name', '')
        if 'xstock' in base_name.lower():
            return False
    if ressemble_a_action_tokenisee(base):
        return False
    return True


def envoyer_telegram(token, chat_id, message):
    """Envoie un message Telegram. Retourne True si succes."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=15,
        )
        return r.ok
    except Exception as e:
        print(f"Erreur envoi Telegram : {e}")
        return False


def decouper_message(lignes, titre, limite=3500):
    """Decoupe une longue liste de lignes en plusieurs messages Telegram
    (limite Telegram = 4096 caracteres, on garde une marge)."""
    messages = []
    message_actuel = f"<b>{titre}</b>\n\n"
    for ligne in lignes:
        if len(message_actuel) + len(ligne) > limite:
            messages.append(message_actuel)
            message_actuel = ""
        message_actuel += ligne + "\n"
    if message_actuel.strip():
        messages.append(message_actuel)
    return messages


# ============================================================
# PIPELINE PRINCIPAL
# ============================================================

exchanges_ccxt = {
    "OKX": ccxt.okx(),
    "Kraken": ccxt.kraken(),
    "Gate.io": ccxt.gate(),
    "LBank": ccxt.lbank(),
}

print(f"Debut du scan complet — {datetime.now().isoformat()}\n")

resultats_finaux = []
total_paires_analysees = 0

for nom_exchange, exchange in exchanges_ccxt.items():
    print(f"\n{'=' * 50}")
    print(f"Exchange : {nom_exchange}")
    print("=" * 50)

    try:
        markets = exchange.load_markets()
    except Exception as e:
        print(f"   Impossible de charger les marches : {e}")
        continue

    paires_spot = [
        symbole for symbole, m in markets.items()
        if m.get('spot', False) and symbole.endswith('/USDT') and est_actif_valide(symbole, m, nom_exchange)
    ]
    print(f"   {len(paires_spot)} paires Spot/USDT valides a analyser.")

    for i, symbole in enumerate(paires_spot):
        total_paires_analysees += 1
        try:
            # ETAPE 1 : recuperation LEGERE (juste assez pour EMA/RSI) pour trier vite
            ohlcv_leger = exchange.fetch_ohlcv(symbole, timeframe='1d', limit=30)
            if len(ohlcv_leger) < 20:
                continue

            df_leger = pd.DataFrame(ohlcv_leger, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            ok_filtres, _ = passe_filtres(df_leger)
            if not ok_filtres:
                continue

            time.sleep(exchange.rateLimit / 1000)

            # ETAPE 2 : uniquement pour les actifs qui passent le tri, on recupere
            # l'historique complet (plus lourd) pour l'age + la detection du W
            ohlcv = exchange.fetch_ohlcv(symbole, timeframe='1d', limit=LIMIT_BOUGIES)
            if len(ohlcv) < 30:
                continue

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.sort_values('date').reset_index(drop=True)

            # Filtre d'age
            age_jours = (df['date'].iloc[-1] - df['date'].iloc[0]).days
            if age_jours >= AGE_MAX_JOURS:
                continue

            # Detection du pattern en W
            resultat = analyser_df(symbole, df, recency_max_jours=RECENCY_MAX_JOURS)

            if resultat['statut'] in ('A SURVEILLER', 'A ACHETER'):
                resultat['exchange'] = nom_exchange
                resultat['symbole'] = symbole
                resultats_finaux.append(resultat)
                print(f"   [{i+1}/{len(paires_spot)}] {symbole} -> {resultat['statut']}")

        except Exception:
            continue

        time.sleep(exchange.rateLimit / 1000)

print(f"\n\n{total_paires_analysees} paires analysees au total.")
print(f"{len(resultats_finaux)} resultats bruts (avant deduplication).")

# ============================================================
# DEDUPLICATION PAR ACTIF
# ============================================================

if resultats_finaux:
    df_export = pd.DataFrame([{
        'exchange': r['exchange'],
        'symbole': r['symbole'],
        'statut': r['statut'],
        'prix_actuel': r['prix_actuel'],
    } for r in resultats_finaux])

    df_export['base'] = df_export['symbole'].str.split('/').str[0]

    lignes_consolidees = []
    for base, groupe in df_export.groupby('base'):
        statut_final = "A ACHETER" if (groupe['statut'] == 'A ACHETER').any() else "A SURVEILLER"
        exchanges_concernes = ", ".join(sorted(groupe['exchange'].unique()))
        prix_moyen = groupe['prix_actuel'].mean()
        lignes_consolidees.append({
            'actif': base,
            'statut': statut_final,
            'exchanges': exchanges_concernes,
            'prix_moyen': prix_moyen,
        })

    df_consolide = pd.DataFrame(lignes_consolidees).sort_values(
        ['statut', 'actif'], ascending=[False, True]
    )
else:
    df_consolide = pd.DataFrame(columns=['actif', 'statut', 'exchanges', 'prix_moyen'])

print(f"\n{len(df_consolide)} actifs uniques apres deduplication.")
print(df_consolide.to_string(index=False))

# ============================================================
# SAUVEGARDE HISTORIQUE
# ============================================================

os.makedirs("resultats", exist_ok=True)
date_str = datetime.now().strftime("%Y-%m-%d")
chemin_csv = f"resultats/resultats_{date_str}.csv"
df_consolide.to_csv(chemin_csv, index=False)
print(f"\nSauvegarde : {chemin_csv}")

# ============================================================
# ENVOI TELEGRAM
# ============================================================

token = os.environ.get("TELEGRAM_BOT_TOKEN")
chat_id = os.environ.get("TELEGRAM_CHAT_ID")

if not token or not chat_id:
    print("\nTELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID non defini(s) — notification non envoyee.")
    print("(normal en test local si tu n'as pas encore configure ces variables)")
else:
    a_acheter = df_consolide[df_consolide['statut'] == 'A ACHETER']
    a_surveiller = df_consolide[df_consolide['statut'] == 'A SURVEILLER']

    if a_acheter.empty and a_surveiller.empty:
        envoyer_telegram(token, chat_id, f"Scan du {date_str} : aucun signal aujourd'hui.")
    else:
        if not a_acheter.empty:
            lignes = [f"• <b>{row['actif']}</b> ({row['exchanges']}) — {row['prix_moyen']:.6g}"
                      for _, row in a_acheter.iterrows()]
            for msg in decouper_message(lignes, f"A ACHETER — {date_str}"):
                envoyer_telegram(token, chat_id, msg)

        if not a_surveiller.empty:
            lignes = [f"• {row['actif']} ({row['exchanges']}) — {row['prix_moyen']:.6g}"
                      for _, row in a_surveiller.iterrows()]
            for msg in decouper_message(lignes, f"A SURVEILLER — {date_str}"):
                envoyer_telegram(token, chat_id, msg)

    print("\nNotifications Telegram envoyees.")

print("\nScan termine.")
