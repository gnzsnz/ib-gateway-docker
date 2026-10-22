"""
strat_mom_20_50.py
====================
Croisement de moyennes mobiles (rapide/lente) sur le Close, filtre par le
regime de volatilite du spread pairs-trade MID_THP/MID_VHP (memes
briques Hedge_Ratio/Spread/Vol que le reste de la famille de strategies).

NETTOYAGE effectue par rapport a la version precedente (voir le recap
complet donne au moment de la demande) :
  - Suppression du code mort : rsi_wilder(), la colonne 'rsi', et les
    variables locales 'close'/'z' dans compute_signal n'etaient jamais
    utilisees dans la logique d'entree/sortie.
  - Suppression de Z_Score et 'entry_threshold' (PARAMS) : le signal ne
    vient plus d'un Z-Score (la DESCRIPTION precedente etait obsolete et
    decrivait l'ancienne logique) mais du croisement MA_Fast/MA_Slow.
  - BUG CORRIGE (impact reel verifie, pas juste theorique) : MA_Fast/
    MA_Slow etaient utilisees dans compute_signal mais ABSENTES de
    REQUIRED_FEATURES -> le dropna ne se basait que sur Hedge_Ratio/Vol/
    Vol_Threshold (~20 barres necessaires), PAS sur MA_Slow (qui a besoin
    de 50 barres). Consequence mesuree sur un dataset de test : le point
    de depart post-dropna tombait ~34 jours plus tot que necessaire, et
    "warmup_bars=20" etait alors compte a partir de CE point trop precoce
    -> le premier trade reel se produisait ~1 mois plus tot que dans la
    version corrigee (2020-03-11 contre 2020-04-08 sur mon test). Le
    mecanisme "NaN < NaN renvoie False" empechait bien un trade sur des
    valeurs non definies, mais decalait quand meme la date de premier
    trade valide de facon incorrecte par rapport a l'intention du warmup.
    Desormais MA_Fast/MA_Slow sont dans REQUIRED_FEATURES : le dropna
    garantit explicitement leur disponibilite AVANT que warmup_bars ne
    commence a compter, comme pour toutes les autres features de la
    famille.
  - Fenetres MA (20 et 50) deplacees en dur -> PARAMS (ma_fast_window,
    ma_slow_window), comme demande.

A VERIFIER DE TON COTE (pas change ici, juste signale) :
  - PARAMS["vol_quantile"] = 1 : un quantile de 1 (100e percentile) sur
    une fenetre glissante rend le filtre de regime calme quasiment un
    no-op (la valeur courante fait quasi toujours partie du maximum de sa
    propre fenetre). Le commentaire d'origine ("25e percentile") ne
    correspondait plus a la valeur (1, pas 0.25) -> corrige ici, mais la
    VALEUR elle-meme n'a pas ete changee, a toi de decider si c'est
    voulu.
  - Le filtre de regime porte sur la vol du SPREAD (MID_THP/MID_VHP), pas
    sur celle du Close effectivement trade par le croisement de MA. Ce
    n'est pas forcement une erreur, mais ca merite d'etre un choix
    deliberement assume plutot qu'un heritage du template Z-Score
    d'origine (strategy1.py) -- vaut le coup de te demander si c'est bien
    l'intention.

IMPORTANT anti-lookahead : identique au reste de la famille, tout est
calcule sur des fenetres glissantes causales (rolling standard, ffill
uniquement vers l'avant dans le temps). Le moteur gere le decalage vers
l'Open(t+1) comme d'habitude.
"""

import numpy as np
import pandas as pd

NAME = "strat_mom_20_50"

DESCRIPTION = (
    "Croisement de moyennes mobiles sur le Close (rapide `ma_fast_window` "
    "vs lente `ma_slow_window`) : Long si MA rapide > MA lente, Short si "
    "MA rapide < MA lente. Filtre : on ne prend/renverse une position que "
    "si la volatilite recente du spread pairs-trade MID_THP/MID_VHP est "
    "sous son quantile glissant (regime calme). Toujours investi une fois "
    "le warmup passe (long ou short, jamais a plat)."
)

