"""Quatre figures : les provisions réelles des banques, la courbe de capital, l'ECL, Enbridge."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442", "#000000"]


def use_style():
    import matplotlib as mpl
    from cycler import cycler
    from matplotlib.ticker import FuncFormatter

    mpl.rcParams.update({
        "figure.dpi": 200, "savefig.dpi": 200, "figure.constrained_layout.use": True,
        "font.size": 11, "axes.titlesize": 12, "axes.prop_cycle": cycler(color=OKABE_ITO),
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.alpha": 0.3, "grid.linewidth": 0.5,
        "legend.frameon": False, "lines.linewidth": 1.8,
    })
    return FuncFormatter(lambda v, _: f"{v:g}".replace(".", ","))


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
