/**
 * Módulo de Investimentos
 * Liga a vista investments.html aos endpoints /api/investments/* do backend.
 * Catálogo, detalhes, carteira (BankAO + externos), acompanhamento (resumo,
 * alocação, evolução), histórico e alertas.
 *
 * Contrato do backend (ver backend/api/routes/investments.py):
 *   GET /catalog      -> { products[], categories[], total_count }
 *   GET /catalog/{id} -> produto + simulations[]
 *   GET /portfolio    -> { summary, allocations{categories,institutions}, investments[], evolution[] }
 *   GET /operations   -> []     GET /notifications -> []
 * Os ids são strings (UUID): nunca interpolar sem aspas em onclick.
 */

const INV = {
    catalog: [],
    portfolio: [],
    summary: null,
    allocations: { categories: [], institutions: [] },
    evolution: [],
    operations: [],
    notifications: [],
    activeTab: "portfolio",
    selectedProductId: null,
    allocView: "categories"
};

const INV_RISK_LABELS = { baixo: "Risco Baixo", moderado: "Risco Moderado", medio: "Risco Moderado", alto: "Risco Alto", muito_alto: "Risco Muito Alto" };
const INV_RISK_CLASS = { baixo: "baixo", moderado: "medio", medio: "medio", alto: "alto", muito_alto: "alto" };
const INV_LIQ_LABELS = { no_vencimento: "No vencimento", diaria: "Diária", mensal: "Mensal", trimestral: "Trimestral", imediata: "Imediata", t2: "T+2" };
const INV_OP_ICONS = { aplicacao: "↓", aplicacao_externa: "＋", reforco: "↓", resgate_total: "↑", resgate_parcial: "↑", juros_dividendo: "✦", ajuste_cotacao: "≈", vencimento: "⏱" };
const INV_OP_FILTERS = {
    all: null,
    aplicacao: ["aplicacao", "aplicacao_externa", "reforco"],
    juros_dividendo: ["juros_dividendo", "ajuste_cotacao"],
    resgate: ["resgate_total", "resgate_parcial", "vencimento"]
};

/* ─── Utilitários ───────────────────────────────────────────────────────── */
const invFmt = (v, cur = "AOA") => formatMoney(v, cur);
const invPct = v => (Number(v) || 0).toFixed(1).replace(".", ",") + "%";
const invEsc = s => escapeHtml(s == null ? "" : s);
const invSet = (id, t) => { const el = document.getElementById(id); if (el) el.textContent = t; };
const invSigned = (v, cur) => (v >= 0 ? "+" : "−") + invFmt(Math.abs(v), cur);

function invDate(iso) {
    if (!iso) return "—";
    const d = new Date(String(iso).length <= 10 ? iso + "T00:00:00" : iso);
    return isNaN(d) ? "—" : d.toLocaleDateString("pt-AO", { day: "2-digit", month: "short", year: "numeric" });
}

function invDaysUntil(iso) {
    if (!iso) return null;
    const d = new Date(String(iso).length <= 10 ? iso + "T00:00:00" : iso);
    if (isNaN(d)) return null;
    const today = new Date(); today.setHours(0, 0, 0, 0);
    return Math.round((d - today) / 86400000);
}

const INV_MODALS = ["modalInvestDetails", "modalInvestApply", "modalInvestExternal", "modalInvestRedeem"];
function invOpen(id) {
    INV_MODALS.forEach(m => { if (m !== id) invClose(m); });   // nunca dois modais empilhados
    const m = document.getElementById(id);
    if (!m) return;
    m.style.display = "flex";
    const body = m.querySelector(".confirm-modal-body");
    if (body) body.scrollTop = 0;
}
function invClose(id) {
    const m = document.getElementById(id);
    if (m) m.style.display = "none";
}

function invBusy(btn, busy, label) {
    if (!btn) return;
    if (busy) {
        if (btn.dataset.busy) return;
        btn.dataset.busy = "1"; btn.dataset.html = btn.innerHTML;
        btn.disabled = true; btn.innerHTML = `<span>${label || "A processar..."}</span>`;
    } else {
        delete btn.dataset.busy; btn.disabled = false;
        if (btn.dataset.html) { btn.innerHTML = btn.dataset.html; delete btn.dataset.html; }
    }
}

/* Mensagem de erro dentro do formulário (visível sem fechar o teclado/modal) */
function invFormError(id, msg) {
    const el = document.getElementById(id);
    if (!el) { if (msg) toast(msg, "error"); return; }
    el.textContent = msg || "";
    el.hidden = !msg;
    if (msg) { try { el.scrollIntoView({ block: "nearest", behavior: "smooth" }); } catch (_) { /* ignore */ } }
}

const invAccountBalance = a => Number(a && (a.balance_decimal != null ? a.balance_decimal : a.balance)) || 0;

function invAccountOptions(currency, selected) {
    const accs = (state.accounts || []).filter(a => !currency || a.currency === currency);
    if (!accs.length) return `<option value="">Sem conta em ${currency || "esta moeda"}</option>`;
    return accs.map(a => {
        const bal = invAccountBalance(a);
        return `<option value="${invEsc(a.id)}" ${a.id === selected ? "selected" : ""}>Conta ${invEsc(a.currency)} · ${invEsc(a.account_number || "")} — ${invFmt(bal, a.currency)}</option>`;
    }).join("");
}

