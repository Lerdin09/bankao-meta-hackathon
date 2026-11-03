/**
 * Gráficos da conta — 2. Entradas vs. saídas
 *   • Gráfico de barras: para cada período, uma barra verde (dinheiro recebido) e uma vermelha (dinheiro gasto).
 *   • Uma linha azul mostra a diferença (entradas − saídas) de cada período.
 *   • Compara semanas, meses ou anos; as setas ‹ › andam para períodos mais antigos ou mais recentes.
 *   • Tocar (ou passar o rato) numa coluna mostra o detalhe desse período por baixo do gráfico.
 * Só usa movimentos reais do extrato, na moeda de preferência (a mesma do cartão de saldo).
 * Depende de card-chart.js (window.ccShared) e é chamado por ele quando este painel está aberto.
 */
(function () {
    "use strict";

    const GRAN_KEY = "bankao_fl_gran";
    const GRANS = {
        week: { one: "semana", prev: "da semana anterior", now: "Semana em curso" },
        month: { one: "mês", prev: "do mês anterior", now: "Mês em curso" },
        year: { one: "ano", prev: "do ano anterior", now: "Ano em curso" }
    };
    const C_IN = "#34D399", C_OUT = "#F87171", C_NET = "#38BDF8";

    const F = {
        gran: (function () {
            try { const g = localStorage.getItem(GRAN_KEY); if (g && g in GRANS) return g; } catch (e) { /* ignorar */ }
            return "month";
        })(),
        off: 0,            // páginas para trás (0 = período mais recente)
        sel: null,
        model: null,
        geom: null,
        width: 0,
        sig: "",
        bound: false
    };

    const el = id => document.getElementById(id);
    const sh = () => window.ccShared;
    const r1 = n => Math.round(n * 10) / 10;

    /* ------------------------------ períodos ------------------------------ */

    function startOf(g, d) {
        if (g === "week") return new Date(d.getFullYear(), d.getMonth(), d.getDate() - ((d.getDay() + 6) % 7));   // segunda-feira
        if (g === "month") return new Date(d.getFullYear(), d.getMonth(), 1);
        return new Date(d.getFullYear(), 0, 1);
    }
    function shift(g, start, n) {
        if (g === "week") return new Date(start.getFullYear(), start.getMonth(), start.getDate() + 7 * n);
        if (g === "month") return new Date(start.getFullYear(), start.getMonth() + n, 1);
        return new Date(start.getFullYear() + n, 0, 1);
    }
    function perPage(w, g) {
        const narrow = w < 520;
        return g === "week" ? (narrow ? 8 : 12) : g === "month" ? (narrow ? 6 : 12) : (narrow ? 4 : 6);
    }
    function labelShort(g, b) {
        const M = sh().MONTHS, d = b.start;
        if (g === "week") return `${d.getDate()} ${M[d.getMonth()]}`;
        if (g === "month") return M[d.getMonth()];
        return String(d.getFullYear());
    }
    function labelLong(g, b) {
        const M = sh().MONTHS, d = b.start;
        if (g === "week") {
            const last = new Date(b.end.getFullYear(), b.end.getMonth(), b.end.getDate() - 1);
            return `${d.getDate()} ${M[d.getMonth()]} – ${last.getDate()} ${M[last.getMonth()]} ${last.getFullYear()}`;
        }
        if (g === "month") return `${M[d.getMonth()]} ${d.getFullYear()}`;
        return String(d.getFullYear());
    }

    /* ------------------------------ dados ------------------------------ */

    function collect() {
        const c = sh().curr();
        const raw = (typeof state !== "undefined" && Array.isArray(state.transactions)) ? state.transactions : [];
        const out = [];
        raw.forEach(tx => {
            if ((tx.currency || "AOA") !== c || /fail|falh/i.test(String(tx.status || ""))) return;
            const t = parseTxDate(tx.created_at);
            const v = Number(tx.amount_decimal) || 0;
            if (!isNaN(t) && v) out.push({ t, v });
        });
        return { c, txs: out, raw };
    }

    function buildModel(w) {
        const { c, txs } = collect();
        const g = F.gran, n = perPage(w, g);
        const empty = !state.token || !(state.accounts || []).some(a => a.currency === c);
        const today = new Date();
        const cur = startOf(g, today);

        // Período mais antigo com dados (para saber até onde as setas podem recuar)
        let first = today;
        txs.forEach(x => { if (x.t < first) first = x.t; });
        try {
            const cr = typeof getAccountCreationDate === "function" ? getAccountCreationDate() : null;
            if (cr && !isNaN(cr) && cr < first) first = cr;
        } catch (e) { /* ignorar */ }
        const firstStart = startOf(g, first);

        const buckets = [];
        for (let i = 0; i < n; i++) {
            const start = shift(g, cur, -(F.off * n + (n - 1 - i)));
            buckets.push({ start, end: shift(g, start, 1), inn: 0, out: 0, net: 0, current: +start === +cur });
        }
        // Não mostra períodos anteriores ao primeiro movimento/conta (ficariam vazios)
        while (buckets.length > 1 && +buckets[0].start < +firstStart) buckets.shift();
        const idx = new Map(buckets.map((b, i) => [+b.start, i]));
        txs.forEach(x => {
            const k = idx.get(+startOf(g, x.t));
            if (k == null) return;
            if (x.v > 0) buckets[k].inn += x.v; else buckets[k].out += -x.v;
        });
        const tot = { inn: 0, out: 0 };
        buckets.forEach(b => { b.net = b.inn - b.out; tot.inn += b.inn; tot.out += b.out; });
        return {
            c, g, n: buckets.length, empty, buckets, tot, net: tot.inn - tot.out,
            canPrev: +buckets[0].start > +firstStart,
            canNext: F.off > 0
        };
    }

    /* ------------------------------ desenho ------------------------------ */

    function geometry(model, w) {
        const h = w < 520 ? 270 : w < 900 ? 310 : 350;
        const m = { l: w < 520 ? 44 : 52, r: 10, t: 14, b: 28 };
        const iw = w - m.l - m.r, ih = h - m.t - m.b, n = model.n;
        let lo = 0, hi = 0;
        model.buckets.forEach(b => { hi = Math.max(hi, b.inn, b.out); lo = Math.min(lo, b.net); });
        const sc = sh().niceScale(lo, hi, lo < 0);
        const slot = iw / n;
        const cx = i => m.l + slot * (i + 0.5);
        const y = v => m.t + ih * (1 - (v - sc.min) / (sc.max - sc.min));
        return { w, h, m, iw, ih, n, sc, slot, cx, y };
    }

    function barPath(x, yTop, yBase, bw) {
        const h = yBase - yTop;
        if (h <= 0.4) return "";
        const r = Math.min(5, bw / 2, h);
        return `M${r1(x)} ${r1(yBase)}V${r1(yTop + r)}Q${r1(x)} ${r1(yTop)} ${r1(x + r)} ${r1(yTop)}H${r1(x + bw - r)}Q${r1(x + bw)} ${r1(yTop)} ${r1(x + bw)} ${r1(yTop + r)}V${r1(yBase)}Z`;
    }

    function svgMarkup(model, w, hide) {
        const g = geometry(model, w);
        const { m, n, sc, slot, cx, y } = g;
        const y0 = y(0);
        const bw = Math.max(5, Math.min(slot * 0.3, 26)), gap = 2;

        const grid = sc.values.map(v => `<line class="${v === 0 ? "base" : ""}" x1="${m.l}" x2="${w - m.r}" y1="${r1(y(v))}" y2="${r1(y(v))}"/>`).join("");
        const maxAbs = Math.max(Math.abs(sc.min), Math.abs(sc.max));
        const unit = maxAbs >= 1e6 ? 1e6 : maxAbs >= 1e4 ? 1e3 : 1;
        const yl = hide ? "" : sc.values.map(v => `<text x="${m.l - 8}" y="${r1(y(v)) + 3.5}" text-anchor="end">${sh().axisLabel(v, unit)}</text>`).join("");
        const step = slot < 44 ? Math.ceil(44 / slot) : 1;
        let xl = "";
        model.buckets.forEach((b, i) => {
            if (i % step) return;
            xl += `<text x="${r1(cx(i))}" y="${g.h - 8}" text-anchor="middle">${labelShort(model.g, b)}</text>`;
        });

        let cols = "", bars = "", hits = "";
        const netPts = [];
        model.buckets.forEach((b, i) => {
            const x = cx(i);
            cols += `<rect class="fl-col" data-i="${i}" x="${r1(x - slot / 2 + 2)}" y="${m.t - 4}" width="${r1(slot - 4)}" height="${r1(g.ih + 4)}" rx="10"/>`;
            bars += `<path class="fl-bar fl-bar--in" style="--d:${i * 35}ms" d="${barPath(x - bw - gap / 2, y(b.inn), y0, bw)}"/>`;
            bars += `<path class="fl-bar fl-bar--out" style="--d:${i * 35 + 60}ms" d="${barPath(x + gap / 2, y(b.out), y0, bw)}"/>`;
            netPts.push([x, y(b.net)]);
            hits += `<rect class="fl-hit" data-i="${i}" x="${r1(x - slot / 2)}" y="0" width="${r1(slot)}" height="${g.h}"/>`;
        });
        const netLine = netPts.map((p, i) => `${i ? "L" : "M"}${r1(p[0])} ${r1(p[1])}`).join("");
        const netDots = netPts.map((p, i) => `<circle class="fl-net-dot" data-i="${i}" cx="${r1(p[0])}" cy="${r1(p[1])}" r="3.6"/>`).join("");

        return `<svg class="cc-svg fl-svg" id="flSvg" viewBox="0 0 ${w} ${g.h}" width="${w}" height="${g.h}" tabindex="0" focusable="true" aria-label="Gráfico de barras. Use as setas para ler cada período.">
<g class="cc-grid">${grid}</g>
<g class="cc-axis">${yl}${xl}</g>
<g>${cols}</g>
<g class="fl-bars">${bars}</g>
<g class="fl-net"><path class="fl-net-line" pathLength="1" d="${netLine}"/>${netDots}</g>
<g>${hits}</g>
</svg>`;
    }

    function drawChart(model, animate) {
        const root = el("flChart");
        if (!root) return;
        const w = Math.max(280, Math.floor(root.clientWidth));
        F.width = w;
        root.classList.toggle("no-anim", !animate);
        if (model.empty) {
            root.innerHTML = `<div class="cc-empty">${state.token ? "Ainda não há dados desta conta." : "Inicie sessão para comparar as suas entradas e saídas."}</div>`;
            F.geom = null;
            return;
        }
        root.innerHTML = svgMarkup(model, w, sh().hidden()) + `<div class="cc-tip" id="flTip" role="status"></div>`;
        F.geom = geometry(model, w);
        root.setAttribute("aria-label", `Gráfico de barras de entradas e saídas, ${model.n} ${model.g === "week" ? "semanas" : model.g === "month" ? "meses" : "anos"}`);

        const svg = el("flSvg");
        svg.querySelectorAll(".fl-hit").forEach(r => {
            const i = +r.dataset.i;
            r.addEventListener("pointerdown", () => select(i, true));
            r.addEventListener("pointermove", ev => { if (ev.pointerType === "mouse") select(i, true); });
            r.addEventListener("pointerleave", ev => { if (ev.pointerType === "mouse") hideTip(); });
        });
        svg.addEventListener("keydown", ev => {
            const cur = F.sel == null ? model.n - 1 : F.sel;
            const map = { ArrowRight: Math.min(model.n - 1, cur + 1), ArrowLeft: Math.max(0, cur - 1), Home: 0, End: model.n - 1 };
            if (ev.key in map) { ev.preventDefault(); select(map[ev.key], true); }
        });
        let def = model.n - 1;
        for (let k = model.n - 1; k >= 0; k--) { if (model.buckets[k].inn || model.buckets[k].out) { def = k; break; } }
        select(F.sel == null || F.sel >= model.n ? def : F.sel, false);
    }

    function hideTip() { const t = el("flTip"); if (t) t.classList.remove("on"); }

    function select(i, showTip) {
        const model = F.model, g = F.geom;
        if (!model || !g || i < 0 || i >= model.n) return;
        F.sel = i;
        document.querySelectorAll("#flSvg .fl-col").forEach(c => c.classList.toggle("on", +c.dataset.i === i));
        document.querySelectorAll("#flSvg .fl-net-dot").forEach(c => c.classList.toggle("on", +c.dataset.i === i));
        drawDetail(model, i);

        const tip = el("flTip");
        if (!tip) return;
        if (!showTip) { tip.classList.remove("on"); return; }
        const b = model.buckets[i], S = sh();
        tip.innerHTML = `<b>${labelLong(model.g, b)}</b>`
            + `<span class="fl-tip-r"><i style="background:${C_IN}"></i>Entradas<strong>${S.money(b.inn, model.c)}</strong></span>`
            + `<span class="fl-tip-r"><i style="background:${C_OUT}"></i>Saídas<strong>${S.money(b.out, model.c)}</strong></span>`
            + `<span class="fl-tip-r"><i style="background:${C_NET}"></i>Diferença<strong>${b.net >= 0 ? "" : "−"}${S.money(Math.abs(b.net), model.c)}</strong></span>`;
        const px = g.cx(i), tw = tip.offsetWidth || 190;
        const scale = (el("flChart").clientWidth || g.w) / g.w;
        let left = px * scale + g.slot * scale * 0.5 + 6;
        if (left + tw > g.w * scale - 2) left = px * scale - g.slot * scale * 0.5 - tw - 6;
        tip.style.left = Math.max(2, left) + "px";
        tip.style.top = (g.m.t + 4) + "px";
        tip.classList.add("on");
    }

    function drawChrome(model) {
        const S = sh(), gi = GRANS[model.g];
        document.querySelectorAll("#flGrans .cc-chip").forEach(b => {
            const on = b.dataset.gran === model.g;
            b.classList.toggle("active", on);
            b.setAttribute("aria-pressed", String(on));
        });
        const a = model.buckets[0], z = model.buckets[model.n - 1];
        el("flRange").textContent = model.g === "year" ? (a.start.getFullYear() === z.start.getFullYear() ? labelLong("year", a) : `${labelLong("year", a)} – ${labelLong("year", z)}`) : `${labelLong(model.g, a).split(" – ")[0]}${model.g === "month" ? "" : ""} – ${labelLong(model.g, z).split(" – ").pop()}`;
        el("ccSubtitle").textContent = model.empty ? (state.token ? "Ainda não há dados desta conta" : "Inicie sessão para ver os seus movimentos") : "Dinheiro recebido contra dinheiro gasto";
        el("flPrev").disabled = !model.canPrev;
        el("flNext").disabled = !model.canNext;

        const e = model.empty, dash = "—", t = model.tot;
        const avg = (v) => S.hidden() ? "\u00a0" : `média ${S.compactMoney(v / model.n, model.c)} / ${gi.one}`;
        el("flStatIn").textContent = e ? dash : S.compactMoney(t.inn, model.c);
        el("flStatOut").textContent = e ? dash : S.compactMoney(t.out, model.c);
        el("flStatInNote").textContent = e ? "\u00a0" : avg(t.inn);
        el("flStatOutNote").textContent = e ? "\u00a0" : avg(t.out);
        el("flStatIn").title = e ? "" : S.money(t.inn, model.c);
        el("flStatOut").title = e ? "" : S.money(t.out, model.c);
        const up = model.net >= 0;
        el("flStatNet").textContent = e ? dash : (S.hidden() ? S.compactMoney(0, model.c) : `${up ? "+" : "−"}${S.compactMoney(Math.abs(model.net), model.c)}`);
        el("flStatNet").title = e ? "" : S.money(model.net, model.c);
        el("flStatNet").style.color = e ? "" : (up ? C_IN : C_OUT);
        el("flStatNetNote").textContent = e || (t.inn === 0 && t.out === 0) ? "\u00a0" : (up ? "Sobrou dinheiro" : "Gastou mais do que recebeu");
        const rate = t.inn > 0 ? Math.round((model.net / t.inn) * 100) : null;
        el("flStatRate").textContent = e || rate == null ? dash : `${rate < 0 ? "−" : ""}${Math.abs(rate)}%`;
        el("flStatRate").style.color = e || rate == null ? "" : (rate >= 0 ? C_IN : C_OUT);
    }

    function drawDetail(model, i) {
        const S = sh(), b = model.buckets[i], gi = GRANS[model.g];
        el("flDetTitle").textContent = labelLong(model.g, b);
        let sub = b.current ? gi.now : "Período fechado";
        const prev = i > 0 ? model.buckets[i - 1] : null;
        if (prev && prev.out > 0 && b.out > 0 && !b.current) {
            const p = Math.round(Math.abs(b.out / prev.out - 1) * 100);
            if (p >= 1) sub += ` · saídas ${p}% ${b.out > prev.out ? "acima" : "abaixo"} ${gi.prev}`;
        }
        el("flDetSub").textContent = sub;
        el("flDetIn").textContent = S.money(b.inn, model.c);
        el("flDetOut").textContent = S.money(b.out, model.c);
        const up = b.net >= 0;
        el("flDetNet").textContent = S.hidden() ? S.money(0, model.c) : (b.net === 0 ? S.money(0, model.c) : `${up ? "+" : "−"}${S.money(Math.abs(b.net), model.c)}`);
        el("flDetNet").style.color = up ? C_IN : C_OUT;
        const total = b.inn + b.out;
        el("flMeterIn").style.width = (total ? (b.inn / total) * 100 : 50) + "%";
        el("flMeterOut").style.width = (total ? (b.out / total) * 100 : 50) + "%";
        const badge = el("flDetBadge");
        if (!total) { badge.hidden = true; return; }
        badge.hidden = false;
        badge.className = "bc-delta " + (up ? "up" : "down");
        badge.textContent = b.inn > 0 ? `${up ? "Poupou" : "Excedeu"} ${Math.abs(Math.round((b.net / b.inn) * 100))}%` : "Só saídas";
    }

    /* ------------------------------ ciclo de vida ------------------------------ */

    function signature() {
        const raw = (typeof state !== "undefined" && Array.isArray(state.transactions)) ? state.transactions : [];
        return [sh().curr(), state.token ? 1 : 0, raw.length, raw[0] ? raw[0].id : "", +sh().dayStart(new Date()), F.gran, F.off, sh().hidden() ? 1 : 0, F.width].join("|");
    }

    function render(opts) {
        const view = el("view-card-chart"), panel = el("bcPanelFlow");
        if (!view || !panel || !view.classList.contains("active") || panel.hidden) return;
        bind();
        const root = el("flChart");
        const w = Math.max(280, Math.floor(root.clientWidth));
        const animate = !(opts && opts.noAnim);
        const model = buildModel(w);
        F.model = model;
        drawChrome(model);
        drawChart(model, animate);
        F.sig = signature();
    }

    function refresh() {
        const view = el("view-card-chart"), panel = el("bcPanelFlow");
        if (!view || !panel || !view.classList.contains("active") || panel.hidden) return;
        if (signature() !== F.sig) render({ noAnim: true });
    }

    function bind() {
        if (F.bound) return;
        F.bound = true;
        document.querySelectorAll("#flGrans .cc-chip").forEach(btn => btn.addEventListener("click", () => {
            if (F.gran === btn.dataset.gran) return;
            F.gran = btn.dataset.gran; F.off = 0; F.sel = null;
            try { localStorage.setItem(GRAN_KEY, F.gran); } catch (e) { /* ignorar */ }
            render();
        }));
        el("flPrev").addEventListener("click", () => { if (F.model && F.model.canPrev) { F.off++; F.sel = null; render(); } });
        el("flNext").addEventListener("click", () => { if (F.off > 0) { F.off--; F.sel = null; render(); } });
        document.addEventListener("pointerdown", ev => {
            const root = el("flChart");
            if (root && !root.contains(ev.target)) hideTip();
        });
        if (typeof ResizeObserver !== "undefined") {
            let raf = 0;
            new ResizeObserver(() => {
                cancelAnimationFrame(raf);
                raf = requestAnimationFrame(() => {
                    const root = el("flChart");
                    if (root && root.clientWidth && Math.floor(root.clientWidth) !== F.width) { F.sel = null; render({ noAnim: true }); }
                });
            }).observe(el("flChart"));
        }
    }

    window.renderFlowChart = render;
    window.refreshFlowChart = refresh;
})();
