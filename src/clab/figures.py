"""Quatre figures : les provisions réelles des banques, la courbe de capital, l'ECL, Enbridge."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from gvf.style import OKABE_ITO, appliquer, formateur

# La palette et les réglages viennent de la couche partagée du portefeuille : les mêmes couleurs et
# la même virgule décimale dans les vingt-neuf dépôts, corrigées à un seul endroit.


def use_style():
    """Les réglages communs, puis le formateur d'axe en français."""
    appliquer()
    return formateur()


def fig_pcl(pcl: pd.Series, dest: Path) -> None:
    """Les provisions des grandes banques canadiennes : le cycle du crédit en une courbe."""
    fr = use_style()
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(pcl.index, pcl.to_numpy(), color=OKABE_ITO[0])
    ax.axvspan(pd.Timestamp("2020-01-01"), pd.Timestamp("2020-12-31"), color="0.88", zorder=0)
    ax.text(pd.Timestamp("2020-02-01"), float(pcl.max()), "COVID", fontsize=9, color="0.4", va="top")
    ax.set_ylabel("Provisions pour pertes / encours de prêts (%)")
    ax.yaxis.set_major_formatter(fr)
    ax.set_title("Les provisions des grandes banques canadiennes triplent en 2020 puis se normalisent")
    fig.savefig(dest)
    plt.close(fig)


def fig_irb(dest: Path) -> None:
    """La courbe de capital K(PD) de l'hypothécaire, avec et sans les planchers de l'OSFI."""
    from clab.irb import irb_k

    fr = use_style()
    pds = np.logspace(-4, np.log10(0.2), 200)
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.plot(100 * pds, [100 * irb_k(p, 0.25, apply_floors=False) for p in pds],
            color=OKABE_ITO[0], linestyle="--", label="Sans plancher (LGD 25 %)")
    ax.plot(100 * pds, [100 * irb_k(p, 0.25, apply_floors=True) for p in pds],
            color=OKABE_ITO[3], label="Avec planchers OSFI (PD 0,05 %, LGD 10 %)")
    ax.set_xscale("log")
    ax.set_xlabel("PD (%, échelle logarithmique)")
    ax.set_ylabel("Capital K (% de l'exposition)")
    ax.yaxis.set_major_formatter(fr)
    ax.set_title("Le capital IRB hypothécaire croît avec la PD, et les planchers coupent le bas de la courbe")
    ax.legend(fontsize=9)
    fig.savefig(dest)
    plt.close(fig)


def fig_ecl(par_scenario: dict[str, float], ponderee: float, part_stade_2: float, dest: Path) -> None:
    """L'ECL par scénario, la pondérée, et ce que la convexité fait au chiffre central."""
    use_style()
    fig, ax = plt.subplots(figsize=(8, 4))
    noms = ["favorable", "de_base", "adverse"]
    vals = [par_scenario[n] for n in noms]
    bars = ax.bar([n.replace("_", " ") for n in noms], vals,
                  color=[OKABE_ITO[2], OKABE_ITO[0], OKABE_ITO[3]], width=0.55)
    ax.axhline(ponderee, color="black", linestyle="--", linewidth=1.4,
               label=f"ECL pondérée ({ponderee:,.0f} $)".replace(",", " "))
    for rect, v in zip(bars, vals, strict=True):
        ax.text(rect.get_x() + rect.get_width() / 2, v, f"{v:,.0f}".replace(",", " "),
                ha="center", va="bottom", fontsize=9)
    from matplotlib.ticker import FuncFormatter

    ax.set_ylabel("ECL du portefeuille synthétique (M$)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1e6:g}".replace(".", ",")))
    ax.set_title(f"Trois scénarios pondérés, {part_stade_2:.0f} % du portefeuille en stade 2".replace(".", ","))
    ax.legend(fontsize=9)
    fig.savefig(dest)
    plt.close(fig)


