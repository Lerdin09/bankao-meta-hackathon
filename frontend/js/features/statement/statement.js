/**
 * Extrato
 * Filtro por datas, processamento progressivo por scroll e renderização dos movimentos.
 */

// ==========================================================================
// EXTRATO: INTERVALO DE DATAS + PROCESSAMENTO PROGRESSIVO POR SCROLL
// ==========================================================================
/**
 * O backend guarda datas em UTC ("YYYY-MM-DD HH:MM:SS" ou ISO sem fuso).
 * Sem o "Z" o browser trataria como hora local e mostraria a hora errada.
 */
function parseTxDate(raw) {
    if (raw instanceof Date) return raw;
    let s = String(raw == null ? "" : raw).trim();
    if (!s) return new Date(NaN);
    if (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(s)) s = s.replace(" ", "T") + "Z";
    return new Date(s);
}
window.parseTxDate = parseTxDate;
/** Índice id → movimento (usado pelo detalhe) */
const statementTxById = new Map();

const STATEMENT_PAGE_SIZE = 25;
let statementAllTxs        = [];
let statementFilteredTxs   = [];
let statementRenderedCount = 0;
let statementRangeFrom     = null;
  // Date | null
let statementRangeTo       = null;
  // Date | null
let statementScrollObserver = null;
let statementRangeTxs = [];
let statementTypeFilter = "all";
const STATEMENT_TYPE_FILTERS = [
    ["all", "Todos", "i-list"],
    ["purchases", "Compras", "i-card"],
    ["transfers", "Transferências", "i-swap"],
    ["deposits", "Depósitos", "i-down"],
    ["others", "Outros", "i-dots"],
];
// Atalhos de período: [chave, rótulo]
const STATEMENT_QUICK_RANGES = [["today", "Hoje"], ["7d", "7 dias"], ["30d", "30 dias"], ["month", "Este mês"], ["lastmonth", "Mês passado"]];
/** Classifica um movimento: compras, transferências, depósitos ou outros */
function classifyStatementTx(tx) {
    const t = String(tx.type || "").toLowerCase();
    if (t.includes("deposit")) return "deposits";
    if (t.startsWith("transfer")) return "transfers";
    const d = String(tx.description || "").toLowerCase();
    if (/pay|purchase|compra|card|cart[aã]o|merchant|refer[eê]ncia|reference|bill|fatura|multicaixa/.test(t) ||
        /compra|pagamento|refer[eê]ncia|multicaixa|fatura/.test(d)) return "purchases";
    return "others";
}
function renderStatementTypeChips() {
    const el = document.getElementById("statementTypeFilters");
    if (!el) return;
    const counts = { all: statementRangeTxs.length, purchases: 0, transfers: 0, deposits: 0, others: 0 };
    statementRangeTxs.forEach(tx => { counts[classifyStatementTx(tx)]++; });

    // Constrói uma só vez; depois só atualiza (assim as transições de cor/escala animam)
    if (el.children.length !== STATEMENT_TYPE_FILTERS.length) {
        el.innerHTML = STATEMENT_TYPE_FILTERS.map(([k, label, icon]) => `
            <button type="button" class="stmt-chip" data-k="${k}" onclick="setStatementTypeFilter('${k}')">
                <svg><use href="#${icon}"/></svg><span>${label}</span><em>0</em>
            </button>`).join("");
    }
    el.querySelectorAll(".stmt-chip").forEach(btn => {
        const k = btn.dataset.k;
        const on = statementTypeFilter === k;
        btn.classList.toggle("active", on);
        btn.setAttribute("aria-pressed", String(on));
        btn.querySelector("em").textContent = counts[k];
    });
    centerActiveChip(el);
}
/** Centra suavemente o chip ativo dentro do scroller horizontal */
function centerActiveChip(scroller) {
    const active = scroller && scroller.querySelector(".active");
    if (!active || scroller.scrollWidth <= scroller.clientWidth) return;
    const left = active.offsetLeft - (scroller.clientWidth - active.offsetWidth) / 2;
    scroller.scrollTo({ left: Math.max(0, left), behavior: "smooth" });
}
/** Intervalo [from, to] (datas locais, início do dia) de um atalho */
function statementQuickRange(key) {
    const [rawFrom, rawTo] = statementQuickRangeRaw(key);
    if (!rawFrom || !rawTo) return [rawFrom, rawTo];
    // Nunca antes da criação da conta (evita avisos desnecessários)
    const c = getAccountCreationDate();
    const minDay = new Date(c.getFullYear(), c.getMonth(), c.getDate());
    const from = rawFrom < minDay ? minDay : rawFrom;
    const to = rawTo < from ? from : rawTo;
    return [from, to];
}
function statementQuickRangeRaw(key) {
    const now = new Date();
    const day = (y, m, d) => new Date(y, m, d, 0, 0, 0, 0);
    const today = day(now.getFullYear(), now.getMonth(), now.getDate());
    switch (key) {
        case "today": return [today, today];
        case "7d": return [day(now.getFullYear(), now.getMonth(), now.getDate() - 6), today];
        case "30d": return [day(now.getFullYear(), now.getMonth(), now.getDate() - 29), today];
        case "month": return [day(now.getFullYear(), now.getMonth(), 1), today];
        case "lastmonth": return [day(now.getFullYear(), now.getMonth() - 1, 1), day(now.getFullYear(), now.getMonth(), 0)];
    }
    return [null, null];
}
function renderStatementQuickRanges() {
    const el = document.getElementById("statementQuickRanges");
    if (!el) return;
    if (el.children.length !== STATEMENT_QUICK_RANGES.length) {
        el.innerHTML = STATEMENT_QUICK_RANGES.map(([k, label]) => `
            <button type="button" class="stmt-chip stmt-chip--sm" data-q="${k}" onclick="setStatementQuickRange('${k}')">
                <svg><use href="#i-calendar"/></svg><span>${label}</span>
            </button>`).join("");
    }
    const same = (a, b) => (!a && !b) || (a && b && a.getTime() === b.getTime());
    el.querySelectorAll(".stmt-chip").forEach(btn => {
        const [f, t] = statementQuickRange(btn.dataset.q);
        const on = !!(statementRangeFrom || statementRangeTo) && same(f, statementRangeFrom) && same(t, statementRangeTo);
        btn.classList.toggle("active", on);
        btn.setAttribute("aria-pressed", String(on));
    });
    centerActiveChip(el);
}
window.setStatementQuickRange = function(key) {
    const [from, to] = statementQuickRange(key);
    const fromInp = document.getElementById("statementDateFrom");
    const toInp   = document.getElementById("statementDateTo");
    // Clicar no atalho já ativo volta a "ver tudo"
    if (statementRangeFrom && statementRangeTo && from && to &&
        statementRangeFrom.getTime() === from.getTime() && statementRangeTo.getTime() === to.getTime()) {
        clearStatementDateFilter();
        return;
    }
    if (fromInp) fromInp.value = toInputDate(from);
    if (toInp)   toInp.value   = toInputDate(to);
    applyStatementDateRange();
};
/** Scroller horizontal com esbatido nas margens que indica que há mais conteúdo */
function initHScrollers() {
    document.querySelectorAll("[data-hs]").forEach(box => {
        const track = box.querySelector(".hs-track");
        if (!track || box.dataset.hsReady) return;
        box.dataset.hsReady = "1";
        const update = () => {
            const max = track.scrollWidth - track.clientWidth;
            box.classList.toggle("can-left", track.scrollLeft > 4);
            box.classList.toggle("can-right", track.scrollLeft < max - 4);
        };
        track.addEventListener("scroll", update, { passive: true });
        window.addEventListener("resize", update);
        if (window.ResizeObserver) new ResizeObserver(update).observe(track);
        update();
    });
}
window.setStatementTypeFilter = function(k) {
    statementTypeFilter = k;
    refreshStatement();
};
/** Converte "YYYY-MM-DD" para Date local ao início do dia */
function parseDateLocal(str) {
    if (!str) return null;
    const parts = str.split("-").map(Number);
    if (parts.length !== 3 || parts.some(isNaN)) return null;
    return new Date(parts[0], parts[1] - 1, parts[2], 0, 0, 0, 0);
}
/** Formata Date para "YYYY-MM-DD" (input[type=date] value) */
function toInputDate(date) {
    if (!date || isNaN(date.getTime())) return "";
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
}
/** Retorna a data de criação da conta do utilizador (ou primeira transação como fallback) */
function getAccountCreationDate() {
    if (state.user && state.user.created_at) {
        const raw = String(state.user.created_at);
        const d = parseTxDate(raw);
        if (!isNaN(d.getTime())) return d;
    }
    if (statementAllTxs && statementAllTxs.length > 0) {
        const oldest = statementAllTxs[statementAllTxs.length - 1];
        if (oldest && oldest.created_at) {
            const d = parseTxDate(oldest.created_at);
            if (!isNaN(d.getTime())) return d;
        }
    }
    return new Date();
}
function buildTxRow(tx) {
    const date = parseTxDate(tx.created_at);
    const when = date.toLocaleDateString("pt-AO", { day: "2-digit", month: "short" }) + " · " +
                 date.toLocaleTimeString("pt-AO", { hour: "2-digit", minute: "2-digit" });
    const isCredit = (tx.amount_minor > 0) || (tx.amount_decimal > 0);
    const typeLabel = { deposit: "Depósito", transfer_iban: "Envio IBAN", transfer_internal: "Transferência", savings_deposit: "Poupança", savings_refund: "Resgate poupança" };
    const label = typeLabel[tx.type] || "Movimento";
    const iconUse = tx.type === "transfer_iban" ? "i-globe" : tx.type === "deposit" ? "i-down" : isCredit ? "i-down" : "i-up";
    const statusMap = { completed: "Concluído", failed: "Falhou" };
    const statusText = statusMap[tx.status] || "Pendente";
    const statusClass = statusMap[tx.status] ? tx.status : "pending";

    return `
        <div class="tx-item" data-tx-id="${escapeHtml(String(tx.id))}" role="button" tabindex="0" aria-label="Ver detalhe: ${escapeHtml(tx.description || label)}">
            <div class="tx-ic ${isCredit ? "credit" : "debit"}"><svg><use href="#${iconUse}"/></svg></div>
            <div class="tx-main">
                <div class="tx-title">${escapeHtml(tx.description || "Operação no BankAO")}</div>
                <div class="tx-sub">${label} · ${when}</div>
            </div>
            <div class="tx-side">
                <span class="tx-amount ${isCredit ? "credit" : "debit"}">${isCredit ? "+" : "−"}${formatMoney(Math.abs(tx.amount_decimal), tx.currency)}</span>
                <span class="status-tag ${statusClass}">${statusText}</span>
            </div>
        </div>`;
}
function applyStatementFilters() {
    statementRangeTxs = statementAllTxs.filter(tx => {
        const d = parseTxDate(tx.created_at);
        const dayStart = new Date(d.getFullYear(), d.getMonth(), d.getDate());
        if (statementRangeFrom && dayStart < statementRangeFrom) return false;
        if (statementRangeTo) {
            const toEnd = new Date(statementRangeTo);
            toEnd.setHours(23, 59, 59, 999);
            if (d > toEnd) return false;
        }
        return true;
    });
    statementFilteredTxs = statementTypeFilter === "all"
        ? statementRangeTxs
        : statementRangeTxs.filter(tx => classifyStatementTx(tx) === statementTypeFilter);
}
function updateStatementActiveBadge() {
    const badge     = document.getElementById("statementActiveBadge");
    const badgeText = document.getElementById("statementActiveBadgeText");
    const btnAll    = document.getElementById("btnSeeAllStatement");

    const hasRange = !!(statementRangeFrom || statementRangeTo);
    if (badge)  badge.style.display = hasRange ? "inline-flex" : "none";
    if (btnAll) btnAll.classList.toggle("active-filter", hasRange);

    if (badgeText && hasRange) {
        const fmt = d => d ? d.toLocaleDateString("pt-AO", { day: "2-digit", month: "short", year: "numeric" }) : "";
        if (statementRangeFrom && statementRangeTo) {
            badgeText.textContent = `${fmt(statementRangeFrom)} → ${fmt(statementRangeTo)}`;
        } else if (statementRangeFrom) {
            badgeText.textContent = `A partir de ${fmt(statementRangeFrom)}`;
        } else if (statementRangeTo) {
            badgeText.textContent = `Até ${fmt(statementRangeTo)}`;
        }
    }
}
function renderStatementBatch() {
    const full = document.getElementById("transactionsList");
    if (!full) return;

    const indicator  = document.getElementById("statementProcessingIndicator");
    const endBadge   = document.getElementById("statementEndBadge");
    const endText    = document.getElementById("statementEndBadgeText");
    const countBadge = document.getElementById("statementCountBadge");

    const slice = statementFilteredTxs.slice(statementRenderedCount, statementRenderedCount + STATEMENT_PAGE_SIZE);

    if (statementRenderedCount === 0) {
        full.innerHTML = "";
        if (statementFilteredTxs.length === 0) {
            full.innerHTML = `<div class="empty">Nenhum movimento encontrado com os filtros selecionados.</div>`;
            if (indicator)  indicator.style.display = "none";
            if (endBadge)   endBadge.style.display  = "flex";
            if (endText)    endText.textContent      = "Nenhum registo para este filtro.";
            if (countBadge) countBadge.textContent   = "0 movimentos";
            return;
        }
    }

    // Separadores visuais por data
    let lastDateStr = statementRenderedCount === 0 ? null
        : parseTxDate(statementFilteredTxs[statementRenderedCount - 1].created_at).toDateString();

    const fragment = document.createDocumentFragment();
    const today     = new Date();
    const yesterday = new Date(); yesterday.setDate(today.getDate() - 1);

    slice.forEach(tx => {
        const d = parseTxDate(tx.created_at);
        const dateStr = d.toDateString();
        if (dateStr !== lastDateStr) {
            const sep = document.createElement("div");
            sep.className = "tx-date-group-header";
            sep.textContent =
                d.toDateString() === today.toDateString()     ? "Hoje"  :
                d.toDateString() === yesterday.toDateString() ? "Ontem" :
                d.toLocaleDateString("pt-AO", { weekday: "long", day: "2-digit", month: "long", year: "numeric" });
            fragment.appendChild(sep);
            lastDateStr = dateStr;
        }
        const wrap = document.createElement("div");
        wrap.innerHTML = buildTxRow(tx).trim();
        while (wrap.firstElementChild) {
            fragment.appendChild(wrap.firstElementChild);
        }
    });
    full.appendChild(fragment);
    statementRenderedCount += slice.length;

    if (countBadge) {
        const t = statementFilteredTxs.length;
        countBadge.textContent = `${t} movimento${t === 1 ? "" : "s"}` + (statementRenderedCount < t ? ` · a mostrar ${statementRenderedCount}` : "");
    }

    if (statementRenderedCount >= statementFilteredTxs.length) {
        if (indicator) indicator.style.display = "none";
        if (endBadge)  endBadge.style.display  = "flex";
        if (endText)   endText.textContent = `${statementFilteredTxs.length} movimento${statementFilteredTxs.length === 1 ? "" : "s"} — livro-razão completo e auditado.`;
        if (statementScrollObserver) statementScrollObserver.disconnect();
    } else {
        if (indicator) indicator.style.display = "flex";
        if (endBadge)  endBadge.style.display  = "none";
    }
}
function initStatementScroll() {
    const sentinel = document.getElementById("statementScrollSentinel");
    if (!sentinel) return;
    if (statementScrollObserver) statementScrollObserver.disconnect();
    statementScrollObserver = new IntersectionObserver(entries => {
        if (entries[0].isIntersecting && statementRenderedCount < statementFilteredTxs.length) {
            renderStatementBatch();
        }
    }, { rootMargin: "300px" });
    statementScrollObserver.observe(sentinel);
}
/**
 * Chamado quando o utilizador navega para o extrato OU quando muda os filtros.
 * Não refaz fetch — usa statementAllTxs já carregado.
 */
