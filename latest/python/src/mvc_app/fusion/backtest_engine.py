"""
backtest_engine.py
===================
Moteur de backtest simple et rigoureux, indépendant de toute stratégie.

MODIFICATION : choix du moment/prix d'execution via run_backtest(..., execution=...)
  - execution="close"      : signal calcule au close de t -> ordre execute au
                             CLOSE de t (meme barre, type ordre "market on close").
  - execution="next_close" : signal calcule au close de t -> ordre execute au
                             CLOSE de t+1.
  - execution="next_open"  (defaut) : signal calcule au close de t -> ordre
                             execute a l'OPEN de t+1 (comportement historique).
Les rendements, les prix d'entree/sortie des trades, le mark-to-market de la
position ouverte et le graphe suivent tous le prix d'execution choisi.

MODIFICATION : stop de portefeuille (overlay de risque) via run_backtest(..., stop=...)
  - stop=None / False : desactive (defaut, comportement historique).
  - stop=True         : parametres par defaut STOP_DEFAULT.
  - stop={...}        : surcharge partielle, ex. {"lookback": 15, "threshold": 0.08}.
  Le declencheur est calcule sur le PnL THEORIQUE (sans stop) du modele combine ;
  la decision pour la position de la barre t n'utilise que les rendements connus
  jusqu'a t-1 (pas de look-ahead).
  Pour un stop sur un MIX de plusieurs modeles : voir run_mix_with_stop().

MODIFICATION : prochain signal / forecast
  - print_report(..., show_next_signal=True) / plot_results(..., show_next_signal=True)
    / next_signal_report(result) : pour CHAQUE strategie, affiche ses parametres,
    les dernieres valeurs de ses features, son signal brut au dernier close et
    l'ordre en attente (changement ou non) -- avec alerte si les features d'une
    strategie sont perimees (NaN sur les dernieres barres).
  - forecast_next_signal(result, moves=...) : scenarios "what-if" sur le close de
    DEMAIN (inconnu) : une barre hypothetique est ajoutee aux donnees et toutes
    les strategies sont recalculees telles quelles -> signal de chaque strategie
    et du modele combine selon le prix, avec les niveaux ou le signal bascule.

MODIFICATION : unite de min_hold_days via run_backtest(..., min_hold_unit=...)
  - min_hold_unit="calendar" (defaut, comportement historique) : min_hold_days = jours
    CALENDAIRES (week-end inclus) entre deux changements du signal. Un changement
    decide le vendredi puis le lundi est a 3 jours d'ecart : avec min_hold_days=3 la
    position peut ne durer qu'UNE barre (ouverte lundi, fermee mardi).
  - min_hold_unit="trading" : min_hold_days = BARRES de trading (lignes du jeu de
    donnees) entre deux changements du signal -> la position executee est tenue au
    moins min_hold_days barres, week-ends et jours feries ne comptant pas.
"""

import copy
import importlib.util
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

REQUIRED_BASE_COLUMNS = ["Date", "Open", "Close"]
# mode -> (colonne du prix d'execution, decalage en barres entre signal et execution)
EXECUTION_MODES = {
    "close":      ("Close", 0),   # close de t   (meme barre que le signal)
    "next_close": ("Close", 1),   # close de t+1
    "next_open":  ("Open",  1),   # open  de t+1
}

# Parametres par defaut du stop de portefeuille
#   lookback  : nb de barres du PnL glissant
#   threshold : seuil de perte, en FRACTION du notionnel (0.10 = -10%)
#   cooldown  : nb de barres a plat apres declenchement (la barre de
#               declenchement + `cooldown` barres suivantes, soit cooldown+1)
STOP_DEFAULT = {"lookback": 20, "threshold": 0.10, "cooldown": 10}

# Modes de combinaison dont le signal combine est DISCRET (-1/0/+1) : seuls ceux-la
# acceptent min_hold_days et ont un "nombre de trades du modele final" lisible.
COMBINE_MODES = ("weighted_sum", "majority", "majority_with_flat", "unanimous")
DISCRETE_COMBINE_MODES = ("majority", "majority_with_flat", "unanimous")

# Unite de min_hold_days : jours calendaires (defaut) ou barres de trading (lignes des donnees).
MIN_HOLD_UNITS = ("calendar", "trading")


def _min_hold_label(min_hold, unit):
    """Libelle court pour les rapports : '3j' (calendaires, comme avant) ou '3 barres'."""
    return f"{min_hold} barres" if unit == "trading" else f"{min_hold}j"


def _resolve_execution(execution):
    """Retourne (price_col, lag) pour le mode d'execution demande."""
    if execution not in EXECUTION_MODES:
        raise ValueError(
            f"execution doit etre 'close', 'next_close' ou 'next_open', recu: {execution!r}"
        )
    return EXECUTION_MODES[execution]


# ----------------------------------------------------------------------
# Stop de portefeuille
# ----------------------------------------------------------------------
def _resolve_stop(stop):
    """None/False -> pas de stop ; True -> defauts ; dict -> defauts surcharges."""
    if stop is None or stop is False:
        return None
    cfg = dict(STOP_DEFAULT)
    if isinstance(stop, dict):
        unknown = set(stop) - set(STOP_DEFAULT)
        if unknown:
            raise ValueError(f"Cles de stop inconnues: {unknown}. Valides: {list(STOP_DEFAULT)}")
        cfg.update(stop)
    elif stop is not True:
        raise ValueError(f"stop doit etre None, True ou un dict, recu: {stop!r}")
    if cfg["lookback"] < 1 or cfg["threshold"] <= 0 or cfg["cooldown"] < 0:
        raise ValueError(f"Parametres de stop invalides: {cfg}")
    return cfg


def compute_stop_flag(theo_return, lookback, threshold, cooldown):
    """
    theo_return : rendements THEORIQUES (sans stop), en fraction du notionnel,
                  au format du moteur (Strategy_Return[t] = rendement gagne
                  par la position de la barre t-1).
    Le PnL glissant est decale de 1 barre : la decision pour la position de la
    barre t n'utilise que les rendements connus jusqu'a t-1.
    Retourne (flag 1/0 indexe comme theo_return, indices des declenchements).
    Le flag vaut 0 de la barre de declenchement jusqu'a +cooldown inclus.
    Le flag s'applique aux POSITIONS (Position_final = Position_theo * flag).
    """
    roll = theo_return.rolling(lookback).sum().shift(1)
    trig = (roll < -threshold).to_numpy()
    n = len(theo_return)
    flag, trigger_idx, flat_until = np.ones(n), [], -1
    for i in range(n):
        if i > flat_until and trig[i]:
            trigger_idx.append(i)
            flat_until = i + cooldown
        if i <= flat_until:
            flag[i] = 0.0
    return pd.Series(flag, index=theo_return.index), trigger_idx


def stop_audit(theo_return, stop=True, notional=100_000):
    """
    Bilan de chaque declenchement du stop, sur le PnL THEORIQUE (sans stop).
      pnl_evite_$ : PnL theorique des (cooldown+1) barres a plat apres le
                    declenchement. NEGATIF = perte evitee (bon), POSITIF =
                    gain rate (cout du stop).
      pnl_pre_$   : PnL theorique des `lookback` barres precedentes.
    theo_return : Series de rendements theoriques (fraction du notionnel),
                  ex. result["data"]["Strategy_Return_Theo"] ou ret du mix.
    """
    cfg = _resolve_stop(stop)
    if cfg is None:
        raise ValueError("stop_audit: stop doit etre actif (True ou dict).")
    pnl = theo_return * notional
    _, idx = compute_stop_flag(theo_return, **cfg)
    rows = []
    for i in idx:
        rows.append({
            "date": pd.Timestamp(theo_return.index[i]).date()
                    if isinstance(theo_return.index, pd.DatetimeIndex) else i,
            "pnl_evite_$": round(float(pnl.iloc[i:i + cfg["cooldown"] + 1].sum())),
            "pnl_pre_$": round(float(pnl.iloc[max(0, i - cfg["lookback"]):i].sum())),
        })
    out = pd.DataFrame(rows, columns=["date", "pnl_evite_$", "pnl_pre_$"])
    if not out.empty:
        print(f"Bilan net du stop (negatif = le stop a fait gagner) : "
              f"{out['pnl_evite_$'].sum():,.0f} $ sur {len(out)} declenchement(s)")
    return out


def run_mix_with_stop(results, weights=None, stop=True, notional=100_000, annualization=252):
    """
    Stop applique sur le PnL theorique d'un MIX de plusieurs modeles.

    results : liste de resultats de run_backtest (un par modele), idealement
              lances SANS stop (sinon on reprend leurs colonnes *_Theo).
    weights : poids du mix (defaut : egal). Le mix est une moyenne ponderee des
              positions et des rendements theoriques de chaque modele.
    stop    : None / True / dict (voir STOP_DEFAULT). None = mix sans stop.
    """
    cfg = _resolve_stop(stop)
    weights = weights or [1 / len(results)] * len(results)

    def col(r, theo, plain):
        d = r["data"].set_index("Date")
        return d[theo] if theo in d.columns else d[plain]

    pos = pd.concat([w * col(r, "Position_Theo", "Position")
                     for w, r in zip(weights, results)], axis=1).fillna(0.0).sum(axis=1)
    ret = pd.concat([w * col(r, "Strategy_Return_Theo", "Strategy_Return")
                     for w, r in zip(weights, results)], axis=1).fillna(0.0).sum(axis=1)

    if cfg:
        flag, idx = compute_stop_flag(ret, **cfg)
        events = [ret.index[i] for i in idx]
    else:
        flag, events = pd.Series(1.0, index=ret.index), []

    # ret[t] est gagne par la position de t-1 -> le flag de t-1 s'applique a ret[t]
    ret_f = ret * flag.shift(1).fillna(1.0)
    eq = notional * (1 + ret_f.cumsum())
    dd = (eq - eq.cummax()) / eq.cummax()
    std = ret_f.std()
    return {
        "position": pos * flag,
        "position_theo": pos,
        "returns": ret_f,
        "returns_theo": ret,
        "equity": eq,
        "flag": flag,
        "stop": cfg,
        "stop_events": events,
        "summary": {
            "Rend. total %": (eq.iloc[-1] / notional - 1) * 100,
            "Sharpe": ret_f.mean() / std * np.sqrt(annualization) if std > 0 else np.nan,
            "MDD equity %": dd.min() * 100,
            "Declenchements": len(events),
        },
    }


