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
from src.models import AlvoMonitoramento, Publicacao, TipoMonitoramento
from src.services.capture import carregar_alvos, get_capture_provider
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run() -> list[Publicacao]:
    """Executa um ciclo completo do pipeline de monitoramento."""
    logger.info(
        "Iniciando pipeline | ambiente=%s | captura=%s | ia=%s",
        settings.app_env,
        settings.capture_provider,
        settings.ai_provider,
    )

    alvos = carregar_alvos()
    if not alvos:
        alvos = [AlvoMonitoramento(tipo=TipoMonitoramento.OAB, valor="123456", uf="SP")]
        logger.warning(
            "Nenhum alvo configurado (MONITOR_TERMS/MONITOR_OAB/MONITOR_PROCESSOS). "
            "Usando alvo de demonstração: %s",
            alvos[0].rotulo,
        )
    logger.info("Alvos monitorados (%d): %s", len(alvos), ", ".join(a.rotulo for a in alvos))

    # 1. CAPTURA -> busca publicações para os alvos monitorados
    provider = get_capture_provider()
    publicacoes = provider.buscar_varios(alvos)
    logger.info("Total de publicações capturadas: %d", len(publicacoes))
    for pub in publicacoes:
        preview = " ".join(pub.conteudo[:90].split())
        logger.info("  • [%s] %s | %s…", pub.termo_monitorado, pub.numero_processo or "s/ nº", preview)

    # 2. INTELIGÊNCIA  -> src/services/intelligence   (TODO: próximo módulo)
    # 3. AGENDA        -> src/services/agenda          (TODO)

    return publicacoes


if __name__ == "__main__":
    run()
