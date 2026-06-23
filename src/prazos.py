"""CLI de gestão de prazos manuais: adicionar, listar e remover.

Exemplos::

    python -m src.prazos add --descricao "Protocolar manifestação" \\
        --tipo manifestacao --prazo-dias 5 --processo 1001234-56.2024.8.26.0100
    python -m src.prazos list
    python -m src.prazos remove --id a1b2c3d4e5f6
"""
from __future__ import annotations

import argparse

from pydantic import ValidationError

from src.models import PrazoManual, TipoPrazo
from src.services.manual import (
    adicionar_prazo_manual,
    listar_prazos_manuais,
    remover_prazo_manual,
)
from src.utils.dates import parse_date
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _add_argumentos_prazo(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--descricao", required=True, help="Descrição da ação/prazo")
    parser.add_argument(
        "--tipo", default="outro", choices=[t.value for t in TipoPrazo], help="Tipo do prazo"
    )
    parser.add_argument("--processo", default=None, help="Número do processo (opcional)")
    parser.add_argument("--data-fatal", default=None, help="Data limite (AAAA-MM-DD ou DD/MM/AAAA)")
    parser.add_argument("--prazo-dias", type=int, default=None, help="Prazo em dias")
    parser.add_argument("--data-base", default=None, help="Início da contagem (padrão: hoje)")
    parser.add_argument("--dias-corridos", action="store_true", help="Contar em dias corridos")
    parser.add_argument("--urgente", action="store_true", help="Marca como urgente")
    parser.add_argument("--obs", default=None, help="Observações adicionais")


def _cmd_add(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
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

    registro = adicionar_prazo_manual(prazo)
    logger.info(
        "Prazo manual adicionado: id=%s | %s | data fatal %s",
        registro.id,
        registro.prazo.descricao,
        registro.data_fatal.isoformat(),
    )


def _cmd_list() -> None:
    registros = listar_prazos_manuais()
    if not registros:
        logger.info("Nenhum prazo manual cadastrado.")
        return
    logger.info("Prazos manuais (%d):", len(registros))
    for reg in registros:
        marca = "⚠️ " if reg.prazo.urgente else "  "
        logger.info(
            "%s%s | %s | %-12s | %s%s",
            marca,
            reg.id,
            reg.data_fatal.isoformat(),
            reg.prazo.tipo.value,
            reg.prazo.descricao,
            f" (proc. {reg.prazo.numero_processo})" if reg.prazo.numero_processo else "",
        )


def _cmd_remove(args: argparse.Namespace) -> None:
    if remover_prazo_manual(args.id):
        logger.info("Prazo manual removido: id=%s", args.id)
    else:
        logger.warning("Prazo manual não encontrado: id=%s", args.id)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.prazos",
        description="Gerencia prazos manuais (adicionar, listar, remover).",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_add = sub.add_parser("add", help="Adiciona um prazo manual")
    _add_argumentos_prazo(p_add)

    sub.add_parser("list", help="Lista os prazos manuais cadastrados")

    p_rem = sub.add_parser("remove", help="Remove um prazo manual pelo id")
    p_rem.add_argument("--id", required=True, help="ID do prazo (veja 'list')")

    args = parser.parse_args(argv)
    if args.comando == "add":
        _cmd_add(args, parser)
    elif args.comando == "list":
        _cmd_list()
    elif args.comando == "remove":
        _cmd_remove(args)


if __name__ == "__main__":
    main()
