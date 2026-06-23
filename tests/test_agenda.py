"""Testes do módulo de agenda (Etapa 3)."""
from __future__ import annotations

from datetime import date

import pytest

from src.models import AnalisePublicacao, EventoAgenda, Prazo, TipoPrazo
from src.services.agenda import get_agenda_provider, montar_eventos
from src.services.agenda.google_calendar import GoogleCalendarProvider
from src.services.agenda.mock import MockAgendaProvider


def _analise(data_fatal: date | None = date(2026, 7, 10), urgente: bool = True) -> AnalisePublicacao:
    return AnalisePublicacao(
        id_externo="pub-1",
        numero_processo="1001234-56.2024.8.26.0100",
        resumo="Resumo da publicação.",
        possui_prazo=True,
        prazos=[
            Prazo(
                tipo=TipoPrazo.RECURSO,
                descricao="Interpor recurso de apelação",
                prazo_dias=15,
                data_fatal=data_fatal,
                urgente=urgente,
            )
        ],
    )


def test_montar_eventos_um_por_prazo_com_data() -> None:
    eventos = montar_eventos([_analise()], lembrete_dias=5)

    assert len(eventos) == 1
    ev = eventos[0]
    assert ev.data == date(2026, 7, 10)
    assert ev.lembrete_dias_antes == 5
    assert ev.urgente is True
    assert "Processo 1001234-56.2024.8.26.0100" in ev.titulo
    assert ev.titulo.startswith("[URGENTE]")
    assert ev.chave_idempotencia == "pub-1:recurso:2026-07-10"


def test_montar_eventos_ignora_prazo_sem_data() -> None:
    eventos = montar_eventos([_analise(data_fatal=None)], lembrete_dias=5)
    assert eventos == []


def test_mock_agenda_registra_eventos() -> None:
    provider = MockAgendaProvider()
    eventos = montar_eventos([_analise()], lembrete_dias=5)

    refs = provider.criar_eventos(eventos)

    assert all(refs)
    assert len(provider.eventos_criados) == 1


def test_google_calendar_monta_corpo_dia_inteiro_com_lembrete() -> None:
    evento = EventoAgenda(
        titulo="Recurso",
        descricao="...",
        data=date(2026, 7, 10),
        lembrete_dias_antes=5,
        chave_idempotencia="pub-1:recurso:2026-07-10",
        urgente=True,
    )

    corpo = GoogleCalendarProvider._montar_corpo(evento)

    assert corpo["start"] == {"date": "2026-07-10"}
    assert corpo["end"] == {"date": "2026-07-11"}  # evento de dia inteiro
    assert corpo["extendedProperties"]["private"]["monitor_key"] == "pub-1:recurso:2026-07-10"
    minutos = {o["minutes"] for o in corpo["reminders"]["overrides"]}
    assert minutos == {5 * 24 * 60}


def test_factory_retorna_mock() -> None:
    assert isinstance(get_agenda_provider("mock"), MockAgendaProvider)


def test_factory_provedor_desconhecido() -> None:
    with pytest.raises(ValueError):
        get_agenda_provider("provedor_inexistente")
