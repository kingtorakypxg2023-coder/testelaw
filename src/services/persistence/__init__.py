"""Persistência: estado de processamento (evita reprocessar/duplicar)."""
from src.services.persistence.base import StateStore
from src.services.persistence.factory import get_state_store

__all__ = ["StateStore", "get_state_store"]
