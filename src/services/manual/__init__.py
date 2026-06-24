"""Inclusão e gestão de prazos manuais (entrada alternativa à captura)."""
from src.services.manual.repository import (
    ManualPrazoRepository,
    get_manual_repository,
)
from src.services.manual.service import (
    adicionar_prazo_manual,
    construir_analise_manual,
    listar_prazos_manuais,
    registrar_prazo_manual,
    remover_prazo_manual,
    salvar_prazos_capturados,
)

__all__ = [
    "ManualPrazoRepository",
    "get_manual_repository",
    "adicionar_prazo_manual",
    "construir_analise_manual",
    "listar_prazos_manuais",
    "registrar_prazo_manual",
    "remover_prazo_manual",
    "salvar_prazos_capturados",
]
