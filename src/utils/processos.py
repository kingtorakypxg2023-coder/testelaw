"""Utilidades para números de processo no padrão CNJ."""
from __future__ import annotations

import re

_SO_DIGITOS = re.compile(r"\D+")


def normalizar_numero_processo(valor: str) -> str:
    """Normaliza um número CNJ para a máscara ``NNNNNNN-DD.AAAA.J.TR.OOOO``.

    Aceita o número com pontos, hífens, espaços ou apenas dígitos. Quando não
    houver exatamente os 20 dígitos esperados, devolve o texto original
    (apenas sem espaços nas pontas), sem tentar reformatar.
    """
    dig = _SO_DIGITOS.sub("", valor or "")
    if len(dig) != 20:
        return (valor or "").strip()
    return f"{dig[0:7]}-{dig[7:9]}.{dig[9:13]}.{dig[13:14]}.{dig[14:16]}.{dig[16:20]}"