/* ─── Inicialização ─────────────────────────────────────────────────────── */
function initInvestments() {
    const bind = (id, ev, fn) => document.getElementById(id)?.addEventListener(ev, fn);
    const chips = (id, sel, fn) => bind(id, "click", e => {
        const b = e.target.closest(".inv-chip" + sel);
        if (!b) return;
        document.querySelectorAll(`#${id} .inv-chip`).forEach(x => x.classList.remove("active"));
        b.classList.add("active");
        fn(b);
    });
    chips("invPortfolioFilters", "[data-filter]", b => renderPortfolioList(b.dataset.filter));
    chips("invCategoryChips", "[data-cat]", () => renderCatalogList());
    chips("invHistoryFilters", "[data-op]", b => renderHistoryList(b.dataset.op));
    bind("invHistoryPeriod", "change", () => {
        const custom = document.getElementById("invHistoryPeriod").value === "custom";
        const r = document.getElementById("invHistoryRange"); if (r) r.hidden = !custom;
        renderHistoryList(invHistoryActiveFilter());
    });
    bind("invHistoryFrom", "change", () => renderHistoryList(invHistoryActiveFilter()));
    bind("invHistoryTo", "change", () => renderHistoryList(invHistoryActiveFilter()));
    bind("invHistoryExport", "click", exportHistoryCsv);
    chips("invAllocToggle", "[data-alloc]", b => { INV.allocView = b.dataset.alloc; renderAllocation(); });
    bind("invCatalogSearch", "input", () => renderCatalogList());
    bind("invCatalogRisk", "change", () => renderCatalogList());
    bind("invCatalogCurrency", "change", () => renderCatalogList());
    bind("invSimAmountInput", "input", runQuickSimulator);
    bind("invSimCurrencySelect", "change", runQuickSimulator);
    bind("mivAppAmountInput", "input", updateApplyPreview);
    bind("mivAppAccountSelect", "change", updateApplyAccountHint);
    bind("mivAppQuickChips", "click", e => {
        const b = e.target.closest(".chip-btn[data-mult]");
        if (!b) return;
        const p = INV.catalog.find(x => x.id === INV.selectedProductId);
        const acc = (state.accounts || []).find(a => a.id === document.getElementById("mivAppAccountSelect")?.value);
        if (!p) return;
        const max = acc ? Math.floor(invAccountBalance(acc)) : 0;
        const v = b.dataset.mult === "max" ? max : Number(p.min_amount) * Number(b.dataset.mult);
        document.getElementById("mivAppAmountInput").value = v > 0 ? v : "";
        updateApplyPreview();
    });
    ["mivAppAmountInput", "mivAppAccountSelect"].forEach(id => bind(id, "input", () => invFormError("mivAppError", "")));
    ["formInvestExternal", "formInvestRedeem"].forEach(id => bind(id, "input", () => invFormError(id === "formInvestExternal" ? "mivExtError" : "mivRedError", "")));

    // Fechar com ESC e ao tocar/clicar no fundo escuro (apenas se o toque começou no fundo)
    document.addEventListener("keydown", e => {
        if (e.key === "Escape") INV_MODALS.forEach(invClose);
    });
    INV_MODALS.forEach(id => {
        const ov = document.getElementById(id);
        if (!ov) return;
        let downOnBackdrop = false;
        ov.addEventListener("pointerdown", e => { downOnBackdrop = e.target === ov; });
        ov.addEventListener("click", e => { if (e.target === ov && downOnBackdrop) invClose(id); });
    });

    const d = document.getElementById("mivExtStartDate");
    if (d) d.value = new Date().toISOString().slice(0, 10);
}

/* ─── Dados ─────────────────────────────────────────────────────────────── */
let invLoadSeq = 0;
async function loadInvestmentsData() {
    if (!state.token) return;
    const seq = ++invLoadSeq;
    try {
        const [cat, port, ops, notifs] = await Promise.all([
            apiRequest("GET", "/api/investments/catalog"),
            apiRequest("GET", "/api/investments/portfolio"),
            apiRequest("GET", "/api/investments/operations?limit=1000"),
            apiRequest("GET", "/api/investments/notifications")
        ]);
        if (seq !== invLoadSeq) return;   // chegou uma resposta mais recente entretanto
        INV.catalog = (cat && cat.products) || [];
        INV.portfolio = ((port && port.investments) || []).filter(i => i.status !== "resgatado" || Number(i.current_value) > 0);
        INV.summary = (port && port.summary) || null;
        INV.allocations = (port && port.allocations) || { categories: [], institutions: [] };
        INV.evolution = (port && port.evolution) || [];
        INV.operations = ops || [];
        INV.notifications = notifs || [];
        renderInvestmentsView();
    } catch (err) {
        console.error("Erro ao carregar investimentos:", err);
        toast(err.message || "Não foi possível carregar os investimentos.", "error");
    }
}

