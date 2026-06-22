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
│  APIs de diários │ ──► │  LLM (Gemini/OpenAI)│ ──► │  Google Calendar     │
│  (Escavador /    │     │  interpreta o texto │     │  / alertas           │
│   Jusbrasil)     │     │  e extrai prazos    │     │                      │
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
garantindo validação e tipagem em todo o fluxo.

---

## 🧰 Stack Tecnológica

- **Linguagem:** Python 3.11+
- **HTTP / Integração:** `requests`
- **Validação & contratos:** `pydantic`, `pydantic-settings`
- **Configuração:** `python-dotenv`
- **Resiliência:** `tenacity` (retentativas em chamadas de API)
- **IA:** `google-genai` (Gemini) e/ou `openai`
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
│   │   ├── intelligence/   # Etapa 2 - IA (extração de prazos)
│   │   └── agenda/         # Etapa 3 - Google Calendar / alertas
│   └── utils/
│       └── logger.py       # Logging centralizado
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

# 4. Executar o pipeline
python -m src.main
```

### Variáveis de Ambiente

As chaves necessárias estão documentadas em [`.env.example`](.env.example).
As principais são:

- `ESCAVADOR_API_KEY` / `JUSBRASIL_API_KEY` — captura de publicações
- `MONITOR_TERMS` — termos/nomes a monitorar (separados por vírgula)
- `AI_PROVIDER`, `GEMINI_API_KEY` / `OPENAI_API_KEY` — etapa de IA
- `GOOGLE_CALENDAR_CREDENTIALS` — integração com a agenda

---

## 🗺️ Roadmap

- [x] Estrutura base do projeto, configuração e contratos de dados
- [ ] **Módulo de Captura** (Etapa 1) — *em desenvolvimento*
- [ ] Módulo de Inteligência Artificial (Etapa 2)
- [ ] Módulo de Integração / Agenda (Etapa 3)
- [ ] Persistência (evitar reprocessar publicações) e agendamento (scheduler)
- [ ] Testes automatizados