def load_strategy(path):
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Fichier de strategie introuvable: '{path}'. "
            f"Verifie le chemin exact (nom de fichier, extension .py, majuscules/minuscules)."
        )

    name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Impossible de charger '{path}' comme module Python. Causes frequentes : "
            f"l'extension du fichier n'est pas '.py', ou le chemin pointe vers un dossier "
            f"au lieu d'un fichier."
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for attr in ("NAME", "compute_features", "compute_signal", "REQUIRED_FEATURES"):
        if not hasattr(module, attr):
            raise AttributeError(f"La strategie '{path}' doit definir '{attr}'")
    return module


def _validate_base(df):
    missing = [c for c in REQUIRED_BASE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes obligatoires manquantes: {missing}")
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    if df["Date"].duplicated().any():
        raise ValueError("Des dates dupliquees ont ete trouvees dans le dataset.")
    return df


def _apply_min_hold(signal, min_hold_days, unit="calendar"):
    """
    Verrouille le signal : un changement n'est accepte que si au moins
    `min_hold_days` se sont ecoules depuis le dernier changement accepte.
      unit="calendar" : jours CALENDAIRES entre les dates des deux changements.
      unit="trading"  : BARRES de trading, c'est-a-dire nombre de lignes du signal
                        (une ligne = une seance presente dans les donnees).
    Le decalage signal -> position (shift) conserve l'ecart en barres : en
    "trading", la position EXECUTEE est donc tenue au moins min_hold_days barres.
    """
    if min_hold_days is None or min_hold_days <= 0:
        return signal

    dates = signal.index.values
    raw_values = signal.values
    out = np.empty(len(raw_values), dtype=float)

    held_value = raw_values[0]
    last_change_date = dates[0]
    last_change_i = 0
    out[0] = held_value

    for i in range(1, len(raw_values)):
        raw = raw_values[i]
        date = dates[i]
        if unit == "trading":
            elapsed = i - last_change_i
        else:
            elapsed = (date - last_change_date) / np.timedelta64(1, "D")

        if raw != held_value and elapsed >= min_hold_days:
            held_value = raw
            last_change_date = date
            last_change_i = i

        out[i] = held_value

    return pd.Series(out, index=signal.index, name=signal.name)


def build_signals(df, strategy_specs, date_mode="union", combine_mode="weighted_sum",
                   min_hold_days=None, min_hold_unit="calendar"):
    """
    min_hold_unit : "calendar" (defaut) | "trading" -- unite de min_hold_days (voir _apply_min_hold).

    combine_mode : "weighted_sum" | "majority" | "majority_with_flat" | "unanimous"

      "majority_with_flat" : vote a TROIS options -- LONG, A PLAT ou SHORT. Le
          "a plat" est un VRAI VOTE (contrairement a "majority", ou un flat
          s'abstient : sign(0)=0 s'ajoute simplement a la somme). Chaque
          strategie PRESENTE vote avec le poids |weight| ; un poids negatif
          inverse long <-> short (jamais le flat). L'option qui totalise le
          PLUS de poids l'emporte ; en cas d'egalite au sommet -> A PLAT.
          Le signal combine vaut donc toujours -1, 0 ou +1.
            2 flat + 1 long  -> flat      2 long + 1 flat  -> long
            1 long + 1 short + 1 flat -> flat (egalite a trois)
          Avec 3 strategies de meme poids, cela revient a "au moins 2 sur 3
          dans le meme sens, sinon a plat". Au-dela, c'est la PLURALITE (l'option
          qui a le plus de poids), pas une majorite absolue (> 50 %).
          Une strategie ABSENTE (NaN, pas encore demarree) ne vote PAS du tout
          -- ce n'est pas un vote "a plat" -- selon date_mode comme ailleurs.

      "unanimous" : chaque strategie PRESENTE sur une date (non-NaN, selon
          date_mode -- voir plus bas) "vote" pour une direction, comme en
          "majority" (sign(raw_signal) * weight, un poids negatif inverse
          le vote). La position combinee ne vaut +1/-1 QUE SI TOUTES LES
          STRATEGIES PRESENTES votent dans le MEME sens (et qu'aucune n'est
          a plat) ; des qu'il y a desaccord (ou qu'une strategie presente
          est a plat), combined_signal[t] = 0 -> sortie du marche.

          Interaction avec date_mode : en "union", une strategie pas encore
          demarree (NaN) est une ABSTENTION -- elle ne compte ni pour ni
          contre l'unanimite. En "intersection", toutes les strategies
          sont de toute facon presentes des que la date existe dans
          combined_signal.
    """
    if date_mode not in ("union", "intersection"):
        raise ValueError(f"date_mode doit etre 'union' ou 'intersection', recu: {date_mode!r}")
    if combine_mode not in COMBINE_MODES:
        raise ValueError(
            f"combine_mode doit etre 'weighted_sum', 'majority', 'majority_with_flat' ou 'unanimous', "
            f"recu: {combine_mode!r}"
        )
    if min_hold_days is not None and min_hold_days > 0 and combine_mode not in DISCRETE_COMBINE_MODES:
        raise ValueError(
            "min_hold_days n'est supporte qu'avec combine_mode='majority', 'majority_with_flat' ou 'unanimous' "
            "(en 'weighted_sum' l'exposition est continue, 'reverser' n'y est pas defini)."
        )
    if min_hold_days is not None and min_hold_days < 0:
        raise ValueError(f"min_hold_days doit etre >= 0, recu: {min_hold_days!r}")
    if min_hold_unit not in MIN_HOLD_UNITS:
        raise ValueError(f"min_hold_unit doit etre 'calendar' ou 'trading', recu: {min_hold_unit!r}")
    if min_hold_unit == "trading" and min_hold_days and float(min_hold_days) != int(min_hold_days):
        raise ValueError(
            f"min_hold_unit='trading' compte des BARRES : min_hold_days doit etre un entier, recu: {min_hold_days!r}"
        )

    detail = {}
    per_strategy_combine_series = []
    abs_weights = []   # |poids| dans l'ordre des strategies = ordre des colonnes de `aligned`

    for path, weight in strategy_specs:
        module = load_strategy(path)
        strat_df = module.compute_features(df.copy())

        missing_feats = [c for c in module.REQUIRED_FEATURES if c not in strat_df.columns]
        if missing_feats:
            raise ValueError(
                f"La strategie '{module.NAME}' reference des colonnes absentes "
                f"apres compute_features: {missing_feats}"
            )

        strat_df = strat_df.dropna(subset=module.REQUIRED_FEATURES).reset_index(drop=True)
        if strat_df.empty:
            raise ValueError(f"La strategie '{module.NAME}' n'a aucune ligne valide apres dropna.")

        raw_signal = module.compute_signal(strat_df)
        raw_signal = pd.Series(np.asarray(raw_signal, dtype=float),
                                index=strat_df["Date"].values, name=module.NAME)

        if combine_mode == "weighted_sum":
            combine_series = raw_signal * weight
        else:  # modes a VOTE de direction : sign(signal) * poids
            combine_series = np.sign(raw_signal) * weight

        per_strategy_combine_series.append(combine_series)
        abs_weights.append(abs(float(weight)))

        # Etat de la strategie conserve pour next_signal_report /
        # forecast_next_signal : photo des PARAMS utilises (copie profonde,
        # pour ne pas dependre d'une mutation ulterieure du module) et table
        # de features post-dropna + signal brut aligne ligne a ligne.
        # Ne change RIEN au calcul des signaux ci-dessus.
        strat_df["Signal_Raw"] = raw_signal.to_numpy()

        detail[module.NAME] = {
            "module": module,
            "path": path,
            "weight": weight,
            "signal": raw_signal,
            "n_valid_rows": len(strat_df),
            "start_date": strat_df["Date"].iloc[0],
            "params": copy.deepcopy(getattr(module, "PARAMS", {})),
            "features": strat_df,
        }

    aligned = pd.concat(per_strategy_combine_series, axis=1, join="outer").sort_index()

    min_count = 1 if date_mode == "union" else aligned.shape[1]

    if combine_mode == "unanimous":
        votes = np.sign(aligned)
        n_present = votes.notna().sum(axis=1)
        row_max = votes.max(axis=1, skipna=True)
        row_min = votes.min(axis=1, skipna=True)

        unanimous_mask = (row_max == row_min) & (row_max != 0) & (n_present >= min_count)

        combined_signal = pd.Series(0.0, index=aligned.index)
        combined_signal[unanimous_mask] = row_max[unanimous_mask]
        combined_signal[n_present < min_count] = np.nan
        combined_signal = combined_signal.dropna()

        if min_hold_days:
            combined_signal = _apply_min_hold(combined_signal, min_hold_days, min_hold_unit)

    elif combine_mode == "majority_with_flat":
        # Vote a 3 options. `aligned` vaut sign(signal)*poids : son SIGNE est la
        # direction du vote (+1 long, -1 short, 0 a plat, NaN = strategie absente).
        # Le POIDS du vote est |poids| (un flat en a un, meme si sign(0)*poids = 0).
        w_abs = np.asarray(abs_weights, dtype=float)
        dirs = np.sign(aligned.to_numpy(dtype=float))
        present = ~np.isnan(dirs)
        w = np.where(present, w_abs[None, :], 0.0)
        with np.errstate(invalid="ignore"):
            w_long = (w * (dirs > 0)).sum(axis=1)
            w_short = (w * (dirs < 0)).sum(axis=1)
            w_flat = (w * (dirs == 0)).sum(axis=1)

        # Egalite = a PLAT. Tolerance relative : sans elle, des poids comme 0.1+0.2 vs
        # 0.3 (egaux en maths, differents de 5e-17 en flottant) feraient "gagner" long.
        tol = 1e-9 * w_abs.sum()
        long_wins = w_long > np.maximum(w_short, w_flat) + tol
        short_wins = w_short > np.maximum(w_long, w_flat) + tol
        vote = np.where(long_wins, 1.0, np.where(short_wins, -1.0, 0.0))
        vote = np.where(present.sum(axis=1) >= min_count, vote, np.nan)

        combined_signal = pd.Series(vote, index=aligned.index).dropna()

        if min_hold_days:
            combined_signal = _apply_min_hold(combined_signal, min_hold_days, min_hold_unit)

    else:
        combined_signal = aligned.sum(axis=1, min_count=min_count)
        combined_signal = combined_signal.dropna()

        if combine_mode == "majority":
            combined_signal = np.sign(combined_signal)
            if min_hold_days:
                combined_signal = _apply_min_hold(combined_signal, min_hold_days, min_hold_unit)

    combined_signal.index.name = "Date"

    if combined_signal.empty:
        raise ValueError(
            f"Aucune date valide entre les strategies fournies (date_mode={date_mode!r})."
        )

    return combined_signal, detail


def _check_returns_sane(returns, dates, label):
    bad = returns <= -1.0
    if not bad.any():
        return

    bad_idx = np.where(bad.values if hasattr(bad, "values") else bad)[0]
    dates_arr = dates.values if hasattr(dates, "values") else np.asarray(dates)
    returns_arr = returns.values if hasattr(returns, "values") else np.asarray(returns)

    examples = []
    for i in bad_idx[:5]:
        d = pd.Timestamp(dates_arr[i]).date() if i < len(dates_arr) else "?"
        examples.append(f"{d}: rendement = {returns_arr[i]*100:.1f}%")
    examples_str = "\n    ".join(examples)
    more = f"\n    ... et {len(bad_idx) - 5} autre(s)" if len(bad_idx) > 5 else ""

    raise ValueError(
        f"[{label}] {len(bad_idx)} periode(s) avec un rendement <= -100% detectee(s) :\n"
        f"    {examples_str}{more}\n\n"
        f"Un rendement <= -100% rend l'equity COMPOSEE indefinie (elle peut devenir "
        f"negative puis re-changer de signe a chaque periode suivante), ce qui "
        f"corrompt silencieusement Max Drawdown, Sharpe et CAGR (Max Drawdown peut "
        f"alors afficher des valeurs < -100%, ce qui est impossible autrement).\n\n"
        f"Causes frequentes a verifier sur ces dates precises :\n"
        f"  - un prix d'execution proche de zero ou un gap de roll de contrat mal gere\n"
        f"  - une donnee dupliquee/erronee dans le dataset source\n"
        f"  - un exces de levier: plusieurs strategies combinees (poids) dont la "
        f"somme depasse 1, qui amplifie un mouvement de prix par ailleurs normal "
        f"au-dela de -100%\n\n"
        f"Corrige la donnee source, ou reduis les poids/la taille des strategies "
        f"impliquees, puis relance."
    )


def _daily_fixed_notional_equity(returns, notional):
    return notional * (1 + returns.cumsum())


def daily_returns(equity, col):
    """Rendements simples (pct_change) de la colonne `col` d'un DataFrame equity."""
    return equity[col].pct_change().dropna()


def sharpe_ratio(equity, col, periods_per_year, rf=0.0):
    r = daily_returns(equity, col)
    if r.empty:
        return float("nan")
    mu_ann = float(r.mean() * periods_per_year)
    vol_ann = float(r.std() * np.sqrt(periods_per_year))
    if vol_ann <= 0 or np.isnan(vol_ann):
        return float("nan")
    return float((mu_ann - rf) / vol_ann)


def _trade_stepped_equity(trades, dates, notional):
    dates_index = pd.Index(pd.to_datetime(np.asarray(dates)))
    equity = pd.Series(float(notional), index=dates_index)
    if trades is None or trades.empty:
        return equity

    trades_sorted = trades.sort_values("exit_date")
    running = float(notional)
    step_values = {}
    for _, tr in trades_sorted.iterrows():
        running += tr["pnl_pct"] * notional
        step_values[pd.Timestamp(tr["exit_date"])] = running

    steps = pd.Series(step_values).sort_index()
    stepped = steps.reindex(dates_index, method="ffill")
    stepped = stepped.fillna(float(notional))
    return stepped


def run_backtest(df, strategy_specs, notional=100_000, annualization=252,
                  date_mode="union", combine_mode="weighted_sum", min_hold_days=None,
                  equity_mode="compounded", metrics_source="combined",
                  execution="next_open", stop=None, min_hold_unit="calendar"):
    """
    min_hold_unit : unite de min_hold_days (modes a vote uniquement).
        "calendar" (defaut) : jours CALENDAIRES entre deux changements du signal. Week-end
                              compris : un changement le vendredi puis le lundi respecte
                              min_hold_days=3, pour une position d'UNE seule barre.
        "trading"           : BARRES de trading (lignes des donnees) : la position executee
                              est tenue au moins min_hold_days barres. Entier requis.

    execution : moment et prix d'execution de l'ordre.
        "close"      : Close de t   (execution le jour meme du signal)
        "next_close" : Close de t+1
        "next_open"  : Open de t+1 (defaut, comportement historique)
        Le signal est TOUJOURS calcule avec l'information du close de t.
        Ce choix s'applique de facon coherente aux rendements, aux trades
        (prix d'entree/sortie), au mark-to-market de la position ouverte
        et au graphe.
        NB "close" : suppose que l'ordre peut etre passe au close de t en
        connaissant ce meme close (type market-on-close) -- hypothese plus
        optimiste que "next_close" / "next_open".

    metrics_source : quelle liste de trades alimente TOUTES les metriques
        agregees (Sharpe, CAGR, winrate, duree, profit factor -- pas
        seulement l'equity). "combined" (par defaut) : combined_trades, le
        modele final. "individual" : l'union des trades de chaque
        strategie (ancien comportement, garde pour compatibilite).

    stop : overlay de risque sur le PnL du MODELE COMBINE de ce backtest.
        None / False : desactive (defaut).
        True         : STOP_DEFAULT = {"lookback": 20, "threshold": 0.10, "cooldown": 10}
        dict         : surcharge partielle, ex. {"lookback": 15, "threshold": 0.08}
        Si le PnL theorique (SANS stop) cumule sur `lookback` barres passe sous
        -threshold (fraction du notionnel), la position est mise a plat pendant
        la barre de declenchement + `cooldown` barres, puis reprend la position
        du vote ce jour-la (sans rattrapage). La decision pour la position de
        la barre t n'utilise que les rendements connus jusqu'a t-1.
        Colonnes ajoutees a result["data"] : Position_Theo, Strategy_Return_Theo,
        Stop_Flag. Les metriques par strategie (strategy_metrics, trades)
        restent SANS stop : elles decrivent chaque brique isolee.
        Pour un stop sur un MIX de plusieurs modeles, utiliser run_mix_with_stop.

    Max Drawdown : TOUJOURS calcule sur l'equity LIVE (mark-to-market
        quotidien, qui bouge CHAQUE jour ou une position est detenue), que
        l'on soit en "compounded" ou "fixed_notional" -- jamais sur une
        courbe qui ne bougerait qu'aux clotures de trade. Voir la note
        detaillee pres de l'appel a _compute_metrics ci-dessous : une
        courbe qui ne bouge qu'a la cloture peut rater completement une
        chute severe survenue PENDANT qu'une position etait ouverte, si
        cette position finit par se redresser avant de cloturer.
    """
    if equity_mode not in ("compounded", "fixed_notional"):
        raise ValueError(f"equity_mode doit etre 'compounded' ou 'fixed_notional', recu: {equity_mode!r}")
    if metrics_source not in ("combined", "individual"):
        raise ValueError(f"metrics_source doit etre 'combined' ou 'individual', recu: {metrics_source!r}")
    price_col, lag = _resolve_execution(execution)
    stop_cfg = _resolve_stop(stop)

    df = _validate_base(df)
    combined_signal, detail = build_signals(df, strategy_specs, date_mode=date_mode,
                                             combine_mode=combine_mode,
                                             min_hold_days=min_hold_days,
                                             min_hold_unit=min_hold_unit)

    bt = df[df["Date"].isin(combined_signal.index)].copy()
    bt = bt.sort_values("Date").reset_index(drop=True)
    bt["Signal"] = bt["Date"].map(combined_signal)

    # Prix d'execution (Open ou Close) et rendement entre deux executions
    # consecutives : Exec_Return[t] = P[t+1] / P[t] - 1, avec P = prix choisi.
    bt["Exec_Price"] = bt[price_col]
    bt["Exec_Return"] = bt["Exec_Price"].shift(-1) / bt["Exec_Price"] - 1

    # Signal connu au close de t -> position detenue a partir de la barre
    # d'execution t+lag (lag=0 : close de t ; lag=1 : open ou close de t+1).
    bt["Position"] = bt["Signal"].shift(lag)
    bt["Strategy_Return"] = (bt["Position"] * bt["Exec_Return"]).shift(1)

    bt["Position"] = bt["Position"].fillna(0.0)
    bt["Strategy_Return"] = bt["Strategy_Return"].fillna(0.0)

    # ---- Stop de portefeuille (overlay sur le modele combine) ----
    # Le declencheur est calcule sur le PnL THEORIQUE (sans stop), jamais sur
    # le PnL encaisse : sinon la fenetre se "vide" pendant qu'on est a plat et
    # le stop se desarme sur une base fausse.
    stop_events = []
    if stop_cfg:
        bt["Position_Theo"] = bt["Position"]
        bt["Strategy_Return_Theo"] = bt["Strategy_Return"]
        flag, trig_idx = compute_stop_flag(bt["Strategy_Return_Theo"], **stop_cfg)
        stop_events = [pd.Timestamp(bt["Date"].iloc[i]) for i in trig_idx]
        bt["Stop_Flag"] = flag.values
        bt["Position"] = np.where(flag.values == 1.0, bt["Position_Theo"], 0.0)
        bt["Strategy_Return"] = (bt["Position"] * bt["Exec_Return"]).shift(1).fillna(0.0)

    _check_returns_sane(bt["Strategy_Return"], bt["Date"], "Modele combine / agrege")

    bt["Equity_Compounded"] = notional * (1 + bt["Strategy_Return"]).cumprod()

    combined_trades, combined_open_position = _extract_trades(
        bt[["Date", "Open", "Close", "Position"]], price_col=price_col
    )
    combined_open_positions = [combined_open_position] if combined_open_position is not None else []

    # Equity a notionnel fixe, mark-to-market QUOTIDIEN (bouge chaque jour
    # ou une position est detenue) -- c'est la courbe "live" utilisee pour
    # l'affichage ET desormais pour le calcul du Max Drawdown en
    # fixed_notional (voir note sur equity_for_drawdown plus bas).
    bt["Equity_Fixed_Notional"] = _daily_fixed_notional_equity(bt["Strategy_Return"], notional).values

    all_trades = []
    open_positions = []
    strategy_metrics = {}
    strategy_equity = {}

    for name, d in detail.items():
        raw_signal_i = d["signal"]
        weight_i = d["weight"]

        aligned = raw_signal_i.reindex(bt["Date"].values)
        position_i = (aligned * weight_i).shift(lag).fillna(0.0)
        return_i = pd.Series(
            position_i.values * bt["Exec_Return"].values, index=bt.index
        ).shift(1).fillna(0.0)
        _check_returns_sane(return_i, bt["Date"], name)

        strat_bt = bt[["Date", "Open", "Close"]].copy()
        strat_bt["Position"] = position_i.values

        trades_i, open_pos_i = _extract_trades(strat_bt, price_col=price_col)
        if not trades_i.empty:
            trades_i.insert(0, "strategy", name)
            trades_i.insert(1, "weight", weight_i)
            all_trades.append(trades_i)

        if open_pos_i is not None:
            open_pos_i["strategy"] = name
            open_pos_i["weight"] = weight_i
            open_positions.append(open_pos_i)

        equity_compounded_i = notional * (1 + return_i).cumprod()
        equity_fixed_i = _daily_fixed_notional_equity(return_i, notional)  # live, quotidienne

        if equity_mode == "compounded":
            equity_for_metrics_i = equity_compounded_i
            returns_for_metrics_i = return_i
            equity_for_drawdown_i = None  # defaut = equity_for_metrics_i (deja live)
        else:
            equity_for_metrics_i = _trade_stepped_equity(trades_i, bt["Date"], notional)
            returns_for_metrics_i = None
            equity_for_drawdown_i = equity_fixed_i  # LIVE, pas la version en escalier

        strategy_metrics[name] = _compute_metrics(
            bt["Date"], equity_for_metrics_i, returns_for_metrics_i,
            trades_i, notional, annualization,
            equity_mode=equity_mode, trades_for_sharpe=trades_i,
            equity_for_drawdown=equity_for_drawdown_i,
        )
        strategy_equity[name] = pd.DataFrame({
            "Date": bt["Date"].values,
            "Equity_Compounded": equity_compounded_i.values,
            "Equity_Fixed_Notional": equity_fixed_i.values,
        })

    if all_trades:
        trades = pd.concat(all_trades, ignore_index=True).sort_values("entry_date").reset_index(drop=True)
    else:
        cols = ["strategy", "weight", "entry_date", "exit_date", "direction", "size",
                "entry_price", "exit_price", "pnl_pct", "duration_days"]
        trades = pd.DataFrame(columns=cols)

    # ---- Choix de la source des trades pour les metriques AGREGEES ----
    # "combined" (par defaut) : TOUTES les metriques (Sharpe, CAGR, winrate,
    #     duree, profit factor) decrivent le MODELE FINAL (bt["Position"],
    #     combined_trades) -- une seule entite coherente du debut a la fin
    #     du rapport.
    # "individual" (ancien comportement) : winrate/duree/profit factor
    #     viennent de l'UNION des trades de chaque strategie individuelle.
    #
    # ATTENTION en combine_mode="weighted_sum" avec metrics_source="combined" :
    # l'exposition combinee est continue, et chaque variation de MAGNITUDE
    # (pas seulement de signe) compte comme un nouveau "trade" dans
    # combined_trades -- le nombre de trades peut alors etre nettement plus
    # eleve qu'avec metrics_source="individual" (meme phenomene que pour
    # les strategies a taille variable, ex: TSMomentum_OLS).
    trades_for_metrics = combined_trades if metrics_source == "combined" else trades

    if equity_mode == "compounded":
        equity_for_metrics = bt["Equity_Compounded"]
        returns_for_metrics = bt["Strategy_Return"]
        trades_for_sharpe = None
        equity_for_drawdown = None  # defaut = equity_for_metrics (deja live, quotidienne)
    else:
        # equity_for_metrics (total_return/CAGR/Sharpe trade-based) et
        # trades_for_sharpe DOIVENT venir de la MEME source (garantie de
        # coherence de signe deja etablie et testee) -- elles suivent donc
        # toutes les deux trades_for_metrics, quel que soit metrics_source.
        #
        # MAX DRAWDOWN, en revanche, NE DOIT PAS etre mesure sur cette
        # courbe en escalier (_trade_stepped_equity) : elle ne bouge qu'aux
        # clotures de trade et peut donc RATER COMPLETEMENT une chute
        # severe survenue PENDANT qu'une position etait ouverte, si cette
        # position finit par se redresser avant de cloturer (demontre :
        # un trade qui perd 25% en cours de route puis cloture en leger
        # gain affiche un Max Drawdown de 0% avec la courbe en escalier,
        # contre -10% avec la courbe live -- la courbe en escalier NE VOIT
        # RIEN). On utilise donc systematiquement bt["Equity_Fixed_Notional"]
        # (la version LIVE, mise a jour chaque jour) pour le calcul du
        # drawdown, quel que soit metrics_source -- le drawdown "vecu" par
        # le compte ne depend pas de quels trades on choisit de compter
        # dans les statistiques de winrate/duree.
        equity_for_metrics = _trade_stepped_equity(trades_for_metrics, bt["Date"], notional)
        returns_for_metrics = None
        trades_for_sharpe = trades_for_metrics
        equity_for_drawdown = bt["Equity_Fixed_Notional"]

    metrics = _compute_metrics(bt["Date"], equity_for_metrics, returns_for_metrics,
                                trades_for_metrics, notional, annualization,
                                equity_mode=equity_mode, trades_for_sharpe=trades_for_sharpe,
                                equity_for_drawdown=equity_for_drawdown)

    if metrics_source == "individual" and combine_mode in DISCRETE_COMBINE_MODES:
        # Redondant si metrics_source="combined" (Nombre de trades EST deja
        # celui du modele final dans ce cas) -- utile seulement quand
        # "Nombre de trades" ci-dessus reflete l'union individuelle.
        metrics["Nombre de trades (modele final)"] = len(combined_trades)

    yearly_metrics = _compute_yearly_metrics(
        bt, trades, combined_trades, notional, annualization, equity_mode
    )

    return {
        "data": bt,
        "trades": trades,
        "open_position": open_positions[0] if len(open_positions) == 1 else (open_positions or None),
        "open_positions": open_positions,
        "combined_trades": combined_trades,
        "combined_open_positions": combined_open_positions,
        "date_mode": date_mode,
        "combine_mode": combine_mode,
        "min_hold_days": min_hold_days,
        "min_hold_unit": min_hold_unit,
        "equity_mode": equity_mode,
        "metrics_source": metrics_source,
        "execution": execution,
        "price_col": price_col,
        "execution_lag": lag,
        "stop": stop_cfg,
        "stop_events": stop_events,
        "metrics": metrics,
        "yearly_metrics": yearly_metrics,
        "strategy_metrics": strategy_metrics,
        "strategy_equity": strategy_equity,
        "strategy_detail": detail,
        "combined_signal": combined_signal,
        "notional": notional,
        # Donnees d'entree validees (TOUTES les lignes, warmup inclus) : bt a
        # perdu les lignes anterieures au demarrage du signal combine, il ne
        # permet donc pas de recalculer les strategies (forecast_next_signal).
        "df_input": df,
    }


def _extract_trades(bt, price_col="Open"):
    """
    price_col : colonne utilisee comme prix d'execution (entree ET sortie) :
        "Open" ou "Close". Le mark-to-market de la position encore ouverte
        reste evalue au dernier Close disponible.
    """
    group_id = (bt["Position"] != bt["Position"].shift()).cumsum()
    tmp = bt.assign(_grp=group_id)

    trades = []
    open_position = None
    n = len(tmp)
    for gid, g in tmp.groupby("_grp"):
        pos_val = g["Position"].iloc[0]
        if pos_val == 0:
            continue

        start_idx = g.index[0]
        end_idx = g.index[-1]

        entry_date = tmp["Date"].iloc[start_idx]
        entry_price = tmp[price_col].iloc[start_idx]

        if end_idx + 1 >= n:
            last_close = tmp["Close"].iloc[-1]
            unrealized_pnl_pct = pos_val * (last_close / entry_price - 1)
            open_position = {
                "entry_date": entry_date,
                "entry_price": entry_price,
                "direction": "Long" if pos_val > 0 else "Short",
                "size": pos_val,
                "days_held_so_far": (tmp["Date"].iloc[-1] - entry_date).days,
                "mark_to_market_close": last_close,
                "unrealized_pnl_pct": unrealized_pnl_pct,
            }
            continue

        exit_date = tmp["Date"].iloc[end_idx + 1]
        exit_price = tmp[price_col].iloc[end_idx + 1]

        direction = "Long" if pos_val > 0 else "Short"
        pnl_pct = pos_val * (exit_price / entry_price - 1)
        duration_days = (exit_date - entry_date).days

        trades.append({
            "entry_date": entry_date,
            "exit_date": exit_date,
            "direction": direction,
            "size": pos_val,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl_pct": pnl_pct,
            "duration_days": duration_days,
        })

    cols = ["entry_date", "exit_date", "direction", "size", "entry_price",
            "exit_price", "pnl_pct", "duration_days"]
    return pd.DataFrame(trades, columns=cols), open_position


def _compute_metrics(dates, equity, returns, trades, notional, annualization,
                      equity_mode="compounded", trades_for_sharpe=None,
                      equity_for_drawdown=None):
    """
    equity_for_drawdown : equity LIVE (mark-to-market quotidien) a utiliser
        SPECIFIQUEMENT pour le Max Drawdown, si elle differe de `equity`
        (qui sert, elle, au Rendement total/CAGR/Sharpe). Si None (defaut),
        `equity` est deja la courbe live et sert aussi au drawdown --
        c'est le cas en "compounded" (bt["Equity_Compounded"] bouge deja
        chaque jour). En "fixed_notional", `equity` est la courbe en
        ESCALIER (exacte, utilisee pour Rendement total/Sharpe -- voir
        _trade_stepped_equity), qui NE DOIT PAS servir au drawdown : elle
        ne bouge qu'aux clotures de trade et peut rater une chute severe
        survenue pendant qu'une position etait ouverte si celle-ci finit
        par se redresser avant de cloturer. equity_for_drawdown doit alors
        etre la version LIVE (_daily_fixed_notional_equity), qui capture
        cette excursion.
    """
    total_return = equity.iloc[-1] / notional - 1
    n_days = (pd.Timestamp(dates.iloc[-1]) - pd.Timestamp(dates.iloc[0])).days
    years = n_days / 365.25 if n_days > 0 else np.nan

    if years and years > 0 and (1 + total_return) > 0:
        cagr = (1 + total_return) ** (1 / years) - 1
    else:
        cagr = np.nan
    avg_return_per_year = total_return / years if years else np.nan

    if equity_mode == "compounded":
        equity_df = pd.DataFrame({"Equity": equity.values})
        sharpe = sharpe_ratio(equity_df, "Equity", annualization, rf=0.0)
        r = daily_returns(equity_df, "Equity")
        vol_annual = float(r.std() * np.sqrt(annualization)) if not r.empty else np.nan
    else:
        trades_sharpe = trades_for_sharpe if trades_for_sharpe is not None else trades
        trade_pnls = trades_sharpe["pnl_pct"] if trades_sharpe is not None and len(trades_sharpe) else pd.Series(dtype=float)
        n_trades_sharpe = len(trade_pnls)
        if n_trades_sharpe >= 2 and years and years > 0:
            trades_per_year = n_trades_sharpe / years
            std_simple = trade_pnls.std(ddof=0)
            vol_annual = std_simple * np.sqrt(trades_per_year)
            sharpe = (trade_pnls.mean() / std_simple) * np.sqrt(trades_per_year) if std_simple > 0 else np.nan
        else:
            vol_annual = np.nan
            sharpe = np.nan

    # ---- Max Drawdown : TOUJOURS sur l'equity LIVE (voir docstring) ----
    equity_dd = equity_for_drawdown if equity_for_drawdown is not None else equity
    running_max = equity_dd.cummax()
    if equity_mode == "compounded":
        drawdown = equity_dd / running_max - 1
    else:
        # "fixed_notional" : equity peut etre proche de 0 ou negative
        # (comptabilite additive, non compoundee) -> diviser par un
        # running_max minuscule/negatif exploserait exactement comme le
        # pct_change() explique dans sharpe_ratio(). On exprime donc le
        # drawdown en % du NOTIONNEL DE DEPART (constant, toujours
        # positif), jamais du pic courant. Peut legitimement depasser
        # -100% dans ce mode -- ce n'est pas un bug, c'est la consequence
        # attendue de ce mode de comptabilite.
        # drawdown = equity_dd / running_max - 1
        drawdown = (equity_dd - running_max) / notional
    max_drawdown = drawdown.min()
    calmar = cagr / abs(max_drawdown) if (max_drawdown is not None and max_drawdown < 0 and not np.isnan(cagr)) else np.nan

    n_trades = len(trades)
    if n_trades > 0:
        wins = trades[trades["pnl_pct"] > 0]
        losses = trades[trades["pnl_pct"] <= 0]
        winrate = len(wins) / n_trades
        avg_win = wins["pnl_pct"].mean() if len(wins) else 0.0
        avg_loss = losses["pnl_pct"].mean() if len(losses) else 0.0
        expectancy = trades["pnl_pct"].mean()
        avg_duration_all = trades["duration_days"].mean()
        avg_duration_win = wins["duration_days"].mean() if len(wins) else np.nan
        avg_duration_loss = losses["duration_days"].mean() if len(losses) else np.nan
        gross_win = wins["pnl_pct"].sum()
        gross_loss = losses["pnl_pct"].sum()
        profit_factor = (gross_win / abs(gross_loss)) if gross_loss != 0 else np.nan
    else:
        winrate = avg_win = avg_loss = expectancy = np.nan
        avg_duration_all = avg_duration_win = avg_duration_loss = np.nan
        profit_factor = np.nan

    return {
        "Rendement total (%)": total_return * 100,
        "CAGR (%)": cagr * 100 if years and not np.isnan(cagr) else np.nan,
        "Rendement moyen / an (%)": avg_return_per_year * 100 if years else np.nan,
        "Volatilite annualisee (%)": vol_annual * 100,
        "Sharpe Ratio": sharpe,
        "Max Drawdown (%)": max_drawdown * 100,
        "Calmar Ratio": calmar,
        "Nombre de trades": n_trades,
        "Winrate (%)": winrate * 100 if n_trades else np.nan,
        "Gain moyen / trade gagnant (%)": avg_win * 100 if n_trades else np.nan,
        "Perte moyenne / trade perdant (%)": avg_loss * 100 if n_trades else np.nan,
        "Esperance / trade (%)": expectancy * 100 if n_trades else np.nan,
        "Profit Factor": profit_factor,
        "Duree moyenne des trades (j)": avg_duration_all,
        "Duree moyenne trades gagnants (j)": avg_duration_win,
        "Duree moyenne trades perdants (j)": avg_duration_loss,
        "Nombre de jours dans le backtest": n_days,
        "Periode (annees)": years,
    }


# ----------------------------------------------------------------------
# Sharpe / Rendement PAR ANNEE CALENDAIRE
# ----------------------------------------------------------------------
def _compute_yearly_metrics(bt, trades, combined_trades, notional, annualization, equity_mode):
    """
    Decoupe le backtest par annee CALENDAIRE et calcule les metriques
    (Sharpe, Rendement, Max Drawdown, nb de trades) INDEPENDAMMENT pour
    chaque annee, en rebasant l'equity a `notional` au premier jour de
    chaque annee.

    Reutilise exactement _compute_metrics (memes formules deja validees)
    plutot que d'improviser un calcul different -- y compris le Max
    Drawdown sur l'equity LIVE (voir equity_for_drawdown).

    La premiere et la derniere annee peuvent etre des annees PARTIELLES --
    retourne quand meme une ligne pour elles, avec le nombre de jours
    reellement couverts en colonne "Jours".

    Retourne un pd.DataFrame, une ligne par annee, trie chronologiquement.
    """
    bt = bt.copy()
    bt["_year"] = pd.to_datetime(bt["Date"]).dt.year

    rows = []
    for year, sub in bt.groupby("_year"):
        sub = sub.reset_index(drop=True)
        if len(sub) < 2:
            continue

        year_start = sub["Date"].iloc[0]
        year_end = sub["Date"].iloc[-1] + pd.Timedelta(days=1)  # borne exclusive

        if equity_mode == "compounded":
            equity_year = notional * (1 + sub["Strategy_Return"]).cumprod()
            returns_year = sub["Strategy_Return"]
            trades_year = trades[
                (trades["exit_date"] >= year_start) & (trades["exit_date"] < year_end)
            ] if not trades.empty else trades
            trades_for_sharpe_year = None
            equity_for_drawdown_year = None  # deja live
        else:
            trades_year = combined_trades[
                (combined_trades["exit_date"] >= year_start) & (combined_trades["exit_date"] < year_end)
            ] if not combined_trades.empty else combined_trades
            equity_year = _trade_stepped_equity(trades_year, sub["Date"], notional)
            returns_year = None
            trades_for_sharpe_year = trades_year
            # Version LIVE (quotidienne) rebasee sur cette seule annee, pour
            # le Max Drawdown -- jamais la version en escalier ci-dessus.
            equity_for_drawdown_year = _daily_fixed_notional_equity(sub["Strategy_Return"], notional)

        m = _compute_metrics(
            sub["Date"], equity_year, returns_year, trades_year,
            notional, annualization, equity_mode=equity_mode,
            trades_for_sharpe=trades_for_sharpe_year,
            equity_for_drawdown=equity_for_drawdown_year,
        )

        rows.append({
            "Annee": int(year),
            "Jours": len(sub),
            "Rendement (%)": m["Rendement total (%)"],
            "Sharpe Ratio": m["Sharpe Ratio"],
            "Max Drawdown (%)": m["Max Drawdown (%)"],
            "Nombre de trades": m["Nombre de trades"],
            "Winrate (%)": m["Winrate (%)"],
        })

    return pd.DataFrame(rows)


def print_yearly_metrics(yearly_metrics, title_suffix=""):
    print("\n" + "-" * 72)
    print(f"Sharpe / Rendement PAR ANNEE {title_suffix}")
    print("-" * 72)
    if yearly_metrics is None or yearly_metrics.empty:
        print("  (pas assez de donnees pour un decoupage annuel)")
        return
    with pd.option_context("display.float_format", "{:.2f}".format, "display.width", 120):
        print(yearly_metrics.to_string(index=False))


# ----------------------------------------------------------------------
# Affichage : graphe + rapport texte
# ----------------------------------------------------------------------
def plot_results(result, title_suffix="", entries="individual", show_strategy_metrics=True,
                  show_yearly_metrics=True, log_scale=False, show_next_signal=False):
    """
    show_next_signal : si True, ajoute en fin de rapport l'etat de chaque
              strategie au dernier close (parametres, features, signal brut,
              ordre en attente) -- voir next_signal_report(). False par defaut.

    entries : "individual" (par defaut) affiche les entrees/sorties de
              CHAQUE strategie (result["trades"]) ; "combined" n'affiche
              que celles du MODELE FINAL (result["combined_trades"]).

    show_strategy_metrics : si False, saute le detail par strategie.
    show_yearly_metrics   : si False, saute le tableau Sharpe/Rendement
              par annee (voir print_yearly_metrics()). True par defaut.
    log_scale : si True, la courbe d'equity (3e panneau) est affichee en
              echelle LOGARITHMIQUE -- les variations en % restent
              visuellement comparables quel que soit le niveau d'equity
              atteint (utile sur de longues periodes a forte croissance
              composee). False par defaut (echelle lineaire, comme avant).

              ATTENTION en equity_mode="fixed_notional" : cette equity est
              ADDITIVE (voir _daily_fixed_notional_equity) et peut devenir
              proche de zero ou NEGATIVE -- une echelle log ne peut pas
              representer de valeurs <= 0 (mathematiquement indefini,
              log(0) et log(negatif) n'existent pas). Si c'est le cas ici,
              un avertissement est affiche et les points concernes
              n'apparaitront simplement pas sur le graphe (trou dans la
              courbe), plutot que de faire planter l'affichage.

    Le prix trace (et les marqueurs d'entree/sortie) suit le prix
    d'execution choisi dans run_backtest (result["price_col"]).
    Si un stop de portefeuille est actif, les periodes a plat dues au stop
    sont grisees dans le panneau d'exposition.
    """
    if entries not in ("individual", "combined"):
        raise ValueError(f"entries doit etre 'individual' ou 'combined', recu: {entries!r}")

    bt = result["data"]
    price_col = result.get("price_col", "Open")
    if entries == "individual":
        trades = result["trades"]
        open_positions = result.get("open_positions") or []
    else:
        trades = result["combined_trades"]
        open_positions = result.get("combined_open_positions") or []

    fig, axes = plt.subplots(
        3, 1, figsize=(16, 13), sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1, 1]},
    )

    ax0 = axes[0]
    ax0.plot(bt["Date"], bt[price_col], color="black", linewidth=0.9)

    for _, tr in trades.iterrows():
        if tr["direction"] == "Long":
            ax0.scatter(tr["entry_date"], tr["entry_price"], marker="^",
                        color="green", s=20, zorder=5)
        else:
            ax0.scatter(tr["entry_date"], tr["entry_price"], marker="v",
                        color="red", s=20, zorder=5)
        ax0.scatter(tr["exit_date"], tr["exit_price"], marker="o",
                    color="orange", s=15, zorder=4)

    for open_pos in open_positions:
        color = "green" if open_pos["direction"] == "Long" else "red"
        marker = "^" if open_pos["direction"] == "Long" else "v"
        ax0.scatter(open_pos["entry_date"], open_pos["entry_price"], marker=marker,
                    facecolors="none", edgecolors=color, s=140, linewidths=2, zorder=6)

    ax0.set_title(f"Entry / Exit {title_suffix} (execution: {result.get('execution', 'next_open')})")
    handles = [
        plt.Line2D([], [], color="black", label=price_col),
        plt.Line2D([], [], color="green", marker="^", linestyle="", label="Entree Long"),
        plt.Line2D([], [], color="red", marker="v", linestyle="", label="Entree Short"),
        plt.Line2D([], [], color="orange", marker="o", linestyle="", label="Sortie"),
    ]
    if open_positions:
        handles.append(plt.Line2D([], [], color="gray", marker="^", linestyle="",
                                   markerfacecolor="none", markeredgewidth=2, markersize=10,
                                   label="Position ouverte (non cloturee)"))
    ax0.legend(handles=handles)
    ax0.grid(alpha=0.3)

    ax_exp = axes[1]
    exposure = bt["Position"]
    ax_exp.fill_between(bt["Date"], exposure, 0, where=(exposure >= 0),
                         color="seagreen", alpha=0.35, step="post")
    ax_exp.fill_between(bt["Date"], exposure, 0, where=(exposure <= 0),
                         color="firebrick", alpha=0.35, step="post")
    ax_exp.plot(bt["Date"], exposure, color="black", linewidth=0.8, drawstyle="steps-post")
    ax_exp.axhline(0, color="black", linewidth=0.6)
    if result.get("stop") and "Stop_Flag" in bt.columns:
        ax_exp.fill_between(bt["Date"], -1.1, 1.1, where=(bt["Stop_Flag"] == 0.0),
                             color="gray", alpha=0.35, step="post", label="Stop actif (a plat)")
        ax_exp.legend(loc="upper right")
    ax_exp.set_ylabel("Exposition (Position)")
    combine_mode = result.get('combine_mode', 'weighted_sum')
    min_hold = result.get("min_hold_days")
    exp_title = f"Exposition combinee ({combine_mode}"
    if combine_mode in DISCRETE_COMBINE_MODES and min_hold:
        exp_title += f", min_hold={_min_hold_label(min_hold, result.get('min_hold_unit', 'calendar'))}"
    if result.get("stop"):
        s = result["stop"]
        exp_title += f", stop {s['lookback']}j/{s['threshold']:.0%}/cd{s['cooldown']}"
    exp_title += ")"
    ax_exp.set_title(exp_title)
    ax_exp.grid(alpha=0.3)

    equity_mode = result.get("equity_mode", "compounded")
    ax_eq = axes[2]
    if equity_mode == "compounded":
        equity_plotted = bt["Equity_Compounded"]
        ax_eq.plot(bt["Date"], equity_plotted, color="steelblue")
        ax_eq.set_ylabel("$ (composee)")
        ax_eq.set_title("Equity - rendement compose (reinvesti)")
    else:
        equity_plotted = bt["Equity_Fixed_Notional"]
        ax_eq.plot(bt["Date"], equity_plotted, color="darkorange")
        ax_eq.set_ylabel("$ (notionnel fixe)")
        ax_eq.set_title(f"Equity - notionnel fixe, mark-to-market quotidien ({result['notional']:,.0f}$)")
    ax_eq.grid(alpha=0.3)

    if log_scale:
        n_non_positive = (equity_plotted <= 0).sum()
        if n_non_positive > 0:
            print(f"AVERTISSEMENT log_scale=True : {n_non_positive} jour(s) ou l'equity est <= 0 "
                  f"(possible en equity_mode='fixed_notional', comptabilite additive) -- "
                  f"log(valeur <= 0) est mathematiquement indefini. Ces points n'apparaitront "
                  f"PAS sur le graphe (trou dans la courbe) plutot que de faire planter l'affichage.")
        ax_eq.set_yscale("log")

    plt.tight_layout()
    plt.show()

    print_report(result, title_suffix, show_strategy_metrics=show_strategy_metrics,
                 show_yearly_metrics=show_yearly_metrics, show_next_signal=show_next_signal)