function renderInvestmentsView() {
    renderHero();
    renderAllocation();
    renderEvolution();
    renderPortfolioList(document.querySelector("#invPortfolioFilters .inv-chip.active")?.dataset.filter || "all");
    renderCatalogList();
    renderHistoryList(document.querySelector("#invHistoryFilters .inv-chip.active")?.dataset.op || "all");
    renderNotifications();
    runQuickSimulator();
    invSet("invPortfolioBadge", String(INV.portfolio.filter(i => i.status === "ativo").length));
    invSet("invCatalogBadge", String(INV.catalog.length));
    const unread = INV.notifications.filter(n => !n.is_read).length;
    const dot = document.getElementById("invAlertsDot");
    if (dot) dot.hidden = unread === 0;
}

/* ─── Resumo (hero) ─────────────────────────────────────────────────────── */
function renderHero() {
    const s = INV.summary || {};
    const cur = Number(s.total_current_aoa) || 0, inv = Number(s.total_invested_aoa) || 0;
    const gain = Number(s.total_gain_aoa) || 0, pct = Number(s.total_gain_percentage) || 0;
    invSet("invTotalValueAoa", invFmt(cur));
    invSet("invTotalInvestedAoa", invFmt(inv));
    invSet("invTotalYieldAoa", invSigned(Number(s.total_yield_aoa) || 0));
    const n = Number(s.active_count) || 0;
    invSet("invActiveCountText", `${n} ativo${n !== 1 ? "s" : ""} em carteira`);
    invSet("invTotalGainText", `${invSigned(gain)} (${pct.toFixed(1).replace(".", ",")}%)`);
    const badge = document.getElementById("invTotalGainBadge");
    if (badge) {
        badge.className = `inv-gain-badge ${gain >= 0 ? "up" : "down"}`;
        const arrow = badge.querySelector(".inv-gain-arrow");
        if (arrow) arrow.textContent = gain >= 0 ? "↑" : "↓";
    }
    if (s.next_maturity_date) {
        const d = invDaysUntil(s.next_maturity_date);
        invSet("invNextMaturityText", invDate(s.next_maturity_date));
        invSet("invNextMaturitySub", (d <= 0 ? "Vence hoje" : d === 1 ? "Vence amanhã" : `Em ${d} dias`) + (s.next_maturity_name ? ` · ${s.next_maturity_name}` : ""));
    } else {
        invSet("invNextMaturityText", "—");
        invSet("invNextMaturitySub", "Sem vencimentos próximos");
    }
}

/* ─── Alocação ──────────────────────────────────────────────────────────── */
function renderAllocation() {
    const card = document.getElementById("invAllocCard");
    const bar = document.getElementById("invAllocBar");
    const legend = document.getElementById("invAllocLegend");
    if (!card || !bar || !legend) return;
    const rows = INV.allocations[INV.allocView] || [];
    card.hidden = rows.length === 0;
    if (!rows.length) return;
    const palette = ["#38BDF8", "#10B981", "#818CF8", "#F59E0B", "#EC4899", "#F87171", "#A78BFA"];
    const seg = rows.map((r, i) => ({
        label: r.label || r.institution || r.key || "—",
        pct: Number(r.percentage) || 0,
        amount: Number(r.amount_aoa) || 0,
        color: r.color || palette[i % palette.length]
    }));
    const totalPct = seg.reduce((a, s) => a + s.pct, 0) || 1;
    bar.innerHTML = seg.map(s => `<div class="inv-alloc-segment" style="width:${(s.pct / totalPct * 100).toFixed(2)}%;background:${s.color}" title="${invEsc(s.label)}: ${invFmt(s.amount)} (${s.pct.toFixed(0)}%)"></div>`).join("");
    legend.innerHTML = seg.map(s => `<span class="inv-alloc-item"><i style="background:${s.color}"></i>${invEsc(s.label)} ${s.pct.toFixed(0)}%</span>`).join("");
}

/* ─── Evolução da carteira (SVG) ────────────────────────────────────────── */
function renderEvolution() {
    const host = document.getElementById("invEvolutionChart");
    const card = document.getElementById("invEvolutionCard");
    if (!host || !card) return;
    const pts = INV.evolution || [];
    const hasData = pts.some(p => Number(p.value_aoa) > 0 || Number(p.invested_aoa) > 0);
    card.hidden = !hasData;
    if (!hasData) return;
    const W = 640, H = 220, L = 12, R = 12, T = 16, B = 28;
    const max = Math.max(...pts.map(p => Math.max(+p.value_aoa || 0, +p.invested_aoa || 0))) * 1.08 || 1;
    const x = i => L + (pts.length === 1 ? (W - L - R) / 2 : i * (W - L - R) / (pts.length - 1));
    const y = v => T + (H - T - B) * (1 - v / max);
    const line = k => pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(+p[k] || 0).toFixed(1)}`).join(" ");
    const area = `${line("value_aoa")} L${x(pts.length - 1).toFixed(1)},${H - B} L${x(0).toFixed(1)},${H - B} Z`;
    host.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Evolução do valor da carteira">
        <defs><linearGradient id="invEvoGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#34D399" stop-opacity=".35"/><stop offset="1" stop-color="#34D399" stop-opacity="0"/>
        </linearGradient></defs>
        <path d="${area}" fill="url(#invEvoGrad)"/>
        <path d="${line("invested_aoa")}" fill="none" stroke="#6C9BFF" stroke-width="2" stroke-dasharray="5 4" vector-effect="non-scaling-stroke"/>
        <path d="${line("value_aoa")}" fill="none" stroke="#34D399" stroke-width="2.5" vector-effect="non-scaling-stroke"/>
    </svg>
    <div class="inv-evo-axis">${pts.map(p => `<span>${invEsc(p.label)}</span>`).join("")}</div>`;
    const last = pts[pts.length - 1] || {};
    invSet("invEvoLastValue", invFmt(+last.value_aoa || 0));
}

