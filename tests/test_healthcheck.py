"""Testes do healthcheck (prontidão dos provedores)."""
from __future__ import annotations

from src.config.settings import Settings
from src.healthcheck import verificar


def _por_nome(componentes) -> dict:
    return {c.nome: c for c in componentes}


def test_ia_pendente_sem_chave() -> None:
    cfg = Settings(
        capture_provider="mock",
        ai_provider="claude",
        anthropic_api_key=None,
        agenda_provider="mock",
        notifier="mock",
    )
    comps = _por_nome(verificar(cfg))
    assert comps["IA"].status == "pendente"
    assert comps["Captura"].status == "mock"
    assert comps["Agenda"].status == "mock"
    assert comps["Persistência"].status == "ok"


def test_ia_ok_com_chave() -> None:
    cfg = Settings(ai_provider="claude", anthropic_api_key="sk-test")
    assert _por_nome(verificar(cfg))["IA"].status == "ok"


def test_jusbrasil_pendente_sem_chave() -> None:
    cfg = Settings(capture_provider="jusbrasil", jusbrasil_api_key=None)
    assert _por_nome(verificar(cfg))["Captura"].status == "pendente"


def test_jusbrasil_ok_com_chave() -> None:
    cfg = Settings(capture_provider="jusbrasil", jusbrasil_api_key="chave-x")
    assert _por_nome(verificar(cfg))["Captura"].status == "ok"


def test_telegram_pendente_sem_credenciais() -> None:
    cfg = Settings(notifier="telegram", telegram_bot_token=None, telegram_chat_id=None)
    assert _por_nome(verificar(cfg))["Notificação"].status == "pendente"
