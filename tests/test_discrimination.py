"""Le pouvoir de classement et la calibration, vérifiés sur des cas construits à la main."""

import numpy as np
import pytest

from clab.discrimination import (
    calibration,
    pouvoir_de_classement,
    rangs_moyens,
    resume_de_calibration,
)


def test_l_aire_vaut_la_part_de_paires_bien_classees():
    """Vérité calculée à la main : deux défauts notés 0,35 et 0,80, deux sains notés 0,10 et 0,40.
    Trois des quatre paires sont dans le bon ordre, donc l'aire vaut exactement 0,75."""
    m = pouvoir_de_classement([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8])
    assert m["aire"] == pytest.approx(0.75)
    assert m["gini"] == pytest.approx(0.5)
    assert m["defauts"] == 2 and m["sains"] == 2


def test_un_score_qui_separe_parfaitement_donne_une_aire_de_un():
    verite = [0] * 40 + [1] * 40
    score = list(np.linspace(0.0, 0.49, 40)) + list(np.linspace(0.5, 1.0, 40))
    m = pouvoir_de_classement(verite, score)
    assert m["aire"] == pytest.approx(1.0)
    assert m["ks"] == pytest.approx(1.0)


def test_un_score_constant_ne_separe_rien():
    """Le piège que le rang moyen répare : sans lui, l'ordre de tri déciderait de l'aire."""
    m = pouvoir_de_classement([0, 1, 0, 1], [1.0, 1.0, 1.0, 1.0])
    assert m["aire"] == pytest.approx(0.5)
    assert m["gini"] == pytest.approx(0.0)


def test_un_score_a_l_envers_donne_une_aire_sous_un_demi():
    """Un score qui classe les bons en tête est pire que le hasard, et le nombre doit le dire."""
    m = pouvoir_de_classement([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1])
    assert m["aire"] < 0.5
    assert m["gini"] < 0.0


def test_les_rangs_moyens_partagent_les_ex_aequo():
    assert list(rangs_moyens(np.array([10.0, 20.0, 20.0, 30.0]))) == [1.0, 2.5, 2.5, 4.0]


def test_un_echantillon_sans_defaut_est_refuse():
    with pytest.raises(ValueError, match="au moins un défaut"):
        pouvoir_de_classement([0, 0, 0], [0.1, 0.2, 0.3])


def _resume(annonce, vrai, graine=30):
    rng = np.random.default_rng(graine)
    defaut = (rng.random(len(vrai)) < vrai).astype(int)
    return resume_de_calibration(calibration(defaut, annonce, tranches=3))


def test_une_annonce_juste_se_distingue_d_une_annonce_fausse():
    """Ce qui compte est l'écart en POINTS, pas le compte de tranches jugées hors du hasard.

    Sur vingt mille emprunteurs par tranche, l'incertitude tombe à 0,07 point : un écart de
    0,15 point, sans intérêt pour un service de crédit, sort déjà du hasard. Le test compare donc
    une annonce juste à une annonce deux fois trop basse, et exige un rapport d'au moins vingt."""
    vrai = np.repeat([0.02, 0.10, 0.40], 20_000)
    juste = _resume(vrai, vrai)
    fausse = _resume(vrai / 2.0, vrai)
    # 0,5 point n'est pas un seuil choisi après coup : c'est le plancher de bruit mesuré, une
    # annonce parfaitement juste s'écartant encore de 0,305 point sur soixante mille emprunteurs
    assert juste["ecart_absolu_moyen_points"] < 0.5
    assert juste["tranches_hors_hasard"] == 0
    assert fausse["ecart_absolu_moyen_points"] > 20 * juste["ecart_absolu_moyen_points"]


def test_une_annonce_trop_basse_a_le_bon_signe():
    """Le modèle annonce la moitié des défauts réels : l'écart doit être négatif et franc."""
    vrai = np.repeat([0.02, 0.10, 0.40], 20_000)
    fausse = _resume(vrai / 2.0, vrai)
    assert fausse["ecart_moyen_points"] < -5.0
    assert fausse["tranches_hors_hasard"] == 3


def test_les_tranches_sont_d_effectif_egal_sur_une_annonce_continue():
    """Des tranches de largeur égale mettraient presque tout le portefeuille dans la première, les
    probabilités de défaut se tassant près de zéro."""
    rng = np.random.default_rng(30)
    annonce = rng.beta(1.2, 30.0, 5000)
    defaut = (rng.random(5000) < annonce).astype(int)
    table = calibration(defaut, annonce, tranches=5)
    assert table["emprunteurs"].nunique() == 1


def test_un_portefeuille_ou_presque_tous_annoncent_la_meme_chose_est_refuse():
    """Neuf emprunteurs sur dix à la même probabilité : des tranches d'effectif égal n'existent pas,
    et la fonction le dit plutôt que d'en fabriquer de bancales."""
    annonce = np.concatenate([np.full(900, 0.005), np.linspace(0.05, 0.5, 100)])
    defaut = np.zeros(1000, dtype=int)
    defaut[:5] = 1
    with pytest.raises(ValueError, match="trop peu variées"):
        calibration(defaut, annonce, tranches=5)


def test_des_probabilites_toutes_identiques_sont_refusees():
    with pytest.raises(ValueError, match="trop peu variées"):
        calibration(np.array([0, 1, 0, 1]), np.full(4, 0.05))
