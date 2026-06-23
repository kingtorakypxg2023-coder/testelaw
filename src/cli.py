"""CLI unificada do Monitor de Diários Oficiais (ponto único do executável).

Comandos:
    gui            Abre a interface gráfica (janela com abas)
    run            Executa um ciclo do pipeline (captura -> IA -> agenda -> alertas)
    scheduler      Executa o pipeline periodicamente (--intervalo, --ciclos)
    prazo          Gerencia prazos manuais (add | list | remove)
    healthcheck    Verifica a prontidão dos provedores (credenciais/config)
"""
from __future__ import annotations

import sys

_USO = """Monitor de Diários Oficiais & Prazos Jurídicos

Uso: monitor-diarios <comando> [opções]

Comandos:
  gui                        Abre a interface gráfica (janela com abas)
  run                        Executa um ciclo do pipeline
  scheduler                  Executa o pipeline periodicamente (--intervalo, --ciclos)
  prazo <add|list|remove>    Gerencia prazos manuais
  healthcheck                Verifica a prontidão dos provedores

Exemplos:
  monitor-diarios gui
  monitor-diarios healthcheck
  monitor-diarios run
  monitor-diarios scheduler --intervalo 3600
  monitor-diarios prazo add --descricao "Protocolar petição" --prazo-dias 5
  monitor-diarios prazo list
"""


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(_USO)
        return

    comando, resto = argv[0], argv[1:]

    if comando == "gui":
        from src.gui import main as gui_main

        gui_main()
    elif comando == "run":
        from src.main import run

        run()
    elif comando == "scheduler":
        from src.scheduler import main as scheduler_main

        scheduler_main(resto)
    elif comando in ("prazo", "prazos"):
        from src.prazos import main as prazos_main

        prazos_main(resto)
    elif comando == "healthcheck":
        from src.healthcheck import main as healthcheck_main

        healthcheck_main()
    else:
        print(f"Comando desconhecido: {comando!r}\n")
        print(_USO)
        sys.exit(2)


if __name__ == "__main__":
    main()
