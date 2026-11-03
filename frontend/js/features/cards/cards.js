/**
 * Módulo de Cartões
 * Liga a vista cards.html aos endpoints /api/cards/*.
 * Carrossel, visão geral, movimentos (pesquisa, filtros, detalhe, CSV),
 * despesas (gráfico + categorias), segurança, alertas e cartão virtual.
 * Valores monetários da API de definições/limites estão em centavos (minor).
 */

/* ─── Estado ─────────────────────────────────────────────────────────────── */
const CARDS = {
    list: [],
    selectedId: null,
    movements: [],      // lista filtrada pelo servidor (tipo de operação)
    movTotal: 0,
    movLimit: 20,
    movOpFilter: "all",
    movSearch: "",
    recent: [],         // últimos movimentos sem filtro (visão geral)
    spending: null,
    notifications: [],
    tab: "overview",
    loadedOnce: false,
    seq: 0,             // evita respostas fora de ordem ao trocar de cartão
    scrollLock: 0,
};

const CAT_ICONS = {
    alimentacao: "🛒", restaurante: "🍽️", supermercado: "🛒", combustivel: "⛽",
    transporte: "🚖", saude: "💊", educacao: "🎓", vestuario: "👗",
    eletronicos: "💻", lazer: "🎬", viagens: "✈️", telecomunicacoes: "📱",
    servicos: "⚙️", levantamento: "🏧", outros: "💳",
};
const CAT_COLORS = ["#38BDF8", "#34D399", "#F59E0B", "#818CF8", "#EC4899", "#FB923C", "#A78BFA", "#6EE7B7"];
const CARDS_TABS = ["overview", "movements", "spending", "security", "alerts"];
const OP_LABELS = { compra: "Compra", levantamento: "Levantamento", reembolso: "Reembolso", pagamento: "Pagamento", taxa: "Taxa" };
const STATUS_LABELS = { completed: "Concluído", pending: "Pendente", reversed: "Revertido", failed: "Falhado" };

/* ─── Inicialização ─────────────────────────────────────────────────────── */
function initCards() {
    const root = document.getElementById("view-cards");
    if (!root) return;

    // Filtros de tipo (servidor)
    document.getElementById("cardsMovFilter")?.addEventListener("click", e => {
        const btn = e.target.closest(".cd-chip[data-op]");
        if (!btn) return;
        document.querySelectorAll("#cardsMovFilter .cd-chip").forEach(b => b.classList.toggle("active", b === btn));
        CARDS.movOpFilter = btn.dataset.op;
        reloadMovements();
    });

    // Pesquisa (cliente, com debounce)
    let t;
    document.getElementById("cdMovSearch")?.addEventListener("input", e => {
        clearTimeout(t);
        t = setTimeout(() => { CARDS.movSearch = e.target.value.trim().toLowerCase(); renderMovements(); }, 160);
    });

    // Abrir detalhe de movimento (delegação)
    root.addEventListener("click", e => {
        const row = e.target.closest("[data-mid]");
        if (row) openMovementDetail(row.dataset.mid);
        const notif = e.target.closest("[data-read]");
        if (notif) markCardNotifRead(notif.dataset.read);
    });

    // Atalhos de valor (limites)
    root.addEventListener("click", e => {
        const b = e.target.closest(".cd-presets button");
        if (!b) return;
        const inp = document.getElementById(b.parentElement.dataset.target);
        if (inp) { inp.value = groupKz(b.dataset.v); inp.dispatchEvent(new Event("input", { bubbles: true })); }
    });

    // Campos de valor: só dígitos, com separador de milhares
    ["cLimitDailyInput", "cLimitMonthlyInput", "mvcLimitInput"].forEach(id => {
        document.getElementById(id)?.addEventListener("input", e => {
            e.target.value = groupKz(e.target.value);
            hideError("cdLimitsError");
        });
    });

    // Setas e rolagem do carrossel
    document.getElementById("cdPrev")?.addEventListener("click", () => stepCard(-1));
    document.getElementById("cdNext")?.addEventListener("click", () => stepCard(1));
    let st;
    document.getElementById("cardsCarousel")?.addEventListener("scroll", () => {
        clearTimeout(st);
        st = setTimeout(syncSelectionFromScroll, 120);
    }, { passive: true });

    // Inclinação 3D do cartão (só rato)
    const car = document.getElementById("cardsCarousel");
    if (car && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
        car.addEventListener("pointermove", e => {
            if (e.pointerType !== "mouse") return;
            const c = e.target.closest(".bank-card");
            if (!c) return;
            const r = c.getBoundingClientRect();
            const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
            c.style.setProperty("--rx", `${((0.5 - y) * 9).toFixed(2)}deg`);
            c.style.setProperty("--ry", `${((x - 0.5) * 11).toFixed(2)}deg`);
            c.style.setProperty("--mx", `${(x * 100).toFixed(0)}%`);
            c.style.setProperty("--my", `${(y * 100).toFixed(0)}%`);
        });
        car.addEventListener("pointerout", e => {
            const c = e.target.closest(".bank-card");
            if (c) { c.style.removeProperty("--rx"); c.style.removeProperty("--ry"); }
        });
    }

    // Teclado nos separadores
    document.querySelector(".cd-tabs")?.addEventListener("keydown", e => {
        if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
        const i = CARDS_TABS.indexOf(CARDS.tab) + (e.key === "ArrowRight" ? 1 : -1);
        const next = CARDS_TABS[(i + CARDS_TABS.length) % CARDS_TABS.length];
        switchCardsTab(next);
        document.getElementById(tabBtnId(next))?.focus();
    });

    // Pré-visualização do cartão virtual
    document.getElementById("mvcLabel")?.addEventListener("input", updateVirtualPreview);
    document.getElementById("mvcExpireDays")?.addEventListener("change", updateVirtualPreview);
    document.getElementById("mccAck")?.addEventListener("change", e => {
        const b = document.getElementById("mccConfirmBtn");
        if (b) b.disabled = !e.target.checked;
    });

    // Folhas: fechar ao clicar fora e com Esc
    document.querySelectorAll(".cd-sheet-overlay").forEach(ov => {
        ov.addEventListener("click", e => { if (e.target === ov) closeCardsSheet(ov.id); });
    });
    document.addEventListener("keydown", e => {
        if (e.key === "Escape") document.querySelectorAll(".cd-sheet-overlay.active").forEach(o => closeCardsSheet(o.id));
    });

    try { const saved = sessionStorage.getItem("cd_tab"); if (CARDS_TABS.includes(saved)) CARDS.tab = saved; } catch (e) { /* sem storage */ }
    switchCardsTab(CARDS.tab, false, true);
}

/* ─── Carregamento ──────────────────────────────────────────────────────── */
async function loadCardsData(manual) {
    if (!state.token) return;
    const btn = document.getElementById("btnRefreshCards");
    if (!CARDS.loadedOnce) showSkeletons();
    if (btn) btn.classList.add("is-loading");
    try {
        const data = await apiRequest("GET", "/api/cards/");
        CARDS.list = data.cards || [];
        if (!CARDS.list.some(c => c.id === CARDS.selectedId)) {
            CARDS.selectedId = (CARDS.list.find(c => c.status === "active") || CARDS.list[0] || {}).id || null;
        }
        CARDS.loadedOnce = true;
        renderCardsView();
        if (manual) cardsToast("Cartões atualizados.", "success");
    } catch (err) {
        console.error("Erro ao carregar cartões:", err);
        if (!CARDS.loadedOnce) renderLoadError();
        else cardsToast(err.message || "Não foi possível atualizar os cartões.", "error");
    } finally {
        if (btn) btn.classList.remove("is-loading");
    }
}