/* ─── Carteira ──────────────────────────────────────────────────────────── */
function renderPortfolioList(filter = "all") {
    const list = document.getElementById("invAssetsList");
    const empty = document.getElementById("invEmptyPortfolio");
    if (!list) return;
    let items = INV.portfolio.filter(i => i.status === "ativo");
    if (filter === "bankao") items = items.filter(i => !i.is_external);
    else if (filter === "external") items = items.filter(i => i.is_external);
    else if (filter === "aoa") items = items.filter(i => i.currency === "AOA");
    else if (filter === "usd") items = items.filter(i => i.currency === "USD");
    if (!items.length) {
        list.innerHTML = "";
        if (empty) empty.hidden = false;
        invSet("invAssetsCountLabel", "Consulte os seus investimentos internos e externos");
        return;
    }
    if (empty) empty.hidden = true;
    invSet("invAssetsCountLabel", `${items.length} ativo${items.length !== 1 ? "s" : ""} encontrado${items.length !== 1 ? "s" : ""}`);
    list.innerHTML = items.map(buildAssetCard).join("");
}

function buildAssetCard(i) {
    const cur = i.currency || "AOA";
    const gain = Number(i.gain_loss) || 0;
    const left = invDaysUntil(i.maturity_date);
    const chip = left === null ? "" :
        `<span class="inv-maturity-chip ${left <= 30 ? "urgent" : ""}">${left < 0 ? "Vencido" : left === 0 ? "Vence hoje" : left === 1 ? "Vence amanhã" : left + "d"}</span>`;
    const id = invEsc(i.id);
    return `
    <div class="inv-asset-card" data-id="${id}">
        <div class="inv-asset-card-top">
            <div class="inv-asset-icon" style="--inv-cat-color:${invEsc(i.category_color || "#8B5CF6")}"><svg><use href="#i-trending"/></svg></div>
            <div class="inv-asset-info">
                <div class="inv-asset-name-row">
                    <strong class="inv-asset-name">${invEsc(i.name)}</strong>
                    ${i.is_external ? '<span class="inv-ext-badge">Externo</span>' : '<span class="inv-bankao-badge">BankAO</span>'}
                    ${chip}
                </div>
                <span class="inv-asset-inst">${invEsc(i.institution)} · ${invEsc(i.category_label || "")}</span>
            </div>
            <div class="inv-asset-value-col">
                <strong class="inv-asset-value">${invFmt(i.current_value, cur)}</strong>
                <span class="inv-asset-gain ${gain >= 0 ? "up" : "down"}">${invSigned(gain, cur)} (${(Number(i.gain_percentage) || 0).toFixed(1).replace(".", ",")}%)</span>
            </div>
        </div>
        <div class="inv-asset-card-meta">
            <span><label>Aplicado</label><b>${invFmt(i.amount_invested, cur)}</b></span>
            <span><label>Taxa</label><b>${i.rate_annual ? invPct(i.rate_annual) + " a.a." : "—"}</b></span>
            <span><label>Rendimentos</label><b class="highlight">+${invFmt(i.accumulated_yield, cur)}</b></span>
            <span><label>Início</label><b>${invDate(i.start_date)}</b></span>
            ${i.maturity_date ? `<span><label>Vencimento</label><b>${invDate(i.maturity_date)}</b></span>` : ""}
            <span><label>Atualizado</label><b>${invDate(i.updated_at)}</b></span>
        </div>
        ${i.notes ? `<p class="inv-asset-notes">${invEsc(i.notes)}</p>` : ""}
        <div class="inv-asset-card-actions">
            <button type="button" class="btn btn-danger-ghost-sm" onclick="openRedeemModal('${id}')"><svg><use href="#i-minus"/></svg><span>${i.is_external ? "Dar baixa" : "Resgatar"}</span></button>
        </div>
    </div>`;
}

