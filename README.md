# ⚖️ Monitor de Diários Oficiais & Automação de Prazos Jurídicos

Aplicação em Python para **monitoramento de diários oficiais** e **automação de
prazos jurídicos** (estilo *clipping inteligente* / eLaw Adv). O sistema captura
publicações por termos e nomes, usa **Inteligência Artificial** para interpretar
o texto e extrair prazos e ações, e integra esses prazos a uma **agenda**
(Google Calendar) com alertas.

---

## 🏗️ Arquitetura

O pipeline é dividido em **3 etapas** desacopladas:

```
┌──────────────────┐     ┌─────────────────────┐     ┌──────────────────────┐
│  1. CAPTURA      │     │  2. INTELIGÊNCIA    │     │  3. INTEGRAÇÃO/AGENDA│
│                  │     │     ARTIFICIAL      │     │                      │
│  APIs de diários │ ──► │ LLM Claude/Gemini/  │ ──► │  Google Calendar     │
│  (DJEN/CNJ,      │     │  OpenAI — extrai    │     │  / alertas           │
│   Jusbrasil)     │     │  prazos em JSON     │     │                      │
└──────────────────┘     └─────────────────────┘     └──────────────────────┘
       │                          │                            │
   Publicacao              AnalisePublicacao                 Prazo
  (texto bruto)            (JSON estruturado)            (evento/lembrete)
```

| Etapa | Responsabilidade | Entrada → Saída | Módulo |
|-------|------------------|-----------------|--------|
| **1. Captura** | Buscar publicações por termos/nomes nas APIs de diários oficiais. | termos → `Publicacao` | `src/services/capture/` |
| **2. Inteligência** | Enviar o texto bruto a um LLM e extrair prazos/ações em JSON estruturado. | `Publicacao` → `AnalisePublicacao` | `src/services/intelligence/` |
| **3. Agenda** | Criar eventos no Google Calendar e disparar alertas. | `Prazo` → evento | `src/services/agenda/` |

O **contrato de dados** entre as etapas é definido com **Pydantic** em
[`src/models.py`](src/models.py) (`Publicacao`, `AnalisePublicacao`, `Prazo`),
garantindo validação e tipagem em todo o fluxo. A IA apenas **extrai** o prazo
(em dias) e datas citadas; a **data fatal é calculada em código**, em dias úteis
(CPC art. 219), por [`src/utils/prazos.py`](src/utils/prazos.py).

---

## 🧰 Stack Tecnológica

- **Linguagem:** Python 3.11+
- **HTTP / Integração:** `requests`
- **Validação & contratos:** `pydantic`, `pydantic-settings`
- **Configuração:** `python-dotenv`
- **Resiliência:** `tenacity` (retentativas em chamadas de API)
- **IA:** `anthropic` (Claude — padrão), `google-genai` (Gemini), `openai` — com saída estruturada (JSON validado)
- **Datas/prazos:** `python-dateutil` + cálculo de dias úteis próprio
- **Agenda:** `google-api-python-client` (Google Calendar)

---

## 📁 Estrutura do Projeto