async function loadSelectedCardData() {
    const id = CARDS.selectedId;
    if (!id) return;
    const seq = ++CARDS.seq;
    setListLoading(true);
    try {
        const opQ = CARDS.movOpFilter !== "all" ? `&op_type=${encodeURIComponent(CARDS.movOpFilter)}` : "";
        const [movData, recentData, spendData, notifData] = await Promise.all([
            apiRequest("GET", `/api/cards/${id}/movements?limit=${CARDS.movLimit}&offset=0${opQ}`),
            CARDS.movOpFilter === "all" ? null : apiRequest("GET", `/api/cards/${id}/movements?limit=5&offset=0`),
            apiRequest("GET", `/api/cards/${id}/spending`),
            apiRequest("GET", "/api/cards/notifications/list"),
        ]);
        if (seq !== CARDS.seq || id !== CARDS.selectedId) return; // resposta antiga
        CARDS.movements = movData.movements || [];
        CARDS.movTotal = movData.total || 0;
        CARDS.recent = (recentData ? recentData.movements : CARDS.movements).slice(0, 5);
        CARDS.spending = spendData;
        CARDS.notifications = notifData.notifications || [];
        setListLoading(false);
        renderOverviewTab();
        renderMovements();
        renderSpending();
        renderNotifications();
    } catch (err) {
        if (seq !== CARDS.seq) return;
        setListLoading(false);
        console.error("Erro ao carregar detalhe do cartão:", err);
        cardsToast(err.message || "Erro ao carregar os dados do cartão.", "error");
    }
}

async function reloadMovements() {
    const id = CARDS.selectedId;
    if (!id) return;
    const seq = ++CARDS.seq;
    const list = document.getElementById("cardsMovementsList");
    if (list) list.innerHTML = skeletonRows(4);
    try {
        const opQ = CARDS.movOpFilter !== "all" ? `&op_type=${encodeURIComponent(CARDS.movOpFilter)}` : "";
        const d = await apiRequest("GET", `/api/cards/${id}/movements?limit=${CARDS.movLimit}&offset=0${opQ}`);
        if (seq !== CARDS.seq) return;
        CARDS.movements = d.movements || [];
        CARDS.movTotal = d.total || 0;
        renderMovements();
    } catch (err) {
        cardsToast(err.message || "Erro ao filtrar movimentos.", "error");
    }
}

async function loadMoreMovements() {
    if (!CARDS.selectedId) return;
    const btn = document.getElementById("cardsLoadMoreBtn");
    if (btn) { btn.disabled = true; btn.textContent = "A carregar…"; }
    try {
        const opQ = CARDS.movOpFilter !== "all" ? `&op_type=${encodeURIComponent(CARDS.movOpFilter)}` : "";
        const d = await apiRequest("GET", `/api/cards/${CARDS.selectedId}/movements?limit=${CARDS.movLimit}&offset=${CARDS.movements.length}${opQ}`);
        CARDS.movements.push(...(d.movements || []));
        CARDS.movTotal = d.total || CARDS.movTotal;
        renderMovements();
    } catch (err) {
        cardsToast(err.message || "Erro ao carregar movimentos.", "error");
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = "Carregar mais movimentos"; }
    }
}

/* ─── Renderização principal ────────────────────────────────────────────── */
function currentCard() { return CARDS.list.find(c => c.id === CARDS.selectedId) || null; }

function renderCardsView() {
    renderCarousel();
    renderInfoStrip();
    if (CARDS.selectedId) {
        renderSecurityTab();
        renderOverviewTab();
        loadSelectedCardData();
    } else {
        ["cardsMovementsPreview", "cardsMovementsList", "cardsCatList", "cardsNotifsList"].forEach(id => {
            const el = document.getElementById(id); if (el) el.innerHTML = "";
        });
    }
}

/* ── Carrossel ───────────────────────────────────────────────────────────── */
function renderCarousel() {
    const carousel = document.getElementById("cardsCarousel");
    const dots = document.getElementById("cardsCarouselDots");
    if (!carousel) return;

    if (CARDS.list.length === 0) {
        carousel.innerHTML = `
        <button type="button" class="cd-add-tile cd-add-tile-only" onclick="openVirtualCardModal()">
            <span class="cd-add-plus"><svg><use href="#i-plus"/></svg></span>
            <strong>Ainda não tem cartões</strong>
            <span>Crie um cartão virtual para começar</span>
        </button>`;
        if (dots) dots.innerHTML = "";
        toggleArrows();
        setActionsEnabled(false);
        return;
    }
    carousel.innerHTML = CARDS.list.map(buildCardVisual).join("") + `
        <button type="button" class="cd-add-tile" onclick="openVirtualCardModal()" aria-label="Criar cartão virtual">
            <span class="cd-add-plus"><svg><use href="#i-plus"/></svg></span>
            <strong>Novo cartão virtual</strong>
        </button>`;
    if (dots) {
        dots.innerHTML = CARDS.list.map((c, i) =>
            `<button type="button" class="cd-dot ${c.id === CARDS.selectedId ? "active" : ""}" role="tab" aria-selected="${c.id === CARDS.selectedId}" aria-label="Cartão ${i + 1}, terminado em ${escCards(c.last_four)}" onclick="selectCard('${c.id}')"></button>`
        ).join("");
    }
    toggleArrows();
    setActionsEnabled(true);
    scrollToCard(CARDS.selectedId, false);
}

function buildCardVisual(card) {
    const scheme = card.color_scheme || "blue";
    const isSel = card.id === CARDS.selectedId;
    const status = card.status !== "active" ? card.status : "";
    const veil = card.status === "blocked"
        ? `<div class="bank-card-veil"><svg><use href="#i-lock"/></svg><span>Bloqueado</span></div>`
        : card.status === "cancelled"
        ? `<div class="bank-card-veil"><svg><use href="#i-x"/></svg><span>Cancelado</span></div>` : "";
    const tag = card.is_virtual
        ? `<span class="bank-card-virtual-badge">${card.is_single_use ? "Virtual · 1 uso" : "Virtual"}</span>` : "";
    const name = card.is_virtual && card.label ? card.label : (card.cardholder_name || "");
    const exp = `${String(card.expires_month).padStart(2, "0")}/${String(card.expires_year).slice(-2)}`;
    return `
    <div class="bank-card scheme-${scheme} ${status} ${isSel ? "selected" : ""}" role="button" tabindex="0"
         aria-label="Cartão ${escCards(card.network)} terminado em ${escCards(card.last_four)}${isSel ? ", selecionado" : ""}"
         onclick="selectCard('${card.id}')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();selectCard('${card.id}')}"
         data-card-id="${card.id}" id="bankCard_${card.id}">
        <span class="bank-card-shine" aria-hidden="true"></span>
        <div class="bank-card-top">
            <span class="bank-card-inst">${escCards(card.institution || "BankAO")}</span>
            ${tag}
        </div>
        <div class="bank-card-mid">
            <div class="bank-card-chip" aria-hidden="true"></div>
            <svg class="bank-card-nfc" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 6c3 3.5 3 8.5 0 12M12 4c4.4 4.5 4.4 11.5 0 16M16 2c5.8 5.5 5.8 14.5 0 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
        </div>
        <div class="bank-card-number">•••• •••• •••• ${escCards(card.last_four)}</div>
        <div class="bank-card-bottom">
            <div class="bank-card-holder-group">
                <span class="bank-card-expiry-label">${card.is_virtual ? "Nome" : "Titular"}</span>
                <span class="bank-card-holder">${escCards(name)}</span>
            </div>
            <div class="bank-card-expiry-group">
                <span class="bank-card-expiry-label">Válido até</span>
                <span class="bank-card-expiry">${exp}</span>
            </div>
            <div class="bank-card-network">${buildNetworkBadge(card.network)}</div>
        </div>
        ${veil}
    </div>`;
}

