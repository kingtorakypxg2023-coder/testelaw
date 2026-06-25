"""Carregamento e validação centralizada das configurações do projeto.

Todas as variáveis de ambiente (definidas em `.env`) são carregadas e
validadas aqui por meio de `pydantic-settings` (que utiliza `python-dotenv`
internamente para ler o arquivo `.env`), garantindo um ponto único de
verdade para a configuração da aplicação.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz para localizar o `.env`: ao lado do executável (PyInstaller) ou, em
# execução normal, a raiz do projeto (src/config/settings.py -> sobe 2 níveis).
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Configurações da aplicação, carregadas do ambiente / arquivo `.env`."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Aplicação ---
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # --- Etapa 1: Captura (Diários Oficiais) ---
    escavador_api_key: str | None = Field(default=None)
    jusbrasil_api_key: str | None = Field(default=None)
    jusbrasil_api_base_url: str = Field(default="https://api.jusbrasil.com.br")
    jusbrasil_search_path: str = Field(default="/v1/publicacoes/busca")
    # DJEN / Comunica (CNJ) — gratuito, sem credencial
    comunica_api_base_url: str = Field(default="https://comunicaapi.pje.jus.br")
    comunica_search_path: str = Field(default="/api/v1/comunicacao")
    comunica_page_size: int = Field(default=100)
    # Provedor de captura ativo: "comunica" (DJEN/CNJ, gratuito e real) |
    # "mock" (demonstração, dados fictícios) | "jusbrasil"
    capture_provider: str = Field(default="comunica")
    # Alvos de monitoramento (listas separadas por vírgula)
    monitor_terms: str = Field(default="")
    monitor_oab: str = Field(default="")
    monitor_processos: str = Field(default="")

    # --- Etapa 2: Inteligência Artificial ---
    ai_provider: str = Field(default="claude")  # claude | gemini | openai | mock
    anthropic_api_key: str | None = Field(default=None)
    claude_model: str = Field(default="claude-haiku-4-5")
    gemini_api_key: str | None = Field(default=None)
    gemini_model: str = Field(default="gemini-2.5-flash")
    openai_api_key: str | None = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")

    # --- Etapa 3: Integração / Agenda (Google Calendar) ---
    agenda_provider: str = Field(default="mock")  # google | mock
    google_calendar_credentials: str = Field(default="credentials.json")
    google_calendar_token: str = Field(default="token.json")
    google_calendar_id: str = Field(default="primary")
    deadline_reminder_days: int = Field(default=5)

    # --- Persistência & Agendamento ---
    state_store: str = Field(default="sqlite")  # sqlite | memory
    state_db_path: str = Field(default="data/monitor.db")
    schedule_interval_seconds: int = Field(default=3600)

    # --- Notificações ---
    notifier: str = Field(default="mock")  # mock | webhook | telegram | email
    notify_only_urgent: bool = Field(default=True)
    webhook_url: str | None = Field(default=None)
    telegram_bot_token: str | None = Field(default=None)
    telegram_chat_id: str | None = Field(default=None)
    smtp_host: str | None = Field(default=None)
    smtp_port: int = Field(default=587)
    smtp_user: str | None = Field(default=None)
    smtp_password: str | None = Field(default=None)
    smtp_from: str | None = Field(default=None)
    smtp_to: str | None = Field(default=None)

    @staticmethod
    def _split_csv(value: str) -> list[str]:
        """Divide uma string separada por vírgulas em itens limpos (sem vazios)."""
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def monitor_terms_list(self) -> list[str]:
        """Termos/nomes livres monitorados."""
        return self._split_csv(self.monitor_terms)

    @property
    def monitor_oab_list(self) -> list[str]:
        """Inscrições da OAB monitoradas (ex.: '123456/SP')."""
        return self._split_csv(self.monitor_oab)

    @property
    def monitor_processos_list(self) -> list[str]:
        """Números de processo (CNJ) monitorados."""
        return self._split_csv(self.monitor_processos)


@lru_cache
def get_settings() -> Settings:
    """Retorna uma instância singleton (cacheada) das configurações."""
    return Settings()


# Instância pronta para importação em todo o projeto: `from src.config.settings import settings`
settings = get_settings()
