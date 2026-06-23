"""CLI para adicionar um prazo manual à agenda.

Exemplos::

    # por prazo em dias (a data fatal é calculada em dias úteis a partir de hoje)
    python -m src.add_prazo --descricao "Protocolar manifestação" \\
        --tipo manifestacao --prazo-dias 5 --processo 1001234-56.2024.8.26.0100

    # por data fatal já conhecida
    python -m src.add_prazo --descricao "Audiência de instrução" \\
        --tipo audiencia --data-fatal 2026-08-01 --urgente
"""
from __future__ import annotations

import argparse

from pydantic import ValidationError

from src.models import PrazoManual, TipoPrazo
from src.services.manual import registrar_prazo_manual
from src.utils.dates import parse_date
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.add_prazo",
        description="Adiciona um prazo manual à agenda (cria evento + lembrete).",
    )
    parser.add_argument("--descricao", required=True, help="Descrição da ação/prazo")
    parser.add_argument(
        "--tipo",
        default="outro",
        choices=[t.value for t in TipoPrazo],
        help="Tipo do prazo (padrão: outro)",
    )
    parser.add_argument("--processo", default=None, help="Número do processo (opcional)")
    parser.add_argument(
        "--data-fatal", default=None, help="Data limite (AAAA-MM-DD ou DD/MM/AAAA)"
    )
    parser.add_argument(
        "--prazo-dias", type=int, default=None, help="Prazo em dias (calcula a data fatal)"
    )
    parser.add_argument(
        "--data-base", default=None, help="Início da contagem do prazo (padrão: hoje)"
    )
    parser.add_argument(
        "--dias-corridos",
        action="store_true",
        help="Contar em dias corridos (padrão: dias úteis)",
    )
    parser.add_argument("--urgente", action="store_true", help="Marca o prazo como urgente")
    parser.add_argument("--obs", default=None, help="Observações adicionais")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        prazo = PrazoManual(
            tipo=TipoPrazo(args.tipo),
            descricao=args.descricao,
            numero_processo=args.processo,
            data_fatal=parse_date(args.data_fatal),
            prazo_dias=args.prazo_dias,
            data_base=parse_date(args.data_base),
            dias_uteis=not args.dias_corridos,
            urgente=args.urgente,
            observacoes=args.obs,
        )
    except ValidationError as exc:
        parser.error(str(exc))

    evento = registrar_prazo_manual(prazo)
    logger.info(
        "Prazo manual registrado: '%s' | data fatal %s | lembrete %d dia(s) antes",
        evento.titulo,
        evento.data.isoformat(),
        evento.lembrete_dias_antes,
    )


if __name__ == "__main__":
    main()