function buildNetworkBadge(network) {
    if (network === "visa") return `<span class="bank-card-network-visa">VISA</span>`;
    if (network === "mastercard") return `<div class="bank-card-network-circles"><span></span><span></span></div>`;
    return `<span class="bank-card-network-multicaixa">Multicaixa</span>`;
}

function selectCard(cardId, opts) {
    if (!CARDS.list.some(c => c.id === cardId)) return;
    const changed = cardId !== CARDS.selectedId;
    CARDS.selectedId = cardId;
    document.querySelectorAll(".bank-card").forEach(el => el.classList.toggle("selected", el.dataset.cardId === cardId));
    document.querySelectorAll(".cd-dot").forEach((dot, i) => {
        const on = CARDS.list[i]?.id === cardId;
        dot.classList.toggle("active", on);
        dot.setAttribute("aria-selected", on);
    });
    if (!(opts && opts.noScroll)) scrollToCard(cardId, true);
    toggleArrows();
    if (!changed) return;
    CARDS.movOpFilter = "all";
    CARDS.movSearch = "";
    const s = document.getElementById("cdMovSearch"); if (s) s.value = "";
    document.querySelectorAll("#cardsMovFilter .cd-chip").forEach(b => b.classList.toggle("active", b.dataset.op === "all"));
    renderInfoStrip();
    renderSecurityTab();
    renderOverviewTab();
    loadSelectedCardData();
}

function stepCard(dir) {
    const i = CARDS.list.findIndex(c => c.id === CARDS.selectedId);
    const next = CARDS.list[i + dir];
    if (next) selectCard(next.id);
}

function toggleArrows() {
    const i = CARDS.list.findIndex(c => c.id === CARDS.selectedId);
    const multi = CARDS.list.length > 1;
    const p = document.getElementById("cdPrev"), n = document.getElementById("cdNext");
    if (p) p.hidden = !multi || i <= 0;
    if (n) n.hidden = !multi || i >= CARDS.list.length - 1;
}

function scrollToCard(cardId, smooth) {
    const car = document.getElementById("cardsCarousel");
    const el = document.getElementById(`bankCard_${cardId}`);
    if (!car || !el) return;
    CARDS.scrollLock = Date.now();
    const left = el.offsetLeft - (car.clientWidth - el.clientWidth) / 2;
    car.scrollTo({ left: Math.max(0, left), behavior: smooth ? "smooth" : "auto" });
}

function syncSelectionFromScroll() {
    if (Date.now() - CARDS.scrollLock < 650) return; // movimento programático
    const car = document.getElementById("cardsCarousel");
    if (!car) return;
    const mid = car.scrollLeft + car.clientWidth / 2;
    let best = null, bestD = Infinity;
    car.querySelectorAll(".bank-card").forEach(el => {
        const d = Math.abs(el.offsetLeft + el.clientWidth / 2 - mid);
        if (d < bestD) { bestD = d; best = el; }
    });
    if (best && best.dataset.cardId !== CARDS.selectedId) selectCard(best.dataset.cardId, { noScroll: true });
}

function setActionsEnabled(on) {
    document.querySelectorAll("#cardsQuickActions .cd-action").forEach(b => {
        if (!b.getAttribute("onclick")?.includes("openVirtualCardModal")) b.disabled = !on;
    });
}

/* ── Detalhes ────────────────────────────────────────────────────────────── */
function renderInfoStrip() {
    const strip = document.getElementById("cardInfoStrip");
    const card = currentCard();
    if (strip) strip.hidden = !card;
    if (!card) return;
    const NET = { visa: "Visa", mastercard: "Mastercard", multicaixa: "Multicaixa" };
    const TYPE = { debit: "Débito", credit: "Crédito", virtual: "Virtual" };
    const ST = { active: "Ativo", blocked: "Bloqueado", cancelled: "Cancelado" };
    setText("cInfoHolder", card.cardholder_name || "—");
    setText("cInfoExpiry", `${String(card.expires_month).padStart(2, "0")}/${card.expires_year}`);
    setText("cInfoNetwork", `${NET[card.network] || card.network} · ${TYPE[card.card_type] || card.card_type}`);
    const st = document.getElementById("cInfoStatus");
    if (st) st.innerHTML = `<span class="cd-badge ${card.status}">${ST[card.status] || escCards(card.status)}</span>`;
    setText("cInfoInst", card.institution || "BankAO");
    const d = parseApiDate(card.created_at);
    setText("cInfoCreated", d ? d.toLocaleDateString("pt-AO", { day: "2-digit", month: "short", year: "numeric" }) : "—");
}

