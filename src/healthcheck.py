"""Healthcheck: verifica a prontidão dos provedores (sem chamadas de rede).

Reporta, por componente, se está pronto (credencial/arquivo presente), em modo
mock, ou pendente de configuração. Útil após preencher o `.env` com as chaves
reais::

    python -m src.healthcheck

Sai com código 1 se houver algum componente pendente (útil para CI/deploy).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from src.config.settings import Settings, settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_MOCKS = {"mock", "fake", "stub", "log", "none"}


@dataclass
class StatusComponente:
    """Estado de prontidão de um componente do pipeline."""

    nome: str
    provedor: str
    status: str  # "ok" | "mock" | "pendente"
    detalhe: str


def _captura(s: Settings) -> StatusComponente:
    prov = s.capture_provider.strip().lower()
    if prov in _MOCKS:
        return StatusComponente("Captura", prov, "mock", "dados simulados")
    if prov in ("comunica", "djen", "cnj"):
        return StatusComponente(
            "Captura", "comunica/DJEN", "ok", "API pública gratuita (CNJ), sem credencial"
        )
    if prov == "jusbrasil":
        ok = bool(s.jusbrasil_api_key)
        return StatusComponente(
            "Captura", prov, "ok" if ok else "pendente",
            "JUSBRASIL_API_KEY " + ("configurada" if ok else "ausente"),
        )
    return StatusComponente("Captura", prov, "pendente", "provedor não implementado")


def _ia(s: Settings) -> StatusComponente:
    prov = s.ai_provider.strip().lower()
    if prov in _MOCKS:
        return StatusComponente("IA", prov, "mock", "extração simulada")
    chaves = {
        "claude": ("ANTHROPIC_API_KEY", s.anthropic_api_key, s.claude_model),
        "anthropic": ("ANTHROPIC_API_KEY", s.anthropic_api_key, s.claude_model),
        "gemini": ("GEMINI_API_KEY", s.gemini_api_key, s.gemini_model),
        "google": ("GEMINI_API_KEY", s.gemini_api_key, s.gemini_model),
        "openai": ("OPENAI_API_KEY", s.openai_api_key, s.openai_model),
    }
    if prov in chaves:
        nome_chave, valor, modelo = chaves[prov]
        ok = bool(valor)
        return StatusComponente(
            "IA", f"{prov} ({modelo})", "ok" if ok else "pendente",
            f"{nome_chave} " + ("configurada" if ok else "ausente"),
        )
    return StatusComponente("IA", prov, "pendente", "provedor desconhecido")


def _agenda(s: Settings) -> StatusComponente:
    prov = s.agenda_provider.strip().lower()
    if prov in _MOCKS:
        return StatusComponente("Agenda", prov, "mock", "eventos simulados")
    if prov in ("google", "google_calendar", "calendar"):
        existe = os.path.exists(s.google_calendar_credentials)
        return StatusComponente(
            "Agenda", "google", "ok" if existe else "pendente",
            f"{s.google_calendar_credentials} " + ("encontrado" if existe else "ausente"),
        )
    return StatusComponente("Agenda", prov, "pendente", "provedor desconhecido")


def _notificacao(s: Settings) -> StatusComponente:
    prov = s.notifier.strip().lower()
    if prov in _MOCKS:
        return StatusComponente("Notificação", prov, "mock", "alertas simulados")
    if prov == "webhook":
        ok = bool(s.webhook_url)
        return StatusComponente(
            "Notificação", prov, "ok" if ok else "pendente",
            "WEBHOOK_URL " + ("configurada" if ok else "ausente"),
        )
    if prov == "telegram":
        ok = bool(s.telegram_bot_token and s.telegram_chat_id)
        return StatusComponente(
            "Notificação", prov, "ok" if ok else "pendente",
            "TELEGRAM_BOT_TOKEN/CHAT_ID " + ("configurados" if ok else "ausentes"),
        )
    if prov == "email":
        ok = bool(s.smtp_host and (s.smtp_from or s.smtp_user) and s.smtp_to)
        return StatusComponente(
            "Notificação", prov, "ok" if ok else "pendente",
            "SMTP_HOST/FROM/TO " + ("configurados" if ok else "ausentes"),
        )
    return StatusComponente("Notificação", prov, "pendente", "canal desconhecido")


def _persistencia(s: Settings) -> StatusComponente:
    prov = s.state_store.strip().lower()
    if prov in ("memory", "mem", "memoria"):
        return StatusComponente("Persistência", prov, "ok", "em memória (efêmero)")
    return StatusComponente("Persistência", "sqlite", "ok", s.state_db_path)


def verificar(config: Settings | None = None) -> list[StatusComponente]:
    """Retorna o estado de prontidão de cada componente do pipeline."""
    s = config or settings
    return [_captura(s), _ia(s), _agenda(s), _notificacao(s), _persistencia(s)]


def main() -> None:
    icones = {"ok": "✅", "mock": "🧪", "pendente": "⏳"}
    componentes = verificar()
    logger.info("Verificação de prontidão (healthcheck):")
    for c in componentes:
        logger.info(
            "  %s %-13s %-24s %s", icones.get(c.status, "?"), c.nome, c.provedor, c.detalhe
        )
    pendentes = [c for c in componentes if c.status == "pendente"]
    if pendentes:
        logger.warning("%d componente(s) pendente(s) de configuração.", len(pendentes))
        sys.exit(1)
    logger.info("Tudo pronto (ok/mock).")


if __name__ == "__main__":
    main()
