"""Ligne de commande : télécharger, faire tourner le laboratoire, produire le dossier de crédit."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(help="Laboratoire de crédit : PD (WoE, hasard, Vasicek), ECL IFRS 9, capital IRB "
                       "OSFI, provisions des banques canadiennes, dossier de crédit Enbridge.")

RHO = 0.15          # la corrélation de l'hypothécaire (OSFI), réutilisée pour Vasicek
LGD = 0.25          # précepte du laboratoire, déclaré


@app.callback()
def main() -> None:
    """Sous-commandes nommées."""


@app.command()
def fetch() -> None:
    """Enbridge (SEC) et provisions des grandes banques (Valet) ; Freddie Mac reste un dépôt manuel."""
    from clab import data

    data.fetch()
    h = data.load_enbridge()
    pcl = data.load_pcl()
    typer.echo(f"Enbridge : exercices {h.index.min()} -> {h.index.max()} ; "
               f"PCL Valet : {pcl.index[0].date()} -> {pcl.index[-1].date()} ({len(pcl)} trimestres)")


@app.command()
def lab(out: Path = Path("results")) -> None:
    """Le laboratoire sur portefeuille synthétique : les trois moteurs, l'ECL, la courbe IRB."""
    import numpy as np
    import pandas as pd

    from clab import data, discrimination, ecl, figures, pd_models

    panel = data.simulate_portfolio()
    typer.echo(f"panel synthétique : {panel['pret'].nunique()} prêts, {len(panel)} lignes prêt-mois, "
               f"taux de défaut cumulé {100 * panel.groupby('pret')['defaut'].max().mean():.1f} %")

    fitted = pd_models.hazard_fit(panel)
    verite = data.TRUE_PARAMS
    tables = out / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"parametre": k, "vrai": verite[k], "estime_hasard": fitted[k]} for k in fitted
    ]).to_csv(tables / "hasard_verite_vs_estime.csv", index=False)

    cohort = pd_models.default_within_12m(panel)
    woe = pd_models.logistic_woe_pd(cohort)
    woe.to_csv(tables / "carte_de_score_woe.csv", index=False)

    # l'ECL du portefeuille : PD TTC par prêt (hasard à macro neutre), octroi = même chose (livre neuf)
    rng = np.random.default_rng(1)
    scores = rng.normal(0.0, 1.0, 2000)
    macro_neutre = np.zeros(12)
    pd_ttc = np.array([pd_models.hazard_pd_12m(fitted, s, macro_neutre) for s in scores])
    pd_octroi = pd_ttc.copy()
    # une détérioration : le tiers le plus faible du livre a vu sa PD tripler depuis l'octroi
    # (bornée à 95 %, une probabilité ne dépasse pas 1)
    worst = np.argsort(scores)[: len(scores) // 3]
    pd_now = pd_ttc.copy()
    pd_now[worst] = np.clip(pd_now[worst] * 3.0, None, 0.95)
    ead = np.full(len(scores), 100_000.0)
    res = ecl.portfolio_ecl(pd_now, pd_octroi, RHO, LGD, ead)
    pd.DataFrame([{"scenario": k, "ecl": v} for k, v in res["par_scenario"].items()]
                 + [{"scenario": "ponderee", "ecl": res["ecl_ponderee"]},
                    {"scenario": "part_stade_2_pct", "ecl": res["part_stade_2_pct"]}]
                 ).to_csv(tables / "ecl_scenarios.csv", index=False)

    # Le score classe-t-il bien, et ses probabilités sont-elles justes ? Les deux se mesurent sur
    # la cohorte d'octroi, sur laquelle on connaît à la fois le score de départ et le défaut à
    # douze mois.
    macro_douze = panel.groupby("mois")["macro"].first().to_numpy()[:12]
    pd_annoncee = np.array([pd_models.hazard_pd_12m(fitted, s, macro_douze)
                            for s in cohort["score"]])
    classement = discrimination.pouvoir_de_classement(cohort["defaut_12m"].to_numpy(), pd_annoncee)
    plafond = discrimination.plafond_du_modele_vrai(cohort, verite, macro_douze)
    calib = discrimination.calibration(cohort["defaut_12m"].to_numpy(), pd_annoncee)
    resume = discrimination.resume_de_calibration(calib)
    calib.to_csv(tables / "calibration.csv", index=False)
    pd.DataFrame([{"mesure": "aire, carte de score", "valeur": classement["aire"]},
                  {"mesure": "aire, modèle vrai", "valeur": plafond["aire"]},
                  {"mesure": "part du plafond atteinte",
                   "valeur": classement["aire"] / plafond["aire"]},
                  {"mesure": "gini, carte de score", "valeur": classement["gini"]},
                  {"mesure": "ecart de Kolmogorov-Smirnov", "valeur": classement["ks"]},
                  {"mesure": "ecart de calibration moyen, points",
                   "valeur": resume["ecart_moyen_points"]},
                  {"mesure": "tranches hors hasard sur " + str(resume["tranches"]),
                   "valeur": resume["tranches_hors_hasard"]}]
                 ).to_csv(tables / "discrimination.csv", index=False)
    typer.echo(f"classement : aire {classement['aire']:.3f} contre {plafond['aire']:.3f} pour le "
               f"modèle vrai, Gini {classement['gini']:.3f}, KS {classement['ks']:.3f} ; "
               f"calibration : écart moyen {resume['ecart_moyen_points']:+.2f} point, "
               f"{resume['tranches_hors_hasard']} tranche(s) hors hasard sur {resume['tranches']}")

    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    figures.fig_discrimination(cohort["defaut_12m"].to_numpy(), pd_annoncee, plafond, calib,
                               figs / "discrimination.png")
    figures.fig_irb(figs / "capital_irb.png")
    figures.fig_ecl(res["par_scenario"], res["ecl_ponderee"], res["part_stade_2_pct"],
                    figs / "ecl_scenarios.png")
    typer.echo(f"ECL pondérée {res['ecl_ponderee']:,.0f} $ (centrale {res['ecl_scenario_central']:,.0f} $), "
               f"stade 2 : {res['part_stade_2_pct']:.1f} %")


@app.command()
def mirror(out: Path = Path("results")) -> None:
    """Le miroir canadien réel : les provisions des grandes banques (Valet), figure et table."""
    from clab import data, figures

    pcl = data.load_pcl()
    tables = out / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    pcl.to_csv(tables / "pcl_grandes_banques.csv")
    (out / "figures").mkdir(parents=True, exist_ok=True)
    figures.fig_pcl(pcl, out / "figures" / "pcl_grandes_banques.png")
    typer.echo(f"PCL : min {pcl.min():.2f} %, max {pcl.max():.2f} % ({pcl.idxmax().date()})")


@app.command()
def credit(out: Path = Path("results")) -> None:
    """Le dossier de crédit Enbridge : étalement, ratios, classeur Excel, figure."""
    from clab import data, excel, figures

    h = data.load_enbridge().loc[2011:]
    ratios = excel.credit_ratios(h)
    table, note, lettre = excel.scorecard(ratios.loc[ratios.index.max()])
    tables = out / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    ratios.round(3).to_csv(tables / "enbridge_etalement_ratios.csv")
    table.to_csv(tables / "enbridge_cotation.csv", index=False)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    figures.fig_enbridge(ratios, out / "figures" / "enbridge_ratios.png")
    excel.build_workbook(ratios, table, note, lettre, Path("reports/dossier_credit_enbridge.xlsx"))
    typer.echo(f"note pondérée {note:.2f} -> lettre interne {lettre} ; "
               f"classeur -> reports/dossier_credit_enbridge.xlsx")


if __name__ == "__main__":
    app()
