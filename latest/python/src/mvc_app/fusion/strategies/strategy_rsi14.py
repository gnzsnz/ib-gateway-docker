"""
strategy1.py
============
Portage direct de ta strategie de retournement (z-score + filtre de vol)
dans le framework du backtest_engine.

Logique identique a ton script original :
  - Z-Score glissant de la colonne 'BASIS' (fenetre `zscore_window`).
  - Filtre de regime : on ne prend/renverse une position que si la
    volatilite recente (`Vol`, std glissante des rendements de BASIS) est
    en dessous de son 25e percentile glissant (`Vol_Threshold`) -> regime
    calme uniquement.
  - Machine a etats "always reversal / always-in": une fois en position,
    on ne repasse a plat, on renverse directement long <-> short des que
    le seuil oppose est franchi (comme ton `current_position` dans la
    boucle originale). Si tu veux plutot une sortie a plat entre les deux,
    vois la note "VARIANTE" en bas du fichier.

IMPORTANT anti-lookahead :
  compute_features() n'utilise QUE du rolling standard (fenetre glissante
  se terminant a la ligne courante) -> tout est connu au close du jour t.
  compute_signal() ne regarde, a chaque ligne i, que les valeurs des
  lignes <= i. Le moteur (backtest_engine.py) se charge tout seul de
  decaler ce signal vers l'Open(t+1) : cette strategie n'a rien a gerer
  de ce cote-la.
"""

import numpy as np
import pandas as pd

NAME = "rsi_Reversal14"

DESCRIPTION = (
    "Retournement systematique sur le Z-Score du spread pairs-trade "
    "MID_VHP vs MID_THP (hedge ratio dynamique = cov/var glissante, "
    "lisse par une moyenne mobile). Long si Z >= +seuil, Short si Z <= -seuil, "
    "uniquement quand la volatilite recente du spread est sous son 25e "
    "percentile glissant (regime calme). Toujours investi une fois le "
    "warmup passe (long ou short, jamais a plat)."
)

PARAMS = {
    "hedge_window": 5,         # fenetre du hedge ratio (cov/var + lissage)
    "zscore_window": 5,        # fenetre de la moyenne/std du spread (Z-Score)
    "entry_threshold": 1,     # seuil d'entree/retournement en unites de Z-Score
    "vol_window": 14,           # fenetre de la vol (std du niveau du spread)
    "vol_quantile_window": 5,   # fenetre glissante du quantile de vol
    "vol_quantile": 0.4,       # quantile utilise comme seuil (25e percentile)
    "warmup_bars": 20,          # nb de barres avant d'autoriser un premier trade
    "size": 1.0,                # taille de position (long=+size, short=-size)
}

# Colonnes sur lesquelles le moteur fera un dropna avant compute_signal
REQUIRED_FEATURES = ["MID_THP", "MID_VHP", "Hedge_Ratio", "Spread",
                      "Z_Score", "Vol", "Vol_Threshold"]


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
    hedge_ratio = hedge_ratio.where(var_x != 0).ffill()   # ffill causal: uniquement du passe
    hedge_ratio = hedge_ratio.rolling(hw).mean()
    df["Hedge_Ratio"] = hedge_ratio

    # Spread instantane avec le ratio dynamique
    df["Spread"] = y - df["Hedge_Ratio"] * x

    zw = p["zscore_window"]
    spread_mean = df["Spread"].rolling(zw).mean()
    spread_std = df["Spread"].rolling(zw).std()
    df["Z_Score"] = (df["Spread"] - spread_mean) / spread_std

    # Vol calculee sur le NIVEAU du spread (comme dans le script original,
    # qui utilisait le niveau du prix et non son rendement) : le spread
    # peut changer de signe, un rendement en % n'aurait pas de sens ici.
    df["Vol"] = df["Spread"].rolling(p["vol_window"]).std()
    df["Vol_Threshold"] = df["Vol"].rolling(p["vol_quantile_window"]).quantile(p["vol_quantile"])

    def rsi_wilder(s: pd.Series, window: int) -> pd.Series:
        """RSI with SMA averages."""
        x = pd.to_numeric(s, errors="coerce")
        delta = x.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=window).mean()
        avg_loss = loss.rolling(window=window).mean()
        rs = avg_gain / (avg_loss+1e-12)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi
    
    df['rsi'] = rsi_wilder(df['Open'],14)   # Open : connu en seance, ordre au close du jour

    return df


def compute_signal(df):
    """
    Reproduit la boucle a etats de ton script original.
    Retourne un signal (position desiree, connue au close de chaque ligne).
    """
    p = PARAMS
    n = len(df)
    signal = np.zeros(n)
    current_position = 0.0
    z = df["Z_Score"].to_numpy()
    vol = df["Vol"].to_numpy()
    vol_th = df["Vol_Threshold"].to_numpy()
    rsi = df['rsi'].to_numpy()


    for i in range(n):
        if i < p["warmup_bars"]:
            signal[i] = np.nan
            continue

        cond_vol = (not np.isnan(vol_th[i])) and (vol[i] <= vol_th[i])
        short_signal = rsi[i] >= 70 
        long_signal = rsi[i] <= 30

        # Passage/retournement en Long
        if long_signal and cond_vol and current_position <= 0:
            current_position = p["size"]
        # Passage/retournement en Short
        elif short_signal and cond_vol and current_position >= 0:
            current_position = -p["size"]

        signal[i] = current_position

    return pd.Series(signal, index=df.index)


# VARIANTE (sortie a plat au lieu de retournement direct) :
# remplace le corps de la boucle par une 3e condition de sortie explicite,
# par ex. |Z_Score| < exit_threshold -> current_position = 0.0