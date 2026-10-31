# Migração para a nova estrutura

## 1. Aplicar no repositório

Na raiz do projeto (onde está o `.git`), **apague** o que foi substituído e copie o conteúdo novo:

```bat
git rm -r --cached app scratch frontend/app.js frontend/style.css frontend/index.html frontend/samples
rmdir /s /q app scratch frontend\samples
del frontend\app.js frontend\style.css frontend\index.html
```
Depois copie por cima da raiz as pastas/ficheiros novos (`backend`, `frontend`, `tests`, `scripts`, `docs`,
`README.md`, `.gitignore`, `.env.example`, `conftest.py`) e faça:

```bat
git add -A
git status
git commit -m "Reorganiza backend, frontend (js/css/partials) e testes"
git push
```
O Git deteta a maior parte dos ficheiros movidos como renomeações, mantendo o histórico.

Ficheiros que **não** estavam no zip e ficam como estão: `tests/*` (os seus), `docs_projeto.md`,
`pytest.ini`, `test_register.ps1`, `test_samples.ps1`.

## 2. Atualizar os seus testes e scripts antigos

```bat
python scripts\migrate_imports.py tests              :: pré-visualiza
python scripts\migrate_imports.py tests --apply      :: grava
```
Também serve para `.ps1`/`.md` que tenham `uvicorn app.main:app` (passa a `uvicorn backend.main:app`).
Se algum teste alterava `app.db.DB_PATH`, passe a alterar `backend.database.connection.DB_PATH`.

## 3. Backend — antigo → novo

| Antes | Agora |
|---|---|
| `app/main.py` (todas as rotas) | `backend/main.py` + `backend/api/routes/*.py` |
| `app/config.py` | `backend/core/config.py` |
| `app/auth.py` | `backend/core/security.py` |
| `app/db.py` | `backend/database/connection.py` + `schema.py` (`init_db`) |
| `app/schemas.py` | `backend/schemas/{auth,kyc,accounts,deposits,transfers,fx,ai}.py` |
| `app/ledger.py` | `backend/services/ledger.py` |
| `app/iban.py` | `backend/services/iban.py` |
| `app/providers/*` | `backend/providers/*` |
| `app/ai/assistant.py` | `backend/ai/{assistant,prompts,intents}.py` |
| `app/ai/kyc.py` (+ `get_meta_client` duplicado) | `backend/ai/kyc.py` + `backend/ai/client.py` |
| `frontend/samples/` | `frontend/assets/samples/` |
| `scratch/test_transfers_currency.py` | `tests/integration/check_transfers_currency.py` |
| `scratch/append_novabank_css.py` | `scripts/legacy/` (obsoleto) |

Imports que continuam a funcionar: `from backend.schemas import UserLogin`,
`from backend.database import get_connection, transaction_scope, init_db`,
`from backend.ai.assistant import BankaoAssistant, extract_action_intent`.

Rotas (`/api/...`) e comportamento são os mesmos; comando de arranque: `uvicorn backend.main:app --reload`.

## 4. Frontend — antigo → novo

**`index.html`** (2 400 linhas) → casca de 70 linhas + `partials/`:
`layout/` (icons, sandbox-banner, sidebar, topbar, bottom-nav, mobile-menu, scripts), `pages/` (home, accounts,
payments, expenses, savings, operations, statement, copilot) e `modals/` (13 modais). O backend monta tudo em `GET /`.

**`app.js`** (3 700 linhas) → `js/` (carregado pela ordem de `partials/layout/scripts.html`):

| Módulo | Conteúdo |
|---|---|
| `core/config.js`, `state.js`, `format.js`, `currency.js`, `ui.js` | constantes, estado, `parseCleanNumber`/`formatMoney`, conversão de moeda, `toast`/`escapeHtml` |
| `features/auth/auth.js` | login, registo, logout |
| `features/dashboard/dashboard.js` | `loadUserData`, cartões de saldo, hero |
| `features/statement/statement.js` | extrato (datas, scroll progressivo) |
| `features/accounts/accounts-view.js`, `payments/payments.js` | vistas Contas e Pagamentos |
| `features/savings/` | `savings-store`, `savings-view`, `goals` (criar/editar/apagar), `deposit` (depósito manual) |
| `features/expenses/` | `expenses-data`, `-chart-controls`, `-budget`, `-view`, `-donut`, `-list`, `-form`, `-ai` |
| `features/operations/` | `tabs`, `deposit`, `transfer-confirm`, `internal-transfer`, `iban-validation`, `bank-transfer` |
| `features/copilot/` | `copilot`, `copilot-actions`, `copilot-chat-ui` |
| `features/shell/shell.js`, `qr/receive-qr.js`, `kyc/kyc.js` | navegação/menu móvel, receber por QR, KYC |
| `main.js` | arranque (`DOMContentLoaded`) |

**`style.css`** (6 200 linhas) → `css/main.css` (30 `@import`) em `base/`, `layout/`, `components/`, `dashboard/`, `features/`.
A divisão **preserva a ordem original** das regras, porque a cascata depende dela.

## 5. Alterações de comportamento (propositadas)

- **Registo corrigido:** `main.py` usava `datetime` sem o importar, por isso `POST /api/auth/register`
  falhava com erro 500 (`NameError`) depois de criar o utilizador. Agora devolve o token normalmente.
- A base de dados continua em `bankao.db` na raiz; passa a respeitar `DATABASE_PATH` do `.env` (por omissão igual).