/* ─── Catálogo ──────────────────────────────────────────────────────────── */
function renderCatalogList() {
    const list = document.getElementById("invCatalogList");
    if (!list) return;
    const cat = document.querySelector("#invCategoryChips .inv-chip.active")?.dataset.cat || "all";
    const q = (document.getElementById("invCatalogSearch")?.value || "").toLowerCase().trim();
    const risk = document.getElementById("invCatalogRisk")?.value || "all";
    const cur = document.getElementById("invCatalogCurrency")?.value || "all";
    const items = INV.catalog.filter(p =>
        (cat === "all" || p.category === cat) &&
        (risk === "all" || INV_RISK_CLASS[p.risk_level] === risk) &&
        (cur === "all" || p.currency === cur) &&
        (!q || [p.name, p.institution, p.category_label].some(t => String(t || "").toLowerCase().includes(q)))
    );
    if (!items.length) {
        list.innerHTML = `<div class="inv-empty-state"><p>Nenhum produto encontrado com estes filtros.</p></div>`;
        return;
    }
    list.innerHTML = items.map(p => {
        const id = invEsc(p.id);
        return `
        <article class="inv-catalog-card">
            <div class="inv-card-top">
                <span class="inv-card-badge" style="--inv-cat-color:${invEsc(p.category_color)}">${invEsc(p.category_label)}</span>
                <span class="inv-risk-badge ${INV_RISK_CLASS[p.risk_level] || "medio"}">${INV_RISK_LABELS[p.risk_level] || "Risco"}</span>
            </div>
            <h4 class="inv-card-title">${invEsc(p.name)}</h4>
            <span class="inv-card-inst">${invEsc(p.institution)}</span>
            <div class="inv-card-rate"><strong>${invPct(p.rate_annual)}</strong><span>a.a. · ${invEsc(p.term_label)}</span></div>
            <div class="inv-card-specs">
                <span><label>Mínimo</label><b>${invFmt(p.min_amount, p.currency)}</b></span>
                <span><label>Liquidez</label><b>${INV_LIQ_LABELS[p.liquidity] || invEsc(p.liquidity)}</b></span>
                <span><label>Moeda</label><b>${invEsc(p.currency)}</b></span>
            </div>
            <p class="inv-card-fees">${invEsc(p.fees_info)}</p>
            <div class="inv-card-actions">
                <button type="button" class="btn btn-secondary" onclick="openProductDetails('${id}')"><span>Detalhes</span></button>
                <button type="button" class="btn btn-primary" onclick="openApplyModal('${id}')"><span>Subscrever</span></button>
            </div>
        </article>`;
    }).join("");
}

function runQuickSimulator() {
    const amount = Number(document.getElementById("invSimAmountInput")?.value) || 0;
    const cur = document.getElementById("invSimCurrencySelect")?.value || "AOA";
    const pool = INV.catalog.filter(p => p.currency === cur && p.category === "deposito_prazo");
    const best = pool.sort((a, b) => b.rate_annual - a.rate_annual)[0] || INV.catalog.filter(p => p.currency === cur).sort((a, b) => b.rate_annual - a.rate_annual)[0];
    const calc = m => best ? invFmt(amount * (best.rate_annual / 100) * (m / 12), cur) : "—";
    invSet("invSim3m", calc(3)); invSet("invSim6m", calc(6)); invSet("invSim12m", calc(12));
    invSet("invSimBasis", best ? `Base: ${best.name} (${invPct(best.rate_annual)} a.a., bruto)` : "Sem produtos nesta moeda");
}

/* ─── Detalhes do produto ───────────────────────────────────────────────── */
async function openProductDetails(productId) {
    INV.selectedProductId = productId;
    try {
        const p = await apiRequest("GET", `/api/investments/catalog/${encodeURIComponent(productId)}`);
        invSet("mivDetTitle", p.name);
        invSet("mivDetInstitution", p.institution);
        invSet("mivDetCategoryBadge", p.category_label);
        invSet("mivDetRateVal", invPct(p.rate_annual));
        invSet("mivDetTermVal", p.term_label);
        const rb = document.getElementById("mivDetRiskVal");
        if (rb) { rb.textContent = INV_RISK_LABELS[p.risk_level] || "Risco"; rb.className = `inv-risk-badge ${INV_RISK_CLASS[p.risk_level] || "medio"}`; }
        invSet("mivDetDesc", p.description);
        invSet("mivDetMinAmount", invFmt(p.min_amount, p.currency));
        invSet("mivDetLiquidity", INV_LIQ_LABELS[p.liquidity] || p.liquidity);
        invSet("mivDetCurrency", p.currency);
        invSet("mivDetTermSpec", p.term_label || "—");
        invSet("mivDetFees", p.fees_info);
        invSet("mivDetRedemption", p.redemption_conditions);
        const body = document.getElementById("mivDetSimTableBody");
        if (body) body.innerHTML = (p.simulations || []).map(s => `
            <tr><td>${invFmt(s.principal, p.currency)}</td><td>${invFmt(s.gross_return, p.currency)}</td>
            <td>${invFmt(s.tax_estimate, p.currency)}</td><td class="highlight">${invFmt(s.net_return, p.currency)}</td>
            <td><b>${invFmt(s.total_at_maturity, p.currency)}</b></td></tr>`).join("");
        invOpen("modalInvestDetails");
    } catch (err) { toast(err.message || "Erro ao carregar o produto.", "error"); }
}

function openApplyFromDetails() {
    invClose("modalInvestDetails");
    if (INV.selectedProductId) openApplyModal(INV.selectedProductId);
}

