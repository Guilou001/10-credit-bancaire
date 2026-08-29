"""L'ECL d'IFRS 9 : la perte attendue, par scénarios pondérés, avec le classement par stades.

L'ECL (expected credit loss), la perte que l'on provisionne AVANT qu'elle n'arrive, se calcule
PD x LGD x EAD : probabilité de défaut, perte en cas de défaut (la fraction non récupérée),
exposition au moment du défaut. IFRS 9 impose trois choses, toutes présentes ici :

1. **Des scénarios pondérés** : l'ECL est la moyenne, pondérée par leurs probabilités, de l'ECL
   calculée sous plusieurs chemins macroéconomiques (de base, adverse, favorable), pas l'ECL du
   seul scénario central : la convexité de la PD dans le cycle rend ces deux nombres différents.
2. **Le classement par stades** : stade 1 (provision sur 12 mois) tant que le crédit ne s'est pas
   « détérioré significativement » depuis l'octroi ; stade 2 (provision à VIE) sinon. La règle
   opérationnelle ici : stade 2 si la PD à 12 mois a plus que doublé depuis l'octroi (seuil déclaré).
3. **La perte à vie** : la somme actualisée, sur la durée restante, des pertes marginales de
   chaque période (PD marginale x LGD x EAD).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from clab.pd_models import vasicek_pit


@dataclass(frozen=True)
class Scenario:
    nom: str
    z: float            # l'état du cycle (positif = mauvais), constant sur l'horizon
    poids: float


SCENARIOS = (Scenario("favorable", -1.0, 0.25), Scenario("de_base", 0.0, 0.50),
             Scenario("adverse", 1.5, 0.25))


def ecl_12m(pd_12m: float, lgd: float, ead: float) -> float:
    return pd_12m * lgd * ead


def ecl_lifetime(pd_annual: float, lgd: float, ead: float, years: int, discount: float) -> float:
    """La somme actualisée des pertes marginales : survie x PD annuelle, année après année."""
    survival = 1.0
    total = 0.0
    for t in range(1, years + 1):
        marginal = survival * pd_annual
        total += marginal * lgd * ead / (1.0 + discount) ** t
        survival *= 1.0 - pd_annual
    return total


def stage(pd_12m_now: float, pd_12m_origination: float, threshold: float = 2.0) -> int:
    """Stade 1 ou 2 : détérioration significative = PD à 12 mois multipliée par plus de `threshold`."""
    return 2 if pd_12m_now > threshold * pd_12m_origination else 1


def portfolio_ecl(pd_ttc: np.ndarray, pd_origination: np.ndarray, rho: float, lgd: float,
                  ead: np.ndarray, years: int = 10, discount: float = 0.04,
                  scenarios: tuple[Scenario, ...] = SCENARIOS) -> dict:
    """L'ECL du portefeuille par scénario et pondérée, avec la part en stade 2.

    Pour chaque scénario, la PD point dans le cycle de chaque prêt vient de Vasicek ; le stade se
    juge à ÉCHELLE COMPARABLE, la PD à travers le cycle d'aujourd'hui contre celle de l'octroi
    (comparer une PIT à une TTC mélangerait le cycle et la détérioration propre du prêt) ; l'ECL
    par prêt vaut 12 mois en stade 1 et à vie en stade 2, et l'ECL IFRS 9 finale est la moyenne
    pondérée des scénarios.
    """
    stages = np.array([stage(p_now, p_o) for p_now, p_o in zip(pd_ttc, pd_origination, strict=True)])
    out = {"stades": stages, "part_stade_2_pct": 100.0 * float((stages == 2).mean()), "par_scenario": {}}
    weighted = 0.0
    for s in scenarios:
        pd_pit = np.array([vasicek_pit(p, rho, s.z) for p in pd_ttc])
        ecl = np.where(stages == 1,
                       [ecl_12m(p, lgd, e) for p, e in zip(pd_pit, ead, strict=True)],
                       [ecl_lifetime(p, lgd, e, years, discount) for p, e in zip(pd_pit, ead, strict=True)])
        out["par_scenario"][s.nom] = float(ecl.sum())
        weighted += s.poids * float(ecl.sum())
    out["ecl_ponderee"] = weighted
    out["ecl_scenario_central"] = out["par_scenario"]["de_base"]
    return out
