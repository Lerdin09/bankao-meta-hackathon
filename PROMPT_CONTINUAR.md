# Prompt para retomar — Página de Investimentos (BankAO)

Anexa o `bank.zip` e cola:

> Tens o projeto BankAO (FastAPI + SQLite, frontend HTML/CSS/JS puro). A página de Investimentos já existe e foi
> alinhada com o backend. Lê `PROMPT_CONTINUAR.md` e continua a partir do estado abaixo, sem reescrever o que funciona.
> Corre `pip install fastapi uvicorn python-dotenv "python-jose" bcrypt openai pillow "pydantic[email]" httpx pytest`
> e `pytest` (têm de passar todos, incluindo `tests/test_investments.py`).

## Estado atual
- Backend: `backend/api/routes/investments.py` (catálogo, detalhe com simulações, carteira, apply, externo, resgate,
  sync, sync-all, operações, notificações). Fornecedores em `backend/providers/investments.py` (adaptadores
  open_banking / bodiva / market_data, modo sandbox determinístico; ponto de ligação a APIs reais: `register_provider`).
- Alertas de vencimento (30/15/7/1 dias) gerados ao consultar notificações e no sync-all, sem duplicar.
- Vencimento automático (`_settle_matured`): ao consultar carteira/notificações ou sincronizar, ativos com
  `maturity_date <= hoje` fixam juros até ao vencimento (`settlement_value` no provider), creditam a conta (internos,
  chave idempotente `inv_mature_<id>`), passam a `vencido`, registam operação `vencimento` e notificam
  (`vencimento_liquidado`). Internos sem conta creditável ficam `ativo` (resgate manual). Juros param no vencimento.
- Evolução da carteira calculada a partir das datas de início e rendimento acumulado (linear).
- Frontend: `frontend/partials/pages/investments.html`, `frontend/js/features/investments/investments.js` (reescrito para
  o contrato real: `catalog.products`, `portfolio.investments/summary/allocations/evolution`, ids UUID entre aspas),
  `frontend/css/features/investments.css`. Modais usam `.modal-overlay` + `.active`.

## Por fazer (por prioridade)
1. Verificação no browser real (`uvicorn backend.main:app --reload`): só testado com jsdom; rever layout/mobile.
2. Compra/venda de ETFs e ações por unidades (preço × quantidade), operações `compra`/`venda`.
3. Reforço de aplicação existente: guardar tranches antes de alterar capital (juros pro-rata usam
   `amount_invested_minor` desde `start_date`).
4. Edição de investimentos externos.
5. APIs reais (BODIVA, corretoras) via `register_provider`, com cache e falhas por fornecedor.
6. ~~Filtro por período no histórico e exportação CSV.~~ FEITO (sem teste em browser/pytest — ambiente sem rede): select de período (30/90/365 dias, este ano, personalizado), contador e botão «Exportar CSV» em `investments.js`; `GET /api/investments/operations` aceita `limit` (1–1000, default 100) e o frontend pede 1000. Falta: correr `pytest` e validar no browser.

---

# Aba Cartões (BankAO) — estado atual

Ficheiros: `frontend/partials/pages/cards.html`, `frontend/js/features/cards/cards.js`, `frontend/css/features/cards.css`,
`backend/api/routes/cards.py`, `tests/test_cards.py`. Todo o CSS é limitado a `#view-cards` / `.cd-sheet*` (prefixo `cd-`).

## Feito
- Layout em 2 colunas (container query ≥920px): cartão + ações + detalhes à esquerda (sticky), separadores à direita; 1 coluna no telemóvel.
- Carrossel com snap, setas, pontos, inclinação 3D (rato), seleção por scroll; cartão realista (aspect-ratio 1.586, `cqw`).
- Visão geral (KPIs, anéis de limite, avisos ≥70/90%), Movimentos (pesquisa, filtros por tipo no servidor,
  agrupados por dia, detalhe em folha, exportação CSV), Despesas (gráfico 30 dias com tooltip, donut + categorias,
  variação vs mês anterior), Segurança (estado, toggles, limites em Kz com atalhos, cancelar com confirmação),
  Alertas (marcar uma/todas), Cartão virtual com pré-visualização.
