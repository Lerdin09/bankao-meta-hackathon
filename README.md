# BankAO — Carteira Digital para Angola e o Mundo

Meta Global AI Developer Hackathon. Backend **FastAPI + SQLite** (livro-razão) e frontend em
**HTML/CSS/JS puro**, com um assistente de IA (Copilot) sobre a Meta Model API.

## Como correr

```bash
pip install fastapi uvicorn python-dotenv "python-jose" bcrypt openai pillow "pydantic[email]"
cp .env.example .env            # opcional: chave da Meta Model API, SECRET_KEY, ...
uvicorn backend.main:app --reload
```

Abra <http://localhost:8000> (app) ou <http://localhost:8000/docs> (API). A base de dados `bankao.db`
é criada na raiz do projeto. Sem `MODEL_API_KEY` o Copilot usa um fallback local.

Testes: `pytest` (a partir da raiz). Para ver o `index.html` final já montado: `python scripts/build_index.py`.

## Estrutura

```
bankao/
├── backend/                    # API (pacote Python)
│   ├── main.py                 # cria a app: CORS, rotas, frontend
│   ├── core/                   # config.py (variáveis e caminhos) · security.py (JWT, passwords)
│   ├── database/               # connection.py (SQLite/WAL) · schema.py (tabelas, migrações, seed)
│   ├── schemas/                # modelos Pydantic, um ficheiro por domínio
│   ├── services/               # regras de negócio: ledger.py (livro-razão) · iban.py
│   ├── providers/              # integrações simuladas: deposits.py · fx.py · payout.py
│   ├── ai/                     # client.py · prompts.py · intents.py · assistant.py · kyc.py
│   ├── api/
│   │   ├── __init__.py         # api_router: junta todas as rotas
│   │   └── routes/             # um ficheiro por domínio: auth, kyc, accounts, deposits,
│   │                           #   users, transfers, iban, fx, transactions, ai
│   └── web/                    # includes.py (montagem de partials) · frontend.py (/ e /static)
│
├── frontend/
│   ├── index.html              # casca: só <!-- @include ... --> e a ordem dos blocos
│   ├── partials/
│   │   ├── layout/             # ícones, banner, sidebar, topbar, bottom-nav, menu móvel, scripts
│   │   ├── pages/              # uma página por ficheiro: home, accounts, payments, expenses,
│   │   │                       #   savings, operations, statement, copilot
│   │   └── modals/             # um modal por ficheiro
│   ├── css/
│   │   ├── main.css            # lista de @import (a ORDEM é a ordem da cascata)
│   │   ├── base/               # tokens (variáveis), reset
│   │   ├── layout/             # shell, sidebar, bottom-nav, breakpoints, acabamento responsivo
│   │   ├── components/         # modais, toasts, copilot, cartões, filtros…
│   │   ├── dashboard/          # estilos da página inicial
│   │   └── features/           # um ficheiro por funcionalidade/página
│   ├── js/
│   │   ├── core/               # config, state, format (valores), currency, ui (toast…)
│   │   ├── features/           # auth, dashboard, statement, accounts, payments, savings,
│   │   │                       #   expenses, operations, copilot, shell, qr, kyc
│   │   └── main.js             # arranque (DOMContentLoaded) — carrega por último
│   └── assets/samples/         # imagens de demonstração do KYC
│
├── tests/                      # pytest + integration/ (scripts manuais)
├── tools/                      # utilitários de apoio: scrapers SWIFT e geradores de documentos/passaportes KYC
├── data/                       # bases de dados de suporte (atlas SWIFT e caches de scraping)
├── scripts/                    # build_index.py · migrate_imports.py · legacy/
└── docs/MIGRACAO.md            # mapa ficheiro antigo → novo
```

## Como acrescentar código

**Nova rota da API** — crie `backend/api/routes/<nome>.py` com
`router = APIRouter(prefix="/api/<nome>", tags=[...])` e acrescente `<nome>` à lista em
`backend/api/__init__.py`. Modelos de entrada/saída vão em `backend/schemas/<nome>.py` (e são
reexportados em `schemas/__init__.py`); regras de negócio em `backend/services/`.

**Nova página** (ex.: `view-cartoes`)
1. `frontend/partials/pages/cartoes.html` com `<section class="view" id="view-cartoes">…</section>`
2. uma linha `<!-- @include partials/pages/cartoes.html -->` em `index.html` (junto das outras páginas)
3. `frontend/css/features/cartoes.css` + `@import` em `css/main.css` (antes de `layout/responsive-polish.css`)
4. `frontend/js/features/cartoes/cartoes.js` + `<script>` em `partials/layout/scripts.html` (antes de `main.js`)
5. entrada no menu em `partials/layout/sidebar.html` / `bottom-nav.html` / `mobile-menu.html`

**Novo modal** — um ficheiro em `partials/modals/` e uma linha `@include` em `index.html`.

**Regras do frontend**
- Os scripts são clássicos (não módulos) e partilham o mesmo escopo global; funções chamadas por
  `onclick="…"` têm de ser globais (`function nome(){}` ou `window.nome = …`).
- Evite lógica que corra logo no carregamento do ficheiro: ligue eventos em funções `initXxx()` chamadas
  por `main.js` (`DOMContentLoaded`). Por serem código legado, `payments/payments.js` e `savings/goals.js`
  ainda ligam alguns eventos ao carregar — mantidos como no original.
- CSS: a ordem importa. Variáveis novas em `base/tokens.css`; estilos de uma funcionalidade no
  seu ficheiro de `features/`.
- `pytest tests/test_frontend_structure.py` avisa se esquecer de ligar um `.js`/`.css`/partial.

## Notas

- Os dados de poupanças, despesas e orçamentos do frontend ficam em `localStorage` (por browser).
- A base de dados SQLite (`bankao.db`) é ignorada pelo Git (ver `.gitignore`).
