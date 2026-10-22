import numpy as np
import pandas as pd

NAME = "SeasonalZScoreExit"

DESCRIPTION = (
    "Z-Score du BASIS desaisonnalise sur fenetre fixe de K annees passees "
    "(meme mois/semaine), machine a etats avec sortie anticipee, stop-loss "
    "et time-stop. Signaux strictement identiques apres eval_start_date "
    "quelle que soit la date de debut des donnees."
)

PARAMS = {
    "basis_col": "MID_THP",
    "date_col": "Date",
    "seasonal_key": "week",       # "month" ou "week"
    "seasonal_years": 2,           # K : nb d'annees passees dans la fenetre
    "min_seasonal_years": 2,       # min d'annees avec donnees pour utiliser le Z saisonnier
    "fallback_window": 20,         # utilise UNIQUEMENT avant eval_start_date
    "eval_start_date": "2018-01-01",  # FIXE, a choisir avant de regarder les resultats
    "entry_threshold": 2,
    "exit_threshold": 0.1,
    "stop_loss_threshold": 1000000.0,
    "max_holding_bars": 100,
    "size": 1.0,
}

REQUIRED_FEATURES = ["Z_Score", "Seasonal_Count"]


def compute_features(df):
    p = PARAMS
    col, date_col = p["basis_col"], p["date_col"]
    K = p["seasonal_years"]
    for c in (col, date_col):
        if c not in df.columns:
            raise ValueError(f"[{NAME}] Colonne requise manquante: {c}")

    dates = pd.to_datetime(df[date_col])
    if not dates.is_monotonic_increasing:
        raise ValueError(f"[{NAME}] '{date_col}' doit etre triee chronologiquement.")

    # Garde-fou : assez d'historique avant la date d'evaluation
    eval_start = pd.Timestamp(p["eval_start_date"])
    if dates.iloc[0] > eval_start - pd.DateOffset(years=K):
        raise ValueError(
            f"[{NAME}] Historique insuffisant : les donnees doivent commencer au plus "
            f"tard le {(eval_start - pd.DateOffset(years=K)).date()} "
            f"(eval_start_date - {K} ans). Debut actuel : {dates.iloc[0].date()}."
        )

    basis = df[col].astype(float)
    year = dates.dt.year.to_numpy()
    if p["seasonal_key"] == "week":
        grp = dates.dt.isocalendar().week.to_numpy().astype(int)
    else:
        grp = dates.dt.month.to_numpy()

    # --- Agregats par (annee, mois/semaine) ---
    tmp = pd.DataFrame({"y": year, "g": grp, "x": basis.to_numpy()})
    tmp["x2"] = tmp["x"] ** 2
    agg = tmp.groupby(["y", "g"]).agg(n=("x", "count"), s=("x", "sum"), s2=("x2", "sum"))

    years_full = np.arange(year.min(), year.max() + 1)
    groups_full = np.sort(np.unique(grp))

    def table(name):
        t = agg[name].unstack("g").reindex(index=years_full, columns=groups_full).fillna(0.0)
        # somme sur les K annees STRICTEMENT anterieures (shift(1))
        return t.rolling(K, min_periods=1).sum().shift(1).fillna(0.0)

    n_t, s_t, s2_t = table("n"), table("s"), table("s2")
    yrs_t = (agg["n"].unstack("g").reindex(index=years_full, columns=groups_full)
             .fillna(0.0) > 0).astype(float).rolling(K, min_periods=1).sum().shift(1).fillna(0.0)

    yi = np.searchsorted(years_full, year)
    gi = np.searchsorted(groups_full, grp)
    n = n_t.to_numpy()[yi, gi]
    s = s_t.to_numpy()[yi, gi]
    s2 = s2_t.to_numpy()[yi, gi]

    with np.errstate(divide="ignore", invalid="ignore"):
        mean = s / n
        var = (s2 - n * mean ** 2) / (n - 1)
        std = np.sqrt(np.where(var > 0, var, np.nan))
        z_seasonal = (basis.to_numpy() - mean) / std

    df["Seasonal_Count"] = yrs_t.to_numpy()[yi, gi]   # nb d'annees passees utilisees

    # --- Z de secours : uniquement avant eval_start_date ---
    fw = p["fallback_window"]
    z_fallback = (basis - basis.rolling(fw).mean()) / basis.rolling(fw).std()

    use_seasonal = df["Seasonal_Count"].to_numpy() >= p["min_seasonal_years"]
    df["Z_Seasonal"] = z_seasonal
    df["Z_Fallback"] = z_fallback
    df["Z_Score"] = np.where(use_seasonal, z_seasonal, z_fallback)
    return df


def compute_signal(df):
    p = PARAMS
    n = len(df)
    signal = np.zeros(n)

    z = df["Z_Score"].to_numpy()
    dates = pd.to_datetime(df[p["date_col"]])
    in_eval = (dates >= pd.Timestamp(p["eval_start_date"])).to_numpy()

    pos, entry_bar = 0.0, None


    for i in range(n):
        if not in_eval[i]:
            signal[i] = np.nan
            continue
        if np.isnan(z[i]):
            signal[i] = pos
            continue

        if pos == 0.0:
            if z[i] >= p["entry_threshold"]:
                pos, entry_bar = p["size"], i
            elif z[i] <= -p["entry_threshold"]:
                pos, entry_bar = -p["size"], i
        else:
            stop = abs(z[i]) >= p["stop_loss_threshold"]
            time_stop = (i - entry_bar) >= p["max_holding_bars"]
            reverted = z[i] <= p["exit_threshold"] if pos > 0 else z[i] >= -p["exit_threshold"]
            if stop or time_stop or reverted:
                pos, entry_bar = 0.0, None
        signal[i] = pos

    return pd.Series(signal, index=df.index)