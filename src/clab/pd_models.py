"""Trois moteurs de probabilité de défaut (PD), du plus bancaire au plus réglementaire.

1. **Logistique à WoE** (le score bancaire classique) : le score continu est découpé en classes,
   chaque classe reçoit son poids de la preuve (WoE, le logarithme du rapport bons/mauvais de la
   classe rapporté à celui du portefeuille), et une régression logistique prédit le défaut à
   12 mois. C'est le standard des cartes de score.
2. **Hasard en temps discret** (Shumway, 2001) : une logistique sur le panel prêt-mois entier,
   avec la covariable macroéconomique ; chaque mois de survie est une observation. La PD à 12 mois
   se compose ensuite mois par mois : 1 - produit des (1 - hasard).
3. **Vasicek point dans le cycle** : la PD à travers le cycle (TTC, la moyenne de long terme) se
   déplace avec le facteur commun Z du moment : PD_PIT = Phi((Phi^-1(PD_TTC) + racine(rho) Z) /
   racine(1 - rho)). C'est le pont entre la carte de score et la formule de capital.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


def default_within_12m(panel: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par prêt observé à son premier mois : le défaut survient-il dans les 12 mois ?"""
    first = panel[panel["mois"] < 12].groupby("pret").agg(score=("score", "first"))
    d12 = panel[(panel["mois"] < 12) & (panel["defaut"] == 1)].groupby("pret").size()
    first["defaut_12m"] = first.index.isin(d12.index).astype(int)
    return first.reset_index()


def woe_table(scores: np.ndarray, defaults: np.ndarray, n_bins: int = 8) -> pd.DataFrame:
    """Le découpage en classes de score et le poids de la preuve de chacune."""
    qs = np.quantile(scores, np.linspace(0, 1, n_bins + 1))
    qs[0], qs[-1] = -np.inf, np.inf
    bins = pd.cut(scores, np.unique(qs))
    df = pd.DataFrame({"bin": bins, "defaut": defaults})
    grp = df.groupby("bin", observed=True)["defaut"].agg(["sum", "count"])
    grp["mauvais"] = grp["sum"].clip(lower=0.5)
    grp["bons"] = (grp["count"] - grp["sum"]).clip(lower=0.5)
    tot_m, tot_b = grp["mauvais"].sum(), grp["bons"].sum()
    grp["woe"] = np.log((grp["bons"] / tot_b) / (grp["mauvais"] / tot_m))
    grp["taux_defaut"] = grp["sum"] / grp["count"]
    return grp.reset_index()


def logistic_woe_pd(train: pd.DataFrame, n_bins: int = 8) -> pd.DataFrame:
    """PD à 12 mois par classe de score : WoE puis logistique univariée sur le WoE."""
    from sklearn.linear_model import LogisticRegression

    table = woe_table(train["score"].to_numpy(), train["defaut_12m"].to_numpy(), n_bins)
    mapping = dict(zip(table["bin"], table["woe"], strict=True))
    x = pd.cut(train["score"], pd.IntervalIndex(table["bin"])).map(mapping).to_numpy().reshape(-1, 1)
    model = LogisticRegression()
    model.fit(x, train["defaut_12m"])
    table["pd_12m"] = model.predict_proba(table["woe"].to_numpy().reshape(-1, 1))[:, 1]
    return table


def hazard_fit(panel: pd.DataFrame) -> dict[str, float]:
    """La logistique de Shumway sur le panel prêt-mois : rend les coefficients estimés."""
    from sklearn.linear_model import LogisticRegression

    x = panel[["score", "macro"]].to_numpy()
    y = panel["defaut"].to_numpy()
    model = LogisticRegression(C=1e6)
    model.fit(x, y)
    return {"intercept": float(model.intercept_[0]),
            "beta_score": float(model.coef_[0][0]),
            "beta_macro": float(model.coef_[0][1])}


def hazard_pd_12m(params: dict[str, float], score: float, macro_path: np.ndarray) -> float:
    """PD à 12 mois composée mois par mois le long d'un chemin macroéconomique donné."""
    from scipy.special import expit

    h = expit(params["intercept"] + params["beta_score"] * score + params["beta_macro"] * macro_path[:12])
    return float(1.0 - np.prod(1.0 - h))


def vasicek_pit(pd_ttc: float, rho: float, z: float) -> float:
    """PD point dans le cycle : Phi((Phi^-1(PD_TTC) + racine(rho) z) / racine(1 - rho)).

    Convention de signe : z > 0 est un MAUVAIS état du cycle (la PD monte avec z).
    """
    return float(norm.cdf((norm.ppf(pd_ttc) + np.sqrt(rho) * z) / np.sqrt(1.0 - rho)))
