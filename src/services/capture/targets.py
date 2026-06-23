"""Carregamento dos alvos de monitoramento a partir das configurações.

Lê as variáveis `MONITOR_TERMS`, `MONITOR_OAB` e `MONITOR_PROCESSOS` e as
converte em uma lista de `AlvoMonitoramento` pronta para a captura.
"""
from __future__ import annotations

from src.config.settings import Settings, settings
from src.models import AlvoMonitoramento, TipoMonitoramento


def _parse_oab(valor: str) -> AlvoMonitoramento:
    """Interpreta uma inscrição de OAB no formato 'NUMERO/UF'."""
    numero, _, uf = valor.partition("/")
    return AlvoMonitoramento(
        tipo=TipoMonitoramento.OAB,
        valor=numero.strip(),
        uf=(uf.strip().upper() or None),
    )


def carregar_alvos(config: Settings | None = None) -> list[AlvoMonitoramento]:
    """Constrói a lista de alvos de monitoramento a partir das configurações."""
    cfg = config or settings
    alvos: list[AlvoMonitoramento] = []

    alvos.extend(
        AlvoMonitoramento(tipo=TipoMonitoramento.TERMO, valor=termo)
        for termo in cfg.monitor_terms_list
    )
    alvos.extend(_parse_oab(oab) for oab in cfg.monitor_oab_list)
    alvos.extend(
        AlvoMonitoramento(tipo=TipoMonitoramento.PROCESSO, valor=proc)
        for proc in cfg.monitor_processos_list
    )
    return alvos
