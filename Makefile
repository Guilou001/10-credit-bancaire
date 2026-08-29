# Prérequis : uv (https://docs.astral.sh/uv/)
UV ?= uv

setup:
	$(UV) sync --locked --all-extras

test:             ## 9 tests : vérité retrouvée par le hasard, IRB à la main, ECL, stades (sans réseau)
	$(UV) run pytest

lint:
	$(UV) run ruff check src tests

lab:              ## laboratoire synthétique + miroir Valet + dossier Enbridge (exige clab fetch)
	$(UV) run clab lab && $(UV) run clab mirror && $(UV) run clab credit
