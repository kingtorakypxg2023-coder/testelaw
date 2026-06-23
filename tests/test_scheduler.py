"""Testes do scheduler."""
from __future__ import annotations

import src.scheduler as scheduler


def test_executar_ciclo_chama_run(monkeypatch) -> None:
    chamadas = {"n": 0}

    def fake_run():
        chamadas["n"] += 1
        return ["analise"]

    monkeypatch.setattr(scheduler, "run", fake_run)

    resultado = scheduler.executar_ciclo()

    assert chamadas["n"] == 1
    assert resultado == ["analise"]


def test_executar_ciclo_engole_excecao(monkeypatch) -> None:
    def fake_run():
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(scheduler, "run", fake_run)

    # Não deve propagar; o scheduler segue no próximo ciclo.
    assert scheduler.executar_ciclo() == []


def test_run_forever_respeita_max_ciclos(monkeypatch) -> None:
    contador = {"n": 0}

    def fake_run():
        contador["n"] += 1
        return []

    monkeypatch.setattr(scheduler, "run", fake_run)

    ciclos = scheduler.run_forever(intervalo=0, max_ciclos=3)

    assert ciclos == 3
    assert contador["n"] == 3
