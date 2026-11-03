/**
 * Gráficos da conta — 4. Gastos por comerciante
 *   • Gráfico de barras horizontais: um comerciante (ou destino) por linha, do que recebeu mais para o que recebeu menos.
 *   • Cada barra mostra o valor total gasto nesse comerciante, quantas operações foram e que parte do total representa.
 *   • Tocar num comerciante mostra o detalhe (total, média, maior operação) e as suas operações, que abrem o detalhe do extrato.
 *   • Resumo: total gasto, nº de comerciantes, principal destino e peso dos três maiores.
 *   • Filtros: moeda, intervalo (30 dias a Tudo) e tipo de destino (compras ou transferências).
 * Usa só os movimentos reais do extrato (saídas concluídas). Sem sessão ou sem dados mostra um estado vazio.
 * Depende de card-chart.js (window.ccShared) e é chamado por ele quando este painel está aberto.
 */
(function () {
    "use strict";

    const PERIOD_KEY = "bankao_mc_period";
    const DAY = 86400000;
    const PERIODS = { "30d": 30, "90d": 90, "6m": 182, "1a": 365, all: 0 };
    const PERIOD_TXT = { "30d": "Últimos 30 dias", "90d": "Últimos 90 dias", "6m": "Últimos 6 meses", "1a": "Último ano", all: "Todo o histórico" };
    const KIND_TXT = { purchase: "Compra", transfer: "Transferência" };
    const STEP = 8;

    const M = {
        cur: null,
        period: (function () {
            try { const p = localStorage.getItem(PERIOD_KEY); if (p && p in PERIODS) return p; } catch (e) { /* ignorar */ }
            return "90d";
        })(),
        kind: "all",
        top: STEP,
        sel: null,
        model: null,
        sig: "",
        bound: false
    };

    const el = id => document.getElementById(id);
    const sh = () => window.ccShared;
    const esc = s => (typeof escapeHtml === "function" ? escapeHtml(String(s)) : String(s).replace(/[&<>"']/g, c => "&#" + c.charCodeAt(0) + ";"));
    const cur = () => M.cur || (M.cur = (state && state.prefCurrency) || "AOA");
    const hm = d => `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    const norm = s => String(s).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, " ").trim();

    /* ------------------------------ dados ------------------------------ */

    /** Nome do comerciante/destino de uma saída, ou null se esta saída não é um gasto (poupança, câmbio…). */
    function destination(tx) {
        const txt = `${tx.type || ""}`.toLowerCase();
        if (/savings|poupan|fx_|c[aâ]mbio/.test(txt)) return null;
        if (/levant|saque|withdraw|\batm\b/i.test(`${txt} ${tx.description || ""}`)) return null;   // levantar dinheiro não é um comerciante
        let kind = null;
        if (txt.startsWith("transfer")) kind = "transfer";
        else if (typeof classifyStatementTx === "function" && classifyStatementTx(tx) === "purchases") kind = "purchase";
        if (!kind) return null;
        let name = (tx.counterparty && tx.counterparty.name) || tx.description || "";
        name = String(name).replace(/\s+/g, " ").trim().replace(/^(compra|pagamento)(\s+(em|a|de|no|na))?\s+/i, "");
        if (!name) name = kind === "transfer" ? "Transferência" : "Compra";
        return { name, kind };
    }

    function collect() {
        const c = cur();
        const raw = (typeof state !== "undefined" && Array.isArray(state.transactions)) ? state.transactions : [];
        const days = PERIODS[M.period];
        const since = days ? Date.now() - days * DAY : 0;
        const out = [];
        raw.forEach(tx => {
            if ((tx.currency || "AOA") !== c) return;
            const v = Number(tx.amount_decimal) || 0;
            if (v >= 0 || !/^(completed|conclu)/i.test(String(tx.status || ""))) return;
            const t = parseTxDate(tx.created_at);
            if (isNaN(t) || (since && +t < since)) return;
            const d = destination(tx);
            if (!d) return;
            if (M.kind !== "all" && d.kind !== M.kind) return;
            out.push({ id: String(tx.id), t, v: -v, name: d.name, kind: d.kind, tx });
        });
        return out;
    }

    function buildModel() {
        const ops = collect();
        const map = new Map();
        ops.forEach(o => {
            const k = norm(o.name);
            let g = map.get(k);
            if (!g) { g = { key: k, name: o.name, total: 0, count: 0, max: 0, last: null, ops: [] }; map.set(k, g); }
            g.total += o.v; g.count++; g.max = Math.max(g.max, o.v);
            if (!g.last || o.t > g.last) g.last = o.t;
            g.ops.push(o);
        });
        const list = [...map.values()].sort((a, b) => b.total - a.total || b.count - a.count);
        list.forEach(g => g.ops.sort((a, b) => b.t - a.t));
        const total = list.reduce((a, g) => a + g.total, 0);
        const top3 = list.slice(0, 3).reduce((a, g) => a + g.total, 0);
        return { c: cur(), list, total, top3, count: list.length, nOps: ops.length, empty: !list.length };
    }

    /* ------------------------------ desenho ------------------------------ */

    const pct = (v, t) => (t > 0 ? Math.round((v / t) * 100) : 0);

    function drawChrome(model) {
        const S = sh(), c = model.c, e = model.empty;
        const pill = el("ccCurrency"); if (pill) pill.textContent = c;
        el("ccSubtitle").textContent = e ? (state.token ? "Ainda não há gastos neste período" : "Inicie sessão para ver os seus gastos") : "Os destinos para onde foi mais dinheiro";
        el("mcRange").textContent = PERIOD_TXT[M.period];
        document.querySelectorAll("#mcCurr .cc-chip").forEach(b => {
            const on = b.dataset.cur === c;
            b.classList.toggle("active", on);
            b.setAttribute("aria-checked", String(on));
        });
        document.querySelectorAll("#mcPeriods .cc-chip").forEach(b => {
            const on = b.dataset.p === M.period;
            b.classList.toggle("active", on);
            b.setAttribute("aria-pressed", String(on));
        });
        document.querySelectorAll("#mcKinds .mc-kind").forEach(b => {
            const on = b.dataset.k === M.kind;
            b.classList.toggle("active", on);
            b.setAttribute("aria-pressed", String(on));
        });

        const dash = "—", nb = "\u00a0", top = model.list[0];
        const set = (id, v, title) => { const n = el(id); n.textContent = e ? dash : v; n.title = e ? "" : (title || ""); };
        set("mcStatTotal", S.compactMoney(model.total, c), S.money(model.total, c));
        el("mcStatTotalNote").textContent = e ? nb : `${model.nOps} ${model.nOps === 1 ? "operação" : "operações"}`;
        set("mcStatCount", String(model.count));
        el("mcStatCountNote").textContent = e ? nb : (model.count === 1 ? "um destino" : "destinos diferentes");
        set("mcStatTop", top ? top.name : dash, top ? top.name : "");
        el("mcStatTopNote").textContent = e ? nb : (S.hidden() ? `${pct(top.total, model.total)}% do total` : `${S.compactMoney(top.total, c)} · ${pct(top.total, model.total)}%`);
        set("mcStatTop3", `${pct(model.top3, model.total)}%`);
        el("mcStatTop3Note").textContent = e ? nb : "do total gasto";
    }

    function drawChart(model, animate) {
        const root = el("mcChart"), more = el("mcMore"), S = sh();
        root.classList.toggle("no-anim", !animate);
        if (model.empty) {
            root.innerHTML = `<div class="cc-empty">${state.token ? "Ainda não há compras nem transferências nesta moeda e neste intervalo." : "Inicie sessão para ver onde gasta o seu dinheiro."}</div>`;
            more.hidden = true;
            return;
        }
        const max = model.list[0].total;
        const vis = model.list.slice(0, M.top);
        root.innerHTML = vis.map((g, i) => {
            const w = Math.max(2, (g.total / max) * 100);
            return `<button type="button" class="mc-row${g.key === M.sel ? " on" : ""}${i === 0 ? " first" : ""}" role="listitem" data-k="${esc(g.key)}" style="--w:${w.toFixed(1)}%;--d:${i * 45}ms" aria-label="${esc(g.name)}: ${esc(S.hidden() ? "valor oculto" : S.money(g.total, model.c))}, ${pct(g.total, model.total)}% do total">
                <span class="mc-rank">${i + 1}</span>
                <span class="mc-body">
                    <span class="mc-line"><b class="mc-name">${esc(g.name)}</b><strong class="mc-val">${S.money(g.total, model.c)}</strong></span>
                    <span class="mc-track"><i class="mc-fill"></i></span>
                    <span class="mc-meta">${g.count} ${g.count === 1 ? "operação" : "operações"} · ${pct(g.total, model.total)}% do total</span>
                </span>
            </button>`;
        }).join("");
        const rest = model.list.length - vis.length;
        more.hidden = rest <= 0 && M.top <= STEP;
        more.textContent = rest > 0 ? `Ver mais comerciantes (${rest})` : "Ver só os principais";
    }

    function drawDetail(model) {
        const S = sh(), c = model.c;
        const g = model.list.find(x => x.key === M.sel) || model.list[0];
        const ids = ["mcDetTotal", "mcDetCount", "mcDetAvg", "mcDetMax"];
        const badge = el("mcDetBadge"), ops = el("mcOps");
        if (!g) {
            el("mcDetTitle").textContent = "Sem comerciantes";
            el("mcDetSub").textContent = "Quando houver gastos, toque num comerciante para ver o detalhe";
            ids.forEach(i => { el(i).textContent = "—"; });
            badge.hidden = true; ops.innerHTML = "";
            return;
        }
        M.sel = g.key;
        el("mcDetTitle").textContent = g.name;
        const kinds = [...new Set(g.ops.map(o => KIND_TXT[o.kind]))].join(" e ");
        el("mcDetSub").textContent = `${kinds} · última a ${g.last.getDate()} ${S.MONTHS[g.last.getMonth()]} ${g.last.getFullYear()}`;
        el("mcDetTotal").textContent = S.money(g.total, c);
        el("mcDetCount").textContent = String(g.count);
        el("mcDetAvg").textContent = S.money(g.total / g.count, c);
        el("mcDetMax").textContent = S.money(g.max, c);
        badge.hidden = false;
        badge.className = "bc-delta";
        badge.textContent = `${pct(g.total, model.total)}% do total`;
        ops.innerHTML = g.ops.slice(0, 5).map(o => {
            const when = `${o.t.getDate()} ${S.MONTHS[o.t.getMonth()]} · ${hm(o.t)}`;
            return `<div class="cs-op" role="button" tabindex="0" data-id="${esc(o.id)}">
                <span class="cs-op-ic ${o.kind === "transfer" ? "withdrawal" : ""}"><svg aria-hidden="true"><use href="#${o.kind === "transfer" ? "i-swap" : "i-cart"}"/></svg></span>
                <span class="cs-op-main"><b>${esc(o.tx.description || o.name)}</b><small>${KIND_TXT[o.kind]} · ${when}</small></span>
                <span class="cs-op-side"><strong>−${S.money(o.v, c)}</strong></span>
            </div>`;
        }).join("") + (g.ops.length > 5 ? `<div class="cs-empty mc-more-note">+ ${g.ops.length - 5} operações anteriores</div>` : "");
        if (typeof statementTxById !== "undefined") g.ops.slice(0, 5).forEach(o => statementTxById.set(o.id, o.tx));
    }

    /* ------------------------------ Copilot ------------------------------ */

    function insights(row, chips, setTitle) {
        setTitle("Análise dos seus gastos por comerciante");
        const m = M.model;
        if (!m || m.empty) {
            row("info", "#i-spark", "Sem gastos para analisar", state.token ? "Neste intervalo não há compras nem transferências nesta moeda." : "Inicie sessão para o Copilot analisar para onde vai o seu dinheiro.");
            chips.push("Como acompanhar os meus gastos?");
            return;
        }
        const S = sh(), b = v => `<b>${S.money(v, m.c)}</b>`, top = m.list[0];
        row("tip", "#i-award", "Principal destino", `${esc(top.name)} recebeu ${b(top.total)}: ${pct(top.total, m.total)}% de tudo o que gastou (${PERIOD_TXT[M.period].toLowerCase()}).`);
        if (m.count >= 3) {
            const p3 = pct(m.top3, m.total);
            row(p3 >= 70 ? "warn" : "info", "#i-pie", p3 >= 70 ? "Gastos concentrados" : "Gastos repartidos",
                `Os três maiores destinos somam ${p3}% do total (${b(m.top3)}).`);
        }
        const freq = [...m.list].sort((a, z) => z.count - a.count)[0];
        if (freq && freq.count > 1 && freq.key !== top.key) row("info", "#i-refresh", "Mais frequente", `${esc(freq.name)} aparece em ${freq.count} operações, num total de ${b(freq.total)}.`);
        chips.push(`Quanto gastei em ${top.name}?`, "Como reduzir os meus maiores gastos?", "Onde posso poupar mais?");
    }

    /* ------------------------------ ciclo de vida ------------------------------ */

    function signature() {
        const raw = (typeof state !== "undefined" && Array.isArray(state.transactions)) ? state.transactions : [];
        return [cur(), state.token ? 1 : 0, raw.length, raw[0] ? raw[0].id : "", M.period, M.kind, M.top, M.sel, sh().hidden() ? 1 : 0].join("|");
    }
    function visible() {
        const v = el("view-card-chart"), p = el("bcPanelMerchants");
        return !!(v && p && v.classList.contains("active") && !p.hidden);
    }

    function render(opts) {
        if (!visible()) return;
        bind();
        const model = buildModel();
        M.model = model;
        if (!model.list.some(g => g.key === M.sel)) M.sel = model.list[0] ? model.list[0].key : null;
        drawChrome(model);
        drawChart(model, !(opts && opts.noAnim));
        drawDetail(model);
        M.sig = signature();
        if (typeof window.refreshCardCopilot === "function") window.refreshCardCopilot();
    }
    function refresh() { if (visible() && signature() !== M.sig) render({ noAnim: true }); }

    function bind() {
        if (M.bound) return;
        M.bound = true;
        el("mcCurr").addEventListener("click", ev => {
            const b = ev.target.closest(".cc-chip");
            if (!b || b.dataset.cur === cur()) return;
            M.cur = b.dataset.cur; M.sel = null; M.top = STEP; render();
        });
        el("mcPeriods").addEventListener("click", ev => {
            const b = ev.target.closest(".cc-chip");
            if (!b || b.dataset.p === M.period) return;
            M.period = b.dataset.p; M.sel = null; M.top = STEP;
            try { localStorage.setItem(PERIOD_KEY, M.period); } catch (e) { /* ignorar */ }
            render();
        });
        el("mcKinds").addEventListener("click", ev => {
            const b = ev.target.closest(".mc-kind");
            if (!b || b.dataset.k === M.kind) return;
            M.kind = b.dataset.k; M.sel = null; M.top = STEP; render();
        });
        el("mcChart").addEventListener("click", ev => {
            const r = ev.target.closest(".mc-row");
            if (!r || !M.model) return;
            M.sel = r.dataset.k;
            document.querySelectorAll("#mcChart .mc-row").forEach(x => x.classList.toggle("on", x === r));
            drawDetail(M.model);
            M.sig = signature();
            if (typeof window.refreshCardCopilot === "function") window.refreshCardCopilot();
        });
        el("mcMore").addEventListener("click", () => {
            const rest = M.model ? M.model.list.length - M.top : 0;
            M.top = rest > 0 ? M.top + STEP : STEP;
            render({ noAnim: true });
        });
        const open = ev => {
            const row = ev.target.closest(".cs-op[data-id]");
            if (!row || (ev.type === "keydown" && ev.key !== "Enter" && ev.key !== " ")) return;
            ev.preventDefault();
            if (typeof openTxDetail === "function") openTxDetail(row.dataset.id);
        };
        el("mcOps").addEventListener("click", open);
        el("mcOps").addEventListener("keydown", open);
    }

    window.renderMerchants = render;
    window.refreshMerchants = refresh;
    window.merchantInsights = insights;
})();
