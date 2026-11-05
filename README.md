<div align="center">

# 🏦 BankAO

**A Primeira Carteira Digital com IA Bancária para Angola e o Mundo**

*Meta Global AI Developer Hackathon 2024*

🌐 **[BankAO — Carteira Digital para Angola e o Mundo](https://bankao.onrender.com/)**

[![Deploy](https://img.shields.io/badge/Live%20Demo-bankao.onrender.com-00c7b7?logo=render&logoColor=white)](https://bankao.onrender.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Meta AI](https://img.shields.io/badge/Meta-Muse%20Spark%20Open-0866FF?logo=meta&logoColor=white)](https://ai.meta.com)
[![Baseten](https://img.shields.io/badge/Baseten-2M%20tokens%2Fmin-5C6BC0)](https://baseten.co)

</div>

---

## 1. O que é o BankAO?

O BankAO é uma **carteira digital inteligente** desenhada para o mercado angolano — e construída para escalar globalmente. Combina as funcionalidades essenciais de um banco digital (contas, transferências, poupanças, investimentos) com um **Copilot de IA conversacional** que permite ao utilizador fazer qualquer operação bancária em linguagem natural, incluindo por **voz**.

> *"Envia 5000 Kz ao João"* → o Copilot interpreta, preenche o formulário e aguarda a confirmação do utilizador. A IA prepara. O humano decide.

---

## 2. O Problema

Angola e grande parte de África têm:

- **Baixa bancarização** — milhões de pessoas sem acesso a serviços financeiros básicos.
- **Interfaces bancárias complexas** — apps que exigem literacia financeira elevada.
- **Falta de ferramentas de gestão de dinheiro** — sem orçamentos, categorias de despesa ou análise de hábitos.
- **Barreiras de idioma e literacia digital** — interfaces em inglês, sem assistência contextual.
- **Dependência de dinheiro físico** — Multicaixa e transferências manuais como único meio.

---

## 3. A Solução

O BankAO resolve estes problemas através de três pilares:

| Pilar | O que faz |
|---|---|
| **Copilot de IA** | Compreende pedidos em português, extrai intenção, preenche formulários e executa ações com confirmação humana obrigatória |
| **Gestão Financeira Completa** | Contas multi-moeda, poupanças com metas, orçamentos, despesas por categoria, investimentos simulados |
| **Acessibilidade Mobile-First** | PWA instalável, interação por voz, suporte a todos os países e indicativos telefónicos |

---

## 4. Integração Meta AI

O BankAO usa **Meta Muse Spark Open** via **Baseten** como motor central de raciocínio bancário.

### Onde a Meta AI é usada

| Componente | Ficheiro | Função |
|---|---|---|
| **Cliente IA unificado** | `backend/ai/client.py` | Ligação a `meta-models/muse-spark-open-1026` via Baseten (OpenAI-compatible). Extrai *chain-of-thought* (`<think>`) e suporta tool calling, visão multimodal e retentativas com backoff exponencial |
| **Interpretação de intenções** | `backend/ai/intents.py` | Converte linguagem natural em ações bancárias (transferência, poupança, despesa, depósito). O modelo JSON do Muse Spark é validado contra um interpretador determinístico antes de ser aceite |
| **Orquestrador de ferramentas** | `backend/ai/orchestrator.py` | Decide qual ferramenta bancária invocar e compõe a resposta final com raciocínio isolado |
| **Assistente bancário** | `backend/ai/assistant.py` | Gestão de sessão e histórico de conversa, contexto financeiro do utilizador injetado no prompt |
| **Ritmo de gasto ideal** | `backend/ai/ideal_pace.py` | O modelo propõe o gasto mensal ideal para cumprir metas de poupança (`POST /api/ai/ideal-pace`), limitado a ±25% do cálculo local |
| **Análise de despesas** | `backend/ai/expense_flow.py` | Categorização automática e análise de padrões de consumo |
| **Análise de investimentos** | `backend/ai/invest_flow.py` | Sugestões de alocação e análise de risco |
| **Visão multimodal** | `backend/ai/vision.py` | Análise de comprovativos Multicaixa, faturas e talões (`POST /api/ai/vision/analyze`) |
| **KYC inteligente** | `backend/ai/kyc.py` | Validação de documentos e passaportes com OCR assistido por IA |
| **Voz conversacional** | `backend/ai/elevenlabs.py` | Integração ElevenLabs com Meta AI como *Custom LLM* para o Copilot de voz em tempo real |

### Modelo e Performance

```
Modelo:    meta-models/muse-spark-open-1026
Plataforma: Baseten (Inferência de Alta Performance)
Throughput: até 2 milhões de tokens/minuto
Reasoning:  Chain-of-thought nativo (extraído e apresentado separadamente)
Fallback:   Regras financeiras locais (sem API key ou sem rede)
```

---

## 5. Arquitetura

```
Utilizador
    │
    ▼
BankAO UI  ──────────────────────────────────────────────────────
(HTML/CSS/JS puro · PWA · Mobile-first · Voz via ElevenLabs)
    │
    ▼
FastAPI Backend (Python)
    │
    ├── API REST  (/api/*)
    │       ├── auth · accounts · transfers · deposits
    │       ├── savings · expenses · investments · cards
    │       ├── fx (câmbio) · iban · transactions · contacts
    │       └── settings · kyc · analytics
    │
    └── AI Copilot  (/api/ai/*)
            │
            ▼
        Orquestrador  (backend/ai/orchestrator.py)
            │   ┌─────────────────────────────────┐
            │   │  Contexto financeiro do utilizador│
            │   │  (saldo, contas, metas, histórico)│
            │   └─────────────────────────────────┘
            ▼
        Meta Muse Spark Open  (via Baseten)
            │
            ├── Chain-of-Thought  →  raciocínio isolado para o utilizador
            │
            └── Intent / Tool Selection
                    │
                    ▼
                APIs Bancárias
                    │
                    ├── Transferência interna / IBAN
                    ├── Depósito Multicaixa Express
                    ├── Criação de meta de poupança
                    ├── Registo de despesa categorizada
                    ├── Conversão cambial (AOA ↔ EUR ↔ USD)
                    └── Análise de investimentos
                            │
                            ▼
                    Formulário pré-preenchido
                            │
                            ▼
                    ✅ Confirmação obrigatória do utilizador
                            │
                            ▼
                        Ação executada · Extrato atualizado
```

---

## 6. Funcionalidades

### 💳 Contas & Cartões
- Contas multi-moeda: **AOA · EUR · USD**
- IBAN angolano gerado automaticamente
- Cartão virtual com histórico de operações
- Gráfico de evolução do saldo (7d / 30d / 3m / 6m / 1a / Total)
- Diagrama de Sankey: fluxo entre contas (origem → conta → destino)

### 💸 Transferências & Pagamentos
- Transferências internas (entre contas próprias)
- Transferências IBAN internacionais
- Referências de pagamento (simuladas)
- Multicaixa Express (simulado)
- Contactos guardados com avatar e histórico

### 🐷 Poupanças
- Metas de poupança com nome, valor-alvo e prazo
- Ritmo de gasto ideal calculado pelo Muse Spark Open
- Depósitos e levantamentos das metas

### 📊 Despesas & Orçamentos
- Registo manual de despesas com 9 categorias
- Orçamento mensal por categoria
- Gráficos de gastos por comerciante e por período
- Análise de padrões via IA

### 📈 Investimentos
- Simulação de portfólios (Conservador / Moderado / Agressivo)
- Análise de risco e sugestões de alocação pelo Muse Spark Open

### 🤖 Copilot IA (Linguagem Natural + Voz)
- Chat em português com o Muse Spark Open
- Interpretação de pedidos bancários em texto e voz
- Raciocínio transparente: o utilizador vê o *chain-of-thought*
- Chips de acção rápida para operações frequentes
- Análise de comprovativos por foto (visão multimodal)
- Voz conversacional em tempo real via ElevenLabs

### 🛂 KYC & Identidade
- Verificação de identidade em 3 passos
- Gerador de documentos de identidade angolanos (`/documento`)
- Gerador de passaportes angolanos (`/passaporte`)
- Análise de documentos com IA (OCR + validação)

### 📱 Mobile & PWA
- Instalável como app nativa (PWA)
- Guard de permissões persistente (microfone + notificações)
- Funciona offline com Service Worker
- Copilot de voz adaptado para HTTP/mobile

---

## 7. Como Correr

### Pré-requisitos

- Python 3.11+
- pip

### Instalação

```bash
# 1. Clonar o repositório
git clone <url-do-repositório>
cd bankao-meta-hackathon

# 2. Instalar dependências Python
pip install fastapi uvicorn python-dotenv "python-jose[cryptography]" bcrypt openai pillow "pydantic[email]" httpx

# 3. Configurar variáveis de ambiente
cp .env.example .env
# Edite o .env e adicione as suas chaves (ver secção 8)

# 4. (Opcional) Gerar 4 contas de teste com 1 ano de histórico completo
python scripts/seed_demo_users.py

# 5. Arrancar o servidor
uvicorn backend.main:app --reload
```

Abra **http://localhost:8000** para a aplicação ou **http://localhost:8000/docs** para a API interativa.

A base de dados SQLite (`bankao.db`) é criada automaticamente na raiz do projeto.

### Acesso em rede local (mobile)

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
# Aceda em http://<ip-local>:8000 no telemóvel
```

### Testes

```bash
pytest tests/ -q
# 174 testes · ~60 segundos
```

### Build do index.html (pré-visualização do HTML montado)

```bash
python scripts/build_index.py
```

### 👥 Contas de Teste (1 Ano de Histórico Bancário)

O projeto inclui um gerador de dados realistas com 4 perfis completos que utilizam o BankAO há **1 ano** (com salários contínuos, dezenas de despesas categorizadas, orçamentos mensais, metas de poupança, cartões de débito com histórico e investimentos ativos).

Para popular ou atualizar os utilizadores de demonstração na base de dados:
```bash
python scripts/seed_demo_users.py
```

| Email | Senha | Nome & Perfil | Dados & Cenário de Teste |
|---|---|---|---|
| `ana@bankao.ao` | `Demo1234!` | **Ana Luísa Ferreira**<br>*Gestora de Marketing* | • 13 salários mensais (350.000 Kz)<br>• 72 despesas categorizadas e movimentos de cartão<br>• 3 metas de poupança (Viagem a Lisboa, Emergência, Mac)<br>• 2 investimentos ativos (DP BankAO Super Rendimento + ETF Vanguard)<br>• Contas ativas em AOA, EUR e USD |
| `carlos@bankao.ao` | `Demo1234!` | **Carlos Manuel Domingos**<br>*Engenheiro Civil* | • 13 salários de alta renda (500.000 Kz)<br>• 72 despesas e levantamentos periódicos<br>• 12 remessas mensais da família em EUR<br>• Metas para Casa Própria e Carro Novo<br>• Investimentos em Obrigações BODIVA OT-2027 + ETF S&P 500 |
| `fatima@bankao.ao` | `Demo1234!` | **Fátima Beatriz Neto**<br>*Professora* | • 13 salários (180.000 Kz) com planeamento rigoroso<br>• 90 despesas com orçamentos por categoria cumpridos<br>• 3 metas (Pós-graduação, Emergência, Telemóvel)<br>• Investimento conservador no Fundo de Liquidez BAI<br>• Excelente perfil para testar limites orçamentais e Copilot de poupança |
| `miguel@bankao.ao` | `Demo1234!` | **Miguel António Silva**<br>*Comerciante* | • Fluxo de caixa de negócio com múltiplos recebimentos de clientes<br>• 108 despesas operacionais e pessoais<br>• Movimentos em USD para importações (Dubai/China)<br>• Levantamentos frequentes em caixas Multicaixa<br>• Investimentos no DP BFA Crescente e FII Imobiliário Atlântico |

---

## 8. Variáveis de Ambiente

Copie `.env.example` para `.env` e preencha:

```env
# ─── Servidor ────────────────────────────────────────────────────────────────
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development

# Chave JWT — mude em produção!
SECRET_KEY=bankao_dev_secret_key_change_in_prod

# ─── Meta AI via Baseten (Hackathon) ─────────────────────────────────────────
# Provedor: "baseten" | "meta" | "auto"
AI_PROVIDER=auto

# Baseten — modelo oficial do Hackathon (2M tokens/min)
BASETEN_API_KEY=           # obtenha em baseten.co
BASETEN_BASE_URL=https://inference.baseten.co/v1
BASETEN_MODEL=meta-models/muse-spark-open-1026

# Meta Direct API (fallback)
MODEL_API_KEY=             # opcional
MODEL_BASE_URL=https://api.meta.ai/v1
MODEL_NAME=muse-spark-1.3

# Parâmetros de inferência
AI_MAX_TOKENS=3500
AI_TEMPERATURE=0.2
AI_REQUEST_TIMEOUT=45
AI_ENABLE_REASONING_TRACE=true   # mostra o chain-of-thought ao utilizador

# ─── Base de dados ────────────────────────────────────────────────────────────
DATABASE_PATH=bankao.db

# ─── ElevenLabs (Voz conversacional — opcional) ───────────────────────────────
ELEVENLABS_API_KEY=        # obtenha em elevenlabs.io
ELEVENLABS_AGENT_ID=       # ID do agente conversacional
ELEVENLABS_CUSTOM_LLM_SECRET=   # UUID aleatório — autentica o Custom LLM
```

> **Sem chaves configuradas**, o Copilot entra em modo de fallback com regras financeiras locais — a aplicação funciona na totalidade exceto o chat com IA.

---

## 9. Demo

🚀 **Aplicação Online:** [BankAO — Carteira Digital para Angola e o Mundo](https://bankao.onrender.com/)

🎥 **[Ver vídeo de demonstração](#)** *(link a adicionar)*

### Rotas notáveis

| URL | Descrição |
|---|---|
| `/` | Aplicação principal |
| `/docs` | API interativa (Swagger) |
| `/documento` | Gerador de Bilhete de Identidade Angolano |
| `/passaporte` | Gerador de Passaporte Angolano |
| `/manifest.json` | Manifesto PWA |

---

## 10. Estrutura do Projeto

```
bankao-meta-hackathon/
├── backend/
│   ├── main.py                  # FastAPI app: CORS, rotas, montagem do frontend
│   ├── core/                    # config.py · security.py (JWT, passwords)
│   ├── database/                # connection.py (SQLite/WAL) · schema.py (migrações, seed)
│   ├── schemas/                 # modelos Pydantic por domínio
│   ├── services/                # ledger.py (livro-razão) · iban.py
│   ├── providers/               # integrações simuladas: deposits · fx · payout
│   ├── ai/
│   │   ├── client.py            # ★ Cliente Meta/Baseten (OpenAI-compat, reasoning, vision)
│   │   ├── orchestrator.py      # ★ Orquestrador de ferramentas bancárias
│   │   ├── intents.py           # ★ Interpretação de linguagem natural → ações
│   │   ├── assistant.py         # Sessão e histórico do Copilot
│   │   ├── prompts.py           # System prompts e contexto financeiro
│   │   ├── ideal_pace.py        # Ritmo de gasto ideal (Meta AI)
│   │   ├── expense_flow.py      # Análise de despesas (Meta AI)
│   │   ├── invest_flow.py       # Sugestões de investimento (Meta AI)
│   │   ├── vision.py            # Análise de comprovativos (Multimodal)
│   │   ├── kyc.py               # Validação de documentos KYC
│   │   ├── elevenlabs.py        # Integração ElevenLabs + Meta Custom LLM
│   │   └── tools/               # Ferramentas bancárias chamadas pelo modelo
│   ├── api/routes/              # auth · accounts · transfers · deposits · savings
│   │                            # expenses · investments · cards · fx · iban
│   │                            # transactions · contacts · kyc · ai · eleven · analytics
│   └── web/                     # frontend.py (rotas estáticas) · includes.py (partials)
│
├── frontend/
│   ├── index.html               # Shell com @include para todos os partials
│   ├── manifest.json            # PWA manifest
│   ├── sw.js                    # Service Worker (cache offline)
│   ├── partials/
│   │   ├── layout/              # icons · sidebar · topbar · bottom-nav · scripts
│   │   ├── pages/               # home · accounts · payments · expenses · savings
│   │   │                        # operations · statement · copilot · investments · cards
│   │   └── modals/              # um ficheiro por modal
│   ├── css/
│   │   ├── main.css             # Ponto de entrada (@import ordenado)
│   │   ├── base/                # tokens CSS · reset
│   │   ├── layout/              # shell · sidebar · responsive
│   │   ├── components/          # modais · toasts · copilot · mobile-guard
│   │   ├── dashboard/           # página inicial
│   │   └── features/            # um ficheiro por funcionalidade
│   └── js/
│       ├── core/                # config · state · format · currency · ui · mobile-app-guard
│       ├── features/            # auth · dashboard · statement · accounts · payments
│       │                        # savings · expenses · operations · copilot · kyc · cards
│       └── main.js              # Arranque (DOMContentLoaded) — carrega por último
│
├── tests/                       # 174 testes pytest
├── tools/                       # Geradores de documentos/passaportes KYC
├── data/                        # Atlas SWIFT, países, caches de scraping
├── scripts/                     # build_index.py · migrate_imports.py
└── docs/                        # MIGRACAO.md e documentação interna
```

---

## 11. Decisões de Design

- **Sem framework de frontend** — HTML/CSS/JS puro. Zero bundlers, zero `node_modules`, zero build step para o frontend. O servidor Python serve o `index.html` montado diretamente.
- **A IA prepara, o humano decide** — O Copilot nunca executa uma operação sem confirmação explícita do utilizador. Preenche formulários; quem carrega em "Confirmar" é sempre a pessoa.
- **Fallback determinístico** — Se a API Meta/Baseten não estiver configurada ou falhar, o sistema cai para regras financeiras locais (sem degradação da UI).
- **SQLite com WAL** — Base de dados de ficheiro único, sem dependências externas, adequada para o hackathon e pequenas deployments.
- **Raciocínio visível** — O *chain-of-thought* do Muse Spark Open é extraído e apresentado ao utilizador numa secção separada, promovendo transparência e confiança.

---

<div align="center">

Feito com ❤️ para o **Meta Global AI Developer Hackathon**

</div>