def print_report(result, title_suffix="", show_strategy_metrics=True, show_yearly_metrics=True,
                  show_next_signal=False):
    """
    show_strategy_metrics : si False, saute la section "Metriques PAR STRATEGIE".
    show_yearly_metrics   : si False, saute le tableau Sharpe/Rendement par annee.
    show_next_signal      : si True, ajoute a la fin l'etat de chaque strategie
                            au dernier close et l'ordre en attente (voir
                            next_signal_report). False par defaut.
    """
    metrics = result["metrics"]
    detail = result["strategy_detail"]

    print("=" * 72)
    print(f"RAPPORT DE BACKTEST {title_suffix}")
    print("=" * 72)
    price_col = result.get("price_col", "Open")
    execution = result.get("execution", "next_open")
    exec_labels = {"close": "Close de t (jour du signal)",
                   "next_close": "Close de t+1",
                   "next_open": "Open de t+1"}
    print(f"\nExecution des ordres : {execution} -> {exec_labels.get(execution, price_col)}")
    print(f"Mode de combinaison des dates : {result.get('date_mode', 'union')}")
    combine_mode = result.get('combine_mode', 'weighted_sum')
    print(f"Mode de combinaison des signaux : {combine_mode}")
    if combine_mode in DISCRETE_COMBINE_MODES:
        min_hold = result.get("min_hold_days")
        unit_txt = "barres de trading" if result.get("min_hold_unit", "calendar") == "trading" else "jours calendaires"
        print(f"Contrainte d'allocation (min_hold_days) : "
              f"{(str(min_hold) + ' ' + unit_txt) if min_hold else 'aucune'}")
    print(f"Base d'equity pour les metriques : {result.get('equity_mode', 'compounded')}")
    print(f"Source des trades pour les metriques : {result.get('metrics_source', 'combined')} "
          f"({'modele final' if result.get('metrics_source', 'combined') == 'combined' else 'union des strategies individuelles'})")
    print("Max Drawdown : toujours calcule sur l'equity LIVE (mark-to-market quotidien)")
    if result.get("stop"):
        ev = result.get("stop_events", [])
        print(f"Stop portefeuille : {result['stop']} -> {len(ev)} declenchement(s)")
        if ev:
            print("   " + ", ".join(str(pd.Timestamp(d).date()) for d in ev))
    else:
        print("Stop portefeuille : desactive")
    print("\nComposition de la strategie :")
    for name, d in detail.items():
        n_trades_strat = (result["trades"]["strategy"] == name).sum() if not result["trades"].empty else 0
        print(f"  - {name}  (poids = {d['weight']:+g})  valide a partir du {pd.Timestamp(d['start_date']).date()}  |  {n_trades_strat} trade(s)")
        module = d["module"]
        if hasattr(module, "DESCRIPTION"):
            print(f"      {module.DESCRIPTION}")
        if hasattr(module, "PARAMS"):
            print(f"      Parametres: {module.PARAMS}")

    print("\nMetriques (modele combine / agrege) :")
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k:42s}: {v:,.3f}")
        else:
            print(f"  {k:42s}: {v}")

    if show_yearly_metrics:
        print_yearly_metrics(result.get("yearly_metrics"), title_suffix)

    strategy_metrics = result.get("strategy_metrics") or {}
    if strategy_metrics and show_strategy_metrics:
        print("\n" + "-" * 72)
        print("Metriques PAR STRATEGIE (isolee, comme si elle tournait seule, SANS stop)")
        print("-" * 72)
        for name, smetrics in strategy_metrics.items():
            print(f"\n  [{name}]")
            for k, v in smetrics.items():
                if isinstance(v, float):
                    print(f"    {k:40s}: {v:,.3f}")
                else:
                    print(f"    {k:40s}: {v}")

    open_positions = result.get("open_positions") or []
    if open_positions:
        print(f"\n{len(open_positions)} position(s) ENCORE OUVERTE(S) a la fin du backtest (non incluses dans les metriques ci-dessus) :")
        for open_pos in open_positions:
            print(f"  [{open_pos['strategy']}] {open_pos['direction']}"
                  f"  entree {pd.Timestamp(open_pos['entry_date']).date()} @ {open_pos['entry_price']:.4f}"
                  f"  | detenue depuis {open_pos['days_held_so_far']}j"
                  f"  | mark-to-market {open_pos['mark_to_market_close']:.4f}"
                  f"  | PnL non realise {open_pos['unrealized_pnl_pct']*100:.2f}%")
    print("=" * 72)

    if show_next_signal:
        next_signal_report(result)


