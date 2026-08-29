"""Le laboratoire sur vérité connue : chaque moteur doit retrouver les paramètres du simulateur."""

import numpy as np
import pytest

from clab.data import TRUE_PARAMS, simulate_portfolio
from clab.ecl import Scenario, ecl_lifetime, portfolio_ecl, stage
from clab.irb import PD_FLOOR, irb_k
from clab.pd_models import (
    default_within_12m,
    hazard_fit,
    hazard_pd_12m,
    logistic_woe_pd,
    vasicek_pit,
)


@pytest.fixture(scope="module")
def panel():
    return simulate_portfolio(n_loans=8000, n_months=72, seed=0)


def test_hazard_recovers_the_true_parameters(panel):
    fitted = hazard_fit(panel)
    assert fitted["intercept"] == pytest.approx(TRUE_PARAMS["intercept"], abs=0.30)
    assert fitted["beta_score"] == pytest.approx(TRUE_PARAMS["beta_score"], abs=0.15)
    assert fitted["beta_macro"] == pytest.approx(TRUE_PARAMS["beta_macro"], abs=0.25)


def test_woe_scorecard_is_monotonic_and_calibrated(panel):
    cohort = default_within_12m(panel)
    table = logistic_woe_pd(cohort)
    assert table["pd_12m"].is_monotonic_decreasing or table["pd_12m"].is_monotonic_increasing
    predicted = float((table["pd_12m"] * table["count"]).sum() / table["count"].sum())
    realized = float(cohort["defaut_12m"].mean())
    assert predicted == pytest.approx(realized, rel=0.2)


def test_hazard_pd_12m_composes_a_constant_hazard():
    params = {"intercept": 0.0, "beta_score": 0.0, "beta_macro": 0.0}
    h = 0.5                                       # expit(0) : hasard mensuel de 50 %
    expected = 1.0 - (1.0 - h) ** 12
    assert hazard_pd_12m(params, 0.0, np.zeros(12)) == pytest.approx(expected, rel=1e-12)


def test_vasicek_pit_averages_back_to_ttc_over_the_cycle():
    # la propriété exacte : la moyenne des PIT sur z ~ N(0, 1) redonne la PD à travers le cycle
    from scipy.stats import norm

    zs = np.linspace(-6, 6, 4001)
    pit = np.array([vasicek_pit(0.02, 0.15, z) for z in zs])
    mean_pit = float(np.trapezoid(pit * norm.pdf(zs), zs))
    assert mean_pit == pytest.approx(0.02, rel=1e-3)
    assert vasicek_pit(0.02, 1e-9, 0.7) == pytest.approx(0.02, rel=1e-3)
    assert vasicek_pit(0.02, 0.15, 1.5) > vasicek_pit(0.02, 0.15, 0.0) > vasicek_pit(0.02, 0.15, -1.5)


def test_irb_k_matches_the_hand_computed_value():
    # PD 1 %, LGD 25 %, R 0,15 : refait à la main avec les quantiles normaux imprimés
    assert irb_k(0.01, 0.25, apply_floors=False) == pytest.approx(0.02508, abs=2e-4)
    assert irb_k(1e-6, 0.25) == irb_k(PD_FLOOR, 0.25)          # le plancher de PD mord
    assert irb_k(0.01, 0.01) == irb_k(0.01, 0.10)              # le plancher de LGD mord
    pds = np.linspace(0.001, 0.2, 50)
    ks = [irb_k(p, 0.25) for p in pds]
    assert all(a <= b + 1e-12 for a, b in zip(ks, ks[1:], strict=False))


def test_ecl_lifetime_matches_a_hand_case():
    # PD 10 %, LGD 50 %, EAD 100, 2 ans, sans actualisation : 5 + 4,5
    assert ecl_lifetime(0.10, 0.50, 100.0, years=2, discount=0.0) == pytest.approx(9.5)


def test_stage_rule_thresholds():
    assert stage(0.019, 0.01) == 1
    assert stage(0.021, 0.01) == 2


def test_portfolio_ecl_orders_scenarios_and_weights():
    pd_ttc = np.array([0.01, 0.02, 0.05])
    res = portfolio_ecl(pd_ttc, pd_ttc, rho=0.15, lgd=0.25, ead=np.full(3, 100.0),
                        scenarios=(Scenario("favorable", -1.0, 0.25), Scenario("de_base", 0.0, 0.5),
                                   Scenario("adverse", 1.5, 0.25)))
    s = res["par_scenario"]
    assert s["favorable"] < s["de_base"] < s["adverse"]
    assert s["favorable"] <= res["ecl_ponderee"] <= s["adverse"]
    assert res["ecl_ponderee"] > res["ecl_scenario_central"]   # la convexité coûte
    assert res["part_stade_2_pct"] == 0.0                      # livre neuf : rien n'a dérivé


def test_vasicek_used_by_stage_two_book():
    pd_ttc = np.array([0.01, 0.01])
    pd_origination = np.array([0.01, 0.003])                   # le second a plus que triplé
    res = portfolio_ecl(pd_ttc, pd_origination, rho=0.15, lgd=0.25, ead=np.full(2, 100.0))
    assert res["part_stade_2_pct"] == pytest.approx(50.0)
