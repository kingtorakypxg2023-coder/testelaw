"""Notificações: alertas de prazos por webhook / Telegram / e-mail."""
from src.services.notifications.base import (
    Notifier,
    NotifierError,
    formatar_evento,
)
from src.services.notifications.factory import get_notifier

__all__ = ["Notifier", "NotifierError", "formatar_evento", "get_notifier"]