def fig_enbridge(ratios: pd.DataFrame, dest: Path) -> None:
    """Dix ans de levier et de couverture : le profil de crédit d'Enbridge d'un coup d'œil."""
    fr = use_style()
    sub = ratios.loc[2017:]         # la dette long terme SEC d'Enbridge commence en 2017
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(sub.index, sub["dette_sur_ebitda"], color=OKABE_ITO[0], alpha=0.85,
           label="Dette / EBITDA (échelle gauche)")
    ax.set_ylabel("Dette long terme / EBITDA (x)")
    ax.yaxis.set_major_formatter(fr)
    ax2 = ax.twinx()
    ax2.plot(sub.index, sub["couverture_interets"], color=OKABE_ITO[3], marker="o",
             label="EBITDA / intérêts (échelle droite)")
    ax2.set_ylabel("Couverture des intérêts (x)")
    ax2.yaxis.set_major_formatter(fr)
    ax2.spines["right"].set_visible(True)
    ax2.grid(False)
    ax.set_title("Enbridge : le levier d'un pipeline réglementé, la couverture qui suit les taux")
    lines = ax.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    labels = ax.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
    ax.legend(lines, labels, loc="upper right", fontsize=9)
    fig.savefig(dest)
    plt.close(fig)


def fig_discrimination(defaut, score_de_risque, plafond: dict, calib, dest: Path) -> dict:
    """Le pouvoir de classement du score, et la justesse des probabilités qu'il annonce.

    Deux volets, parce que ce sont deux questions différentes. À gauche, le score range-t-il les
    emprunteurs dans le bon ordre. À droite, les probabilités annoncées tombent-elles juste.
    """
    from gvf.figures import roc_ks
    from gvf.style import GRIS, enregistrer, fr

    from .discrimination import pouvoir_de_classement

    use_style()
    mesures = pouvoir_de_classement(defaut, score_de_risque)
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.4))

    roc_ks(axes[0], defaut, score_de_risque, etiquette="carte de score estimée")
    axes[0].set_title(f"Aire {fr(mesures['aire'], 3)}, Gini {fr(mesures['gini'], 3)}, "
                      f"écart de Kolmogorov-Smirnov {fr(mesures['ks'], 3)}")
    # l'égalité avec le modèle vrai n'est pas un exploit et il ne faut pas la présenter comme tel :
    # avec une seule variable d'emprunteur, tout classement croissant donne le même ordre
    identique = abs(mesures["aire"] - plafond["aire"]) < 1e-12
    axes[0].annotate("un devin qui connaîtrait le vrai modèle classerait\n"
                     + ("exactement pareil : avec une seule variable\nd'emprunteur, il n'y a rien à "
                        "gagner sur le classement" if identique
                        else f"un peu mieux, à {fr(plafond['aire'], 3)}"),
                     (0.40, 0.14), fontsize=9, color=GRIS)

    annonce = 100 * calib["pd_annoncee_moyenne"]
    observe = 100 * calib["taux_de_defaut_observe"]
    erreur = 100 * 1.96 * calib["erreur_type"]
    axes[1].errorbar(annonce, observe, yerr=erreur, fmt="o", markersize=6, capsize=3,
                     color=OKABE_ITO[0], label="tranches de probabilité annoncée")
    borne = float(max(annonce.max(), observe.max())) * 1.12
    axes[1].plot([0, borne], [0, borne], color=GRIS, linestyle="--", linewidth=1.2,
                 label="annonce exacte")
    axes[1].set_xlim(0, borne)
    axes[1].set_ylim(0, borne)
    axes[1].set_xlabel("Probabilité de défaut annoncée par le modèle (%)")
    axes[1].set_ylabel("Défauts réellement survenus (%)")
    axes[1].legend(loc="upper left")
    hors = int((abs(calib["ecart"]) > 2 * calib["erreur_type"]).sum())
    axes[1].set_title(f"{len(calib) - hors} tranches sur {len(calib)} tiennent dans le hasard de "
                      "l'échantillon")

    fig.suptitle("Classer et chiffrer sont deux exercices différents ; c'est le second qui se joue "
                 "à l'estimation")
    dest.parent.mkdir(parents=True, exist_ok=True)
    enregistrer(fig, dest.parent, dest.stem)
    plt.close(fig)
    return mesures