```
testelaw/
├── .env.example            # Modelo de variáveis de ambiente (copie p/ .env)
├── .gitignore
├── README.md
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── run.py                  # Entry do executável (PyInstaller)
├── monitor.spec            # Spec do PyInstaller
├── src/
│   ├── cli.py              # CLI unificada (run/scheduler/prazo/healthcheck)
│   ├── main.py             # Orquestrador do pipeline (ponto de entrada)
│   ├── scheduler.py        # Execução periódica do pipeline (loop/cron)
│   ├── add_prazo.py        # CLI: adicionar prazo manual à agenda
│   ├── prazos.py           # CLI: gerir prazos manuais (add/list/remove)
│   ├── healthcheck.py      # Verificação de prontidão (credenciais/config)
│   ├── models.py           # Contratos de dados (Pydantic)
│   ├── config/
│   │   └── settings.py     # Carregamento das configurações (.env)
│   ├── services/
│   │   ├── capture/        # Etapa 1 - Captura (diários oficiais)
│   │   │   ├── base.py         # Contrato CaptureProvider
│   │   │   ├── comunica.py     # DJEN/Comunica (CNJ) — gratuito, sem credencial
│   │   │   ├── jusbrasil.py    # Cliente da API Jusbrasil
│   │   │   ├── mock.py         # Provedor mock (sem credenciais)
│   │   │   ├── factory.py      # Seleção do provedor (CAPTURE_PROVIDER)
│   │   │   └── targets.py      # Alvos: termos / OAB / processos
│   │   ├── intelligence/   # Etapa 2 - IA (extração de prazos)
│   │   │   ├── base.py         # IntelligenceProvider + cálculo da data fatal
│   │   │   ├── claude.py       # Provedor Claude (padrão)
│   │   │   ├── gemini.py       # Provedor Gemini
│   │   │   ├── openai.py       # Provedor OpenAI
│   │   │   ├── mock.py         # Provedor mock (heurística, sem credenciais)
│   │   │   ├── factory.py      # Seleção do provedor (AI_PROVIDER)
│   │   │   └── prompts.py      # System prompt / prompt de extração
│   │   ├── agenda/         # Etapa 3 - Google Calendar / alertas
│   │   │   ├── base.py             # Contrato AgendaProvider
│   │   │   ├── google_calendar.py  # Cliente Google Calendar (OAuth)
│   │   │   ├── mock.py             # Provedor mock (sem credenciais)
│   │   │   ├── factory.py          # Seleção do provedor (AGENDA_PROVIDER)
│   │   │   └── eventos.py          # Converte prazos -> EventoAgenda
│   │   ├── manual/        # Prazos manuais (CRUD: add/list/remove)
│   │   ├── notifications/ # Alertas: webhook / Telegram / e-mail
│   │   └── persistence/   # Estado processado (SQLite) - evita reprocessar/duplicar
│   └── utils/
│       ├── logger.py       # Logging centralizado
│       ├── dates.py        # Parsing de datas (BR e ISO)
│       └── prazos.py       # Cálculo de data fatal (dias úteis - CPC)
└── tests/
```

---

## 🚀 Configuração do Ambiente

```bash
# 1. Criar e ativar o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

# 2. Instalar as dependências
pip install -r requirements.txt

# 3. Configurar as variáveis de ambiente
cp .env.example .env
# edite o arquivo .env e preencha suas chaves de API

# 4. Executar o pipeline (com CAPTURE_PROVIDER=mock roda sem credenciais)
python -m src.main

# 5. (Opcional) Rodar os testes
pip install -r requirements-dev.txt
pytest
```

### Variáveis de Ambiente

As chaves necessárias estão documentadas em [`.env.example`](.env.example).
As principais são:

- `CAPTURE_PROVIDER` — captura: `comunica` (DJEN/CNJ, grátis), `jusbrasil`, `escavador` ou `mock`
- `JUSBRASIL_API_KEY` / `ESCAVADOR_API_KEY` — credenciais (apenas para as fontes pagas)
- `MONITOR_TERMS` / `MONITOR_OAB` / `MONITOR_PROCESSOS` — alvos monitorados (termos, OAB, processos)
- `AI_PROVIDER` — provedor de IA: `claude` (padrão), `gemini`, `openai` ou `mock`
- `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `OPENAI_API_KEY` + `CLAUDE_MODEL` — etapa de IA
- `AGENDA_PROVIDER` — destino da agenda: `google` ou `mock`
- `GOOGLE_CALENDAR_CREDENTIALS` / `DEADLINE_REMINDER_DAYS` — agenda e antecedência do lembrete
- `STATE_STORE` / `STATE_DB_PATH` — persistência do estado (`sqlite` ou `memory`)
- `SCHEDULE_INTERVAL_SECONDS` — intervalo do scheduler (segundos)
- `NOTIFIER` / `NOTIFY_ONLY_URGENT` — alertas: `mock`, `webhook`, `telegram` ou `email`

---

## ✍️ Prazos Manuais

Além da captura automática, é possível **incluir prazos manualmente** — eles
passam pelo mesmo cálculo de data fatal (dias úteis) e vão para a agenda:

```bash
# Por prazo em dias (data fatal calculada a partir de hoje)
python -m src.add_prazo --descricao "Protocolar manifestação" \
    --tipo manifestacao --prazo-dias 5 --processo 1001234-56.2024.8.26.0100

# Por data fatal já conhecida
python -m src.add_prazo --descricao "Audiência de instrução" \
    --tipo audiencia --data-fatal 2026-08-01 --urgente
