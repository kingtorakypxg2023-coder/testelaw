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
from datetime import date
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from pydantic import ValidationError

from src.config.settings import BASE_DIR, settings
from src.models import PrazoManual, PrazoManualRegistro, TipoPrazo
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
        self._nb.select(2)  # abre direto na aba Prazos
        logger.info("Interface iniciada. Captura=%s | OAB=%s", settings.capture_provider, settings.monitor_oab or "(nenhuma)")
        # Alimenta a lista automaticamente ao iniciar e, depois, periodicamente.
        self.after(800, self._auto_buscar)

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

        ttk.Label(frame, text="Cliente (autor do processo)").grid(
            row=1, column=0, sticky="w", padx=8, pady=6
        )
        self._np["cliente"] = tk.StringVar()
        ttk.Entry(frame, textvariable=self._np["cliente"], width=52).grid(
            row=1, column=1, columnspan=2, sticky="w", padx=8, pady=6
        )

        ttk.Label(frame, text="Parte contrária (réu)").grid(
            row=2, column=0, sticky="w", padx=8, pady=6
        )
        self._np["parte_contraria"] = tk.StringVar()
        ttk.Entry(frame, textvariable=self._np["parte_contraria"], width=52).grid(
            row=2, column=1, columnspan=2, sticky="w", padx=8, pady=6
        )

        ttk.Label(frame, text="Tipo").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        self._np["tipo"] = tk.StringVar(value="outro")
        ttk.Combobox(
            frame, textvariable=self._np["tipo"], values=[t.value for t in TipoPrazo],
            width=22, state="readonly",
        ).grid(row=3, column=1, sticky="w", padx=8, pady=6)

        ttk.Label(frame, text="Processo (opcional)").grid(row=4, column=0, sticky="w", padx=8, pady=6)
        self._np["processo"] = tk.StringVar()
        ttk.Entry(frame, textvariable=self._np["processo"], width=42).grid(
            row=4, column=1, sticky="w", padx=8, pady=6
        )

        self._np["modo"] = tk.StringVar(value="dias")
        ttk.Radiobutton(
            frame, text="Por prazo em dias", variable=self._np["modo"], value="dias"
        ).grid(row=5, column=0, sticky="w", padx=8, pady=6)
        self._np["prazo_dias"] = tk.StringVar(value="15")
        ttk.Entry(frame, textvariable=self._np["prazo_dias"], width=8).grid(
            row=5, column=1, sticky="w", padx=8, pady=6
        )

        ttk.Radiobutton(
            frame, text="Por data fatal (AAAA-MM-DD ou DD/MM/AAAA)",
            variable=self._np["modo"], value="data",
        ).grid(row=6, column=0, sticky="w", padx=8, pady=6)
        self._np["data_fatal"] = tk.StringVar()
        ttk.Entry(frame, textvariable=self._np["data_fatal"], width=16).grid(
            row=6, column=1, sticky="w", padx=8, pady=6
        )

        self._np["dias_corridos"] = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame, text="Contar em dias corridos (padrão: dias úteis - CPC)",
            variable=self._np["dias_corridos"],
        ).grid(row=7, column=0, columnspan=2, sticky="w", padx=8, pady=6)

        self._np["urgente"] = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Urgente", variable=self._np["urgente"]).grid(
            row=8, column=0, sticky="w", padx=8, pady=6
        )

        ttk.Label(frame, text="Observações").grid(row=9, column=0, sticky="w", padx=8, pady=6)
        self._np["obs"] = tk.StringVar()
        ttk.Entry(frame, textvariable=self._np["obs"], width=52).grid(
            row=9, column=1, columnspan=2, sticky="w", padx=8, pady=6
        )

        ttk.Button(frame, text="Adicionar prazo", command=self._adicionar_prazo).grid(
            row=10, column=1, sticky="w", padx=8, pady=14
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
                cliente=str(dados["cliente"].get()).strip() or None,
                parte_contraria=str(dados["parte_contraria"].get()).strip() or None,
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
        dados["cliente"].set("")
        dados["parte_contraria"].set("")
        dados["processo"].set("")
        dados["obs"].set("")
        self._atualizar_prazos()

    # ------------------------------------------------------------- Prazos
    def _aba_prazos(self) -> None:
        frame = ttk.Frame(self._nb)
        self._nb.add(frame, text="Prazos")

        # iid da linha -> registro (evita ler valores já convertidos da Treeview,
        # que estraga números de processo e zeros à esquerda).
        self._linhas: dict[str, PrazoManualRegistro] = {}
        self._linhas_partes: dict[str, str] = {}

        sub = ttk.Notebook(frame)
        sub.pack(fill="both", expand=True, padx=2, pady=4)

        # ---- sub-aba: lista de prazos ----
        aba_lista = ttk.Frame(sub)
        sub.add(aba_lista, text="Prazos")

        barra = ttk.Frame(aba_lista)
        barra.pack(fill="x", padx=6, pady=(8, 4))
        ttk.Button(
            barra, text="Buscar publicações agora", command=self._buscar
        ).pack(side="left")
        ttk.Button(barra, text="Atualizar", command=self._atualizar_prazos).pack(
            side="left", padx=6
        )
        ttk.Button(
            barra, text="Copiar nº do processo", command=self._copiar_processo
        ).pack(side="left")
        ttk.Button(barra, text="Remover selecionado", command=self._remover_prazo).pack(
            side="left", padx=6
        )

        colunas = (
            "data", "situacao", "origem", "tipo", "urgente",
            "cliente", "descricao", "processo",
        )
        self._tree = ttk.Treeview(aba_lista, columns=colunas, show="headings", height=15)
        for col, titulo, largura in [
            ("data", "Data fatal", 85),
            ("situacao", "Situação", 75),
            ("origem", "Origem", 70),
            ("tipo", "Tipo", 95),
            ("urgente", "Urg.", 45),
            ("cliente", "Cliente", 150),
            ("descricao", "Descrição", 260),
            ("processo", "Processo", 160),
        ]:
            self._tree.heading(col, text=titulo)
            self._tree.column(col, width=largura, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=6, pady=6)
        # copiar também com duplo-clique sobre a linha
        self._tree.bind("<Double-1>", lambda _e: self._copiar_processo())

        self._prazos_status = ttk.Label(aba_lista, text="", foreground="#666")
        self._prazos_status.pack(anchor="w", padx=8, pady=(0, 6))

        # ---- sub-aba: partes do processo ----
        aba_partes = ttk.Frame(sub)
        sub.add(aba_partes, text="Partes")

        barra_p = ttk.Frame(aba_partes)
        barra_p.pack(fill="x", padx=6, pady=(8, 4))
        ttk.Button(
            barra_p, text="Copiar nº do processo", command=self._copiar_processo_partes
        ).pack(side="left")

        colunas_p = ("processo", "cliente", "parte_contraria")
        self._partes_tree = ttk.Treeview(
            aba_partes, columns=colunas_p, show="headings", height=15
        )
        for col, titulo, largura in [
            ("processo", "Processo", 200),
            ("cliente", "Cliente (autor)", 240),
            ("parte_contraria", "Parte contrária (réu)", 240),
        ]:
            self._partes_tree.heading(col, text=titulo)
            self._partes_tree.column(col, width=largura, anchor="w")
        self._partes_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self._partes_tree.bind("<Double-1>", lambda _e: self._copiar_processo_partes())

        self._partes_status = ttk.Label(aba_partes, text="", foreground="#666")
        self._partes_status.pack(anchor="w", padx=8, pady=(0, 6))

    def _atualizar_prazos(self) -> None:
        if not hasattr(self, "_tree"):
            return
        for item in self._tree.get_children():
            self._tree.delete(item)
        for item in self._partes_tree.get_children():
            self._partes_tree.delete(item)
        self._linhas.clear()
        self._linhas_partes.clear()
        try:
            registros = listar_prazos_manuais()
        except Exception as exc:
            logger.warning("Falha ao listar prazos: %s", exc)
            registros = []
        hoje = date.today()
        # Agrega as partes por processo: cada processo aparece uma única vez.
        partes: dict[str, list[str]] = {}
        ordem_partes: list[str] = []
        for reg in registros:
            situacao = "Pendente" if reg.data_fatal >= hoje else "Vencido"
            origem = "Capturado" if reg.origem == "captura" else "Manual"
            iid = self._tree.insert(
                "", "end",
                values=(
                    reg.data_fatal.strftime("%d/%m/%Y"),
                    situacao,
                    origem,
                    reg.prazo.tipo.value,
                    "SIM" if reg.prazo.urgente else "",
                    reg.prazo.cliente or "",
                    reg.prazo.descricao,
                    reg.prazo.numero_processo or "",
                ),
            )
            self._linhas[iid] = reg

            processo = (reg.prazo.numero_processo or "").strip()
            chave = processo or f"(sem nº) {reg.prazo.cliente or reg.prazo.descricao}"
            if chave not in partes:
                partes[chave] = [
                    processo, reg.prazo.cliente or "", reg.prazo.parte_contraria or ""
                ]
                ordem_partes.append(chave)
            else:  # completa os campos que ainda estiverem vazios
                atual = partes[chave]
                atual[1] = atual[1] or (reg.prazo.cliente or "")
                atual[2] = atual[2] or (reg.prazo.parte_contraria or "")

        for chave in ordem_partes:
            processo, cliente, parte_contraria = partes[chave]
            iid = self._partes_tree.insert(
                "", "end", values=(processo, cliente, parte_contraria)
            )
            self._linhas_partes[iid] = processo

        if hasattr(self, "_prazos_status"):
            if not registros:
                self._prazos_status.config(
                    text="Nenhum prazo ainda. Clique em 'Buscar publicações agora' "
                    "(busca no diário pela sua OAB) ou cadastre em 'Novo Prazo'."
                )
            else:
                pendentes = sum(1 for r in registros if r.data_fatal >= hoje)
                self._prazos_status.config(
                    text=f"{len(registros)} prazo(s) na lista — {pendentes} pendente(s)."
                )
        if hasattr(self, "_partes_status"):
            self._partes_status.config(
                text=(
                    f"{len(ordem_partes)} processo(s)/parte(s)."
                    if ordem_partes
                    else "As partes aparecem aqui conforme os prazos forem "
                    "cadastrados ou capturados."
                )
            )

    def _remover_prazo(self) -> None:
        selecao = self._tree.selection()
        if not selecao:
            messagebox.showinfo("Remover", "Selecione um prazo na lista.")
            return
        reg = self._linhas.get(selecao[0])
        if reg is None:
            return
        if not messagebox.askyesno("Remover", "Remover o prazo selecionado?"):
            return
        try:
            ok = remover_prazo_manual(reg.id)
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))
            return
        if ok:
            logger.info("Prazo removido: %s", reg.id)
        self._atualizar_prazos()

    def _copiar_texto(self, texto: str) -> None:
        """Copia um texto para a área de transferência e confirma na barra de status."""
        self.clipboard_clear()
        self.clipboard_append(texto)
        self.update()  # garante que o conteúdo permaneça na área de transferência
        msg = f"Número do processo copiado: {texto}"
        for atributo in ("_prazos_status", "_partes_status"):
            rotulo = getattr(self, atributo, None)
            if rotulo is not None:
                rotulo.config(text=msg)

    def _copiar_processo(self) -> None:
        """Copia o nº do processo da linha selecionada (lê do registro, não da tabela)."""
        selecao = self._tree.selection()
        if not selecao:
            messagebox.showinfo("Copiar", "Selecione um prazo na lista.")
            return
        reg = self._linhas.get(selecao[0])
        processo = (reg.prazo.numero_processo or "").strip() if reg else ""
        if not processo:
            messagebox.showinfo("Copiar", "Este prazo não tem número de processo.")
            return
        self._copiar_texto(processo)

    def _copiar_processo_partes(self) -> None:
        """Copia o nº do processo da linha selecionada na sub-aba Partes."""
        selecao = self._partes_tree.selection()
        if not selecao:
            messagebox.showinfo("Copiar", "Selecione uma linha na lista de partes.")
            return
        processo = (self._linhas_partes.get(selecao[0]) or "").strip()
        if not processo:
            messagebox.showinfo("Copiar", "Esta linha não tem número de processo.")
            return
        self._copiar_texto(processo)

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
            "O andamento e o resultado aparecem na aba 'Registro'.",
            foreground="#666",
            justify="left",
        ).pack(anchor="w", padx=10)
        self._btn_buscar = ttk.Button(
            frame, text="Buscar publicações agora", command=self._buscar
        )
        self._btn_buscar.pack(anchor="w", padx=10, pady=14)
        self._status = ttk.Label(frame, text="")
        self._status.pack(anchor="w", padx=10)

    def _buscar(self, auto: bool = False) -> None:
        if getattr(self, "_buscando", False):
            return
        self._buscando = True
        self._busca_auto = auto
        self._btn_buscar.config(state="disabled")
        self._status.config(text="Buscando... aguarde.")
        if hasattr(self, "_prazos_status"):
            self._prazos_status.config(text="Buscando publicações no diário...")
        if not auto:
            self._nb.select(4)  # aba Registro (acompanhar o andamento)
        threading.Thread(target=self._buscar_worker, daemon=True).start()

    def _auto_buscar(self) -> None:
        """Busca automática: alimenta a lista ao iniciar e a cada intervalo."""
        self._buscar(auto=True)
        intervalo_ms = max(60, settings.schedule_interval_seconds) * 1000
        self.after(intervalo_ms, self._auto_buscar)

    def _buscar_worker(self) -> None:
        try:
            from src.main import run

            analises = run()
            total = sum(len(a.prazos) for a in analises)
            self._eventos_fila.put(("buscar_ok", total))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha ao buscar publicações")
            self._eventos_fila.put(("buscar_erro", str(exc)))

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
                    auto = getattr(self, "_busca_auto", False)
                    self._buscando = False
                    self._btn_buscar.config(state="normal")
                    self._status.config(text=f"Concluído. Prazos extraídos: {dado}.")
                    self._atualizar_prazos()
                    if not auto:
                        self._nb.select(2)  # vai direto para a aba Prazos
                elif tipo == "buscar_erro":
                    auto = getattr(self, "_busca_auto", False)
                    self._buscando = False
                    self._btn_buscar.config(state="normal")
                    self._status.config(text="Erro na busca (veja a aba Registro).")
                    if not auto:  # em busca automática, não interrompe com pop-up
                        messagebox.showerror("Erro na busca", str(dado))
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
