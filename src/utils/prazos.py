"""Cálculo de prazos jurídicos (datas fatais).

Por padrão, os prazos processuais são contados em **dias úteis** (art. 219 do
CPC): exclui-se o dia do começo e contam-se apenas os dias úteis seguintes,
pulando sábados, domingos e feriados informados.

Observação: feriados nacionais/estaduais e o recesso forense (art. 220 do CPC)
dependem da jurisdição e devem ser injetados via `feriados`. Em produção,
recomenda-se alimentar esse conjunto a partir de uma fonte oficial/calendário
(ex.: biblioteca de feriados ou calendário do tribunal).
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta


def adicionar_dias_uteis(
    data_base: date, dias: int, feriados: Iterable[date] = ()
) -> date:
    """Soma `dias` dias úteis a `data_base`, excluindo o dia inicial.

    Pula sábados, domingos e os feriados informados.
    """
    conjunto_feriados = set(feriados)
    atual = data_base
    restantes = dias
    while restantes > 0:
        atual += timedelta(days=1)
        if atual.weekday() < 5 and atual not in conjunto_feriados:
            restantes -= 1
    return atual


def calcular_data_fatal(
    data_base: date | None,
    prazo_dias: int | None,
    *,
    dias_uteis: bool = True,
    feriados: Iterable[date] = (),
) -> date | None:
    """Calcula a data fatal a partir de uma data base e um prazo em dias.

    Retorna `None` quando faltar a data base ou o prazo. Com `dias_uteis=False`,
    soma dias corridos.
    """
    if data_base is None or prazo_dias is None:
        return None
    if prazo_dias <= 0:
        return data_base
    if dias_uteis:
        return adicionar_dias_uteis(data_base, prazo_dias, feriados)
    return data_base + timedelta(days=prazo_dias)