# ----------------------------------------------------------------------
# Prochain signal : etat de chaque strategie + forecast "what-if"
# ----------------------------------------------------------------------
_EXEC_LABELS = {"close": "Close de t (jour du signal)",
                "next_close": "Close de t+1",
                "next_open": "Open de t+1"}


def _direction_label(x):
    if pd.isna(x):
        return "n/a"
    return "LONG" if x > 0 else ("SHORT" if x < 0 else "A PLAT")


def _next_bar_stop_flag(result):
    """
    Etat du stop de portefeuille pour la PROCHAINE barre (pas encore dans les
    donnees). Retourne None si le stop est inactif, sinon (flag, declenche) :
    flag = 1.0 (position autorisee) ou 0.0 (a plat), declenche = True si le
    stop se declenche PRECISEMENT sur cette prochaine barre.

    Methode exacte (pas une approximation) : on prolonge d'une barre la serie
    des rendements theoriques puis on relance compute_stop_flag. Le flag de la
    barre n n'utilise que les rendements jusqu'a n-1 (decalage de 1 barre), tous
    connus ; la valeur placeholder (0.0) de la barre n n'influence donc rien.
    """
    cfg = result.get("stop")
    bt = result["data"]
    if not cfg or "Strategy_Return_Theo" not in bt.columns:
        return None
    theo = bt["Strategy_Return_Theo"].reset_index(drop=True)
    ext = pd.concat([theo, pd.Series([0.0])], ignore_index=True)
    flag, idx = compute_stop_flag(ext, **cfg)
    return float(flag.iloc[-1]), (len(ext) - 1) in idx


