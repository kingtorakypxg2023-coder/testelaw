"""Scheduler: executa o pipeline de monitoramento periodicamente.

Uso::

    python -m src.scheduler                 # usa SCHEDULE_INTERVAL_SECONDS
    python -m src.scheduler --intervalo 1800
    python -m src.scheduler --ciclos 1      # roda uma vez e sai

Encerra de forma limpa ao receber SIGINT/SIGTERM (após o ciclo atual).
Para produção, também é possível agendar `python -m src.main` via cron.
"""
from __future__ import annotations

import argparse
import signal
import time

from src.config.settings import settings
from src.main import run
from src.utils.logger import get_logger

logger = get_logger(__name__)

_parar = False


def _solicitar_parada(signum, _frame) -> None:
    global _parar
    _parar = True
    logger.info("Sinal %s recebido; encerrando após o ciclo atual.", signum)


def executar_ciclo() -> list:
    """Executa um ciclo do pipeline, isolando exceções para não derrubar o loop."""
    try:
        return run()
    except Exception:  # noqa: BLE001 - um ciclo não deve derrubar o scheduler
        logger.exception("Falha no ciclo do pipeline; seguirá no próximo ciclo.")
        return []


def _dormir(intervalo: int) -> None:
    """Aguarda `intervalo` segundos, reagindo a pedidos de parada."""
    restante = intervalo
    while restante > 0 and not _parar:
        time.sleep(min(1, restante))
        restante -= 1


def run_forever(intervalo: int | None = None, max_ciclos: int | None = None) -> int:
    """Executa o pipeline em ciclos. Retorna o número de ciclos executados."""
    global _parar
    _parar = False
    intervalo = settings.schedule_interval_seconds if intervalo is None else intervalo

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _solicitar_parada)
        except ValueError:  # pragma: no cover - fora da thread principal
            pass

    logger.info(
        "Scheduler iniciado | intervalo=%ds | max_ciclos=%s",
        intervalo,
        max_ciclos if max_ciclos is not None else "∞",
    )
    ciclos = 0
    while not _parar:
        executar_ciclo()
        ciclos += 1
        if max_ciclos is not None and ciclos >= max_ciclos:
            break
        _dormir(intervalo)

    logger.info("Scheduler encerrado após %d ciclo(s).", ciclos)
    return ciclos


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.scheduler",
        description="Executa o pipeline de monitoramento periodicamente.",
    )
    parser.add_argument(
        "--intervalo", type=int, default=None, help="Intervalo entre ciclos (segundos)"
    )
    parser.add_argument(
        "--ciclos", type=int, default=None, help="Número máximo de ciclos (padrão: infinito)"
    )
    args = parser.parse_args(argv)
    run_forever(intervalo=args.intervalo, max_ciclos=args.ciclos)


if __name__ == "__main__":
    main()
