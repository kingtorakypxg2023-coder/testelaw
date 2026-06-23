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
from src.models import AlvoMonitoramento, AnalisePublicacao, TipoMonitoramento
from src.services.agenda import AgendaError, get_agenda_provider, montar_eventos
from src.services.capture import carregar_alvos, get_capture_provider
from src.services.intelligence import IntelligenceError, get_intelligence_provider
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run() -> list[AnalisePublicacao]:
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

    # 2. INTELIGÊNCIA -> interpreta o texto e extrai prazos (data fatal calculada em código)
    try:
        ia = get_intelligence_provider()
    except IntelligenceError as exc:
        logger.warning(
            "Provedor de IA '%s' indisponível (%s). Usando provedor 'mock'.",
            settings.ai_provider,
            exc,
        )
        ia = get_intelligence_provider("mock")

    analises = ia.analisar_varias(publicacoes)
    total_prazos = sum(len(a.prazos) for a in analises)
    logger.info("Análises geradas: %d | prazos extraídos: %d", len(analises), total_prazos)
    for analise in analises:
        for prazo in analise.prazos:
            logger.info(
                "    ↳ [%s] %s | data fatal: %s | urgente=%s",
                prazo.tipo.value,
                prazo.descricao,
                prazo.data_fatal.isoformat() if prazo.data_fatal else "—",
                prazo.urgente,
            )

    # 3. AGENDA -> cria eventos/lembretes para os prazos com data fatal
    eventos = montar_eventos(analises, settings.deadline_reminder_days)
    if not eventos:
        logger.info("Nenhum prazo com data fatal para agendar.")
        return analises

    try:
        agenda = get_agenda_provider()
    except AgendaError as exc:
        logger.warning(
            "Provedor de agenda '%s' indisponível (%s). Usando provedor 'mock'.",
            settings.agenda_provider,
            exc,
        )
        agenda = get_agenda_provider("mock")

    refs = agenda.criar_eventos(eventos)
    criados = sum(1 for ref in refs if ref)
    logger.info("Eventos enviados à agenda: %d/%d", criados, len(eventos))

    return analises


if __name__ == "__main__":
    run()