def next_signal_report(result, last_n=3, show_params=True, show_features=True):
    """
    Etat de chaque strategie au DERNIER CLOSE connu, pour preparer le prochain
    ordre.

    Pour chaque strategie : poids, parametres (PARAMS), signal brut au dernier
    close (et celui de la veille : changement ou non), dernieres valeurs de ses
    features (REQUIRED_FEATURES). Puis le modele combine : signal combine,
    position actuellement detenue, ordre en attente (execute selon le mode
    d'execution du backtest) et etat du stop de portefeuille s'il est actif.

    Le signal au dernier close est DEJA CONNU : c'est l'ordre en attente. Pour
    anticiper le signal de DEMAIN (close pas encore connu), voir
    forecast_next_signal().

    ALERTE "perime" : si les features d'une strategie sont NaN sur les dernieres
    barres (donnee source manquante), le moteur retire silencieusement ces
    lignes et la strategie reste sur son DERNIER signal valide, plus ancien que
    le dernier close. Ce rapport le signale explicitement.

    last_n : nombre de dernieres barres de features affichees par strategie.
    """
    detail = result["strategy_detail"]
    bt = result["data"]
    df_in = result.get("df_input")
    lag = result.get("execution_lag", 1)
    execution = result.get("execution", "next_open")
    combined = result["combined_signal"]

    last_date_all = pd.Timestamp(df_in["Date"].iloc[-1] if df_in is not None else bt["Date"].iloc[-1])
    last_close = float(df_in["Close"].iloc[-1] if df_in is not None else bt["Close"].iloc[-1])

    print("=" * 72)
    print("PROCHAIN SIGNAL / ETAT DES STRATEGIES AU DERNIER CLOSE")
    print("=" * 72)
    print(f"Dernier close connu : {last_date_all.date()}  (Close = {last_close:.4f})")
    cm = result.get("combine_mode", "weighted_sum")
    mh = result.get("min_hold_days")
    print(f"Combinaison : {cm}" + (f" (min_hold={_min_hold_label(mh, result.get('min_hold_unit', 'calendar'))})" if mh else "")
          + f"  |  dates : {result.get('date_mode', 'union')}"
          + f"  |  execution : {execution} -> {_EXEC_LABELS.get(execution, '?')}")

    for name, d in detail.items():
        module = d["module"]
        feat = d["features"]
        sig_last = float(feat["Signal_Raw"].iloc[-1])
        sig_prev = float(feat["Signal_Raw"].iloc[-2]) if len(feat) > 1 else np.nan
        last_valid = pd.Timestamp(feat["Date"].iloc[-1])

        print("\n" + "-" * 72)
        print(f"[{name}]  poids = {d['weight']:+g}")
        print("-" * 72)

        if last_valid < last_date_all:
            print(f"  !! ATTENTION : derniere ligne VALIDE de cette strategie = {last_valid.date()}, "
                  f"anterieure au dernier close ({last_date_all.date()}).")
            print("     Des features sont NaN sur les dernieres barres (donnee source manquante ?) : "
                  "le signal ci-dessous est PERIME.")

        if show_params:
            params = d.get("params") or {}
            if params:
                print("  Parametres :")
                for k, v in params.items():
                    print(f"      {k:<26s}: {v}")
            else:
                print("  Parametres : (aucun PARAMS defini dans le fichier de strategie)")

        if pd.isna(sig_last):
            print(f"  Signal brut au close du {last_valid.date()} : n/a (warmup)")
        else:
            changed = (not pd.isna(sig_prev)) and sig_prev != sig_last
            evo = (f"CHANGE ({_direction_label(sig_prev)} -> {_direction_label(sig_last)})"
                   if changed else "inchange")
            print(f"  Signal brut au close du {last_valid.date()} : {sig_last:+g} "
                  f"({_direction_label(sig_last)})  | veille : {sig_prev:+g}  -> {evo}")

        if show_features:
            cols = ["Date"]
            for c in ["Close"] + list(module.REQUIRED_FEATURES) + ["Signal_Raw"]:
                if c in feat.columns and c not in cols:
                    cols.append(c)
            tail = feat[cols].tail(last_n).copy()
            tail["Date"] = pd.to_datetime(tail["Date"]).dt.date
            print(f"  Dernieres valeurs ({len(tail)} barres) :")
            with pd.option_context("display.float_format", "{:.4f}".format,
                                   "display.width", 200, "display.max_columns", None):
                for line in tail.to_string(index=False).splitlines():
                    print("     " + line)

    # ---- Modele combine ----
    print("\n" + "=" * 72)
    print("MODELE COMBINE")
    print("=" * 72)
    comb_last = float(combined.iloc[-1])
    comb_date = pd.Timestamp(combined.index[-1])
    held = float(bt["Position"].iloc[-1])
    if comb_date < last_date_all:
        print(f"  !! ATTENTION : le signal combine s'arrete au {comb_date.date()}, "
              f"anterieur au dernier close ({last_date_all.date()}).")
    print(f"  Signal combine au close du {comb_date.date()} : {comb_last:+g} ({_direction_label(comb_last)})")
    print(f"  Position actuellement detenue (derniere barre) : {held:+g} ({_direction_label(held)})")

    if lag == 0:
        print("  Execution 'close' : l'ordre du dernier close est suppose execute a ce meme close "
              "(market-on-close) -- deja inclus dans la position ci-dessus.")
    else:
        target = comb_last
        stop_state = _next_bar_stop_flag(result)
        if stop_state is not None:
            flag, triggered = stop_state
            if flag == 0.0:
                why = "se declenche sur la prochaine barre" if triggered else "deja actif (cooldown en cours)"
                print(f"  Stop portefeuille pour la prochaine barre : A PLAT ({why}).")
            else:
                print("  Stop portefeuille pour la prochaine barre : inactif (position du vote autorisee).")
            target = comb_last * flag
        print(f"  Ordre en attente (execution : {_EXEC_LABELS.get(execution, '?')}) : "
              f"position cible {target:+g} ({_direction_label(target)})")
        if np.isclose(target, held):
            print(f"  -> AUCUN CHANGEMENT : conserver la position {held:+g}.")
        else:
            print(f"  -> CHANGEMENT : passer de {held:+g} a {target:+g}.")
    print("=" * 72)