PARAMS = {
    "hedge_window": 5,          # fenetre du hedge ratio (cov/var + lissage)
    "ma_fast_window": 20,       # fenetre de la moyenne mobile rapide (Close)
    "ma_slow_window": 50,       # fenetre de la moyenne mobile lente (Close)
    "vol_window": 14,           # fenetre de la vol (std du niveau du spread)
    "vol_quantile_window": 5,   # fenetre glissante du quantile de vol
    "vol_quantile": 1,          # quantile utilise comme seuil -- voir avertissement en tete de fichier
    "warmup_bars": 20,          # marge de securite supplementaire au-dela du dropna
    "size": 1.0,                # taille de position (long=+size, short=-size)
}

# Colonnes sur lesquelles le moteur fera un dropna avant compute_signal.
# MA_Fast/MA_Slow desormais incluses (c'etait le bug corrige, voir en tete
# de fichier) ; Z_Score retiree (plus calculee, plus utilisee).
REQUIRED_FEATURES = ["MID_THP", "MID_VHP", "Hedge_Ratio", "Spread",
                      "Vol", "Vol_Threshold", "MA_Fast", "MA_Slow"]


def compute_features(df):
    """
    Toutes les features utilisent .rolling(...) standard (fenetre se
    terminant a la ligne courante incluse) => aucune anticipation.
    Le .ffill() sur Hedge_Ratio ne propage que des valeurs PASSEES
    (dernier hedge ratio valide connu) -> pas de lookahead non plus.
    """
    p = PARAMS
    required_cols = ["MID_THP", "MID_VHP"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"[{NAME}] Colonnes requises manquantes: {missing}")

    y = df["MID_THP"] / 100
    x = df["MID_VHP"] / 100

    hw = p["hedge_window"]
    cov_xy = y.rolling(hw).cov(x)
    var_x = x.rolling(hw).var()

    hedge_ratio = cov_xy / var_x
    # Variance quasi nulle = fenetre plate (spot reconduit) : pandas 3 y renvoie
    # un bruit d'arrondi (~1e-17) au lieu de 0, d'ou une tolerance.
    hedge_ratio = hedge_ratio.where(var_x.abs() > 1e-12).ffill()   # ffill causal: uniquement du passe
    hedge_ratio = hedge_ratio.rolling(hw).mean()
    df["Hedge_Ratio"] = hedge_ratio

    # Spread instantane avec le ratio dynamique -- sert uniquement de base
    # au filtre de vol ci-dessous (le signal lui-meme vient du croisement
    # de MA sur Close, pas du spread).
    df["Spread"] = y - df["Hedge_Ratio"] * x

    # Vol calculee sur le NIVEAU du spread (peut changer de signe, un
    # rendement en % n'aurait pas de sens ici).
    df["Vol"] = df["Spread"].rolling(p["vol_window"]).std()
    df["Vol_Threshold"] = df["Vol"].rolling(p["vol_quantile_window"]).quantile(p["vol_quantile"])

    # Croisement de moyennes mobiles sur le Close (l'instrument trade).
    df["MA_Fast"] = df["Close"].rolling(p["ma_fast_window"]).mean()
    df["MA_Slow"] = df["Close"].rolling(p["ma_slow_window"]).mean()

    return df


def compute_signal(df):
    """
    Machine a etats "always-in" (retournement direct, jamais a plat une
    fois le warmup passe) : direction pilotee par le croisement de MA,
    gatee par le filtre de regime de vol du spread.
    """
    p = PARAMS
    n = len(df)
    signal = np.zeros(n)
    current_position = 0.0

    vol = df["Vol"].to_numpy()
    vol_th = df["Vol_Threshold"].to_numpy()
    ma_fast = df["MA_Fast"].to_numpy()
    ma_slow = df["MA_Slow"].to_numpy()

    for i in range(n):
        if i < p["warmup_bars"]:
            signal[i] = np.nan
            continue

        cond_vol = (not np.isnan(vol_th[i])) and (vol[i] <= vol_th[i])
        long_signal = ma_fast[i] > ma_slow[i]
        short_signal = ma_fast[i] < ma_slow[i]

        # Passage/retournement en Long
        if long_signal and cond_vol and current_position <= 0:
            current_position = p["size"]
        # Passage/retournement en Short
        elif short_signal and cond_vol and current_position >= 0:
            current_position = -p["size"]
        # sinon : on garde la position courante (persistance de l'etat)

        signal[i] = current_position

    return pd.Series(signal, index=df.index)


# VARIANTE (sortie a plat au lieu de retournement direct) :
# remplace le corps de la boucle par une 3e condition de sortie explicite,
# par ex. |MA_Fast - MA_Slow| / MA_Slow < exit_threshold -> current_position = 0.0