/* ─── Subscrição ────────────────────────────────────────────────────────── */
function openApplyModal(productId) {
    const p = INV.catalog.find(x => x.id === productId);
    if (!p) return;
    invFormError("mivAppError", "");
    INV.selectedProductId = productId;
    document.getElementById("mivAppProductId").value = productId;
    invSet("mivAppTitle", p.name);
    invSet("mivAppSubtitle", `${p.institution} · débito em conta BankAO (${p.currency})`);
    invSet("mivAppCurrencyTag", p.currency);
    invSet("mivAppMinAmountHint", `Mínimo: ${invFmt(p.min_amount, p.currency)}`);
    invSet("mivAppPreviewRate", invPct(p.rate_annual) + " a.a.");
    invSet("mivAppPreviewTerm", p.term_label);
    const amt = document.getElementById("mivAppAmountInput");
    amt.min = p.min_amount; amt.value = p.min_amount; amt.step = "any";
    document.getElementById("mivAppAccountSelect").innerHTML = invAccountOptions(p.currency);
    document.getElementById("mivAppNotesInput").value = "";
    updateApplyAccountHint(); updateApplyPreview();
    invOpen("modalInvestApply");
}

function updateApplyPreview() {
    const p = INV.catalog.find(x => x.id === INV.selectedProductId);
    if (!p) return;
    const a = Number(document.getElementById("mivAppAmountInput")?.value) || 0;
    const months = p.term_months || 12;
    const gross = a * (p.rate_annual / 100) * (months / 12);
    const net = ["deposito_prazo", "obrigacoes"].includes(p.category) ? gross * 0.9 : gross;
    invSet("mivAppPreviewReturn", `${invFmt(net, p.currency)} líquido${p.term_months ? "" : " / ano (estimativa)"}`);
}

function updateApplyAccountHint() {
    const id = document.getElementById("mivAppAccountSelect")?.value;
    const acc = (state.accounts || []).find(a => a.id === id);
    invSet("mivAppAccountBalanceHint", acc ? `Saldo disponível: ${invFmt(acc.balance_decimal != null ? acc.balance_decimal : acc.balance, acc.currency)}` : "Saldo disponível: —");
}

async function handleInvestApplySubmit(e) {
    e.preventDefault();
    const btn = document.getElementById("mivAppSubmitBtn");
    if (btn && btn.dataset.busy) return;
    const p = INV.catalog.find(x => x.id === document.getElementById("mivAppProductId").value);
    const accId = document.getElementById("mivAppAccountSelect").value;
    const acc = (state.accounts || []).find(a => a.id === accId);
    const amount = Number(document.getElementById("mivAppAmountInput").value);
    if (!p) return invFormError("mivAppError", "Produto inválido. Feche e tente novamente.");
    if (!acc) return invFormError("mivAppError", `Não tem nenhuma conta em ${p.currency} para debitar.`);
    if (!(amount > 0)) return invFormError("mivAppError", "Indique o montante a aplicar.");
    if (amount < Number(p.min_amount)) return invFormError("mivAppError", `O montante mínimo é ${invFmt(p.min_amount, p.currency)}.`);
    if (amount > invAccountBalance(acc)) return invFormError("mivAppError", "Saldo insuficiente na conta selecionada.");
    invFormError("mivAppError", "");

    // Exigir confirmação por PIN antes de aplicar fundos em investimentos
    if (typeof window.requirePinAuthorization === "function") {
        const desc = `Investir ${invFmt(amount, p.currency)} em ${p.name || "produto financeiro"}`;
        const authorized = await window.requirePinAuthorization(desc);
        if (!authorized) return;
    }

    invBusy(btn, true);
    try {
        const res = await apiRequest("POST", "/api/investments/portfolio/apply", {
            product_id: p.id,
            amount,
            account_id: accId || null,
            notes: document.getElementById("mivAppNotesInput").value.trim() || null
        });
        invClose("modalInvestApply");
        toast((res && res.message) || "Investimento subscrito com sucesso!", "success");

        // Notificação do sistema (respeita definições n_investments e ch_push)
        if (typeof window.bkNotify === "function") {
            window.bkNotify(`Investimento subscrito: ${p.name || "Produto"} · ${invFmt(amount, p.currency)}`, "success", "n_investments");
        }

        if (typeof copilotAnnounceDone === "function") {
            copilotAnnounceDone("investment", `✅ **Investimento realizado!** Subscreveu **${p.name || "o produto"}** com **${invFmt(amount, p.currency)}**.\n\nPode acompanhá-lo em **Investimentos → Carteira**.`, `Concluído. O investimento em ${p.name || "o produto"} foi realizado com sucesso.`);
        }
        await loadInvestmentsData();
        if (typeof loadUserData === "function") loadUserData();
        switchInvestTab("portfolio");
    } catch (err) { invFormError("mivAppError", err.message || "Erro ao subscrever."); }
    finally { invBusy(btn, false); }
}

/* ─── Investimento externo ──────────────────────────────────────────────── */
function openExternalInvestModal() {
    document.getElementById("formInvestExternal")?.reset();
    invFormError("mivExtError", "");
    const d = document.getElementById("mivExtStartDate");
    if (d) d.value = new Date().toISOString().slice(0, 10);
    invOpen("modalInvestExternal");
}

