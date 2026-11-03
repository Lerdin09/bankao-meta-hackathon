/**
 * Gráficos da conta — 3. Fluxo de gastos do cartão
 *   • Gráfico de barras por dia, semana ou mês: cada barra empilha Compras, Levantamentos e Pendentes;
 *     os Estornos descem abaixo da linha do zero (dinheiro que voltou ao cartão).
 *   • Um cartão por moeda (Kwanza, Euro, Dólar): tocar no cartão muda a análise.
 *   • "Comparar períodos": toque numa barra (A) e noutra (B) para ver a diferença categoria a categoria.
 *     Sem comparar, o detalhe mostra a variação face ao período anterior.
 *   • Lista de operações do período escolhido, filtrável (compras, levantamentos, estornos, pendentes).
 *     Tocar numa operação abre o detalhe do extrato.
 * Usa só os movimentos reais do extrato; sem sessão ou sem operações de cartão mostra um estado vazio.
 * Depende de card-chart.js (window.ccShared) e é chamado por ele quando este painel está aberto.
 */
(function () {
    "use strict";

    const GRAN_KEY = "bankao_cs_gran";
    const DAY = 86400000;
    const GRANS = {
        day: { one: "dia", prev: "do dia anterior", now: "Hoje", many: "dias" },
        week: { one: "semana", prev: "da semana anterior", now: "Semana em curso", many: "semanas" },
        month: { one: "mês", prev: "do mês anterior", now: "Mês em curso", many: "meses" }
    };
    const CARDS = [
        { cur: "AOA", name: "Kwanza", cls: "card-aoa" },
        { cur: "EUR", name: "Euro", cls: "card-eur" },
        { cur: "USD", name: "Dólar", cls: "card-usd" }
    ];
    const KINDS = {
        purchase: { label: "Compra", icon: "i-cart" },
        withdrawal: { label: "Levantamento", icon: "i-wallet" },
        refund: { label: "Estorno", icon: "i-refresh" }
    };
    const FILTERS = [
        ["all", "Todas"], ["purchase", "Compras"], ["withdrawal", "Levantamentos"], ["refund", "Estornos"], ["pending", "Pendentes"]
    ];
    const C_BUY = "#818CF8", C_WD = "#FBBF24", C_PEND = "#94A3B8", C_REF = "#34D399";
    const PAGE = 8;

    const C = {
        card: null,
        gran: (function () {
            try { const g = localStorage.getItem(GRAN_KEY); if (g && g in GRANS) return g; } catch (e) { /* ignorar */ }
            return "week";
        })(),
        off: 0,
        sel: null,
        cmp: false,
        cmpB: null,
        filter: "all",
        shown: PAGE,
        model: null,
        data: null,
        geom: null,
        width: 0,
        sig: "",
        bound: false
    };

    const el = id => document.getElementById(id);
    const sh = () => window.ccShared;
    const r1 = n => Math.round(n * 10) / 10;
    const esc = s => (typeof escapeHtml === "function" ? escapeHtml(String(s)) : String(s).replace(/[&<>"']/g, c => "&#" + c.charCodeAt(0) + ";"));
    const cur = () => C.card || (C.card = (state && state.prefCurrency) || "AOA");

    /* ------------------------------ períodos ------------------------------ */

    function startOf(g, d) {
        if (g === "day") return new Date(d.getFullYear(), d.getMonth(), d.getDate());
        if (g === "week") return new Date(d.getFullYear(), d.getMonth(), d.getDate() - ((d.getDay() + 6) % 7));
        return new Date(d.getFullYear(), d.getMonth(), 1);
    }
    function shift(g, s, n) {
        if (g === "day") return new Date(s.getFullYear(), s.getMonth(), s.getDate() + n);
        if (g === "week") return new Date(s.getFullYear(), s.getMonth(), s.getDate() + 7 * n);
        return new Date(s.getFullYear(), s.getMonth() + n, 1);
    }
    function perPage(w, g) {
        const narrow = w < 520;
        return g === "day" ? (narrow ? 7 : 14) : g === "week" ? (narrow ? 8 : 12) : (narrow ? 6 : 12);
    }
    function labelShort(g, b) {
        const M = sh().MONTHS, d = b.start;
        if (g === "month") return M[d.getMonth()];
        return `${d.getDate()} ${M[d.getMonth()]}`;
    }
    function labelLong(g, b) {
        const M = sh().MONTHS, d = b.start;
        if (g === "day") return `${d.getDate()} ${M[d.getMonth()]} ${d.getFullYear()}`;
        if (g === "week") {
            const last = new Date(b.end.getFullYear(), b.end.getMonth(), b.end.getDate() - 1);
            return `${d.getDate()} ${M[d.getMonth()]} – ${last.getDate()} ${M[last.getMonth()]} ${last.getFullYear()}`;
        }
        return `${M[d.getMonth()]} ${d.getFullYear()}`;
    }
    const hm = d => `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;

    /* ------------------------------ dados ------------------------------ */

    /** Classifica um movimento real como operação de cartão (ou null se não for). */
    function classify(tx) {
        const v = Number(tx.amount_decimal) || 0;
        if (!v) return null;
        const txt = `${tx.type || ""} ${tx.description || ""}`.toLowerCase();
        if (/savings|poupan|deposit|dep[oó]sito|fx_|c[aâ]mbio/.test(txt)) return null;
        if (v > 0) return /estorn|refund|reembols|devolu|chargeback/.test(txt) ? "refund" : null;
        if (/levant|saque|withdraw|\batm\b/.test(txt)) return "withdrawal";
        if (typeof classifyStatementTx === "function" && classifyStatementTx(tx) === "purchases") return "purchase";
        return null;
    }

    function realOps(c) {
        const raw = (typeof state !== "undefined" && Array.isArray(state.transactions)) ? state.transactions : [];
        const ops = [];
        raw.forEach(tx => {
            if ((tx.currency || "AOA") !== c || /fail|falh/i.test(String(tx.status || ""))) return;
            const kind = classify(tx);
            if (!kind) return;
            const t = parseTxDate(tx.created_at);
            if (isNaN(t)) return;
            ops.push({
                id: String(tx.id), t, v: Math.abs(Number(tx.amount_decimal) || 0), kind,
                pending: !/^(completed|conclu)/i.test(String(tx.status || "")),
                desc: tx.description || KINDS[kind].label, tx
            });
        });
        return ops;
    }

    function collect() {
        const c = cur();
        const ops = state.token ? realOps(c) : [];
        ops.sort((a, b) => b.t - a.t);
        return { c, ops, hasSession: !!state.token };
    }

    function buildModel(w) {
        const data = collect();
        C.data = data;
        const g = C.gran, n = perPage(w, g), today = new Date(), now = startOf(g, today);
        let first = today;
        data.ops.forEach(o => { if (o.t < first) first = o.t; });
        const firstStart = startOf(g, first);

        const buckets = [];
        for (let i = 0; i < n; i++) {
            const start = shift(g, now, -(C.off * n + (n - 1 - i)));
            buckets.push({ start, end: shift(g, start, 1), buy: 0, wd: 0, pend: 0, ref: 0, ops: [], current: +start === +now });
        }
        while (buckets.length > 1 && +buckets[0].start < +firstStart) buckets.shift();
        const idx = new Map(buckets.map((b, i) => [+b.start, i]));
        data.ops.forEach(o => {
            const k = idx.get(+startOf(g, o.t));
            if (k == null) return;
            const b = buckets[k];
            b.ops.push(o);
            if (o.pending) { if (o.kind !== "refund") b.pend += o.v; }
            else if (o.kind === "purchase") b.buy += o.v;
            else if (o.kind === "withdrawal") b.wd += o.v;
            else b.ref += o.v;
        });
        const tot = { buy: 0, wd: 0, pend: 0, ref: 0, nBuy: 0, nWd: 0, nRef: 0, nPend: 0 };
        buckets.forEach(b => {
            b.spent = b.buy + b.wd;
            tot.buy += b.buy; tot.wd += b.wd; tot.pend += b.pend; tot.ref += b.ref;
            b.ops.forEach(o => {
                if (o.pending) tot.nPend++;
                else if (o.kind === "purchase") tot.nBuy++;
                else if (o.kind === "withdrawal") tot.nWd++;
                else tot.nRef++;
            });
        });
        tot.spent = tot.buy + tot.wd;
        return { c: data.c, g, n: buckets.length, empty: data.ops.length === 0, buckets, tot, canPrev: +buckets[0].start > +firstStart, canNext: C.off > 0 };
    }

    /* ------------------------------ desenho ------------------------------ */

    function geometry(model, w) {
        const h = w < 520 ? 270 : w < 900 ? 310 : 350;
        const m = { l: w < 520 ? 44 : 52, r: 10, t: 14, b: 28 };
        const iw = w - m.l - m.r, ih = h - m.t - m.b, n = model.n;
        let hi = 0, lo = 0;
        model.buckets.forEach(b => { hi = Math.max(hi, b.spent + b.pend); lo = Math.min(lo, -b.ref); });
        const sc = sh().niceScale(lo, hi, lo < 0);
        const slot = iw / n;
        const cx = i => m.l + slot * (i + 0.5);
        const y = v => m.t + ih * (1 - (v - sc.min) / (sc.max - sc.min));
        return { w, h, m, iw, ih, n, sc, slot, cx, y };
    }

    function topRounded(x, yTop, yBase, bw) {
        const h = yBase - yTop;
        if (h <= 0.4) return "";
        const r = Math.min(5, bw / 2, h);
        return `M${r1(x)} ${r1(yBase)}V${r1(yTop + r)}Q${r1(x)} ${r1(yTop)} ${r1(x + r)} ${r1(yTop)}H${r1(x + bw - r)}Q${r1(x + bw)} ${r1(yTop)} ${r1(x + bw)} ${r1(yTop + r)}V${r1(yBase)}Z`;
    }
    const rect = (x, y1, y2, bw, cls) => (y2 - y1 > 0.4 ? `<rect class="${cls}" x="${r1(x)}" y="${r1(y1)}" width="${r1(bw)}" height="${r1(y2 - y1)}"/>` : "");

    function svgMarkup(model, w, hide) {
        const g = geometry(model, w);
        const { m, n, sc, slot, cx, y } = g;
        const y0 = y(0);
        const bw = Math.max(6, Math.min(slot * 0.56, 40));
        const grid = sc.values.map(v => `<line class="${v === 0 ? "base" : ""}" x1="${m.l}" x2="${w - m.r}" y1="${r1(y(v))}" y2="${r1(y(v))}"/>`).join("");
        const maxAbs = Math.max(Math.abs(sc.min), Math.abs(sc.max));
        const unit = maxAbs >= 1e6 ? 1e6 : maxAbs >= 1e4 ? 1e3 : 1;
        const yl = hide ? "" : sc.values.map(v => `<text x="${m.l - 8}" y="${r1(y(v)) + 3.5}" text-anchor="end">${sh().axisLabel(v, unit)}</text>`).join("");
        const step = slot < 46 ? Math.ceil(46 / slot) : 1;
        let xl = "";
        model.buckets.forEach((b, i) => { if (i % step === 0) xl += `<text x="${r1(cx(i))}" y="${g.h - 8}" text-anchor="middle">${labelShort(model.g, b)}</text>`; });

        let cols = "", bars = "", hits = "";
        model.buckets.forEach((b, i) => {
            const x = cx(i) - bw / 2;
            cols += `<rect class="cs-col" data-i="${i}" x="${r1(cx(i) - slot / 2 + 2)}" y="${m.t - 4}" width="${r1(slot - 4)}" height="${r1(g.ih + 4)}" rx="10"/>`;
            const segs = [["buy", b.buy], ["wd", b.wd], ["pend", b.pend]].filter(s => s[1] > 0);
            let base = 0;
            segs.forEach((s, k) => {
                const top = base + s[1], last = k === segs.length - 1;
                const cls = `fl-bar cs-bar-${s[0]}`;
                const style = `style="--d:${i * 30}ms"`;
                if (last) bars += `<path class="${cls}" ${style} d="${topRounded(x, y(top), y(base), bw)}"/>`;
                else bars += rect(x, y(top), y(base), bw, cls).replace("class=", `${style} class=`);
                base = top;
            });
            if (b.ref > 0) bars += rect(x, y0, y(-b.ref), bw, "fl-bar cs-bar-ref").replace("class=", `style="--d:${i * 30 + 80}ms" class=`);
            hits += `<rect class="fl-hit" data-i="${i}" x="${r1(cx(i) - slot / 2)}" y="0" width="${r1(slot)}" height="${g.h}"/>`;
        });
        const defs = `<defs><pattern id="csHatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="rgba(148,163,184,.16)"/><rect width="2.6" height="6" fill="rgba(203,213,225,.78)"/></pattern></defs>`;
        return `<svg class="cc-svg fl-svg cs-svg" id="csSvg" viewBox="0 0 ${w} ${g.h}" width="${w}" height="${g.h}" tabindex="0" focusable="true" aria-label="Gráfico de barras. Use as setas para ler cada período.">
${defs}<g class="cc-grid">${grid}</g>
<g class="cc-axis">${yl}${xl}</g>
<g>${cols}</g>
<g class="fl-bars">${bars}</g>
<g>${hits}</g>
</svg>`;
    }

    function drawChart(model, animate) {
        const root = el("csChart");
        if (!root) return;
        const w = Math.max(280, Math.floor(root.clientWidth));
        C.width = w;
        root.classList.toggle("no-anim", !animate);
        if (model.empty) {
            root.innerHTML = `<div class="cc-empty">${state.token ? "Ainda não há compras nem levantamentos neste cartão." : "Inicie sessão para ver os gastos do seu cartão."}</div>`;
            C.geom = null;
            C.sel = model.n - 1;
            drawDetail(model, C.sel);
            drawOps(model, C.sel);
            return;
        }
        root.innerHTML = svgMarkup(model, w, sh().hidden()) + `<div class="cc-tip" id="csTip" role="status"></div>`;
        C.geom = geometry(model, w);
        root.setAttribute("aria-label", `Gráfico de barras dos gastos do cartão, ${model.n} ${GRANS[model.g].many}`);

        const svg = el("csSvg");
        svg.querySelectorAll(".fl-hit").forEach(r => {
            const i = +r.dataset.i;
            r.addEventListener("pointerdown", () => pick(i, true));
            r.addEventListener("pointermove", ev => { if (ev.pointerType === "mouse" && !C.cmp) select(i, true); });
            r.addEventListener("pointerleave", ev => { if (ev.pointerType === "mouse") hideTip(); });
        });
        svg.addEventListener("keydown", ev => {
            const curI = C.sel == null ? model.n - 1 : C.sel;
            const map = { ArrowRight: Math.min(model.n - 1, curI + 1), ArrowLeft: Math.max(0, curI - 1), Home: 0, End: model.n - 1 };
            if (ev.key in map) { ev.preventDefault(); pick(map[ev.key], true); }
        });
        let def = model.n - 1;
        for (let k = model.n - 1; k >= 0; k--) { if (model.buckets[k].ops.length) { def = k; break; } }
        select(C.sel == null || C.sel >= model.n ? def : C.sel, false);
    }

    function hideTip() { const t = el("csTip"); if (t) t.classList.remove("on"); }

    /** Toque numa barra: em modo comparar alterna entre A e B; senão escolhe o período. */
    function pick(i, showTip) {
        if (C.cmp && C.sel != null && C.cmpB == null && i !== C.sel) {
            C.cmpB = i;
            select(C.sel, false);
            return;
        }
        if (C.cmp && C.cmpB != null) C.cmpB = null;
        if (i !== C.sel) C.shown = PAGE;
        select(i, showTip);
        if (typeof window.refreshCardCopilot === "function") window.refreshCardCopilot();
    }

    function markCols() {
        document.querySelectorAll("#csSvg .cs-col").forEach(c => {
            const i = +c.dataset.i;
            c.classList.toggle("on", i === C.sel);
            c.classList.toggle("on-b", C.cmp && i === C.cmpB);
        });
    }

    function select(i, showTip) {
        const model = C.model, g = C.geom;
        if (!model || !g || i < 0 || i >= model.n) return;
        C.sel = i;
        markCols();
        drawDetail(model, i);
        drawOps(model, i);

        const tip = el("csTip");
        if (!tip) return;
        if (!showTip) { tip.classList.remove("on"); return; }
        const b = model.buckets[i], S = sh();
        const row = (col, lbl, v) => `<span class="fl-tip-r"><i style="background:${col}"></i>${lbl}<strong>${S.money(v, model.c)}</strong></span>`;
        tip.innerHTML = `<b>${labelLong(model.g, b)}</b>` + row(C_BUY, "Compras", b.buy) + row(C_WD, "Levantamentos", b.wd)
            + (b.pend ? row(C_PEND, "Pendentes", b.pend) : "") + (b.ref ? row(C_REF, "Estornos", b.ref) : "");
        const px = g.cx(i), tw = tip.offsetWidth || 190;
        const scale = (el("csChart").clientWidth || g.w) / g.w;
        let left = px * scale + g.slot * scale * 0.5 + 6;
        if (left + tw > g.w * scale - 2) left = px * scale - g.slot * scale * 0.5 - tw - 6;
        tip.style.left = Math.max(2, left) + "px";
        tip.style.top = (g.m.t + 4) + "px";
        tip.classList.add("on");
    }

    /* ------------------------------ cartões, resumo e detalhe ------------------------------ */

    function drawCards() {
        const root = el("csCards");
        if (!root) return;
        const S = sh();
        const hasAcc = c => (state.accounts || []).some(a => a.currency === c);
        const html = CARDS.map(k => {
            const on = k.cur === cur();
            const acc = (state.accounts || []).find(a => a.currency === k.cur);
            const sub = acc ? `Cartão ·· ${String(acc.account_number || "").slice(-4) || "0000"}` : (state.token ? "Sem conta" : "Sem sessão");
            return `<button type="button" class="cs-card ${k.cls}${on ? " active" : ""}" role="radio" aria-checked="${on}" data-cur="${k.cur}">
                <span class="cs-card-chip" aria-hidden="true"></span>
                <span class="cs-card-name">${k.name}<b>${k.cur}</b></span>
                <span class="cs-card-sub">${esc(sub)}</span>
            </button>`;
        }).join("");
        if (root.dataset.sig !== html) { root.innerHTML = html; root.dataset.sig = html; }
        void S; void hasAcc;
    }

    function pctTxt(a, b) {
        if (!(b > 0)) return null;
        return Math.round(Math.abs(a / b - 1) * 100);
    }

    function drawChrome(model) {
        const S = sh(), gi = GRANS[model.g], t = model.tot, c = model.c;
        document.querySelectorAll("#csGrans .cc-chip").forEach(b => {
            const on = b.dataset.gran === model.g;
            b.classList.toggle("active", on);
            b.setAttribute("aria-pressed", String(on));
        });
        const cmp = el("csCmp");
        cmp.classList.toggle("active", C.cmp);
        cmp.setAttribute("aria-pressed", String(C.cmp));
        const a = model.buckets[0], z = model.buckets[model.n - 1];
        el("csRange").textContent = model.g === "month"
            ? (labelLong("month", a) === labelLong("month", z) ? labelLong("month", z) : `${labelLong("month", a)} – ${labelLong("month", z)}`)
            : `${labelLong(model.g, a).split(" – ")[0]} – ${labelLong(model.g, z).split(" – ").pop()}`;
        el("ccSubtitle").textContent = model.empty ? (state.token ? "Ainda não há operações neste cartão" : "Inicie sessão para ver as suas operações") : "Compras, levantamentos, estornos e operações pendentes";
        const pill = el("ccCurrency"); if (pill) pill.textContent = c;
        el("csPrev").disabled = !model.canPrev;
        el("csNext").disabled = !model.canNext;

        const avg = v => S.hidden() ? "\u00a0" : `≈ ${S.compactMoney(v / model.n, c)} / ${model.g === "week" ? "sem." : gi.one}`;
        const e = model.empty;
        const set = (id, v, title) => { const n = el(id); n.textContent = e ? "—" : v; n.title = e ? "" : (title || ""); };
        set("csStatSpent", S.compactMoney(t.spent, c), S.money(t.spent, c));
        el("csStatSpentNote").textContent = e ? "\u00a0" : t.pend > 0 && !S.hidden() ? `+ ${S.compactMoney(t.pend, c)} pendentes` : (t.spent ? avg(t.spent) : "\u00a0");
        set("csStatBuy", S.compactMoney(t.buy, c), S.money(t.buy, c));
        el("csStatBuyNote").textContent = e ? "\u00a0" : `${t.nBuy} ${t.nBuy === 1 ? "compra" : "compras"}`;
        set("csStatWd", S.compactMoney(t.wd, c), S.money(t.wd, c));
        el("csStatWdNote").textContent = e ? "\u00a0" : `${t.nWd} ${t.nWd === 1 ? "levantamento" : "levantamentos"}`;
        set("csStatRef", S.compactMoney(t.ref, c), S.money(t.ref, c));
        el("csStatRefNote").textContent = e ? "\u00a0" : `${t.nRef} ${t.nRef === 1 ? "estorno" : "estornos"}`;
    }

    function drawDetail(model, i) {
        const S = sh(), b = model.buckets[i], gi = GRANS[model.g], c = model.c;
        el("csDetTitle").textContent = (C.cmp ? "A · " : "") + labelLong(model.g, b);
        let sub = b.current ? gi.now : "Período fechado";
        const prev = i > 0 ? model.buckets[i - 1] : null;
        const badge = el("csDetBadge");
        badge.hidden = true;
        if (!C.cmp && prev) {
            const p = pctTxt(b.spent, prev.spent);
            if (p != null && p >= 1 && prev.spent > 0 && b.spent > 0) {
                const up = b.spent > prev.spent;
                sub += ` · gastos ${p}% ${up ? "acima" : "abaixo"} ${gi.prev}`;
                badge.hidden = false;
                badge.className = "bc-delta " + (up ? "down" : "up");
                badge.textContent = `${up ? "+" : "−"}${p}%`;
            }
        }
        if (C.cmp) sub = C.cmpB == null ? "Toque noutra barra para escolher o período B" : "A comparar dois períodos";
        el("csDetSub").textContent = sub;
        el("csDetBuy").textContent = S.money(b.buy, c);
        el("csDetWd").textContent = S.money(b.wd, c);
        el("csDetPend").textContent = S.money(b.pend, c);
        el("csDetRef").textContent = S.money(b.ref, c);
        const total = b.buy + b.wd + b.pend;
        const pc = v => (total ? (v / total) * 100 : 0) + "%";
        el("csMBuy").style.width = pc(b.buy);
        el("csMWd").style.width = pc(b.wd);
        el("csMPend").style.width = pc(b.pend);
        el("csMeter").classList.toggle("empty", !total);
        drawCompare(model, i);
    }

    function drawCompare(model, i) {
        const box = el("csCompare");
        if (!C.cmp || C.cmpB == null || C.cmpB >= model.n) { box.hidden = true; box.innerHTML = ""; return; }
        const S = sh(), A = model.buckets[i], B = model.buckets[C.cmpB], c = model.c;
        const rows = [["Total gasto", A.spent, B.spent, true], ["Compras", A.buy, B.buy, true], ["Levantamentos", A.wd, B.wd, true], ["Pendentes", A.pend, B.pend, true], ["Estornos", A.ref, B.ref, false]];
        const delta = (a, bb, bad) => {
            if (!a && !bb) return `<span class="cs-cmp-d flat">—</span>`;
            const p = pctTxt(a, bb);
            const up = a > bb;
            const cls = a === bb ? "flat" : (up === bad ? "down" : "up");
            return `<span class="cs-cmp-d ${cls}">${a === bb ? "igual" : (up ? "+" : "−") + (p != null ? p + "%" : "novo")}</span>`;
        };
        box.innerHTML = `<div class="cs-cmp-head"><span></span><b>A</b><b>B</b><span>Var.</span></div>
            <div class="cs-cmp-sub"><span></span><small>${esc(labelShort(model.g, A))}</small><small>${esc(labelShort(model.g, B))}</small><span></span></div>`
            + rows.map(r => `<div class="cs-cmp-row${r[0] === "Total gasto" ? " total" : ""}"><span>${r[0]}</span><b>${S.compactMoney(r[1], c)}</b><b>${S.compactMoney(r[2], c)}</b>${delta(r[1], r[2], r[3])}</div>`).join("");
        box.hidden = false;
    }

    /* ------------------------------ operações ------------------------------ */

    function drawOps(model, i) {
        const S = sh(), b = model.buckets[i], c = model.c;
        const counts = { all: b.ops.length, purchase: 0, withdrawal: 0, refund: 0, pending: 0 };
        b.ops.forEach(o => { if (o.pending) counts.pending++; else counts[o.kind]++; });
        el("csOpsTitle").textContent = `Operações · ${labelLong(model.g, b)}`;
        el("csOpsSub").textContent = b.ops.length ? `${b.ops.length} ${b.ops.length === 1 ? "operação" : "operações"} neste período` : "Sem operações neste período";

        const f = el("csFilters");
        f.innerHTML = FILTERS.map(k => `<button type="button" class="cs-filter${C.filter === k[0] ? " active" : ""}" data-f="${k[0]}" aria-pressed="${C.filter === k[0]}">${k[1]}<em>${counts[k[0]]}</em></button>`).join("");

        const list = b.ops.filter(o => C.filter === "all" || (C.filter === "pending" ? o.pending : (!o.pending && o.kind === C.filter)));
        const root = el("csList"), more = el("csMore");
        if (!list.length) {
            root.innerHTML = `<div class="cs-empty">${b.ops.length ? "Nenhuma operação deste tipo neste período." : (model.empty && !state.token ? "Inicie sessão para ver as operações do seu cartão." : "Não há operações de cartão neste período.")}</div>`;
            more.hidden = true;
            return;
        }
        const vis = list.slice(0, C.shown);
        root.innerHTML = vis.map(o => {
            const k = KINDS[o.kind], credit = o.kind === "refund";
            const when = `${o.t.getDate()} ${S.MONTHS[o.t.getMonth()]} · ${hm(o.t)}`;
            const tag = o.pending ? `<span class="cs-tag pend">Pendente</span>` : (credit ? `<span class="cs-tag ref">Estorno</span>` : `<span class="cs-tag ok">Concluído</span>`);
            return `<div class="cs-op" role="button" tabindex="0" data-id="${esc(o.id)}">
                <span class="cs-op-ic ${o.pending ? "pend" : o.kind}"><svg aria-hidden="true"><use href="#${k.icon}"/></svg></span>
                <span class="cs-op-main"><b>${esc(o.desc)}</b><small>${k.label} · ${when}</small></span>
                <span class="cs-op-side"><strong class="${credit ? "in" : ""}">${credit ? "+" : "−"}${S.money(o.v, c)}</strong>${tag}</span>
            </div>`;
        }).join("");
        more.hidden = list.length <= C.shown;
        if (!more.hidden) more.textContent = `Ver mais operações (${list.length - C.shown})`;
        if (typeof statementTxById !== "undefined") vis.forEach(o => { if (o.tx) statementTxById.set(String(o.id), o.tx); });
    }

    /* ------------------------------ Copilot ------------------------------ */

    function insights(row, chips, setTitle) {
        setTitle("Análise dos gastos do cartão");
        const m = C.model;
        if (!m) { row("info", "#i-spark", "A preparar a análise", "Abra o gráfico para o Copilot analisar os gastos do cartão."); return; }
        const S = sh(), c = m.c, b = v => `<b>${S.money(v, c)}</b>`;
        const gi = GRANS[m.g];
        const i = C.sel == null ? m.n - 1 : C.sel, cur0 = m.buckets[i], prev = i > 0 ? m.buckets[i - 1] : null;
        if (m.empty || (!cur0.ops.length && !m.tot.spent)) {
            row("info", "#i-spark", "Sem gastos no cartão", m.empty && !state.token ? "Inicie sessão para o Copilot analisar os gastos do seu cartão." : "Neste intervalo não há compras nem levantamentos neste cartão.");
            chips.push("Como controlar os gastos do meu cartão?");
            return;
        }
        if (prev && prev.spent > 0 && cur0.spent > 0) {
            const p = pctTxt(cur0.spent, prev.spent), up = cur0.spent > prev.spent;
            row(up ? "warn" : "good", "#i-trending", up ? "Gastos a subir" : "Gastos a descer",
                `Em ${esc(labelLong(m.g, cur0))} gastou ${b(cur0.spent)}: ${p}% ${up ? "mais" : "menos"} do que ${gi.prev} (${b(prev.spent)}).`);
        } else {
            row("info", "#i-trending", "Gasto do período", `Em ${esc(labelLong(m.g, cur0))} gastou ${b(cur0.spent)}.`);
        }
        const big = m.buckets.flatMap(x => x.ops).filter(o => o.kind === "purchase" && !o.pending).sort((x, y) => y.v - x.v)[0];
        if (big) row("tip", "#i-cart", "Maior compra", `${b(big.v)} em ${esc(big.desc)}, a ${big.t.getDate()} de ${S.MONTHS[big.t.getMonth()]}.`);
        if (m.tot.pend > 0) row("info", "#i-bell", "Operações pendentes", `${m.tot.nPend} ${m.tot.nPend === 1 ? "operação ainda não foi confirmada" : "operações ainda não foram confirmadas"}, no total de ${b(m.tot.pend)}.`);
        if (m.tot.ref > 0) row("good", "#i-refresh", "Estornos recebidos", `Já recuperou ${b(m.tot.ref)} em ${m.tot.nRef} ${m.tot.nRef === 1 ? "estorno" : "estornos"}.`);
        chips.push("Onde estou a gastar mais com o cartão?", "Como reduzir os meus gastos do cartão?", "Tenho operações pendentes?");
    }

    /* ------------------------------ ciclo de vida ------------------------------ */

    function signature() {
        const raw = (typeof state !== "undefined" && Array.isArray(state.transactions)) ? state.transactions : [];
        return [cur(), state.token ? 1 : 0, raw.length, raw[0] ? raw[0].id : "", +sh().dayStart(new Date()), C.gran, C.off, sh().hidden() ? 1 : 0, C.width].join("|");
    }

    function visible() {
        const view = el("view-card-chart"), panel = el("bcPanelCard");
        return !!(view && panel && view.classList.contains("active") && !panel.hidden);
    }

    function render(opts) {
        if (!visible()) return;
        bind();
        const root = el("csChart");
        const w = Math.max(280, Math.floor(root.clientWidth));
        const model = buildModel(w);
        C.model = model;
        drawCards();
        drawChrome(model);
        drawChart(model, !(opts && opts.noAnim));
        C.sig = signature();
        if (typeof window.refreshCardCopilot === "function") window.refreshCardCopilot();
    }

    function refresh() {
        if (visible() && signature() !== C.sig) render({ noAnim: true });
    }

    function reset() { C.off = 0; C.sel = null; C.cmpB = null; C.shown = PAGE; }

    function bind() {
        if (C.bound) return;
        C.bound = true;
        el("csCards").addEventListener("click", ev => {
            const b = ev.target.closest(".cs-card");
            if (!b || b.dataset.cur === cur()) return;
            C.card = b.dataset.cur; reset(); C.filter = "all";
            render();
        });
        document.querySelectorAll("#csGrans .cc-chip").forEach(btn => btn.addEventListener("click", () => {
            if (C.gran === btn.dataset.gran) return;
            C.gran = btn.dataset.gran; reset();
            try { localStorage.setItem(GRAN_KEY, C.gran); } catch (e) { /* ignorar */ }
            render();
        }));
        el("csCmp").addEventListener("click", () => {
            C.cmp = !C.cmp; C.cmpB = null;
            if (C.model) { markCols(); drawChrome(C.model); drawDetail(C.model, C.sel == null ? C.model.n - 1 : C.sel); }
        });
        el("csPrev").addEventListener("click", () => { if (C.model && C.model.canPrev) { C.off++; C.sel = null; C.cmpB = null; render(); } });
        el("csNext").addEventListener("click", () => { if (C.off > 0) { C.off--; C.sel = null; C.cmpB = null; render(); } });
        el("csFilters").addEventListener("click", ev => {
            const b = ev.target.closest(".cs-filter");
            if (!b) return;
            C.filter = b.dataset.f; C.shown = PAGE;
            if (C.model && C.sel != null) drawOps(C.model, C.sel);
        });
        el("csMore").addEventListener("click", () => { C.shown += PAGE; if (C.model && C.sel != null) drawOps(C.model, C.sel); });
        const open = ev => {
            const row = ev.target.closest(".cs-op[data-id]");
            if (!row || (ev.type === "keydown" && ev.key !== "Enter" && ev.key !== " ")) return;
            ev.preventDefault();
            if (typeof openTxDetail === "function") openTxDetail(row.dataset.id);
        };
        el("csList").addEventListener("click", open);
        el("csList").addEventListener("keydown", open);
        document.addEventListener("pointerdown", ev => {
            const root = el("csChart");
            if (root && !root.contains(ev.target)) hideTip();
        });
        if (typeof ResizeObserver !== "undefined") {
            let raf = 0;
            new ResizeObserver(() => {
                cancelAnimationFrame(raf);
                raf = requestAnimationFrame(() => {
                    const root = el("csChart");
                    if (visible() && root && root.clientWidth && Math.floor(root.clientWidth) !== C.width) { C.sel = null; C.cmpB = null; render({ noAnim: true }); }
                });
            }).observe(el("csChart"));
        }
    }

    window.renderCardSpend = render;
    window.refreshCardSpend = refresh;
    window.cardSpendInsights = insights;
})();
