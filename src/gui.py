"""Interface gráfica (GUI) com abas — Monitor de Diários & Prazos Jurídicos.

Janela única, sem terminal. Abas: Configurações, Novo Prazo, Prazos,
Monitoramento e Registro. Reaproveita todo o backend (captura, IA, agenda,
prazos manuais). Empacotável como executável de janela (PyInstaller windowed).
"""
from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from pydantic import ValidationError

from src.config.settings import BASE_DIR, settings
from src.models import PrazoManual, TipoPrazo
from src.services.manual import (
    adicionar_prazo_manual,
    listar_prazos_manuais,
    remover_prazo_manual,
)
from src.utils.dates import parse_date
from src.utils.logger import LOG_FORMAT, get_logger

logger = get_logger("gui")


class _QueueLogHandler(logging.Handler):
    """Handler de logging que envia as linhas para uma fila (thread-safe)."""

    def __init__(self, fila: "queue.Queue[str]") -> None:
        super().__init__()
        self.fila = fila
        self.setFormatter(logging.Formatter(LOG_FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.fila.put_nowait(self.format(record))
        except Exception:  # nunca deixar o logging quebrar a GUI
            pass


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Monitor de Diários & Prazos Jurídicos")
        self.geometry("920x620")
        self.minsize(760, 520)

        self._log_fila: "queue.Queue[str]" = queue.Queue()
        self._eventos_fila: "queue.Queue[tuple[str, object]]" = queue.Queue()

        # Controle da busca automática (alimenta a aba Prazos sem clique manual).
        self._busca_em_andamento = False
        self._auto_after_id: str | None = None

        logging.getLogger().addHandler(_QueueLogHandler(self._log_fila))

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self._nb = nb
        self._aba_config()
        self._aba_novo_prazo()
        self._aba_prazos()
        self._aba_monitoramento()
        self._aba_log()

        self._atualizar_prazos()
        self.after(150, self._drenar_filas)
        # Primeira busca automática logo após a janela renderizar (ver _busca_inicial).
        self.after(1500, self._busca_inicial)
        logger.info("Interface iniciada. Captura=%s | OAB=%s", settings.capture_provider, settings.monitor_oab or "(nenhuma)")

    # ------------------------------------------------------------- Config
    def _aba_config(self) -> None:
        frame = ttk.Frame(self._nb)
        self._nb.add(frame, text="Configurações")
        self._cfg: dict[str, tk.StringVar] = {}
        campos = [
            ("OAB (ex.: 226608/RJ)", "MONITOR_OAB", settings.monitor_oab or "", "entry"),
            ("Processos (separados por vírgula)", "MONITOR_PROCESSOS", settings.monitor_processos or "", "entry"),
            ("Captura", "CAPTURE_PROVIDER", settings.capture_provider, ("comunica", "mock", "jusbrasil")),
            ("Inteligência (IA)", "AI_PROVIDER", settings.ai_provider, ("mock", "claude", "gemini", "openai")),
            ("Chave da IA (se usar Claude)", "ANTHROPIC_API_KEY", settings.anthropic_api_key or "", "senha"),
            ("Agenda", "AGENDA_PROVIDER", settings.agenda_provider, ("mock", "google")),
            ("Notificação", "NOTIFIER", settings.notifier, ("mock", "webhook", "telegram", "email")),
            ("Lembrete (dias antes)", "DEADLINE_REMINDER_DAYS", str(settings.deadline_reminder_days), "entry"),
        ]
        for i, (rotulo, chave, valor, tipo) in enumerate(campos):
            ttk.Label(frame, text=rotulo).grid(row=i, column=0, sticky="w", padx=8, pady=6)
            var = tk.StringVar(value=valor)
            if tipo in ("entry", "senha"):
                ent = ttk.Entry(frame, textvariable=var, width=42)
                if tipo == "senha":
                    ent.config(show="*")
                ent.grid(row=i, column=1, sticky="w", padx=8, pady=6)
            else:
                ttk.Combobox(
                    frame, textvariable=var, values=list(tipo), width=22, state="readonly"
                ).grid(row=i, column=1, sticky="w", padx=8, pady=6)
            self._cfg[chave] = var
        ttk.Button(frame, text="Salvar configurações", command=self._salvar_config).grid(
            row=len(campos), column=1, sticky="w", padx=8, pady=14
        )
        ttk.Label(
            frame,
            text="Após salvar, feche e abra o programa novamente para aplicar.",
            foreground="#777",
        ).grid(row=len(campos) + 1, column=0, columnspan=2, sticky="w", padx=8)

    def _salvar_config(self) -> None:
        conteudo = {
            "APP_ENV": "production",
            "LOG_LEVEL": "INFO",
            "COMUNICA_API_BASE_URL": settings.comunica_api_base_url,
            "COMUNICA_SEARCH_PATH": settings.comunica_search_path,
            "NOTIFY_ONLY_URGENT": "true",
            "STATE_STORE": "sqlite",
            "STATE_DB_PATH": "data/monitor.db",
            "SCHEDULE_INTERVAL_SECONDS": "3600",
        }
        for chave, var in self._cfg.items():
            conteudo[chave] = var.get().strip()
        linhas = [f"{chave}={valor}" for chave, valor in conteudo.items()]
        caminho = BASE_DIR / ".env"
        try:
            caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Erro ao salvar", f"Não foi possível gravar o .env: {exc}")
            return
        logger.info("Configurações salvas em %s", caminho)
        messagebox.showinfo(
            "Salvo",
            "Configurações salvas!\n\nFeche e abra o programa novamente para aplicar.",
        )

    # --------------------------------------------------------- Novo prazo
    def _aba_novo_prazo(self) -> None:
        frame = ttk.Frame(self._nb)
        self._nb.add(frame, text="Novo Prazo")
        self._np: dict[str, tk.Variable] = {}

        ttk.Label(frame, text="Descrição").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self._np["descricao"] = tk.StringVar()
        ttk.Entry(frame, textvariable=self._np["descricao"], width=52).grid(
            row=0, column=1, columnspan=2, sticky="w", padx=8, pady=6
        )

        ttk.Label(frame, text="Tipo").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        self._np["tipo"] = tk.StringVar(value="outro")
        ttk.Combobox(
            frame, textvariable=self._np["tipo"], values=[t.value for t in TipoPrazo],
            width=22, state="readonly",
        ).grid(row=1, column=1, sticky="w", padx=8, pady=6)

        ttk.Label(frame, text="Processo (opcional)").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        self._np["processo"] = tk.StringVar()
        ttk.Entry(frame, textvariable=self._np["processo"], width=42).grid(
            row=2, column=1, sticky="w", padx=8, pady=6
        )

        self._np["modo"] = tk.StringVar(value="dias")
        ttk.Radiobutton(
            frame, text="Por prazo em dias", variable=self._np["modo"], value="dias"
        ).grid(row=3, column=0, sticky="w", padx=8, pady=6)
        self._np["prazo_dias"] = tk.StringVar(value="15")
        ttk.Entry(frame, textvariable=self._np["prazo_dias"], width=8).grid(
            row=3, column=1, sticky="w", padx=8, pady=6
        )

        ttk.Radiobutton(
            frame, text="Por data fatal (AAAA-MM-DD ou DD/MM/AAAA)",
            variable=self._np["modo"], value="data",
        ).grid(row=4, column=0, sticky="w", padx=8, pady=6)
        self._np["data_fatal"] = tk.StringVar()
        ttk.Entry(frame, textvariable=self._np["data_fatal"], width=16).grid(
            row=4, column=1, sticky="w", padx=8, pady=6
        )

        self._np["dias_corridos"] = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame, text="Contar em dias corridos (padrão: dias úteis - CPC)",
            variable=self._np["dias_corridos"],
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=8, pady=6)

        self._np["urgente"] = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Urgente", variable=self._np["urgente"]).grid(
            row=6, column=0, sticky="w", padx=8, pady=6
        )

        ttk.Label(frame, text="Observações").grid(row=7, column=0, sticky="w", padx=8, pady=6)
        self._np["obs"] = tk.StringVar()
        ttk.Entry(frame, textvariable=self._np["obs"], width=52).grid(
            row=7, column=1, columnspan=2, sticky="w", padx=8, pady=6
        )

        ttk.Button(frame, text="Adicionar prazo", command=self._adicionar_prazo).grid(
            row=8, column=1, sticky="w", padx=8, pady=14
        )

    def _adicionar_prazo(self) -> None:
        dados = self._np
        modo = dados["modo"].get()
        try:
            prazo_dias = None
            if modo == "dias" and str(dados["prazo_dias"].get()).strip():
                prazo_dias = int(dados["prazo_dias"].get())
            data_fatal = parse_date(dados["data_fatal"].get()) if modo == "data" else None
            prazo = PrazoManual(
                tipo=TipoPrazo(dados["tipo"].get()),
                descricao=str(dados["descricao"].get()).strip(),
                numero_processo=str(dados["processo"].get()).strip() or None,
                data_fatal=data_fatal,
                prazo_dias=prazo_dias,
                dias_uteis=not bool(dados["dias_corridos"].get()),
                urgente=bool(dados["urgente"].get()),
                observacoes=str(dados["obs"].get()).strip() or None,
            )
        except (ValidationError, ValueError) as exc:
            messagebox.showerror("Dados inválidos", str(exc))
            return

        try:
            registro = adicionar_prazo_manual(prazo)
        except Exception as exc:
            messagebox.showerror("Erro", f"Não foi possível adicionar o prazo: {exc}")
            return

        messagebox.showinfo(
            "Prazo adicionado",
            f"Prazo criado.\nData fatal: {registro.data_fatal.strftime('%d/%m/%Y')}",
        )
        dados["descricao"].set("")
        dados["processo"].set("")
        dados["obs"].set("")
        self._atualizar_prazos()

    # ------------------------------------------------------------- Prazos
    def _aba_prazos(self) -> None:
        frame = ttk.Frame(self._nb)
        self._nb.add(frame, text="Prazos")
        colunas = ("data", "situacao", "origem", "tipo", "urgente", "descricao", "processo", "id")
        self._tree = ttk.Treeview(frame, columns=colunas, show="headings", height=15)
        for col, titulo, largura in [
            ("data", "Data fatal", 85),
            ("situacao", "Situação", 75),
            ("origem", "Origem", 70),
            ("tipo", "Tipo", 95),
            ("urgente", "Urg.", 45),
            ("descricao", "Descrição", 300),
            ("processo", "Processo", 150),
            ("id", "ID", 90),
        ]:
            self._tree.heading(col, text=titulo)
            self._tree.column(col, width=largura, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=6, pady=6)

        barra = ttk.Frame(frame)
        barra.pack(fill="x", padx=6, pady=4)
        ttk.Label(
            barra, text="Pendentes (capturados + manuais), ordenados por data fatal.",
            foreground="#666",
        ).pack(side="left")
        ttk.Button(barra, text="Remover selecionado", command=self._remover_prazo).pack(
            side="right"
        )
        ttk.Button(barra, text="Atualizar", command=self._atualizar_prazos).pack(side="right", padx=6)

    def _atualizar_prazos(self) -> None:
        if not hasattr(self, "_tree"):
            return
        for item in self._tree.get_children():
            self._tree.delete(item)
        try:
            registros = listar_prazos_manuais()
        except Exception as exc:
            logger.warning("Falha ao listar prazos: %s", exc)
            registros = []
        hoje = date.today()
        for reg in registros:
            situacao = "Pendente" if reg.data_fatal >= hoje else "Vencido"
            origem = "Capturado" if reg.origem == "captura" else "Manual"
            self._tree.insert(
                "", "end",
                values=(
                    reg.data_fatal.strftime("%d/%m/%Y"),
                    situacao,
                    origem,
                    reg.prazo.tipo.value,
                    "SIM" if reg.prazo.urgente else "",
                    reg.prazo.descricao,
                    reg.prazo.numero_processo or "",
                    reg.id,
                ),
            )

    def _remover_prazo(self) -> None:
        selecao = self._tree.selection()
        if not selecao:
            messagebox.showinfo("Remover", "Selecione um prazo na lista.")
            return
        valores = self._tree.item(selecao[0]).get("values") or []
        if len(valores) < 8:
            return
        id_ = str(valores[7])
        if not messagebox.askyesno("Remover", "Remover o prazo selecionado?"):
            return
        try:
            ok = remover_prazo_manual(id_)
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))
            return
        if ok:
            logger.info("Prazo removido: %s", id_)
        self._atualizar_prazos()

    # ----------------------------------------------------- Monitoramento
    def _aba_monitoramento(self) -> None:
        frame = ttk.Frame(self._nb)
        self._nb.add(frame, text="Monitoramento")
        resumo = (
            f"Captura: {settings.capture_provider}    |    "
            f"OAB: {settings.monitor_oab or '(nenhuma)'}    |    "
            f"IA: {settings.ai_provider}"
        )
        ttk.Label(frame, text=resumo, font=("", 10, "bold")).pack(anchor="w", padx=10, pady=10)
        ttk.Label(
            frame,
            text="Busca publicações no diário oficial e extrai os prazos.\n"
            "Os prazos encontrados alimentam a aba 'Prazos' automaticamente.\n"
            "O andamento e o resultado aparecem na aba 'Registro'.",
            foreground="#666",
            justify="left",
        ).pack(anchor="w", padx=10)

        minutos = max(1, settings.schedule_interval_seconds // 60)
        self._auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame,
            text=f"Atualização automática (ao abrir e a cada {minutos} min)",
            variable=self._auto_var,
            command=self._alternar_auto,
        ).pack(anchor="w", padx=10, pady=(12, 4))

        self._btn_buscar = ttk.Button(
            frame, text="Buscar publicações agora", command=self._buscar
        )
        self._btn_buscar.pack(anchor="w", padx=10, pady=10)
        self._status = ttk.Label(frame, text="")
        self._status.pack(anchor="w", padx=10)

    def _buscar(self) -> None:
        """Clique manual em 'Buscar publicações agora'."""
        self._iniciar_busca(auto=False)

    def _iniciar_busca(self, *, auto: bool) -> None:
        """Dispara o pipeline em background, evitando execuções sobrepostas."""
        if self._busca_em_andamento:
            if not auto:
                self._status.config(text="Já existe uma busca em andamento...")
            return
        self._busca_em_andamento = True
        self._btn_buscar.config(state="disabled")
        if auto:
            self._status.config(text="Atualização automática: buscando...")
        else:
            self._status.config(text="Buscando... aguarde.")
            self._nb.select(4)  # aba Registro
        threading.Thread(target=self._buscar_worker, args=(auto,), daemon=True).start()

    def _buscar_worker(self, auto: bool) -> None:
        try:
            from src.main import run

            analises = run()
            total = sum(len(a.prazos) for a in analises)
            self._eventos_fila.put(("buscar_ok", (total, auto)))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha ao buscar publicações")
            self._eventos_fila.put(("buscar_erro", (str(exc), auto)))

    # --------------------------------------------------- Busca automática
    def _busca_inicial(self) -> None:
        """Primeira busca ao abrir o programa e início do ciclo periódico."""
        if self._auto_var.get():
            self._iniciar_busca(auto=True)
        self._agendar_auto_busca()

    def _tick_auto_busca(self) -> None:
        """Disparo periódico: busca (se ligada) e reagenda o próximo ciclo."""
        self._auto_after_id = None
        if self._auto_var.get():
            self._iniciar_busca(auto=True)
        self._agendar_auto_busca()

    def _agendar_auto_busca(self) -> None:
        """(Re)agenda a próxima busca automática conforme o intervalo configurado."""
        if self._auto_after_id is not None:
            try:
                self.after_cancel(self._auto_after_id)
            except Exception:  # noqa: BLE001
                pass
            self._auto_after_id = None
        if not self._auto_var.get():
            return
        intervalo_ms = max(60, settings.schedule_interval_seconds) * 1000
        self._auto_after_id = self.after(intervalo_ms, self._tick_auto_busca)

    def _alternar_auto(self) -> None:
        """Liga/desliga a busca automática pela interface."""
        if self._auto_var.get():
            logger.info(
                "Atualização automática ligada (a cada %ds).",
                settings.schedule_interval_seconds,
            )
            self._iniciar_busca(auto=True)
        else:
            logger.info("Atualização automática desligada.")
        self._agendar_auto_busca()

    # ---------------------------------------------------------- Registro
    def _aba_log(self) -> None:
        frame = ttk.Frame(self._nb)
        self._nb.add(frame, text="Registro")
        self._log = ScrolledText(frame, height=20, state="disabled", wrap="word")
        self._log.pack(fill="both", expand=True, padx=6, pady=6)

    def _drenar_filas(self) -> None:
        linhas: list[str] = []
        try:
            while True:
                linhas.append(self._log_fila.get_nowait())
        except queue.Empty:
            pass
        if linhas:
            self._log.config(state="normal")
            for linha in linhas:
                self._log.insert("end", linha + "\n")
            self._log.see("end")
            self._log.config(state="disabled")

        try:
            while True:
                tipo, dado = self._eventos_fila.get_nowait()
                if tipo == "buscar_ok":
                    total, auto = dado
                    self._busca_em_andamento = False
                    self._btn_buscar.config(state="normal")
                    self._atualizar_prazos()  # alimenta a aba Prazos
                    if auto:
                        hora = datetime.now().strftime("%H:%M")
                        self._status.config(
                            text=f"Atualizado automaticamente às {hora}. "
                            f"Prazos extraídos: {total}."
                        )
                    else:
                        self._status.config(text=f"Concluído. Prazos extraídos: {total}.")
                        self._nb.select(2)  # vai direto para a aba Prazos
                elif tipo == "buscar_erro":
                    msg, auto = dado
                    self._busca_em_andamento = False
                    self._btn_buscar.config(state="normal")
                    if auto:
                        self._status.config(
                            text="Falha na atualização automática (veja a aba Registro)."
                        )
                    else:
                        self._status.config(text="Erro na busca (veja a aba Registro).")
                        messagebox.showerror("Erro na busca", str(msg))
        except queue.Empty:
            pass

        self.after(150, self._drenar_filas)


def main() -> None:
    try:
        App().mainloop()
    except Exception:  # registra crash para diagnóstico (app de janela não tem console)
        import traceback

        try:
            (BASE_DIR / "erro_monitor.log").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
