"""Carregamento e validação centralizada das configurações do projeto.

Todas as variáveis de ambiente (definidas em `.env`) são carregadas e
validadas aqui por meio de `pydantic-settings` (que utiliza `python-dotenv`
internamente para ler o arquivo `.env`), garantindo um ponto único de
verdade para a configuração da aplicação.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz do projeto (este arquivo está em src/config/settings.py -> sobe 2 níveis)
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
    monitor_terms: str = Field(default="")

    # --- Etapa 2: Inteligência Artificial ---
    ai_provider: str = Field(default="gemini")
    gemini_api_key: str | None = Field(default=None)
    gemini_model: str = Field(default="gemini-2.5-flash")
    openai_api_key: str | None = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")

    # --- Etapa 3: Integração / Agenda (Google Calendar) ---
    google_calendar_credentials: str = Field(default="credentials.json")
    google_calendar_token: str = Field(default="token.json")
    google_calendar_id: str = Field(default="primary")
    deadline_reminder_days: int = Field(default=5)

    @property
    def monitor_terms_list(self) -> list[str]:
        """Retorna os termos monitorados como uma lista limpa (sem vazios)."""
        return [t.strip() for t in self.monitor_terms.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    """Retorna uma instância singleton (cacheada) das configurações."""
    return Settings()


# Instância pronta para importação em todo o projeto: `from src.config.settings import settings`
settings = get_settings()