async function handleInvestExternalSubmit(e) {
    e.preventDefault();
    const g = id => document.getElementById(id).value;
    const btn = e.target.querySelector("button[type=submit]");
    if (btn && btn.dataset.busy) return;
    const name = g("mivExtName").trim(), inst = g("mivExtInstitution").trim();
    const amount = Number(g("mivExtAmount")), start = g("mivExtStartDate"), mat = g("mivExtMaturityDate");
    if (!name || !inst) return invFormError("mivExtError", "Preencha o nome do ativo e a instituição.");
    if (!(amount > 0)) return invFormError("mivExtError", "Indique um montante aplicado válido.");
    if (!start) return invFormError("mivExtError", "Indique a data da aplicação.");
    if (mat && mat < start) return invFormError("mivExtError", "O vencimento não pode ser anterior à data da aplicação.");
    invFormError("mivExtError", "");
    invBusy(btn, true);
    try {
        await apiRequest("POST", "/api/investments/portfolio/external", {
            name,
            category: g("mivExtCategory"),
            institution: inst,
            amount,
            currency: g("mivExtCurrency"),
            rate_annual: Number(g("mivExtRate")) || 0,
            start_date: start,
            maturity_date: mat || null,
            notes: g("mivExtNotes").trim() || null
        });
        invClose("modalInvestExternal");
        toast("Investimento externo registado com sucesso!", "success");
        await loadInvestmentsData();
        switchInvestTab("portfolio");
    } catch (err) { invFormError("mivExtError", err.message || "Erro ao registar."); }
    finally { invBusy(btn, false); }
}

/* ─── Resgate ───────────────────────────────────────────────────────────── */
function openRedeemModal(id) {
    const i = INV.portfolio.find(x => x.id === id);
    if (!i) return;
    invFormError("mivRedError", "");
    document.getElementById("mivRedInvestmentId").value = id;
    invSet("mivRedTitle", (i.is_external ? "Dar baixa: " : "Resgatar: ") + i.name);
    invSet("mivRedSubtitle", i.is_external ? "Remove o ativo da carteira (sem movimento na conta BankAO)" : "Liquidar e creditar fundos na sua conta");
    invSet("mivRedAssetName", i.name);
    invSet("mivRedAvailableVal", invFmt(i.current_value, i.currency));
    const grp = document.getElementById("mivRedAccountGroup");
    if (grp) grp.hidden = !!i.is_external;
    document.getElementById("mivRedAccountSelect").innerHTML = invAccountOptions(i.currency, i.account_id);
    document.querySelectorAll("input[name='redeemType']").forEach(r => r.checked = r.value === "total");
    const amt = document.getElementById("mivRedAmountInput");
    amt.value = ""; amt.max = i.current_value; amt.step = "any";
    toggleRedeemAmountField();
    invOpen("modalInvestRedeem");
}

function toggleRedeemAmountField() {
    const partial = document.querySelector("input[name='redeemType']:checked")?.value === "partial";
    const g = document.getElementById("mivRedAmountGroup"); if (g) g.hidden = !partial;
    const inp = document.getElementById("mivRedAmountInput"); if (inp) inp.required = partial;
}

async function handleInvestRedeemSubmit(e) {
    e.preventDefault();
    const id = document.getElementById("mivRedInvestmentId").value;
    const i = INV.portfolio.find(x => x.id === id);
    const partial = document.querySelector("input[name='redeemType']:checked")?.value === "partial";
    const btn = document.getElementById("mivRedSubmitBtn");
    if (btn && btn.dataset.busy) return;
    if (!i) return invFormError("mivRedError", "Investimento não encontrado. Atualize a página.");
    const amount = partial ? Number(document.getElementById("mivRedAmountInput").value) : null;
    const accId = i.is_external ? null : (document.getElementById("mivRedAccountSelect").value || null);
    if (partial && !(amount > 0)) return invFormError("mivRedError", "Indique o montante a resgatar.");
    if (partial && amount > Number(i.current_value)) return invFormError("mivRedError", `O máximo disponível é ${invFmt(i.current_value, i.currency)}.`);
    if (!i.is_external && !accId) return invFormError("mivRedError", `Não tem nenhuma conta em ${i.currency} para creditar.`);
    invFormError("mivRedError", "");
    invBusy(btn, true);
    try {
        const res = await apiRequest("POST", `/api/investments/portfolio/${encodeURIComponent(id)}/redeem`, {
            amount,
            account_id: accId
        });
        invClose("modalInvestRedeem");
        toast((res && res.message) || "Resgate processado com sucesso!", "success");
        await loadInvestmentsData();
        if (typeof loadUserData === "function") loadUserData();
    } catch (err) { invFormError("mivRedError", err.message || "Erro ao processar resgate."); }
    finally { invBusy(btn, false); }
}

/* ─── Histórico ─────────────────────────────────────────────────────────── */
const invHistoryActiveFilter = () =>
    document.querySelector("#invHistoryFilters .inv-chip.active")?.dataset.op || "all";

