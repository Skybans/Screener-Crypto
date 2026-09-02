import pandas as pd
import numpy as np


def find_pivot_lows(df, start=0, end=None, window=3):
    if end is None:
        end = len(df)
    lows = df['low'].values
    pivots = []
    for i in range(max(start, window), min(end, len(df) - window)):
        segment = lows[i - window:i + window + 1]
        if lows[i] == segment.min():
            pivots.append(i)
    return pivots


def find_pivot_highs(df, start=0, end=None, window=3):
    if end is None:
        end = len(df)
    highs = df['high'].values
    pivots = []
    for i in range(max(start, window), min(end, len(df) - window)):
        segment = highs[i - window:i + window + 1]
        if highs[i] == segment.max():
            pivots.append(i)
    return pivots


def detect_nested_w(df, idx_start, idx_end, window=1):
    """Cherche un W resserré (fenetre fine) dans la plage [idx_start, idx_end]."""
    pivot_lows = find_pivot_lows(df, idx_start, idx_end, window=window)
    pivot_highs = find_pivot_highs(df, idx_start, idx_end, window=window)

    resultats = []
    for idx_a in pivot_lows:
        prix_a = df['low'].iloc[idx_a]
        candidats_b = [h for h in pivot_highs if idx_a < h <= idx_a + 15]
        if not candidats_b:
            continue
        idx_b = candidats_b[0]
        prix_b = df['high'].iloc[idx_b]
        if prix_b <= prix_a:
            continue

        range_fib = prix_b - prix_a
        niveau_618 = prix_b - 0.618 * range_fib
        niveau_100 = prix_a

        apres_b = df.iloc[idx_b + 1: min(idx_b + 15, len(df))]
        if apres_b.empty:
            continue
        idx_c_rel = apres_b['low'].idxmin()
        prix_c = df['low'].loc[idx_c_rel]
        idx_c = df.index.get_loc(idx_c_rel)

        dans_zone = (prix_c <= niveau_618) and (prix_c >= niveau_100)
        if not dans_zone:
            continue

        apres_c = df.iloc[idx_c + 1:]
        validation_idx = None
        for i, row in apres_c.iterrows():
            if row['close'] > prix_b:
                validation_idx = i
                break

        resultats.append({
            'date_A': df['date'].iloc[idx_a], 'prix_A': prix_a,
            'date_B': df['date'].iloc[idx_b], 'prix_B': prix_b,
            'date_C': df['date'].loc[idx_c_rel], 'prix_C': prix_c,
            'valide': validation_idx is not None,
            'date_validation': df['date'].loc[validation_idx] if validation_idx is not None else None,
        })
    return resultats


def detect_macro_w(df, window=3, max_gap=60, lookback=180):
    """Detecte le grand W, limite a une fenetre recente (lookback jours)
    pour eviter de remonter des structures obsoletes."""
    idx_min = max(0, len(df) - lookback)
    pivot_lows = find_pivot_lows(df, start=idx_min, window=window)

    resultats = []
    for idx_a in pivot_lows:
        prix_a = df['low'].iloc[idx_a]

        fin_recherche = min(idx_a + max_gap, len(df))
        zone_recherche = df.iloc[idx_a + 1: fin_recherche]
        if zone_recherche.empty:
            continue

        idx_b_rel = zone_recherche['high'].idxmax()
        idx_b = df.index.get_loc(idx_b_rel)
        prix_b = df['high'].loc[idx_b_rel]

        if prix_b <= prix_a:
            continue

        range_fib = prix_b - prix_a
        niveau_618 = prix_b - 0.618 * range_fib
        niveau_100 = prix_a

        # 2eme jambe = ce qui suit B, dans une fenetre raisonnable (pas jusqu'a la fin des donnees)
        idx_leg2_start = idx_b + 1
        idx_leg2_end = min(idx_b + max_gap, len(df))

        resultats.append({
            'date_A': df['date'].iloc[idx_a], 'prix_A': prix_a,
            'date_B': df['date'].iloc[idx_b], 'prix_B': prix_b,
            'niveau_618': niveau_618, 'niveau_100': niveau_100,
            'idx_leg2_start': idx_leg2_start, 'idx_leg2_end': idx_leg2_end,
            'idx_A': idx_a, 'idx_B': idx_b,
        })
    return resultats


