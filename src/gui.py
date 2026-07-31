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
from src.utils.processos import normalizar_numero_processo

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
        self._aba_consulta()
        self._aba_monitoramento()
        self._aba_log()

        self._atualizar_prazos()
        self.after(150, self._drenar_filas)
        self._nb.select(self._tab_prazos)  # abre direto na aba Prazos
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
        self._tab_prazos = frame

        # iid da linha -> registro (evita ler valores já convertidos da Treeview,
        # que estraga números de processo e zeros à esquerda).
        self._linhas: dict[str, PrazoManualRegistro] = {}

        # Aviso quando a captura está em modo de demonstração (dados fictícios).
        if settings.capture_provider.strip().lower() in ("mock", "fake", "stub"):
            ttk.Label(
                frame,
                text=(
                    "⚠ MODO DEMONSTRAÇÃO: os processos abaixo são fictícios "
                    "(exemplos). Vá em Configurações, selecione Captura = "
                    "'comunica' (DJEN) e informe a sua OAB para ver processos reais."
                ),
                foreground="#a00000",
                wraplength=880,
                justify="left",
            ).pack(fill="x", padx=8, pady=(8, 0))

        barra = ttk.Frame(frame)
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
        ttk.Button(
            barra, text="Limpar capturados", command=self._limpar_capturados
        ).pack(side="left")

        # Tabela com barras de rolagem vertical e horizontal.
        container = ttk.Frame(frame)
        container.pack(fill="both", expand=True, padx=6, pady=6)

        colunas = (
            "data", "situacao", "origem", "tipo", "urgente",
            "cliente", "parte_contraria", "descricao", "processo",
        )
        self._tree = ttk.Treeview(
            container, columns=colunas, show="headings", height=15
        )
        for col, titulo, largura in [
            ("data", "Data fatal", 85),
            ("situacao", "Situação", 75),
            ("origem", "Origem", 70),
            ("tipo", "Tipo", 95),
            ("urgente", "Urg.", 45),
            ("cliente", "Cliente (autor)", 150),
            ("parte_contraria", "Parte contrária (réu)", 170),
            ("descricao", "Descrição", 240),
            ("processo", "Processo", 160),
        ]:
            self._tree.heading(col, text=titulo)
            self._tree.column(col, width=largura, anchor="w")

        vsb = ttk.Scrollbar(container, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(container, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        # copiar também com duplo-clique sobre a linha
        self._tree.bind("<Double-1>", lambda _e: self._copiar_processo())

        self._prazos_status = ttk.Label(frame, text="", foreground="#666")
        self._prazos_status.pack(anchor="w", padx=8, pady=(0, 6))

    def _atualizar_prazos(self) -> None:
        if not hasattr(self, "_tree"):
            return
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._linhas.clear()
        try:
            registros = listar_prazos_manuais()
        except Exception as exc:
            logger.warning("Falha ao listar prazos: %s", exc)
            registros = []
        hoje = date.today()
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
                    reg.prazo.parte_contraria or "",
                    reg.prazo.descricao,
                    reg.prazo.numero_processo or "",
                ),
            )
            self._linhas[iid] = reg

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

    def _limpar_capturados(self) -> None:
        """Remove todos os prazos de origem 'captura' (inclui os de demonstração)."""
        try:
            registros = listar_prazos_manuais()
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))
            return
        capturados = [r for r in registros if r.origem == "captura"]
        if not capturados:
            messagebox.showinfo(
                "Limpar capturados", "Não há prazos capturados na lista."
            )
            return
        if not messagebox.askyesno(
            "Limpar capturados",
            f"Remover {len(capturados)} prazo(s) capturado(s) da lista? "
            "Os prazos cadastrados manualmente serão mantidos.",
        ):
            return
        removidos = 0
        for reg in capturados:
            try:
                if remover_prazo_manual(reg.id):
                    removidos += 1
            except Exception:  # noqa: BLE001
                logger.exception("Falha ao remover prazo capturado %s", reg.id)
        logger.info("Prazos capturados removidos: %d", removidos)
        self._atualizar_prazos()

    def _copiar_texto(self, texto: str) -> None:
        """Copia um texto para a área de transferência e confirma na barra de status."""
        self.clipboard_clear()
        self.clipboard_append(texto)
        self.update()  # garante que o conteúdo permaneça na área de transferência
        if hasattr(self, "_prazos_status"):
            self._prazos_status.config(text=f"Número do processo copiado: {texto}")

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

    # --------------------------------------------------- Consultar processo
    def _aba_consulta(self) -> None:
        frame = ttk.Frame(self._nb)
        self._nb.add(frame, text="Consultar / Movimentações")
        self._consulta_linhas: dict[str, str] = {}

        top = ttk.Frame(frame)
        top.pack(fill="x", padx=8, pady=(10, 4))
        ttk.Label(top, text="OAB (ex.: 80036/RJ) ou nº do processo:").pack(side="left")
        self._consulta_num = tk.StringVar(
            value=(settings.monitor_oab or "").split(",")[0].strip()
        )
        ent = ttk.Entry(top, textvariable=self._consulta_num, width=32)
        ent.pack(side="left", padx=6)
        ent.bind("<Return>", lambda _e: self._consultar())
        ttk.Button(top, text="Consultar", command=self._consultar).pack(side="left")
        ttk.Button(top, text="Copiar nº do processo", command=self._copiar_consulta).pack(
            side="left", padx=6
        )

        ttk.Label(
            frame,
            text="Lista as movimentações/comunicações recentes no DJEN (precisa de "
            "internet). Digite a sua OAB com UF (80036/RJ) ou um número de processo.",
            foreground="#666",
            justify="left",
            wraplength=880,
        ).pack(anchor="w", padx=10, pady=(0, 6))

        container = ttk.Frame(frame)
        container.pack(fill="both", expand=True, padx=8, pady=6)
        colunas = ("data", "processo", "orgao", "partes", "advogados", "trecho")
        self._consulta_tree = ttk.Treeview(
            container, columns=colunas, show="headings", height=13
        )
        for col, titulo, largura in [
            ("data", "Data", 85),
            ("processo", "Processo", 175),
            ("orgao", "Órgão/Diário", 140),
            ("partes", "Partes (autor x réu)", 220),
            ("advogados", "Advogados/Procuradores", 240),
            ("trecho", "Trecho da publicação", 320),
        ]:
            self._consulta_tree.heading(col, text=titulo)
            self._consulta_tree.column(col, width=largura, anchor="w")
        vsb = ttk.Scrollbar(container, orient="vertical", command=self._consulta_tree.yview)
        hsb = ttk.Scrollbar(container, orient="horizontal", command=self._consulta_tree.xview)
        self._consulta_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._consulta_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        self._consulta_tree.bind("<Double-1>", lambda _e: self._copiar_consulta())

        self._consulta_status = ttk.Label(frame, text="", foreground="#666")
        self._consulta_status.pack(anchor="w", padx=10, pady=(0, 8))

    def _consultar(self) -> None:
        entrada = (self._consulta_num.get() or "").strip()
        if not entrada:
            messagebox.showinfo("Consultar", "Digite a sua OAB (com UF) ou um processo.")
            return
        if getattr(self, "_consultando", False):
            return
        self._consultando = True
        for item in self._consulta_tree.get_children():
            self._consulta_tree.delete(item)
        self._consulta_linhas.clear()
        self._consulta_status.config(text=f"Consultando '{entrada}' no DJEN...")
        threading.Thread(
            target=self._consulta_worker, args=(entrada,), daemon=True
        ).start()

    @staticmethod
    def _montar_alvo_consulta(entrada: str):
        """Interpreta a entrada como OAB (com UF) ou número de processo."""
        from src.models import AlvoMonitoramento, TipoMonitoramento

        texto = entrada.strip()
        # Processo CNJ: tem muitos dígitos (>= 15) e separadores típicos.
        digitos = sum(c.isdigit() for c in texto)
        if digitos >= 15:
            return AlvoMonitoramento(
                tipo=TipoMonitoramento.PROCESSO,
                valor=normalizar_numero_processo(texto),
            )
        # OAB no formato "80036/RJ", "80036-RJ" ou "80036 RJ".
        numero, uf = texto, None
        for sep in ("/", "-", " "):
            if sep in texto:
                partes = texto.split(sep, 1)
                numero, uf = partes[0].strip(), partes[1].strip().upper() or None
                break
        return AlvoMonitoramento(
            tipo=TipoMonitoramento.OAB, valor=numero.strip(), uf=uf
        )

    def _consulta_worker(self, entrada: str) -> None:
        try:
            from src.services.capture.comunica import ComunicaProvider

            alvo = self._montar_alvo_consulta(entrada)
            pubs = ComunicaProvider().buscar(alvo, max_paginas=3)
            # Mais recentes primeiro.
            pubs.sort(key=lambda p: (p.data_publicacao or date.min), reverse=True)
            self._eventos_fila.put(("consulta_ok", (alvo.rotulo, pubs)))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha na consulta de processo/OAB")
            self._eventos_fila.put(("consulta_erro", str(exc)))

    def _preencher_consulta(self, rotulo: str, pubs: list) -> None:
        for item in self._consulta_tree.get_children():
            self._consulta_tree.delete(item)
        self._consulta_linhas.clear()
        for p in pubs:
            partes = " x ".join(
                x for x in [p.cliente or "?", p.parte_contraria or "?"] if x
            )
            data = p.data_publicacao.strftime("%d/%m/%Y") if p.data_publicacao else ""
            trecho = " ".join((p.conteudo or "").split())[:200]
            iid = self._consulta_tree.insert(
                "", "end",
                values=(
                    data,
                    p.numero_processo or "",
                    p.diario or "",
                    partes,
                    p.advogados or "",
                    trecho,
                ),
            )
            self._consulta_linhas[iid] = p.numero_processo or ""
        if pubs:
            self._consulta_status.config(
                text=f"{len(pubs)} movimentação(ões) encontrada(s) para {rotulo}."
            )
        else:
            self._consulta_status.config(
                text=f"Nenhuma movimentação recente encontrada no DJEN para {rotulo}."
            )

    def _copiar_consulta(self) -> None:
        selecao = self._consulta_tree.selection()
        if not selecao:
            messagebox.showinfo("Copiar", "Selecione uma linha.")
            return
        processo = (self._consulta_linhas.get(selecao[0]) or "").strip()
        if not processo:
            messagebox.showinfo("Copiar", "Esta linha não tem número de processo.")
            return
        self.clipboard_clear()
        self.clipboard_append(processo)
        self.update()
        self._consulta_status.config(text=f"Número do processo copiado: {processo}")

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
            self._nb.select(self._tab_registro)  # aba Registro (acompanhar)
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
        self._tab_registro = frame
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
                        self._nb.select(self._tab_prazos)  # vai para a aba Prazos
                elif tipo == "buscar_erro":
                    auto = getattr(self, "_busca_auto", False)
                    self._buscando = False
                    self._btn_buscar.config(state="normal")
                    self._status.config(text="Erro na busca (veja a aba Registro).")
                    if not auto:  # em busca automática, não interrompe com pop-up
                        messagebox.showerror("Erro na busca", str(dado))
                elif tipo == "consulta_ok":
                    self._consultando = False
                    self._preencher_consulta(*dado)
                elif tipo == "consulta_erro":
                    self._consultando = False
                    self._consulta_status.config(
                        text="Erro na consulta (veja a aba Registro)."
                    )
                    messagebox.showerror("Erro na consulta", str(dado))
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