def forecast_next_signal(result, moves=None, overrides=None, verbose=True):
    """
    Scenarios "what-if" : quel sera le signal calcule au close de DEMAIN selon
    le prix de demain ?

    Methode : pour chaque scenario, une barre hypothetique (date = jour ouvre
    suivant) est ajoutee aux donnees d'entree et TOUTES les strategies sont
    recalculees telles quelles (memes fichiers, memes parametres, meme mode de
    combinaison / min_hold_days / date_mode que le backtest). Pas de formule
    approchee a maintenir par strategie : on lit le signal produit a la barre
    hypothetique. Le signal obtenu est celui genere au close de demain ; il
    sera execute selon le mode d'execution du backtest.

    moves     : variations du close de demain par rapport au dernier close, en
                fraction (ex. [-0.02, -0.01, 0.01, 0.02]). Defaut : 11 points
                de -5% a +5%.
    overrides : dict {colonne: valeur} applique a la barre hypothetique pour les
                colonnes autres que Open/Close (ex. {"BASIS": 1.2}).

    HYPOTHESES (a garder en tete) :
      - Open = Close = prix hypothetique (le signal ne depend du prix que via le
        close dans les strategies usuelles).
      - Toutes les AUTRES colonnes sont reconduites a l'identique du dernier
        close, sauf `overrides`. Si une strategie depend d'autres colonnes que
        le prix (BASIS, MID_THP...), le scenario ne fait varier que le prix.
      - La resolution est celle de la grille `moves` : les niveaux de bascule
        affiches sont des intervalles, pas des valeurs exactes.

    GARDE-FOU anti look-ahead : le signal d'une strategie au DERNIER CLOSE REEL
    ne doit pas changer quand on ajoute une barre future. Sinon la strategie
    utilise l'avenir (ex. shift(-1)) : un avertissement la nomme.

    Retourne un DataFrame : une ligne par scenario (variation, close hypothetique,
    signal de chaque strategie, COMBINE, et COMBINE_apres_stop si un stop est
    actif et force l'a-plat sur la prochaine barre).
    """
    df_in = result.get("df_input")
    if df_in is None:
        raise ValueError("result ne contient pas 'df_input' : relance run_backtest avec ce moteur.")

    detail = result["strategy_detail"]
    specs = [(d["path"], d["weight"]) for d in detail.values()]
    moves = list(np.linspace(-0.05, 0.05, 11)) if moves is None else sorted(float(m) for m in moves)
    overrides = dict(overrides or {})

    last_row = df_in.iloc[-1]
    last_date = pd.Timestamp(last_row["Date"])
    last_close = float(last_row["Close"])
    next_date = last_date + pd.offsets.BDay(1)

    baseline_combined = float(result["combined_signal"].iloc[-1])
    baseline_last = {name: d["signal"].get(last_date, np.nan) for name, d in detail.items()}

    rows, offenders = [], set()
    for m in moves:
        px = last_close * (1.0 + m)
        new_row = last_row.to_dict()
        new_row.update({"Date": next_date, "Open": px, "Close": px})
        new_row.update(overrides)
        df_ext = pd.concat([df_in, pd.DataFrame([new_row])], ignore_index=True)

        sig, det = build_signals(
            df_ext, specs,
            date_mode=result.get("date_mode", "union"),
            combine_mode=result.get("combine_mode", "weighted_sum"),
            min_hold_days=result.get("min_hold_days"),
            min_hold_unit=result.get("min_hold_unit", "calendar"),
        )

        out = {"variation_%": m * 100.0, "close_hyp": px}
        for name, d in det.items():
            out[name] = float(d["signal"].get(next_date, np.nan))
            # Garde-fou causalite : le signal au dernier close REEL ne doit pas bouger.
            before, after = baseline_last[name], d["signal"].get(last_date, np.nan)
            if not (pd.isna(before) and pd.isna(after)) and not np.isclose(before, after, equal_nan=False):
                offenders.add(name)
        out["COMBINE"] = float(sig.get(next_date, np.nan))
        rows.append(out)

    table = pd.DataFrame(rows)

    stop_state = _next_bar_stop_flag(result) if result.get("execution_lag", 1) >= 1 else None
    if stop_state is not None and stop_state[0] == 0.0:
        table["COMBINE_apres_stop"] = table["COMBINE"] * 0.0

    if verbose:
        print("=" * 72)
        print("FORECAST DU SIGNAL DE DEMAIN (scenarios sur le close)")
        print("=" * 72)
        print(f"Dernier close : {last_close:.4f} ({last_date.date()})  |  barre hypothetique : {next_date.date()}")
        print(f"Signal combine actuel (au dernier close) : {baseline_combined:+g} ({_direction_label(baseline_combined)})")
        if overrides:
            print(f"Colonnes forcees sur la barre hypothetique : {overrides}")
        if stop_state is not None and stop_state[0] == 0.0:
            print("Stop portefeuille : la prochaine barre est A PLAT quel que soit le signal "
                  "(voir COMBINE_apres_stop).")
        if offenders:
            print(f"!! ATTENTION LOOK-AHEAD : le signal au dernier close REEL change quand on ajoute une barre "
                  f"future pour : {sorted(offenders)}. Ces strategies utilisent l'avenir "
                  f"(shift negatif ?) : leurs signaux ne sont pas fiables.")
        print()
        with pd.option_context("display.float_format", "{:.4f}".format,
                               "display.width", 200, "display.max_columns", None):
            print(table.to_string(index=False))

        cols = [c for c in table.columns if c not in ("variation_%", "close_hyp", "COMBINE_apres_stop")]
        flips = []
        for c in cols:
            s = table[c]
            for i in range(1, len(table)):
                a, b = s.iloc[i - 1], s.iloc[i]
                if pd.isna(a) or pd.isna(b) or a == b:
                    continue
                flips.append(
                    f"  {c}: {a:+g} -> {b:+g} entre {table['variation_%'].iloc[i-1]:+.2f}% "
                    f"(close {table['close_hyp'].iloc[i-1]:.4f}) et {table['variation_%'].iloc[i]:+.2f}% "
                    f"(close {table['close_hyp'].iloc[i]:.4f})"
                )
        print("\nNiveaux de bascule (resolution = pas de la grille) :")
        print("\n".join(flips) if flips else "  aucune bascule dans la plage testee.")
        print("=" * 72)

    return table