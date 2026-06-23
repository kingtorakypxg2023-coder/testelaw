"""Inclusão de prazos manuais (entrada alternativa à captura automática)."""
from src.services.manual.service import construir_analise_manual, registrar_prazo_manual

__all__ = ["construir_analise_manual", "registrar_prazo_manual"]