/* ── 1 · Visão geral ─────────────────────────────────────────────────────── */
function renderOverviewTab() {
    const card = currentCard();
    if (!card) return;
    const cur = card.currency || "AOA";
    const dPct = pctOf(card.daily_spent, card.daily_limit);
    const mPct = pctOf(card.monthly_spent, card.monthly_limit);

    setHtml("cdRingDaily", ringSvg(dPct));
    setHtml("cdRingMonthly", ringSvg(mPct));
    setText("cLimitDailyUsed", fmt(card.daily_spent, cur));
    setText("cLimitDailyRemain", card.daily_limit > 0 ? `${fmt(Math.max(0, card.daily_limit - card.daily_spent), cur)} disponível de ${fmtCompact(card.daily_limit, cur)}` : "Sem limite definido");
    setText("cLimitMonthlyUsed", fmt(card.monthly_spent, cur));
    setText("cLimitMonthlyRemain", card.monthly_limit > 0 ? `${fmt(Math.max(0, card.monthly_limit - card.monthly_spent), cur)} disponível de ${fmtCompact(card.monthly_limit, cur)}` : "Sem limite definido");

    const credit = document.getElementById("cCreditCard");
    if (credit) {
        const on = card.card_type === "credit" && card.credit_limit > 0;
        credit.hidden = !on;
        if (on) {
            setHtml("cdRingCredit", ringSvg(pctOf(card.credit_used, card.credit_limit)));
            setText("cCreditAvail", fmt(card.credit_available, cur));
            setText("cCreditUsed", `${fmt(card.credit_used, cur)} utilizado de ${fmtCompact(card.credit_limit, cur)}`);
        }
    }

    // Aviso contextual
    const al = document.getElementById("cdLimitAlert");
    if (al) {
        let msg = "", kind = "";
        if (card.status === "blocked") { msg = "Este cartão está bloqueado. Nenhuma transação será aprovada até o desbloquear."; kind = "info"; }
        else if (card.status === "cancelled") { msg = "Este cartão foi cancelado e já não pode ser utilizado."; kind = "danger"; }
        else if (mPct >= 90) { msg = `Já utilizou ${Math.round(mPct)}% do limite mensal. Considere aumentar o limite ou rever as despesas.`; kind = "danger"; }
        else if (dPct >= 90) { msg = `Já utilizou ${Math.round(dPct)}% do limite diário.`; kind = "warn"; }
        else if (mPct >= 70) { msg = `Atenção: ${Math.round(mPct)}% do limite mensal já foi utilizado.`; kind = "warn"; }
        al.hidden = !msg;
        al.className = `cd-alert ${kind}`;
        al.textContent = msg;
    }

    // KPIs
    const sp = CARDS.spending;
    setText("cdKpiMonth", sp ? fmtCompact(sp.monthly_total, cur) : fmtCompact(card.monthly_spent, cur));
    renderDelta("cdKpiMonthDelta", sp);
    setText("cdKpiToday", fmtCompact(card.daily_spent, cur));
    setText("cdKpiTodaySub", card.daily_limit > 0 ? `${Math.round(dPct)}% do limite` : "Sem limite");
    setText("cdKpiBiggest", sp ? fmtCompact(sp.biggest_amount || 0, cur) : "—");
    setText("cdKpiBiggestSub", sp && sp.biggest_merchant ? sp.biggest_merchant : "Neste mês");
    setText("cdKpiAvg", sp ? fmtCompact(sp.avg_daily || 0, cur) : "—");
    setText("cdKpiCount", sp ? `${sp.tx_count || 0} compra${sp.tx_count === 1 ? "" : "s"} no mês` : "—");

    updateBlockButton(card.status);

    const preview = document.getElementById("cardsMovementsPreview");
    const empty = document.getElementById("cardsEmptyMovements");
    if (preview) {
        if (CARDS.recent.length === 0 && CARDS.spending) {
            preview.innerHTML = ""; if (empty) empty.hidden = false;
        } else {
            if (empty) empty.hidden = true;
            preview.innerHTML = CARDS.recent.map(buildMovRow).join("");
        }
    }
}

function renderDelta(id, sp) {
    const el = document.getElementById(id);
    if (!el) return;
    if (!sp || !(sp.prev_month_total > 0)) { el.hidden = true; return; }
    const diff = ((sp.monthly_total - sp.prev_month_total) / sp.prev_month_total) * 100;
    const up = diff > 0.5, down = diff < -0.5;
    el.hidden = false;
    el.className = `cd-delta ${up ? "up" : down ? "down" : "flat"}`;
    el.textContent = `${up ? "▲" : down ? "▼" : "•"} ${Math.abs(diff).toFixed(0)}% vs mês anterior`;
}

function updateBlockButton(status) {
    const label = document.getElementById("cBtnBlockLabel");
    const btn = document.getElementById("cBtnBlock");
    const tLabel = document.getElementById("cToggleBlockLabel");
    const tBtn = document.getElementById("cToggleBlock");
    const iconUse = btn?.querySelector("use");
    const iconWrap = btn?.querySelector(".cd-action-icon");
    const txt = status === "blocked" ? "Desbloquear" : "Bloquear";
    if (label) label.textContent = txt;
    if (tLabel) tLabel.textContent = txt;
    if (iconWrap) iconWrap.className = `cd-action-icon ${status === "blocked" ? "ok" : "danger"}`;
    if (iconUse) iconUse.setAttribute("href", status === "blocked" ? "#i-key" : "#i-lock");
    if (btn) btn.disabled = status === "cancelled";
    if (tBtn) { tBtn.disabled = status === "cancelled"; tBtn.classList.toggle("unblock", status === "blocked"); }
}

/* ── 2 · Movimentos ──────────────────────────────────────────────────────── */
function visibleMovements() {
    const q = CARDS.movSearch;
    if (!q) return CARDS.movements;
    return CARDS.movements.filter(m =>
        `${m.merchant_name} ${formatCatLabel(m.merchant_category)} ${m.description} ${OP_LABELS[m.operation_type] || ""}`.toLowerCase().includes(q));
}

function renderMovements() {
    const list = document.getElementById("cardsMovementsList");
    const empty = document.getElementById("cardsEmptyMovsFull");
    const more = document.getElementById("cardsLoadMoreBtn");
    const sum = document.getElementById("cdMovSummary");
    if (!list) return;
    const items = visibleMovements();
    const cur = currentCard()?.currency || "AOA";

    if (more) more.hidden = CARDS.movements.length >= CARDS.movTotal;
    if (items.length === 0) {
        list.innerHTML = "";
        if (empty) empty.hidden = false;
        if (sum) sum.hidden = true;
        return;
    }
    if (empty) empty.hidden = true;

    let out = 0, inn = 0;
    items.forEach(m => { if (m.status === "reversed" || m.status === "failed") return; m.is_debit ? out += m.amount : inn += m.amount; });
    if (sum) {
        sum.hidden = false;
        setText("cdMovCount", CARDS.movements.length < CARDS.movTotal && !CARDS.movSearch
            ? `${items.length} de ${CARDS.movTotal} movimentos` : `${items.length} movimento${items.length === 1 ? "" : "s"}`);
        setText("cdMovOut", `−${fmt(out, cur)}`);
        setText("cdMovIn", `+${fmt(inn, cur)}`);
    }

    // Agrupar por dia
    let html = "", lastKey = "";
    items.forEach(m => {
        const d = parseApiDate(m.created_at);
        const key = d ? d.toDateString() : "—";
        if (key !== lastKey) { html += `<div class="cd-day">${dayLabel(d)}</div>`; lastKey = key; }
        html += buildMovRow(m);
    });
    list.innerHTML = html;
}

function buildMovRow(mov) {
    const cls = mov.is_debit ? "debit" : "credit";
    const icon = CAT_ICONS[mov.merchant_category] || "💳";
    const d = parseApiDate(mov.created_at);
    const time = d ? d.toLocaleTimeString("pt-AO", { hour: "2-digit", minute: "2-digit" }) : "";
    const chip = mov.status === "pending" ? `<span class="cd-pill pending">Pendente</span>`
        : mov.status === "reversed" ? `<span class="cd-pill reversed">Revertido</span>`
        : mov.status === "failed" ? `<span class="cd-pill failed">Falhado</span>` : "";
    const struck = mov.status === "reversed" || mov.status === "failed" ? " struck" : "";
    return `
    <button type="button" class="cd-mov" data-mid="${escCards(mov.id)}">
        <span class="cd-mov-icon ${cls}">${icon}</span>
        <span class="cd-mov-info">
            <span class="cd-mov-merchant">${escCards(mov.merchant_name)}</span>
            <span class="cd-mov-meta">${escCards(formatCatLabel(mov.merchant_category))}${time ? ` · ${time}` : ""} ${chip}</span>
        </span>
        <span class="cd-mov-amount ${cls}${struck}">${mov.is_debit ? "−" : "+"}${fmt(mov.amount, mov.currency)}</span>
    </button>`;
}

