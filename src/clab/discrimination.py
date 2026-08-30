"""Le score sépare-t-il les bons des mauvais, et ses probabilités sont-elles justes ?

Ce sont les deux questions qu'on pose à une carte de score dans un entretien de crédit, et ce sont
deux questions différentes.

**La première est celle du classement.** Si on range tous les emprunteurs du plus risqué au moins
risqué selon le score, les défaillants se retrouvent-ils bien en haut de la liste ? On la mesure par
l'**aire sous la courbe**, qui est la probabilité qu'un défaillant tiré au hasard soit mieux classé
qu'un non-défaillant tiré au hasard. Une aire de 0,5 est le hasard pur, une aire de 1 est la
perfection. Le **Gini** est la même chose sur une autre échelle, deux fois l'aire moins un, et
l'**écart de Kolmogorov-Smirnov** est la plus grande distance entre les deux populations, c'est-à-dire
l'endroit où le score sépare le mieux.

**La seconde est celle du niveau.** Un score peut classer parfaitement et se tromper sur les
montants : annoncer 2 % de défauts là où il y en a 6 %. C'est la **calibration**, et elle se vérifie
en découpant le portefeuille en tranches de probabilité annoncée, puis en comparant l'annoncé au
réalisé dans chaque tranche.

Un modèle peut être bon sur l'une et mauvais sur l'autre. Les deux se mesurent donc séparément.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .pd_models import hazard_pd_12m


def rangs_moyens(x: np.ndarray) -> np.ndarray:
    """Les rangs croissants, les valeurs égales recevant leur rang moyen.

    C'est ce qui rend l'aire exacte quand plusieurs emprunteurs partagent le même score, cas
    fréquent dès qu'une carte de score travaille par classes.
    """
    ordre = np.argsort(x, kind="mergesort")
    tries = x[ordre]
    rangs = np.empty(len(x), dtype=float)
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and tries[j + 1] == tries[i]:
            j += 1
        rangs[ordre[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return rangs


def pouvoir_de_classement(defaut: np.ndarray, score_de_risque: np.ndarray) -> dict:
    """L'aire, le Gini et l'écart de Kolmogorov-Smirnov d'un score de risque.

    Le score est croissant avec le risque : plus il est haut, plus le défaut est probable. L'aire
    est calculée par la statistique de Mann et Whitney, donc exactement et non par intégration
    approchée.
    """
    defaut = np.asarray(defaut).astype(int)
    score = np.asarray(score_de_risque, dtype=float)
    mauvais, bons = int(defaut.sum()), int((1 - defaut).sum())
    if mauvais == 0 or bons == 0:
        raise ValueError("il faut au moins un défaut et un non-défaut pour mesurer un classement")

    rangs = rangs_moyens(score)
    aire = float((rangs[defaut == 1].sum() - mauvais * (mauvais + 1) / 2) / (mauvais * bons))

    ordre = np.argsort(-score, kind="mergesort")
    part_mauvais = np.concatenate([[0.0], np.cumsum(defaut[ordre]) / mauvais])
    part_bons = np.concatenate([[0.0], np.cumsum(1 - defaut[ordre]) / bons])
    ecarts = part_mauvais - part_bons
    i = int(np.argmax(ecarts))
    return {"aire": aire, "gini": 2.0 * aire - 1.0, "ks": float(ecarts[i]),
            "seuil_ks": float(score[ordre][min(i, len(ordre) - 1)]),
            "defauts": mauvais, "sains": bons}


def plafond_du_modele_vrai(cohorte: pd.DataFrame, parametres: dict, macro: np.ndarray) -> dict:
    """Le pouvoir de classement qu'atteindrait quelqu'un qui connaîtrait le vrai modèle.

    C'est le point de repère du dépôt. Sur un portefeuille construit, on connaît la loi qui engendre
    les défauts, donc on peut calculer le classement d'un devin parfait. Aucune carte de score ne
    peut faire mieux, et l'écart entre les deux mesure ce que l'estimation a perdu. Sans ce plafond,
    une aire de 0,75 ne veut rien dire : elle peut être excellente ou médiocre selon le portefeuille.
    """
    parfait = np.array([hazard_pd_12m(parametres, s, macro) for s in cohorte["score"]])
    return pouvoir_de_classement(cohorte["defaut_12m"].to_numpy(), parfait)


def calibration(defaut: np.ndarray, pd_annoncee: np.ndarray, tranches: int = 10) -> pd.DataFrame:
    """L'annoncé contre le réalisé, tranche par tranche de probabilité annoncée.

    Les tranches sont d'effectif égal et non de largeur égale : les probabilités de défaut se
    tassent près de zéro, si bien que des tranches de largeur égale mettraient presque tout le
    portefeuille dans la première.
    """
    defaut = np.asarray(defaut).astype(int)
    pd_annoncee = np.asarray(pd_annoncee, dtype=float)
    bornes = np.quantile(pd_annoncee, np.linspace(0.0, 1.0, tranches + 1))
    bornes = np.unique(bornes)
    if len(bornes) < 3:
        raise ValueError("les probabilités annoncées sont trop peu variées pour être découpées")
    numero = np.clip(np.digitize(pd_annoncee, bornes[1:-1]), 0, len(bornes) - 2)

    lignes = []
    for t in range(len(bornes) - 1):
        dedans = numero == t
        if not dedans.any():
            continue
        observe = float(defaut[dedans].mean())
        n = int(dedans.sum())
        # l'incertitude d'une proportion sur n observations : sans elle, un écart ne prouve rien
        erreur = float(np.sqrt(max(observe * (1.0 - observe), 1e-12) / n))
        lignes.append({"tranche": t + 1, "emprunteurs": n,
                       "pd_annoncee_moyenne": float(pd_annoncee[dedans].mean()),
                       "taux_de_defaut_observe": observe, "erreur_type": erreur,
                       "ecart": float(pd_annoncee[dedans].mean()) - observe})
    return pd.DataFrame(lignes)


def resume_de_calibration(table: pd.DataFrame) -> dict:
    """Deux nombres qui disent si le niveau annoncé est juste.

    Le premier est l'écart moyen, en points de pourcentage. Le second est le nombre de tranches où
    l'écart dépasse deux fois l'incertitude, c'est-à-dire où il ne peut pas s'expliquer par le
    hasard de l'échantillon.

    Le second nombre est à lire avec la taille de l'échantillon en tête. Sur vingt mille emprunteurs
    par tranche, l'incertitude tombe à 0,07 point et un écart de 0,15 point sort déjà du hasard, ce
    qui ne veut pas dire qu'il compte pour un service de crédit. C'est l'écart en points qui décide,
    et le compte de tranches qui alerte.
    """
    ecarts = table["ecart"].to_numpy()
    depassent = int((np.abs(ecarts) > 2.0 * table["erreur_type"].to_numpy()).sum())
    return {"tranches": int(len(table)), "ecart_moyen_points": float(100.0 * ecarts.mean()),
            "ecart_absolu_moyen_points": float(100.0 * np.abs(ecarts).mean()),
            "tranches_hors_hasard": depassent}
