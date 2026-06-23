"""Utilitários para parsing e manipulação de datas."""
from __future__ import annotations

from datetime import date, datetime

from dateutil import parser as _dateparser


def parse_date(value: object) -> date | None:
    """Converte um valor heterogêneo (str/date/datetime) em `date`.

    Aceita formatos brasileiros (DD/MM/AAAA) e ISO (AAAA-MM-DD). Retorna
    `None` quando o valor é vazio ou não pôde ser interpretado.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        # dayfirst=True para priorizar o padrão brasileiro DD/MM/AAAA.
        return _dateparser.parse(str(value), dayfirst=True).date()
    except (ValueError, OverflowError, TypeError):
        return None
