"""Testes do cálculo de prazos / datas fatais (dias úteis)."""
from __future__ import annotations

from datetime import date

from src.utils.prazos import adicionar_dias_uteis, calcular_data_fatal

# 2026-06-19 é uma sexta-feira (referência das contagens abaixo).
SEXTA = date(2026, 6, 19)


def test_um_dia_util_pula_fim_de_semana() -> None:
    # Sexta + 1 dia útil -> segunda-feira (22/06).
    assert adicionar_dias_uteis(SEXTA, 1) == date(2026, 6, 22)


def test_quinze_dias_uteis() -> None:
    # 15 dias úteis a partir de sexta 19/06 -> sexta 10/07.
    assert calcular_data_fatal(SEXTA, 15) == date(2026, 7, 10)


def test_dias_corridos() -> None:
    assert calcular_data_fatal(SEXTA, 10, dias_uteis=False) == date(2026, 6, 29)


def test_feriado_e_pulado() -> None:
    # Feriado na segunda (22/06) empurra o 1º dia útil para terça (23/06).
    assert adicionar_dias_uteis(SEXTA, 1, feriados={date(2026, 6, 22)}) == date(2026, 6, 23)


def test_sem_data_base_ou_prazo() -> None:
    assert calcular_data_fatal(None, 15) is None
    assert calcular_data_fatal(SEXTA, None) is None
