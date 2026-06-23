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
│  (Jusbrasil /    │     │  OpenAI — extrai    │     │  / alertas           │
│   Escavador)     │     │  prazos em JSON     │     │                      │
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
├── src/
│   ├── main.py             # Orquestrador do pipeline (ponto de entrada)
│   ├── models.py           # Contratos de dados (Pydantic)
│   ├── config/
│   │   └── settings.py     # Carregamento das configurações (.env)
│   ├── services/
│   │   ├── capture/        # Etapa 1 - Captura (diários oficiais)
│   │   │   ├── base.py         # Contrato CaptureProvider
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
│   │   └── agenda/         # Etapa 3 - Google Calendar / alertas
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

- `CAPTURE_PROVIDER` — provedor de captura ativo: `jusbrasil` ou `mock`
- `JUSBRASIL_API_KEY` / `ESCAVADOR_API_KEY` — credenciais de captura (Etapa 1)
- `MONITOR_TERMS` / `MONITOR_OAB` / `MONITOR_PROCESSOS` — alvos monitorados (termos, OAB, processos)
- `AI_PROVIDER` — provedor de IA: `claude` (padrão), `gemini`, `openai` ou `mock`
- `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `OPENAI_API_KEY` + `CLAUDE_MODEL` — etapa de IA
- `GOOGLE_CALENDAR_CREDENTIALS` — integração com a agenda

---

## 🗺️ Roadmap

- [x] Estrutura base do projeto, configuração e contratos de dados
- [x] **Módulo de Captura** (Etapa 1) — Jusbrasil + mock, por termo/OAB/processo
- [x] **Módulo de Inteligência** (Etapa 2) — Claude/Gemini/OpenAI + mock; data fatal em dias úteis
- [ ] Módulo de Integração / Agenda (Etapa 3) — *próximo*
- [ ] Persistência (evitar reprocessar publicações) e agendamento (scheduler)
- [ ] Cobertura de testes ampliada
