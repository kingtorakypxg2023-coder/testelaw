"""Testes da normalização de número de processo (CNJ)."""
from __future__ import annotations

from src.utils.processos import normalizar_numero_processo


def test_normaliza_com_pontos() -> None:
    # Formato que o usuário costuma colar (com ponto no lugar do hífen).
    assert (
        normalizar_numero_processo("0100417.94.2026.5.01.0551")
        == "0100417-94.2026.5.01.0551"
    )


def test_normaliza_so_digitos() -> None:
    assert (
        normalizar_numero_processo("01004179420265010551")
        == "0100417-94.2026.5.01.0551"
    )


def test_mantem_mascara_correta() -> None:
    mascara = "1001234-56.2024.8.26.0100"
    assert normalizar_numero_processo(mascara) == mascara


def test_passthrough_quando_nao_tem_20_digitos() -> None:
    # Não é um CNJ completo: devolve o texto original (apenas aparado).
    assert normalizar_numero_processo("  80036/RJ ") == "80036/RJ"