function refreshStatement() {
    statementRenderedCount = 0;
    const indicator = document.getElementById("statementProcessingIndicator");
    const endBadge  = document.getElementById("statementEndBadge");
    if (indicator) indicator.style.display = "none";
    if (endBadge)  endBadge.style.display  = "none";
    updateStatementActiveBadge();
    applyStatementFilters();
    renderStatementTypeChips();
    renderStatementQuickRanges();
    initHScrollers();
    renderStatementBatch();
    initStatementScroll();
    // Pequena animação de entrada da lista ao mudar de filtro
    const list = document.getElementById("transactionsList");
    if (list) {
        list.classList.remove("stmt-enter");
        void list.offsetWidth;
        list.classList.add("stmt-enter");
    }
}
/** Chamado pelo input "De" e "Até" */
function applyStatementDateRange() {
    const fromInp = document.getElementById("statementDateFrom");
    const toInp   = document.getElementById("statementDateTo");
    const fromVal = fromInp?.value;
    const toVal   = toInp?.value;

    const creationDate = getAccountCreationDate();
    const minDay = new Date(creationDate.getFullYear(), creationDate.getMonth(), creationDate.getDate());
    const today = new Date();
    today.setHours(23, 59, 59, 999);

    let parsedFrom = parseDateLocal(fromVal);
    let parsedTo   = parseDateLocal(toVal);

    // Se o utilizador tentar uma data anterior à criação da conta, ajusta para o dia da criação
    if (parsedFrom && parsedFrom < minDay) {
        parsedFrom = minDay;
        if (fromInp) fromInp.value = toInputDate(minDay);
        toast("A data de início não pode ser anterior à criação da sua conta.", "info");
    }

    // Se o utilizador tentar uma data no futuro além de hoje
    if (parsedTo && parsedTo > today) {
        parsedTo = new Date();
        if (toInp) toInp.value = toInputDate(parsedTo);
    }

    // Garantir coerência: "Até" não pode ser anterior a "De"
    if (parsedFrom && parsedTo && parsedTo < parsedFrom) {
        parsedTo = null;
        if (toInp) toInp.value = "";
        toast("A data final não pode ser anterior à data inicial.", "error");
    }

    statementRangeFrom = parsedFrom;
    statementRangeTo   = parsedTo;

    // Atualizar limites recíprocos nos inputs:
    // "De" não pode ultrapassar "Até"
    if (fromInp) {
        fromInp.max = statementRangeTo ? toInputDate(statementRangeTo) : toInputDate(new Date());
    }
    // "Até" não pode ser antes de "De"
    if (toInp) {
        toInp.min = statementRangeFrom ? toInputDate(statementRangeFrom) : toInputDate(minDay);
    }

    refreshStatement();
}
window.applyStatementDateRange = applyStatementDateRange;
/** "Ver tudo" — limpa filtros e repõe os limites padrão dos inputs */
function clearStatementDateFilter() {
    statementRangeFrom = null;
    statementRangeTo   = null;
    const fromInp = document.getElementById("statementDateFrom");
    const toInp   = document.getElementById("statementDateTo");
    if (fromInp) fromInp.value = "";
    if (toInp)   toInp.value   = "";
    initStatementDateRange();
    refreshStatement();
}
window.clearStatementDateFilter = clearStatementDateFilter;
/** Configura os limites dos inputs de data a partir da data de criação da conta */
function initStatementDateRange() {
    const creationDate = getAccountCreationDate();
    const minDateStr = toInputDate(creationDate);
    const maxDateStr = toInputDate(new Date());

    const fromInp = document.getElementById("statementDateFrom");
    const toInp   = document.getElementById("statementDateTo");
    if (fromInp) {
        fromInp.min = minDateStr;
        fromInp.max = statementRangeTo ? toInputDate(statementRangeTo) : maxDateStr;
    }
    if (toInp) {
        toInp.min = statementRangeFrom ? toInputDate(statementRangeFrom) : minDateStr;
        toInp.max = maxDateStr;
    }
}
window.initStatementDateRange = initStatementDateRange;
// Renderizar Movimentos — guarda tudo e atualiza o extrato se visível
function renderTransactions(txs) {
    const recent = document.getElementById("recentTx");

    statementAllTxs = (txs || []).slice().sort((a, b) => parseTxDate(b.created_at) - parseTxDate(a.created_at));

    statementTxById.clear();
    statementAllTxs.forEach(tx => statementTxById.set(String(tx.id), tx));

    initStatementDateRange();

    // Se o view de extrato estiver activo, atualiza imediatamente
    const stmtView = document.getElementById("view-statement");
    if (stmtView && stmtView.classList.contains("active")) {
        refreshStatement();
    }

    // Recentes no dashboard — sempre os 3 mais recentes
    if (recent) {
        recent.innerHTML = statementAllTxs.length
            ? statementAllTxs.slice(0, 3).map(buildTxRow).join("")
            : `<div class="empty">Nenhuma transação registada ainda.</div>`;
    }
}
