"""Ponto de entrada / orquestrador do pipeline de monitoramento.

Fluxo geral (implementado módulo a módulo):

    1. CAPTURA       -> busca publicações por termos/nomes monitorados
    2. INTELIGÊNCIA  -> interpreta o texto e extrai prazos (JSON estruturado)
    3. AGENDA        -> cria eventos/alertas para os prazos extraídos

Execução (a partir da raiz do projeto):

    python -m src.main
"""
from __future__ import annotations

from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run() -> None:
    """Executa um ciclo completo do pipeline de monitoramento."""
    logger.info(
        "Iniciando pipeline | ambiente=%s | provedor_ia=%s",
        settings.app_env,
        settings.ai_provider,
    )
    logger.info(
        "Termos monitorados: %s",
        settings.monitor_terms_list or "(nenhum configurado)",
    )

    # 1. CAPTURA       -> src/services/capture        (TODO: próximo módulo)
    # 2. INTELIGÊNCIA  -> src/services/intelligence   (TODO)
    # 3. AGENDA        -> src/services/agenda          (TODO)

    logger.warning(
        "Módulos de captura/IA/agenda ainda não implementados. "
        "Estrutura base pronta para desenvolvimento."
    )


if __name__ == "__main__":
    run()
