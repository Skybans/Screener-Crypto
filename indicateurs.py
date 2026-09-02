import pandas as pd


def ema(series, period):
    """Moyenne mobile exponentielle, meme formule que TradingView."""
    return series.ewm(span=period, adjust=False).mean()


def rsi(series, period=14):
    """RSI (Wilder), meme formule que TradingView."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def ema5_au_dessus_ema10(df, rapide=5, lent=10):
    """True si l'EMA rapide est actuellement au-dessus de l'EMA lente
    (etat, peu importe quand le croisement a eu lieu)."""
    ema_rapide = ema(df['close'], rapide)
    ema_lente = ema(df['close'], lent)
    return ema_rapide.iloc[-1] > ema_lente.iloc[-1]


def passe_filtres(df, rsi_max=60):
    """Applique le filtre EMA + RSI sur la derniere bougie cloturee.
    Retourne (True/False, valeurs pour info)."""
    if len(df) < 20:
        return False, {}

    ema5 = ema(df['close'], 5)
    ema10 = ema(df['close'], 10)
    rsi14 = rsi(df['close'], 14)

    ema_ok = ema5.iloc[-1] > ema10.iloc[-1]
    rsi_actuel = rsi14.iloc[-1]
    rsi_ok = rsi_actuel <= rsi_max

    infos = {
        'ema5': ema5.iloc[-1],
        'ema10': ema10.iloc[-1],
        'ema_ok': ema_ok,
        'rsi14': rsi_actuel,
        'rsi_ok': rsi_ok,
    }

    return (ema_ok and rsi_ok), infos


if __name__ == "__main__":
    actifs = [
        ("BLESS", "data/BLESS_USDT_daily.csv"),
        ("PIPPIN", "data/PIPPIN_USDT_daily.csv"),
        ("WISHBONE", "data/WISHBONE_USDT_daily.csv"),
    ]

    for nom, chemin in actifs:
        df = pd.read_csv(chemin)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)

        ok, infos = passe_filtres(df)

        print(f"\n{nom}")
        print(f"   EMA5  : {infos.get('ema5', 0):.6f}")
        print(f"   EMA10 : {infos.get('ema10', 0):.6f}")
        print(f"   EMA5 > EMA10 : {infos.get('ema_ok')}")
        print(f"   RSI14 : {infos.get('rsi14', 0):.2f}  (<= 60 ? {infos.get('rsi_ok')})")
        print(f"   PASSE LES FILTRES : {ok}")
