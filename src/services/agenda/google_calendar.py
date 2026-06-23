"""Provedor de agenda usando a API do Google Calendar (Etapa 3).

Cria um evento de dia inteiro na data fatal do prazo, com lembrete configurável
(popup + e-mail) de antecedência. Usa `extendedProperties` como chave de
idempotência para não duplicar eventos quando o pipeline roda repetidamente.
"""
from __future__ import annotations

import os
from datetime import timedelta

from src.config.settings import settings
from src.models import EventoAgenda
from src.services.agenda.base import AgendaError, AgendaProvider
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
# Limite do Google Calendar para lembretes (28 dias, em minutos).
_LEMBRETE_MAX_MIN = 40320


class GoogleCalendarProvider(AgendaProvider):
    """Cria eventos/lembretes no Google Calendar."""

    def __init__(
        self,
        credentials_path: str | None = None,
        token_path: str | None = None,
        calendar_id: str | None = None,
    ) -> None:
        self.credentials_path = credentials_path or settings.google_calendar_credentials
        self.token_path = token_path or settings.google_calendar_token
        self.calendar_id = calendar_id or settings.google_calendar_id
        try:
            from googleapiclient.discovery import build
        except ModuleNotFoundError as exc:  # pragma: no cover - depende do ambiente
            raise AgendaError(
                "Pacotes do Google API não instalados. Rode: pip install -r requirements.txt"
            ) from exc
        self._service = build(
            "calendar", "v3", credentials=self._carregar_credenciais()
        )

    def _carregar_credenciais(self):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ModuleNotFoundError as exc:  # pragma: no cover - depende do ambiente
            raise AgendaError(
                "Pacotes de autenticação do Google não instalados."
            ) from exc

        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, _SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise AgendaError(
                        f"Credenciais OAuth '{self.credentials_path}' não encontradas. "
                        "Baixe o client_secret do Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, _SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(self.token_path, "w", encoding="utf-8") as fh:
                fh.write(creds.to_json())
        return creds

    def criar_evento(self, evento: EventoAgenda) -> str | None:
        if self._evento_existente(evento.chave_idempotencia):
            logger.info(
                "Evento já existe na agenda (chave=%s); ignorando.",
                evento.chave_idempotencia,
            )
            return None
        try:
            criado = (
                self._service.events()
                .insert(calendarId=self.calendar_id, body=self._montar_corpo(evento))
                .execute()
            )
        except Exception as exc:  # boundary com a API do Google
            raise AgendaError(f"Falha ao criar evento no Google Calendar: {exc}") from exc
        logger.info("Evento criado: %s (%s)", criado.get("id"), evento.titulo)
        return criado.get("id")

    def _evento_existente(self, chave: str) -> bool:
        try:
            resposta = (
                self._service.events()
                .list(
                    calendarId=self.calendar_id,
                    privateExtendedProperty=f"monitor_key={chave}",
                    maxResults=1,
                )
                .execute()
            )
        except Exception:  # consulta de dedup não deve quebrar o fluxo
            return False
        return bool(resposta.get("items"))

    @staticmethod
    def _montar_corpo(evento: EventoAgenda) -> dict:
        lembrete_min = min(max(evento.lembrete_dias_antes, 0) * 24 * 60, _LEMBRETE_MAX_MIN)
        return {
            "summary": evento.titulo,
            "description": evento.descricao,
            "start": {"date": evento.data.isoformat()},
            "end": {"date": (evento.data + timedelta(days=1)).isoformat()},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": lembrete_min},
                    {"method": "email", "minutes": lembrete_min},
                ],
            },
            "extendedProperties": {"private": {"monitor_key": evento.chave_idempotencia}},
        }
