"""Conversão de análises/prazos (Etapa 2) em eventos de agenda (Etapa 3)."""
from __future__ import annotations

from src.models import AnalisePublicacao, EventoAgenda, Prazo


def _titulo(prazo: Prazo, numero_processo: str | None) -> str:
    prefixo = "[URGENTE] " if prazo.urgente else ""
    processo = numero_processo or "sem processo"
    return f"{prefixo}{prazo.tipo.value.capitalize()} — Processo {processo}"


def _descricao(analise: AnalisePublicacao, prazo: Prazo) -> str:
    linhas = [prazo.descricao]
    if prazo.prazo_dias is not None:
        linhas.append(f"Prazo: {prazo.prazo_dias} dias úteis.")
    if prazo.data_fatal is not None:
        linhas.append(f"Data fatal: {prazo.data_fatal.strftime('%d/%m/%Y')}.")
    if analise.resumo:
        linhas.append("")
        linhas.append(f"Resumo: {analise.resumo}")
    if prazo.observacoes:
        linhas.append(f"Obs.: {prazo.observacoes}")
    return "\n".join(linhas)


def montar_eventos(
    analises: list[AnalisePublicacao], lembrete_dias: int
) -> list[EventoAgenda]:
    """Gera um `EventoAgenda` por prazo que possua data fatal."""
    eventos: list[EventoAgenda] = []
    for analise in analises:
        for prazo in analise.prazos:
            if prazo.data_fatal is None:
                continue
            chave = f"{analise.id_externo}:{prazo.tipo.value}:{prazo.data_fatal.isoformat()}"
            eventos.append(
                EventoAgenda(
                    titulo=_titulo(prazo, analise.numero_processo),
                    descricao=_descricao(analise, prazo),
                    data=prazo.data_fatal,
                    lembrete_dias_antes=lembrete_dias,
                    chave_idempotencia=chave,
                    urgente=prazo.urgente,
                )
            )
    return eventos