```

Use `--dias-corridos` para prazos materiais (não processuais) e `--help` para
todas as opções.

**Gerenciar** os prazos manuais cadastrados (listar/remover):

```bash
python -m src.prazos add --descricao "Protocolar manifestação" --prazo-dias 5
python -m src.prazos list
python -m src.prazos remove --id <id>   # remove também o evento na agenda
```

---

## ⏱️ Execução Periódica & Persistência

O sistema guarda em **SQLite** o que já foi processado/agendado, então rodar o
pipeline repetidamente **não reprocessa** publicações (economiza IA) nem
**duplica** eventos. Para rodar em ciclos:

```bash
python -m src.scheduler                 # usa SCHEDULE_INTERVAL_SECONDS
python -m src.scheduler --intervalo 1800
python -m src.scheduler --ciclos 1      # roda uma vez e sai
```

Alternativamente, agende `python -m src.main` via **cron** (ex.: de hora em hora).

---

## 🔌 Indo a Produção (credenciais reais)

> 💡 **Atalho gratuito:** `cp .env.comunica .env` já configura a **captura real
> via DJEN/CNJ (grátis)** + IA `mock` — roda o pipeline ponta a ponta sem
> nenhuma credencial. Depois é só trocar `AI_PROVIDER`/`AGENDA_PROVIDER` e
> informar as chaves para a versão completa.

1. Copie e preencha o `.env`: `cp .env.example .env` (chaves de Jusbrasil,
   Anthropic/Gemini/OpenAI, Google Calendar, notificações).
2. Troque os provedores: `CAPTURE_PROVIDER=jusbrasil`, `AI_PROVIDER=claude`,
   `AGENDA_PROVIDER=google`, `NOTIFIER=telegram` (etc.).
3. **Verifique a prontidão** (sem chamadas de rede):
   ```bash
   python -m src.healthcheck
   ```
4. Rode um ciclo e confira o resultado: `python -m src.main`.

## 🐳 Docker

```bash
# Sobe o scheduler continuamente (lê o .env e persiste em ./data)
docker compose up --build

# Ou via imagem direta:
docker build -t monitor-diarios .
docker run --env-file .env -v "$PWD/data:/app/data" monitor-diarios
```

---

## 🖥️ Executável (sem Python)

Gera um binário único (`monitor-diarios`) que roda **sem Python instalado**, com
todos os comandos: `run`, `scheduler`, `prazo` e `healthcheck`.

```bash
# Linux/macOS
./build.sh
./dist/monitor-diarios healthcheck

# Windows
build.bat
dist\monitor-diarios.exe healthcheck
```

> ⚠️ O PyInstaller **não faz cross-compile**: cada SO gera o seu binário
> (Linux→ELF, Windows→`.exe`, macOS→Mach-O). Para obter os três sem ter as
> máquinas, use o **GitHub Actions** (`.github/workflows/build.yml`): dispare em
> *Actions → Run workflow*, ou crie uma tag (`git tag v0.1.0 && git push --tags`),
> e baixe os artefatos `monitor-diarios-windows-latest` / `-macos-latest` / `-ubuntu-latest`.

O executável lê o `.env` da **mesma pasta do binário** (ou via variáveis de ambiente).

---

## 🗺️ Roadmap

- [x] Estrutura base do projeto, configuração e contratos de dados
- [x] **Módulo de Captura** (Etapa 1) — DJEN/CNJ (grátis) + Jusbrasil + mock; por termo/OAB/processo
- [x] **Módulo de Inteligência** (Etapa 2) — Claude/Gemini/OpenAI + mock; data fatal em dias úteis
- [x] **Módulo de Agenda** (Etapa 3) — Google Calendar + mock; evento/lembrete por prazo
- [x] **Prazos manuais** (CLI) — inclusão manual com cálculo de data fatal
- [x] **Persistência + scheduler** — SQLite (evita reprocessar/duplicar) + execução periódica
- [x] **Notificações** — webhook / Telegram / e-mail (+ mock); alerta de prazos urgentes
- [x] **Docker + healthcheck** — empacotamento (scheduler) e verificação de prontidão
- [x] **Executável** (PyInstaller) — binário único + build Win/Mac/Linux via GitHub Actions
- [x] Cobertura de testes (pytest) cobrindo todos os módulos