/** Operações filtradas por tipo (chip) e período (select / datas). Datas em AAAA-MM-DD, comparadas como texto. */
function invFilteredOperations(filter = "all") {
    const types = INV_OP_FILTERS[filter];
    const period = document.getElementById("invHistoryPeriod")?.value || "all";
    const ymd = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    let from = "", to = "";
    if (period === "ytd") from = `${new Date().getFullYear()}-01-01`;
    else if (period === "custom") {
        from = document.getElementById("invHistoryFrom")?.value || "";
        to = document.getElementById("invHistoryTo")?.value || "";
    } else if (period !== "all") {
        const d = new Date(); d.setDate(d.getDate() - Number(period)); from = ymd(d);
    }
    return INV.operations.filter(o => {
        if (types && !types.includes(o.operation_type)) return false;
        const day = String(o.operation_date || "").slice(0, 10);
        if (from && day < from) return false;
        if (to && day > to) return false;
        return true;
    });
}

function renderHistoryList(filter = "all") {
    const list = document.getElementById("invHistoryList");
    const empty = document.getElementById("invEmptyHistory");
    if (!list) return;
    const items = invFilteredOperations(filter);
    if (empty) empty.hidden = items.length > 0;
    invSet("invHistoryCount", items.length ? `${items.length} operação(ões)` : "");
    const exp = document.getElementById("invHistoryExport"); if (exp) exp.disabled = !items.length;
    list.innerHTML = items.map(o => {
        const out = o.operation_type.startsWith("resgate");
        const inflow = o.operation_type === "juros_dividendo";
        return `
        <div class="inv-history-row">
            <div class="inv-history-icon ${out ? "out" : inflow ? "yield" : "in"}">${INV_OP_ICONS[o.operation_type] || "•"}</div>
            <div class="inv-history-info">
                <strong>${invEsc(o.type_label)} · ${invEsc(o.investment_name)}</strong>
                <span>${invEsc(o.institution)} · ${invDate(o.operation_date)}${o.description ? " · " + invEsc(o.description) : ""}</span>
            </div>
            <div class="inv-history-amount ${out || inflow ? "up" : ""}">${out || inflow ? "+" : "−"}${invFmt(o.amount, o.currency)}</div>
        </div>`;
    }).join("");
}

/** Exporta para CSV (;, UTF-8 com BOM) as operações atualmente visíveis. */
function exportHistoryCsv() {
    const items = invFilteredOperations(invHistoryActiveFilter());
    if (!items.length) { toast("Não há operações para exportar.", "error"); return; }
    // Prefixa ' em texto que começa por = + - @ para evitar injeção de fórmulas no Excel.
    const esc = v => { let t = String(v ?? ""); if (/^[=+\-@]/.test(t)) t = "'" + t; return `"${t.replace(/"/g, '""')}"`; };
    const out = t => t.startsWith("resgate") || t === "juros_dividendo" || t === "vencimento";
    const lines = [["Data", "Tipo", "Investimento", "Instituição", "Descrição", "Sinal", "Valor", "Moeda"].map(esc).join(";")];
    items.forEach(o => lines.push([
        String(o.operation_date || "").slice(0, 10), o.type_label, o.investment_name, o.institution, o.description,
        out(o.operation_type) ? "+" : "-", Number(o.amount || 0).toFixed(2).replace(".", ","), o.currency
    ].map(esc).join(";")));
    const blob = new Blob(["\uFEFF" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `investimentos-historico-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1500);
    toast(`${items.length} operações exportadas.`, "success");
}

/* ─── Alertas ───────────────────────────────────────────────────────────── */
function renderNotifications() {
    const list = document.getElementById("invNotificationsList");
    const empty = document.getElementById("invEmptyAlerts");
    if (!list) return;
    if (empty) empty.hidden = INV.notifications.length > 0;
    list.innerHTML = INV.notifications.map(n => `
        <div class="inv-notif-card ${n.is_read ? "read" : "unread"}" data-type="${invEsc(n.type)}">
            <div class="inv-notif-body">
                <strong>${invEsc(n.title)}</strong>
                <p>${invEsc(n.message)}</p>
                <span class="inv-notif-time">${invDate(n.created_at)}${n.investment_name ? " · " + invEsc(n.investment_name) : ""}</span>
            </div>
            ${n.is_read ? "" : `<button type="button" class="btn btn-ghost-sm" onclick="markNotificationRead('${invEsc(n.id)}')"><span>Marcar como lida</span></button>`}
        </div>`).join("");
}

async function markNotificationRead(id) {
    try {
        await apiRequest("POST", `/api/investments/notifications/${encodeURIComponent(id)}/read`);
        const n = INV.notifications.find(x => x.id === id);
        if (n) n.is_read = true;
        renderNotifications();
        const dot = document.getElementById("invAlertsDot");
        if (dot) dot.hidden = INV.notifications.every(x => x.is_read);
    } catch (err) { toast(err.message || "Erro.", "error"); }
}

/* ─── Abas ──────────────────────────────────────────────────────────────── */
function switchInvestTab(tab) {
    INV.activeTab = tab;
    const map = { portfolio: "Portfolio", catalog: "Catalog", history: "History", alerts: "Alerts" };
    Object.entries(map).forEach(([k, v]) => {
        const on = k === tab;
        document.getElementById("invPanel" + v)?.classList.toggle("active", on);
        const b = document.getElementById("tabBtn" + v);
        if (b) { b.classList.toggle("active", on); b.setAttribute("aria-selected", String(on)); }
    });
}