function openMovementDetail(id) {
    const m = [...CARDS.movements, ...CARDS.recent].find(x => String(x.id) === String(id));
    if (!m) return;
    const d = parseApiDate(m.created_at);
    setText("cmvSub", d ? d.toLocaleDateString("pt-AO", { weekday: "long", day: "numeric", month: "long", year: "numeric" }) : "—");
    setText("cmvIcon", CAT_ICONS[m.merchant_category] || "💳");
    const amt = document.getElementById("cmvAmount");
    if (amt) { amt.textContent = `${m.is_debit ? "−" : "+"}${fmt(m.amount, m.currency)}`; amt.className = m.is_debit ? "debit" : "credit"; }
    setText("cmvMerchant", m.merchant_name);
    const card = currentCard();
    const rows = [
        ["Data e hora", d ? d.toLocaleString("pt-AO", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"],
        ["Tipo", OP_LABELS[m.operation_type] || m.operation_type],
        ["Categoria", formatCatLabel(m.merchant_category)],
        ["Estado", STATUS_LABELS[m.status] || m.status],
        ["Cartão", card ? `${card.is_virtual && card.label ? card.label + " · " : ""}•••• ${card.last_four}` : "—"],
    ];
    if (m.description) rows.push(["Descrição", m.description]);
    rows.push(["Referência", String(m.id).slice(0, 8).toUpperCase()]);
    setHtml("cmvList", rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${escCards(v)}</dd></div>`).join(""));
    openCardsSheet("modalCardMovement");
}

async function exportCardMovements() {
    const card = currentCard();
    if (!card) { cardsToast("Selecione um cartão.", "error"); return; }
    try {
        let all = [], offset = 0, total = Infinity;
        while (offset < total && offset < 2000) {
            const d = await apiRequest("GET", `/api/cards/${card.id}/movements?limit=200&offset=${offset}`);
            all = all.concat(d.movements || []);
            total = d.total || 0;
            if (!(d.movements || []).length) break;
            offset = all.length;
        }
        if (!all.length) { cardsToast("Não há movimentos para exportar.", "error"); return; }
        const esc = v => `"${String(v ?? "").replace(/"/g, '""')}"`;
        const lines = [["Data", "Comerciante", "Categoria", "Tipo", "Estado", "Sinal", "Valor", "Moeda"].map(esc).join(";")];
        all.forEach(m => {
            const d = parseApiDate(m.created_at);
            lines.push([d ? d.toISOString().replace("T", " ").slice(0, 19) : "", m.merchant_name, formatCatLabel(m.merchant_category),
                OP_LABELS[m.operation_type] || m.operation_type, STATUS_LABELS[m.status] || m.status,
                m.is_debit ? "-" : "+", m.amount.toFixed(2).replace(".", ","), m.currency].map(esc).join(";"));
        });
        const blob = new Blob(["\uFEFF" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `cartao-${card.last_four}-movimentos.csv`;
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 1500);
        cardsToast(`${all.length} movimentos exportados com sucesso.`, "success");
    } catch (err) {
        cardsToast(err.message || "Erro ao exportar movimentos.", "error");
    }
}

/* ── 3 · Despesas ────────────────────────────────────────────────────────── */
function renderSpending() {
    const sp = CARDS.spending;
    if (!sp) return;
    const cur = currentCard()?.currency || "AOA";
    setText("cardsMonthTotal", fmt(sp.monthly_total, cur));
    renderDelta("cdSpendDelta", sp);
    if (sp.month_start) {
        const d = new Date(sp.month_start + "T00:00:00");
        setText("cardsSpendingPeriod", `1 de ${d.toLocaleString("pt-AO", { month: "long" })} — hoje`);
    }
    renderBarChart(sp.daily_evolution || [], cur);

    const catList = document.getElementById("cardsCatList");
    const empty = document.getElementById("cardsEmptySpending");
    const donut = document.getElementById("cdDonut");
    const cats = sp.by_category || [];
    if (!catList) return;
    const wrap = catList.parentElement;
    if (cats.length === 0 || !(sp.monthly_total > 0)) {
        catList.innerHTML = ""; if (donut) donut.style.background = "";
        if (wrap) wrap.hidden = true;
        if (empty) empty.hidden = false;
        return;
    }
    if (wrap) wrap.hidden = false;
    if (empty) empty.hidden = true;

    const total = cats.reduce((s, c) => s + c.total, 0) || 1;
    let acc = 0;
    const stops = cats.map((c, i) => {
        const from = (acc / total) * 100; acc += c.total;
        return `${CAT_COLORS[i % CAT_COLORS.length]} ${from.toFixed(2)}% ${((acc / total) * 100).toFixed(2)}%`;
    });
    if (donut) {
        donut.style.background = `conic-gradient(${stops.join(",")})`;
        donut.innerHTML = `<div class="cd-donut-center"><strong>${Math.round((cats[0].total / total) * 100)}%</strong><span>${escCards(formatCatLabel(cats[0].category))}</span></div>`;
    }
    catList.innerHTML = cats.map((c, i) => {
        const share = (c.total / total) * 100;
        const color = CAT_COLORS[i % CAT_COLORS.length];
        return `
        <div class="cd-cat">
            <span class="cd-cat-icon" style="--c:${color}">${CAT_ICONS[c.category] || "💳"}</span>
            <div class="cd-cat-info">
                <div class="cd-cat-top"><span class="cd-cat-name">${escCards(formatCatLabel(c.category))}</span><span class="cd-cat-amount">${fmt(c.total, cur)}</span></div>
                <div class="cd-cat-bar"><span style="width:${share.toFixed(1)}%;background:${color}"></span></div>
            </div>
            <span class="cd-cat-pct">${share.toFixed(0)}%</span>
        </div>`;
    }).join("");
}

function last30Days(daily) {
    const map = new Map(daily.map(d => [d.day, d.total]));
    const out = [];
    const base = new Date();
    for (let i = 29; i >= 0; i--) {
        const d = new Date(Date.UTC(base.getUTCFullYear(), base.getUTCMonth(), base.getUTCDate() - i));
        const key = d.toISOString().slice(0, 10);
        out.push({ day: key, total: map.get(key) || 0 });
    }
    return out;
}

function renderBarChart(daily, currency) {
    const el = document.getElementById("cardsBarChart");
    if (!el) return;
    const days = last30Days(daily);
    const sum = days.reduce((s, d) => s + d.total, 0);
    setText("cdChartNote", sum > 0 ? `Total ${fmtCompact(sum, currency)}` : "");
    if (sum <= 0) {
        el.innerHTML = `<div class="cd-chart-empty">Sem despesas nos últimos 30 dias</div>`;
        return;
    }
    const W = 600, H = 200, padT = 14;
    const max = Math.max(...days.map(d => d.total)) * 1.12;
    const step = W / (days.length - 1);
    const pts = days.map((d, i) => [i * step, padT + (H - padT) * (1 - d.total / max)]);
    const line = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
    const avgY = padT + (H - padT) * (1 - (sum / days.length) / max);
    const bw = Math.max(4, step * 0.58);
    const bars = days.map((d, i) => d.total > 0
        ? `<rect x="${(pts[i][0] - bw / 2).toFixed(1)}" y="${pts[i][1].toFixed(1)}" width="${bw.toFixed(1)}" height="${(H - pts[i][1]).toFixed(1)}" rx="3" fill="url(#cdBar)"/>` : "").join("");
    el.innerHTML = `
    <div class="cd-chart-plot" id="cdPlot">
        <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Despesas diárias dos últimos 30 dias">
            <defs>
                <linearGradient id="cdBar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#38BDF8" stop-opacity=".95"/><stop offset="1" stop-color="#6C9BFF" stop-opacity=".25"/></linearGradient>
            </defs>
            <g class="cd-grid">${[0.25, 0.5, 0.75].map(f => `<line x1="0" x2="${W}" y1="${(padT + (H - padT) * f).toFixed(1)}" y2="${(padT + (H - padT) * f).toFixed(1)}"/>`).join("")}</g>
            ${bars}
            <line class="cd-avg" x1="0" x2="${W}" y1="${avgY.toFixed(1)}" y2="${avgY.toFixed(1)}"/>
            <path class="cd-line" d="${line}"/>
        </svg>
        <div class="cd-guide" id="cdGuide" hidden></div>
        <div class="cd-tip" id="cdTip" hidden></div>
    </div>
    <div class="cd-axis"><span>${shortDay(days[0].day)}</span><span>${shortDay(days[14].day)}</span><span>${shortDay(days[29].day)}</span></div>`;

    const plot = document.getElementById("cdPlot"), tip = document.getElementById("cdTip"), guide = document.getElementById("cdGuide");
    const show = e => {
        const r = plot.getBoundingClientRect();
        const x = Math.min(Math.max((e.clientX - r.left) / r.width, 0), 1);
        const i = Math.round(x * (days.length - 1));
        const left = (i / (days.length - 1)) * 100;
        guide.hidden = tip.hidden = false;
        guide.style.left = `${left}%`;
        tip.style.left = `${Math.min(Math.max(left, 14), 86)}%`;
        tip.innerHTML = `<span>${shortDay(days[i].day, true)}</span><strong>${fmt(days[i].total, currency)}</strong>`;
    };
    plot.addEventListener("pointermove", show);
    plot.addEventListener("pointerdown", show);
    plot.addEventListener("pointerleave", () => { guide.hidden = tip.hidden = true; });
}

/* ── 4 · Segurança ───────────────────────────────────────────────────────── */
function renderSecurityTab() {
    const card = currentCard();
    if (!card) return;
    setToggle("cToggleOnline", card.online_payments);
    setToggle("cToggleIntl", card.international_payments);
    setToggle("cToggleAtm", card.atm_withdrawals);
    setToggle("cToggleNfc", card.contactless);

    const d = document.getElementById("cLimitDailyInput"), m = document.getElementById("cLimitMonthlyInput");
    if (d) d.value = card.daily_limit_minor ? groupKz(Math.round(card.daily_limit_minor / 100)) : "";
    if (m) m.value = card.monthly_limit_minor ? groupKz(Math.round(card.monthly_limit_minor / 100)) : "";
    hideError("cdLimitsError");

    const panel = document.getElementById("ctabPanelSecurity");
    if (panel) panel.classList.toggle("is-cancelled", card.status === "cancelled");
    document.querySelectorAll("#ctabPanelSecurity input, #cdLimitsSave").forEach(i => { i.disabled = card.status === "cancelled"; });

    const banner = document.getElementById("cdStatusBanner");
    const T = {
        active: ["Cartão ativo", "Pode ser usado normalmente, dentro dos limites e funcionalidades abaixo."],
        blocked: ["Cartão bloqueado", "Todas as transações estão a ser recusadas. Desbloqueie quando quiser voltar a usá-lo."],
        cancelled: ["Cartão cancelado", "Cancelado de forma permanente. Já não pode ser reativado nem alterado."],
    }[card.status] || ["Cartão", ""];
    if (banner) banner.className = `cd-status ${card.status}`;
    setText("cdStatusTitle", T[0]);
    setText("cdStatusDesc", T[1]);
    updateBlockButton(card.status);
}

function setToggle(id, value) {
    const el = document.getElementById(id);
    if (el) el.checked = Boolean(value);
}

async function updateCardToggle(field, value) {
    const card = currentCard();
    if (!card) return;
    try {
        await apiRequest("PATCH", `/api/cards/${card.id}/settings`, { [field]: value });
        card[field] = value;
        cardsToast(`${toggleLabel(field)} ${value ? "ativado" : "desativado"} com sucesso.`, "success");
    } catch (err) {
        cardsToast(err.message || "Erro ao atualizar definição.", "error");
        renderSecurityTab(); // reverter
    }
}

function toggleLabel(field) {
    return { online_payments: "Pagamentos online", international_payments: "Pagamentos internacionais",
        atm_withdrawals: "Levantamentos ATM", contactless: "Contactless" }[field] || field;
}

async function handleCardLimitsSubmit(event) {
    event.preventDefault();
    const card = currentCard();
    if (!card) return;
    const daily = digitsToInt(document.getElementById("cLimitDailyInput")?.value);
    const monthly = digitsToInt(document.getElementById("cLimitMonthlyInput")?.value);
    if (!daily && !monthly) return showError("cdLimitsError", "Indique pelo menos um limite.");
    if (daily && monthly && daily > monthly) return showError("cdLimitsError", "O limite diário não pode ser superior ao mensal.");
    const body = {};
    if (daily) body.daily_limit_minor = daily * 100;       // Kz → centavos
    if (monthly) body.monthly_limit_minor = monthly * 100;
    const btn = document.getElementById("cdLimitsSave");
    if (btn) btn.disabled = true;
    try {
        await apiRequest("PATCH", `/api/cards/${card.id}/settings`, body);
        cardsToast("Limites atualizados com sucesso.", "success");
        await loadCardsData();
    } catch (err) {
        showError("cdLimitsError", err.message || "Erro ao guardar limites.");
    } finally {
        if (btn) btn.disabled = card.status === "cancelled";
    }
}

/* ── 5 · Alertas ─────────────────────────────────────────────────────────── */
const NOTIF_META = {
    suspeita: ["#i-shield", "danger"], limite: ["#i-target", "warn"], controlo: ["#i-lock", ""],
    transacao: ["#i-card", ""], virtual_criado: ["#i-spark", "ok"],
};

function renderNotifications() {
    const list = document.getElementById("cardsNotifsList");
    const empty = document.getElementById("cardsEmptyAlerts");
    const readAll = document.getElementById("cdReadAll");
    if (!list) return;
    const items = CARDS.notifications;
    const unread = items.filter(n => !n.is_read).length;
    const badge = document.getElementById("cardsAlertsDot");
    if (badge) { badge.hidden = unread === 0; badge.textContent = unread > 9 ? "9+" : String(unread); }
    if (readAll) readAll.hidden = unread === 0;
    if (items.length === 0) { list.innerHTML = ""; if (empty) empty.hidden = false; return; }
    if (empty) empty.hidden = true;

    list.innerHTML = items.map(n => {
        const [icon, tone] = NOTIF_META[n.type] || ["#i-bell", ""];
        const card = CARDS.list.find(c => c.id === n.card_id);
        return `
        <div class="cd-notif ${n.is_read ? "" : "unread"}">
            <span class="cd-notif-icon ${tone}"><svg><use href="${icon}"/></svg></span>
            <div class="cd-notif-body">
                <strong>${escCards(n.title)}</strong>
                <p>${escCards(n.message)}</p>
                <span class="cd-notif-date">${relTime(parseApiDate(n.created_at))}${card ? ` · •••• ${escCards(card.last_four)}` : ""}</span>
            </div>
            ${n.is_read ? "" : `<button type="button" class="cd-notif-read" data-read="${escCards(n.id)}" aria-label="Marcar como lida"><svg><use href="#i-check"/></svg></button>`}
        </div>`;
    }).join("");
}

async function markCardNotifRead(id) {
    try {
        await apiRequest("POST", `/api/cards/notifications/${id}/read`);
        const n = CARDS.notifications.find(x => x.id === id);
        if (n) n.is_read = true;
        renderNotifications();
    } catch (err) { cardsToast(err.message || "Erro ao marcar notificação.", "error"); }
}

async function markAllCardNotifsRead() {
    try {
        await apiRequest("POST", "/api/cards/notifications/read-all");
        CARDS.notifications.forEach(n => { n.is_read = true; });
        renderNotifications();
        cardsToast("Todas as notificações foram marcadas como lidas.", "success");
    } catch (err) { cardsToast(err.message || "Erro ao marcar notificações.", "error"); }
}

/* ── Bloquear / desbloquear / cancelar ───────────────────────────────────── */
async function quickBlockCard() {
    const card = currentCard();
    if (!card) return;
    if (card.status === "cancelled") return cardsToast("Um cartão cancelado não pode ser alterado.", "error");
    const action = card.status === "active" ? "block" : "unblock";
    document.querySelectorAll("#cBtnBlock, #cToggleBlock").forEach(b => { b.disabled = true; });
    try {
        const res = await apiRequest("POST", `/api/cards/${card.id}/control`, { action });
        card.status = res.status;
        cardsToast(res.message || (action === "block" ? "Cartão bloqueado com sucesso." : "Cartão desbloqueado com sucesso."), "success");
        renderCarousel(); renderInfoStrip(); renderSecurityTab(); renderOverviewTab();
        loadSelectedCardData();
    } catch (err) {
        cardsToast(err.message || "Erro ao alterar o estado do cartão.", "error");
        updateBlockButton(card.status);
    }
}

function confirmCancelCard() {
    const card = currentCard();
    if (!card) return;
    setText("mccLastFour", card.last_four);
    const r = document.getElementById("mccReason"); if (r) r.value = "";
    const a = document.getElementById("mccAck"); if (a) a.checked = false;
    const b = document.getElementById("mccConfirmBtn"); if (b) b.disabled = true;
    openCardsSheet("modalCancelCard");
}

async function handleCancelCard() {
    const reason = document.getElementById("mccReason")?.value || "";
    const btn = document.getElementById("mccConfirmBtn");
    if (btn) { btn.disabled = true; btn.querySelector("span").textContent = "A cancelar…"; }
    try {
        await apiRequest("POST", `/api/cards/${CARDS.selectedId}/control`, { action: "cancel", reason });
        closeCardsSheet("modalCancelCard");
        cardsToast("Cartão cancelado com sucesso.", "success");
        await loadCardsData();
    } catch (err) {
        cardsToast(err.message || "Erro ao cancelar cartão.", "error");
    } finally {
        if (btn) { btn.querySelector("span").textContent = "Cancelar definitivamente"; btn.disabled = !document.getElementById("mccAck")?.checked; }
    }
}

/* ── Cartão virtual ──────────────────────────────────────────────────────── */
function openVirtualCardModal() {
    document.getElementById("formVirtualCard")?.reset();
    hideError("mvcError");
    const sel = document.getElementById("mvcAccountSelect");
    const accounts = (typeof state !== "undefined" && state.accounts) || [];
    if (sel) {
        sel.innerHTML = accounts.length
            ? accounts.map(a => `<option value="${escCards(a.id)}">${escCards(a.account_type || a.currency)} — ${formatMoney(a.balance, a.currency)}</option>`).join("")
            : `<option value="">Sem contas disponíveis</option>`;
        const cur = currentCard();
        if (cur && accounts.some(a => a.id === cur.account_id)) sel.value = cur.account_id;
    }
    updateVirtualPreview();
    openCardsSheet("modalVirtualCard");
}

function updateVirtualPreview() {
    const label = document.getElementById("mvcLabel")?.value.trim();
    setText("mvcPreviewLabel", label || "Cartão virtual");
    const days = parseInt(document.getElementById("mvcExpireDays")?.value || "365", 10);
    const d = new Date(); d.setDate(d.getDate() + days);
    setText("mvcPreviewExp", `${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getFullYear()).slice(-2)}`);
}

async function handleCreateVirtualCard(event) {
    event.preventDefault();
    const label = document.getElementById("mvcLabel")?.value.trim() || "Cartão virtual";
    const account_id = document.getElementById("mvcAccountSelect")?.value;
    const limitKz = digitsToInt(document.getElementById("mvcLimitInput")?.value);
    const expires_in_days = parseInt(document.getElementById("mvcExpireDays")?.value || "365", 10);
    const single_use = Boolean(document.getElementById("mvcSingleUse")?.checked);
    if (!account_id) return showError("mvcError", "Selecione uma conta.");
    if (limitKz && limitKz < 1000) return showError("mvcError", "O limite mínimo é de 1 000 Kz.");

    const btn = document.getElementById("mvcSubmitBtn");
    if (btn) btn.disabled = true;
    try {
        const res = await apiRequest("POST", "/api/cards/virtual/create", {
            account_id, label, single_use, expires_in_days,
            spending_limit_minor: limitKz ? limitKz * 100 : null,   // Kz → centavos
        });
        closeCardsSheet("modalVirtualCard");
        CARDS.selectedId = res.card_id || CARDS.selectedId;
        cardsToast(`Cartão virtual «${label}» terminado em ${res.last_four} criado com sucesso.`, "success");
        await loadCardsData();
        switchCardsTab("overview");
    } catch (err) {
        showError("mvcError", err.message || "Erro ao criar cartão virtual.");
    } finally {
        if (btn) btn.disabled = false;
    }
}

/* ── Separadores ─────────────────────────────────────────────────────────── */
function tabBtnId(tab) { return "ctabBtn" + tab.charAt(0).toUpperCase() + tab.slice(1); }
function tabPanelId(tab) { return "ctabPanel" + tab.charAt(0).toUpperCase() + tab.slice(1); }

function switchCardsTab(tab, focusLimits, silent) {
    if (!CARDS_TABS.includes(tab)) tab = "overview";
    CARDS.tab = tab;
    try { sessionStorage.setItem("cd_tab", tab); } catch (e) { /* sem storage */ }
    CARDS_TABS.forEach(t => {
        const b = document.getElementById(tabBtnId(t)), p = document.getElementById(tabPanelId(t));
        const on = t === tab;
        if (b) { b.classList.toggle("active", on); b.setAttribute("aria-selected", on); b.tabIndex = on ? 0 : -1; }
        if (p) p.classList.toggle("active", on);
    });
    const nav = document.querySelector(".cd-tabs"), btn = document.getElementById(tabBtnId(tab));
    if (nav && btn) nav.scrollTo({ left: btn.offsetLeft - (nav.clientWidth - btn.clientWidth) / 2, behavior: silent ? "auto" : "smooth" });
    if (focusLimits) {
        setTimeout(() => {
            const c = document.getElementById("cdLimitsCard");
            if (c) { c.scrollIntoView({ behavior: "smooth", block: "center" }); c.classList.add("flash"); setTimeout(() => c.classList.remove("flash"), 1400); }
        }, 60);
    }
}

/* ── Folhas (modais) ─────────────────────────────────────────────────────── */
function openCardsSheet(id) {
    const ov = document.getElementById(id);
    if (!ov) return;
    ov.classList.add("active");
    ov.setAttribute("aria-hidden", "false");
    document.documentElement.classList.add("cd-lock");
    setTimeout(() => ov.querySelector("input:not([type=checkbox]):not([disabled]), select, button.btn-primary")?.focus({ preventScroll: true }), 80);
}
function closeCardsSheet(id) {
    const ov = document.getElementById(id);
    if (!ov) return;
    ov.classList.remove("active");
    ov.setAttribute("aria-hidden", "true");
    if (!document.querySelector(".cd-sheet-overlay.active")) document.documentElement.classList.remove("cd-lock");
}

/* ── Estados de carregamento ─────────────────────────────────────────────── */
function skeletonRows(n) {
    return Array.from({ length: n }, () => `<div class="cd-skel-row"><span class="cd-skel c1"></span><span class="cd-skel-lines"><span class="cd-skel"></span><span class="cd-skel s"></span></span><span class="cd-skel c2"></span></div>`).join("");
}
function showSkeletons() {
    const c = document.getElementById("cardsCarousel");
    if (c) c.innerHTML = `<div class="bank-card cd-skel-card"><span class="cd-skel"></span></div>`;
    setListLoading(true);
}
function setListLoading(on) {
    if (!on) return;
    ["cardsMovementsPreview", "cardsMovementsList"].forEach(id => {
        const el = document.getElementById(id);
        if (el && !el.children.length) el.innerHTML = skeletonRows(id === "cardsMovementsPreview" ? 3 : 4);
    });
}
function renderLoadError() {
    const c = document.getElementById("cardsCarousel");
    if (c) c.innerHTML = `<button type="button" class="cd-add-tile cd-add-tile-only" onclick="loadCardsData(true)"><span class="cd-add-plus"><svg><use href="#i-refresh"/></svg></span><strong>Não foi possível carregar</strong><span>Toque para tentar novamente</span></button>`;
    ["cardsMovementsPreview", "cardsMovementsList"].forEach(id => { const el = document.getElementById(id); if (el) el.innerHTML = ""; });
}

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function fmt(amount, currency = "AOA") { return formatMoney(amount || 0, currency); }

function fmtCompact(amount, currency = "AOA") {
    const v = Number(amount) || 0, a = Math.abs(v);
    if (a < 1_000_000) return fmt(v, currency);
    const n = (a / 1_000_000).toLocaleString("pt-AO", { maximumFractionDigits: 2 });
    const unit = (currency || "AOA").toUpperCase() === "AOA" ? "KZ" : currency;
    return `${v < 0 ? "−" : ""}${n} M ${unit}`;
}

function pctOf(used, limit) { return limit > 0 ? Math.min(100, Math.max(0, (used / limit) * 100)) : 0; }

function ringSvg(pct) {
    const r = 26, c = 2 * Math.PI * r;
    const color = pct >= 90 ? "#F87171" : pct >= 70 ? "#F59E0B" : "#38BDF8";
    return `<svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="${r}" class="cd-ring-bg"/><circle cx="32" cy="32" r="${r}" class="cd-ring-fg" stroke="${color}" stroke-dasharray="${((pct / 100) * c).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 32 32)"/></svg><span>${Math.round(pct)}%</span>`;
}

function parseApiDate(s) {
    if (!s) return null;
    let v = String(s).trim().replace(" ", "T");
    if (!/[zZ]|[+-]\d{2}:?\d{2}$/.test(v)) v += "Z";   // a API guarda em UTC
    const d = new Date(v);
    return isNaN(d) ? null : d;
}

function dayLabel(d) {
    if (!d) return "—";
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const that = new Date(d); that.setHours(0, 0, 0, 0);
    const diff = Math.round((today - that) / 86400000);
    if (diff === 0) return "Hoje";
    if (diff === 1) return "Ontem";
    return d.toLocaleDateString("pt-AO", { weekday: "long", day: "numeric", month: "long" });
}

function relTime(d) {
    if (!d) return "—";
    const s = Math.round((Date.now() - d.getTime()) / 1000);
    if (s < 60) return "agora mesmo";
    if (s < 3600) return `há ${Math.floor(s / 60)} min`;
    if (s < 86400) return `há ${Math.floor(s / 3600)} h`;
    if (s < 172800) return "ontem";
    return d.toLocaleDateString("pt-AO", { day: "2-digit", month: "short" });
}

function shortDay(iso, long) {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("pt-AO", long ? { weekday: "short", day: "numeric", month: "short" } : { day: "numeric", month: "short" });
}

function digitsToInt(v) { return parseInt(String(v || "").replace(/\D/g, ""), 10) || 0; }
function groupKz(v) { const n = String(v ?? "").replace(/\D/g, ""); return n ? n.replace(/\B(?=(\d{3})+(?!\d))/g, " ") : ""; }

function setText(id, text) { const el = document.getElementById(id); if (el) el.textContent = text; }
function setHtml(id, html) { const el = document.getElementById(id); if (el) el.innerHTML = html; }
function showError(id, msg) { const el = document.getElementById(id); if (el) { el.textContent = msg; el.hidden = false; } }
function hideError(id) { const el = document.getElementById(id); if (el) el.hidden = true; }

function escCards(str) {
    return String(str ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function formatCatLabel(cat) {
    return {
        alimentacao: "Alimentação", restaurante: "Restaurantes", supermercado: "Supermercado",
        combustivel: "Combustível", transporte: "Transportes", saude: "Saúde",
        educacao: "Educação", vestuario: "Vestuário", eletronicos: "Eletrónicos",
        lazer: "Lazer & Entretenimento", viagens: "Viagens", telecomunicacoes: "Telecomunicações",
        servicos: "Serviços", levantamento: "Levantamentos ATM", outros: "Outros",
    }[cat] || cat || "Outros";
}

function cardsToast(msg, type = "success") {
    if (typeof toast === "function") toast(msg, type === "error" ? "error" : "success");
}
