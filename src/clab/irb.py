"""Le capital réglementaire IRB pour l'hypothécaire résidentiel, aux paramètres de l'OSFI.

La formule de Bâle (fondation Vasicek, BCBS 2005) répond à : quel capital faut-il pour absorber la
perte de crédit d'une année à 99,9 % de confiance, au-delà de la perte attendue déjà provisionnée ?

K = LGD x Phi( (Phi^-1(PD) + racine(R) x Phi^-1(0,999)) / racine(1 - R) ) - PD x LGD

Pour l'hypothécaire résidentiel : corrélation R fixée à 0,15, pas d'ajustement de maturité
(portefeuille de détail). Les planchers du chapitre 5 de la ligne directrice NFP (CAR) de l'OSFI,
rapportés : PD plancher 0,05 %, LGD plancher 10 %. Les actifs pondérés valent RWA = K x 12,5 x EAD.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

R_MORTGAGE = 0.15
PD_FLOOR = 0.0005
LGD_FLOOR = 0.10
CONFIDENCE = 0.999


def irb_k(pd: float, lgd: float, r: float = R_MORTGAGE, apply_floors: bool = True) -> float:
    """L'exigence de capital K (fraction de l'EAD) pour un prêt hypothécaire résidentiel."""
    if apply_floors:
        pd = max(pd, PD_FLOOR)
        lgd = max(lgd, LGD_FLOOR)
    pd = min(pd, 0.9999)
    cond = norm.cdf((norm.ppf(pd) + np.sqrt(r) * norm.ppf(CONFIDENCE)) / np.sqrt(1.0 - r))
    return float(lgd * cond - pd * lgd)


def rwa(pd: float, lgd: float, ead: float, r: float = R_MORTGAGE) -> float:
    return irb_k(pd, lgd, r) * 12.5 * ead