- Correções: `openModal/closeModal/showNotification` não existiam (modais e toasts mortos) → folhas próprias `openCardsSheet/closeCardsSheet`
  e `toast()`; limites enviados em Kz como se fossem centavos → agora ×100 (a API usa centavos); datas UTC do SQLite parseadas com `parseApiDate`.
- Backend: `POST /api/cards/notifications/read-all`; `/spending` devolve `tx_count, biggest_amount, biggest_merchant, avg_daily, prev_month_total`.
- Testes novos em `tests/test_cards.py` (`test_spending_has_extra_stats`, `test_mark_all_notifications_read`).

## Por verificar / fazer
1. Correr `pytest` (não foi possível no ambiente de desenvolvimento, sem rede) e abrir no browser real: rever mobile (≤420px) e iPad.
2. Congelar cartão por tempo / limites por categoria; alterar PIN; ver número completo com reautenticação (só se o backend guardar o PAN).
3. Pesquisa de movimentos no servidor (hoje filtra só os já carregados) e filtro por intervalo de datas.
4. Cartão de crédito: pagamento da fatura (UI do anel de crédito já existe).


---

# Contactos (separador em Operações) — estado atual

Ficheiros: `backend/api/routes/contacts.py`, `backend/schemas/contacts.py`, tabela `contacts` (em `database/schema.py`),
`frontend/js/features/contacts/contacts.js`, `frontend/css/features/contacts.css`, separador `tab-contacts` em
`frontend/partials/pages/operations.html` (o selector passou a 4 separadores), `tests/test_contacts.py`.

## Feito
- `GET /api/contacts` junta o histórico (tabela `transfers`: enviei a clientes BankAO, recebi de clientes BankAO, enviei por IBAN)
  com os contactos guardados (apelido, favorito). Quem já movimentou dinheiro aparece sozinho como «sugerido» (`saved: false`).
  Ordem: favoritos, depois o mais recente. Nunca expõe o e-mail de terceiros (só nome e nº de conta).
- `POST /api/contacts` (guardar/atualizar, idempotente), `PATCH /api/contacts/{id}`, `DELETE /api/contacts/{id}`
  (remove dos guardados; o histórico continua a sugeri-lo). Recusa conta própria, conta inexistente, IBAN inválido (Mod 97) e IBAN próprio.
- UI: pesquisa, filtros (Todos / Favoritos / Enviei / Recebi de / Clientes BankAO / IBAN), novo contacto, editar apelido, favorito, remover (com confirmação).
  «Enviar» muda para a transferência certa e pré-preenche conta BankAO ou IBAN + titular; só falta o valor.
- Verificado só com: lógica SQL real contra SQLite temporário (rotas chamadas diretamente) e interface no Chromium com a API simulada
  (desktop 1280px e telemóvel 390px). **Não** correu `pytest` nem a app real (sem rede para instalar FastAPI).

- Ficha do contacto (clicar na pessoa): `GET /api/contacts/history?key=&limit=&offset=` devolve as transferências com essa pessoa/IBAN
  (valor, nome, data, forma, saldo antes e depois — soma acumulada do livro-razão). No frontend (`ctOpenSheet`) carrega 10 de cada vez
  com IntersectionObserver; janela deslizante de no máximo 50 linhas no DOM (ao chegar às 60 carregadas, as 10 primeiras saem para um
  espaçador com a mesma altura e voltam ao subir; `ctdSyncToScroll` trata saltos grandes). Testado no Chromium com 75 itens simulados.

## Por fazer
1. Correr `pytest` (incl. `tests/test_contacts.py`) e abrir no browser real.
2. Oferecer «Guardar como contacto» no ecrã de sucesso depois de uma transferência (hoje basta o histórico + favorito).
3. Beneficiários de IBAN: permitir editar o nome do titular (hoje só o apelido).
4. Usar o contacto no Copilot («envia 5000 à Ana»).
