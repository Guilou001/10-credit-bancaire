"""Données : un portefeuille synthétique à vérité connue, la SEC pour Enbridge, Valet pour les banques.

Trois sources, trois rôles :

1. **Le portefeuille synthétique** est le banc d'essai des moteurs de PD : un panel prêt-mois généré
   par un modèle de hasard en temps discret dont on CONNAÎT les paramètres (score de l'emprunteur,
   cycle macroéconomique, remboursement anticipé en risque concurrent). Un moteur honnête doit les
   retrouver ; c'est testé.
2. **L'échantillon Freddie Mac** (50 000 prêts par millésime, 1999-2026) exige une inscription
   gratuite à usage non commercial : il n'est PAS téléchargeable par script. Le chargeur attend un
   dépôt manuel dans data/raw/freddie/ au format officiel ; en son absence, tout le laboratoire
   tourne sur le synthétique, et c'est déclaré.
3. **Enbridge** (dossier de crédit) par l'API companyfacts de la SEC, et les **provisions pour
   pertes des grandes banques canadiennes** par l'API Valet de la Banque du Canada (série
   FVI_PCL_RATIO_SIB) : deux sources libres, scriptables, jamais commitées.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit

CIK_ENBRIDGE = "0000895728"
UA = {"User-Agent": "Guillaume Vaudescal vaudescal.guillaumepro@gmail.com"}
RAW = Path("data/raw")
ENB_FACTS = RAW / "enb_companyfacts.json"
PCL = RAW / "pcl_grandes_banques.json"

CONCEPTS: dict[str, list[str]] = {
    "revenus": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"],
    "resultat_exploitation": ["OperatingIncomeLoss"],
    "amortissements": ["DepreciationDepletionAndAmortization"],
    "flux_exploitation": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "interets": ["InterestExpense"],
    "remboursements_dette": ["RepaymentsOfLongTermDebt"],
    "dette_long_terme": ["LongTermDebt"],
    "tresorerie": ["CashAndCashEquivalentsAtCarryingValue"],
}
FLOW = {"revenus", "resultat_exploitation", "amortissements", "flux_exploitation", "capex",
        "interets", "remboursements_dette"}


def fetch(raw: Path = RAW) -> None:
    """Télécharge companyfacts d'Enbridge (SEC) et la série de provisions Valet (BdC)."""
    import requests

    raw.mkdir(parents=True, exist_ok=True)
    resp = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK_ENBRIDGE}.json",
                        headers=UA, timeout=120)
    resp.raise_for_status()
    ENB_FACTS.write_bytes(resp.content)
    resp = requests.get("https://www.bankofcanada.ca/valet/observations/FVI_PCL_RATIO_SIB/json",
                        timeout=60)
    resp.raise_for_status()
    PCL.write_bytes(resp.content)


def _annual_points(fact: dict, flow: bool) -> pd.Series:
    unit = "CAD" if "CAD" in fact["units"] else list(fact["units"].keys())[0]
    rows: dict[int, tuple[str, float]] = {}
    for p in fact["units"][unit]:
        end = pd.Timestamp(p["end"])
        if flow:
            if "start" not in p:
                continue
            if not 350 <= (end - pd.Timestamp(p["start"])).days <= 380:
                continue
        elif not (end.month == 12 and end.day == 31):
            continue
        filed = p.get("filed", "")
        if end.year not in rows or filed >= rows[end.year][0]:
            rows[end.year] = (filed, float(p["val"]))
    return pd.Series({y: v for y, (_, v) in sorted(rows.items())})


def load_enbridge(path: Path = ENB_FACTS) -> pd.DataFrame:
    """L'historique annuel d'Enbridge en millions de CAD (mêmes règles que le dépôt 09)."""
    if not path.exists():
        raise FileNotFoundError(f"{path} absent : lancer d'abord `clab fetch` (données non commitées)")
    facts = json.loads(path.read_text())["facts"]["us-gaap"]
    out = {}
    for name, concepts in CONCEPTS.items():
        series = [_annual_points(facts[c], name in FLOW) for c in concepts if c in facts]
        if series:
            merged = series[0]
            for s in series[1:]:
                merged = s.combine_first(merged)
            out[name] = merged / 1e6
    df = pd.DataFrame(out)
    df.index.name = "exercice"
    return df


def load_pcl(path: Path = PCL) -> pd.Series:
    """Provisions pour pertes sur prêts des grandes banques canadiennes, en % des encours (Valet)."""
    if not path.exists():
        raise FileNotFoundError(f"{path} absent : lancer d'abord `clab fetch`")
    obs = json.loads(path.read_text())["observations"]
    s = pd.Series({pd.Timestamp(o["d"]): float(o["FVI_PCL_RATIO_SIB"]["v"]) for o in obs}).sort_index()
    s.name = "pcl_pct"
    return s


# ---------------------------------------------------------------------------------------------
# Le portefeuille synthétique : la vérité que les moteurs doivent retrouver.

TRUE_PARAMS = {"intercept": -6.2, "beta_score": -1.1, "beta_macro": 0.9, "prepay_base": 0.008}


def simulate_portfolio(n_loans: int = 8000, n_months: int = 72, seed: int = 0) -> pd.DataFrame:
    """Un panel prêt-mois : défaut si le hasard s'active, remboursement anticipé concurrent.

    Le hasard mensuel de défaut est logistique : h = expit(a + b_score x score + b_macro x macro),
    où `score` est la qualité de l'emprunteur (centrée réduite, connue à l'octroi) et `macro` un
    cycle sinusoïdal commun. Le remboursement anticipé censure la trajectoire (risque concurrent).
    """
    rng = np.random.default_rng(seed)
    score = rng.normal(0.0, 1.0, n_loans)
    macro = np.sin(np.arange(n_months) * 2.0 * np.pi / 48.0)      # un cycle de quatre ans
    p = TRUE_PARAMS
    alive = np.ones(n_loans, dtype=bool)
    cols: dict[str, list[np.ndarray]] = {k: [] for k in ("pret", "mois", "score", "macro", "defaut", "prepaye")}
    ids = np.arange(n_loans)
    for t in range(n_months):
        if not alive.any():
            break
        idx = ids[alive]
        h = expit(p["intercept"] + p["beta_score"] * score[idx] + p["beta_macro"] * macro[t])
        default = rng.uniform(size=len(idx)) < h
        prepay = ~default & (rng.uniform(size=len(idx)) < p["prepay_base"])
        cols["pret"].append(idx)
        cols["mois"].append(np.full(len(idx), t))
        cols["score"].append(score[idx])
        cols["macro"].append(np.full(len(idx), macro[t]))
        cols["defaut"].append(default.astype(int))
        cols["prepaye"].append(prepay.astype(int))
        alive[idx[default | prepay]] = False
    return pd.DataFrame({k: np.concatenate(v) for k, v in cols.items()})