def analyser_actif(nom, chemin_csv):
    df = pd.read_csv(chemin_csv)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    print(f"\n{'=' * 65}")
    print(f"{nom}")
    print("=" * 65)

    macros = detect_macro_w(df, window=3)
    if not macros:
        print("   Aucun grand W (macro) detecte.")
        return

    prix_actuel = df['close'].iloc[-1]

    # On ne garde que les candidats dont le prix ACTUEL est dans la zone Fibo 61.8%-100%
    macros_pertinents = [
        m for m in macros
        if m['niveau_100'] <= prix_actuel <= m['niveau_618']
    ]

    print(f"\n  Prix actuel : {prix_actuel:.6f}")

    if not macros_pertinents:
        print(f"\n   -> Aucun grand W actuellement pertinent (le prix n'est dans aucune zone Fibo 61.8%-100%).")
        print(f"   STATUT GLOBAL : RIEN A SIGNALER")
        return

    # Deduplication : on regroupe par point B (souvent le meme sommet detecte plusieurs fois
    # avec des A differents), et on garde le A le plus bas (jambe la plus significative) par groupe
    groupes = {}
    for m in macros_pertinents:
        cle = m['date_B']
        if cle not in groupes or m['prix_A'] < groupes[cle]['prix_A']:
            groupes[cle] = m

    candidats_finaux = sorted(groupes.values(), key=lambda m: m['date_B'], reverse=True)

    print(f"  {len(macros_pertinents)} candidats bruts -> {len(candidats_finaux)} structure(s) distincte(s) apres deduplication\n")

    statuts_globaux = []

    for macro in candidats_finaux:
        print(f"  --- Structure : A {macro['date_A'].date()} ({macro['prix_A']:.6f})  ->  B {macro['date_B'].date()} ({macro['prix_B']:.6f}) ---")
        print(f"      Zone Fibo 61.8%-100% : {macro['niveau_618']:.6f} a {macro['niveau_100']:.6f}")

        nested = detect_nested_w(df, macro['idx_leg2_start'], macro['idx_leg2_end'], window=1)

        if not nested:
            print(f"      -> Pas de W daily nichE detectE pour l'instant.")
            print(f"      STATUT : A SURVEILLER\n")
            statuts_globaux.append("A SURVEILLER")
            continue

        a_acheter = any(n['valide'] for n in nested)
        for n in nested:
            statut = "VALIDE" if n['valide'] else "en formation"
            ligne = f"      W nichE -> A: {n['date_A'].date()} ({n['prix_A']:.6f})  B: {n['date_B'].date()} ({n['prix_B']:.6f})  [{statut}]"
            if n['valide']:
                ligne += f"  validE le {n['date_validation'].date()}"
            print(ligne)

        print(f"      STATUT : {'A ACHETER' if a_acheter else 'A SURVEILLER'}\n")
        statuts_globaux.append("A ACHETER" if a_acheter else "A SURVEILLER")

    print(f"  ===> RESUME {nom} : {', '.join(sorted(set(statuts_globaux)))}")
    return


def structure_est_haussiere(df, idx_a, idx_b, prix_a, prix_b, window=3):
    """Rejette une structure si elle correspond a une tendance baissiere classique :
    le point A est un creux PLUS BAS que le creux precedent, ET le point B est
    un sommet PLUS BAS que le sommet precedent. Si les deux conditions ne sont
    pas reunies, on considere que ce n'est pas (ou plus) une tendance baissiere claire."""
    pivot_lows_avant = find_pivot_lows(df, start=0, end=idx_a, window=window)
    pivot_highs_avant = find_pivot_highs(df, start=0, end=idx_a, window=window)

    creux_plus_bas = False
    sommet_plus_bas = False

    if pivot_lows_avant:
        prix_low_precedent = df['low'].iloc[pivot_lows_avant[-1]]
        if prix_a < prix_low_precedent:
            creux_plus_bas = True

    if pivot_highs_avant:
        prix_high_precedent = df['high'].iloc[pivot_highs_avant[-1]]
        if prix_b < prix_high_precedent:
            sommet_plus_bas = True

    # Rejete uniquement si les DEUX conditions de la tendance baissiere sont reunies
    return not (creux_plus_bas and sommet_plus_bas)


def analyser_df(nom, df, recency_max_jours=30):
    """Version silencieuse : retourne les resultats sous forme de donnees
    au lieu de les afficher, pour pouvoir scanner beaucoup d'actifs d'affilee.

    recency_max_jours : une validation de W niche ne compte pour "A ACHETER"
    que si elle date de moins de X jours (structure recente = signal actionnable)."""
    if len(df) < 30:
        return {'nom': nom, 'statut': 'DONNEES INSUFFISANTES', 'structures': []}

    macros = detect_macro_w(df, window=3)
    if not macros:
        return {'nom': nom, 'statut': 'RIEN A SIGNALER', 'structures': []}

    prix_actuel = df['close'].iloc[-1]
    date_reference = df['date'].iloc[-1]

    macros_pertinents = [
        m for m in macros
        if m['niveau_100'] <= prix_actuel <= m['niveau_618']
    ]

    if not macros_pertinents:
        return {'nom': nom, 'statut': 'RIEN A SIGNALER', 'structures': [], 'prix_actuel': prix_actuel}

    groupes = {}
    for m in macros_pertinents:
        cle = m['date_B']
        if cle not in groupes or m['prix_A'] < groupes[cle]['prix_A']:
            groupes[cle] = m

    candidats_finaux = sorted(groupes.values(), key=lambda m: m['date_B'], reverse=True)

    # On ecarte les structures qui correspondent encore a une tendance baissiere classique
    candidats_finaux = [
        m for m in candidats_finaux
        if structure_est_haussiere(df, m['idx_A'], m['idx_B'], m['prix_A'], m['prix_B'])
    ]

    if not candidats_finaux:
        return {'nom': nom, 'statut': 'RIEN A SIGNALER', 'structures': [], 'prix_actuel': prix_actuel}

    structures = []
    statuts_globaux = []

    for macro in candidats_finaux:
        nested = detect_nested_w(df, macro['idx_leg2_start'], macro['idx_leg2_end'], window=1)

        # Une validation ne compte que si elle est recente (structure actionnable maintenant)
        validations_recentes = [
            n for n in nested
            if n['valide'] and (date_reference - n['date_validation']).days <= recency_max_jours
        ]
        a_acheter = len(validations_recentes) > 0

        statut = "A ACHETER" if a_acheter else "A SURVEILLER"
        statuts_globaux.append(statut)

        structures.append({
            'date_A': macro['date_A'], 'prix_A': macro['prix_A'],
            'date_B': macro['date_B'], 'prix_B': macro['prix_B'],
            'nb_w_niches': len(nested),
            'w_niche_valide': a_acheter,
            'statut': statut,
        })

    statut_global = "A ACHETER" if "A ACHETER" in statuts_globaux else "A SURVEILLER"

    return {
        'nom': nom,
        'statut': statut_global,
        'prix_actuel': prix_actuel,
        'structures': structures,
    }


if __name__ == "__main__":
    analyser_actif("WISHBONE - Daily", "data/WISHBONE_USDT_daily.csv")
