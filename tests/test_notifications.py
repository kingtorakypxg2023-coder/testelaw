"""Testes das notificações (Etapa de alertas)."""
from __future__ import annotations

from datetime import date

import pytest
import requests

from src.models import EventoAgenda
from src.services.notifications import formatar_evento, get_notifier
from src.services.notifications.base import NotifierError
from src.services.notifications.mock import MockNotifier
from src.services.notifications.telegram import TelegramNotifier
from src.services.notifications.webhook import WebhookNotifier


def _evento(urgente: bool = True) -> EventoAgenda:
    return EventoAgenda(
        titulo="[URGENTE] Recurso — Processo 0001",
        descricao="Interpor apelação",
        data=date(2026, 7, 10),
        lembrete_dias_antes=5,
        chave_idempotencia="k1",
        urgente=urgente,
    )


def test_formatar_evento_inclui_data_e_titulo() -> None:
    titulo, corpo = formatar_evento(_evento())
    assert "Recurso" in titulo
    assert "10/07/2026" in corpo
    assert "Interpor apelação" in corpo


def test_mock_notifier_registra_envio() -> None:
    notifier = MockNotifier()
    resultados = notifier.notificar_eventos([_evento(), _evento(urgente=False)])
    assert resultados == [True, True]
    assert len(notifier.enviadas) == 2


def test_factory_mock() -> None:
    assert isinstance(get_notifier("mock"), MockNotifier)


def test_factory_desconhecido() -> None:
    with pytest.raises(ValueError):
        get_notifier("canal_inexistente")


def test_webhook_sem_url_falha() -> None:
    with pytest.raises(NotifierError):
        WebhookNotifier(url=None)


def test_webhook_envia(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas = {}

    class _Resp:
        def raise_for_status(self) -> None:  # noqa: D401
            return None

    def fake_post(url, json=None, timeout=None):
        chamadas["url"] = url
        chamadas["json"] = json
        return _Resp()

    monkeypatch.setattr(requests, "post", fake_post)
    notifier = WebhookNotifier(url="https://exemplo/webhook")

    assert notifier.enviar("Título", "Corpo", urgente=True) is True
    assert chamadas["url"] == "https://exemplo/webhook"
    assert chamadas["json"]["urgente"] is True


def test_telegram_sem_token_falha() -> None:
    with pytest.raises(NotifierError):
        TelegramNotifier(token=None, chat_id=None)
