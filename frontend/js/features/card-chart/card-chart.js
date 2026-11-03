/**
 * Gráficos da conta
 * Página aberta ao tocar no cartão de saldo do início. Tem um menu com 6 gráficos;
 * estão desenvolvidos o 1.º "Evolução do saldo" (linhas), o 2.º "Entradas vs. saídas" (barras),
 * o 3.º "Fluxo de gastos do cartão" (barras empilhadas, ver card-spend-chart.js),
 * o 4.º "Gastos por comerciante" (barras horizontais, ver merchants-chart.js)
 * e o 5.º "Fluxo entre contas" (diagrama de Sankey, ver accounts-flow-chart.js).
 *
 * Evolução do saldo
 *   • Gráfico de linhas do saldo ao longo do tempo, desenhado movimento a movimento (com a hora real):
 *     o saldo fica parado até ao próximo movimento e depois muda de uma vez, como numa conta a sério.
 *   • Mostra saldo inicial, saldo atual (ou final), máximo e mínimo do intervalo.
 *     O máximo e o mínimo olham para CADA movimento, e não só para o fecho do dia: se teve 22 mil
 *     e ficou com 3 mil no mesmo dia, o máximo continua a ser 22 mil.
 *   • Filtros rápidos: 7 dias, 30 dias, 90 dias, 6 meses e 1 ano.
 *   • Intervalo flexível (no fim da página, antes do Copilot): barra com o histórico todo, com uma janela
 *     que se arrasta e se estica; campos de data E HORA; atalhos (última hora, 6 h, 24 h, hoje) e botões
 *     para aproximar/afastar e andar para trás/frente. Dá para ver, por exemplo, só as 17h–18h.
 *   • No fim da página há sempre o Copilot (análise do gráfico aberto + perguntas rápidas).
 *
 * O saldo é reconstruído a partir do saldo atual, recuando pelos movimentos reais do extrato.
 * Não há dados inventados.
 *
 * Para acrescentar o gráfico seguinte: criar o painel em partials/pages/card-chart.html,
 * escrever aqui o seu desenho e tirar o atributo data-soon do botão em #bcTypes.
 */
(function () {
    "use strict";

    const MIN = 60000, HOUR = 3600000, DAY = 86400000;
    const MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
    const PRESETS = { "7d": 7, "30d": 30, "90d": 90, "6m": 182, "1a": 365 };   // em dias
    const QUICK = { "1h": HOUR, "6h": 6 * HOUR, "24h": DAY, "hoje": 0 };        // atalhos de horas
    const MIN_SPAN = 10 * MIN;          // a janela nunca fica com menos de 10 minutos
    const MIN_HISTORY = 7 * DAY;        // histórico mínimo desenhado (contas novas)
    const STORE_KEY = "bankao_bc_period";
    const SOON_NAMES = {};
    const C_UP = "#34D399", C_DOWN = "#F87171", C_FLAT = "#38BDF8";
    const MASK = "••••••";

    const S = {
        period: (function () {
            try { const p = localStorage.getItem(STORE_KEY); if (p && p in PRESETS) return p; } catch (e) { /* ignorar */ }
            return "30d";
        })(),
        custom: null,        // { s, e } em ms; e === null significa "até agora" (a janela acompanha o relógio)
        chart: "balance",    // gráfico aberto: "balance" | "flow" | "card" | "merchants" | "accounts"
        series: null,        // movimentos + saldos em cache
        seriesKey: "",
        model: null,
        selT: null,          // instante selecionado no gráfico
        geom: null,
        width: 0,
        sig: "",
        drag: null,
        raf: 0,
        bound: false
    };

    /* ------------------------------ utilitários ------------------------------ */

    const el = id => document.getElementById(id);
    const r1 = n => Math.round(n * 10) / 10;
    const p2 = n => String(n).padStart(2, "0");
    const dayStart = d => new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
    const curr = () => (typeof state !== "undefined" && state.prefCurrency) || "AOA";
    const hidden = () => document.body.classList.contains("balances-hidden");
    const esc = s => (typeof escapeHtml === "function" ? escapeHtml(String(s)) : String(s).replace(/[&<>"']/g, c => "&#" + c.charCodeAt(0) + ";"));
    function symbol(c) {
        const info = typeof CURRENCY_INFO !== "undefined" ? CURRENCY_INFO[c] : null;
        return info ? info.symbol : c;
    }
    const hm = d => `${p2(d.getHours())}:${p2(d.getMinutes())}`;
    const dateShort = d => `${d.getDate()} ${MONTHS[d.getMonth()]}`;
    const dateLong = d => `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
    const dtShort = t => { const d = new Date(t); return `${dateShort(d)} · ${hm(d)}`; };
    const dtLong = t => { const d = new Date(t); return `${dateLong(d)}, ${hm(d)}`; };
    const inputValue = t => { const d = new Date(t); return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}T${p2(d.getHours())}:${p2(d.getMinutes())}`; };

    /** 5400000 -> "1 h 30 min" · 3 dias -> "3 dias" */
    function durLabel(ms) {
        const m = Math.max(1, Math.round(ms / MIN));
        if (m < 60) return `${m} min`;
        if (m < 1440) { const h = Math.floor(m / 60), r = m % 60; return r ? `${h} h ${r} min` : `${h} h`; }
        const d = Math.floor(m / 1440), h = Math.round((m % 1440) / 60);
        if (d >= 10 || !h) return `${d + (h === 24 ? 1 : 0)} ${d === 1 && h !== 24 ? "dia" : "dias"}`;
        return `${d} ${d === 1 ? "dia" : "dias"} ${h} h`;
    }

    /** 1250000 -> "1.250.000 KZ" (ou máscara com os saldos ocultos) */
    function money(n, c) {
        if (hidden()) return MASK;
        const v = (c || curr()) === "AOA" ? Math.round(n) : Math.round(n * 100) / 100;
        return formatNumberWithDots(v) + "\u00a0" + symbol(c || curr());
    }
    /** Versão curta para os cartões do resumo: 1250000 -> "1,25 M KZ" */
    function compactMoney(n, c) {
        if (hidden()) return MASK;
        const a = Math.abs(n);
        const fix = (v, d) => String(parseFloat(v.toFixed(d))).replace(".", ",");
        let t;
        if (a >= 1e9) t = fix(n / 1e9, 2) + "\u00a0MM";
        else if (a >= 1e6) t = fix(n / 1e6, 2) + "\u00a0M";
        else if (a >= 1e5) t = fix(n / 1e3, 0) + "\u00a0k";
        else t = formatNumberWithDots((c || curr()) === "AOA" ? Math.round(n) : Math.round(n * 100) / 100);
        return t + "\u00a0" + symbol(c || curr());
    }

    /* ------------------------------ dados ------------------------------ */

    /**
     * Movimentos da conta (na moeda escolhida), do mais antigo para o mais recente, cada um com o saldo
     * de ANTES e de DEPOIS. Cache: só se refaz quando os dados mudam.
     */
    function getSeries() {
        const c = curr();
        const acc = (typeof state !== "undefined" && Array.isArray(state.accounts)) ? state.accounts.find(a => a.currency === c) : null;
        const raw = (typeof state !== "undefined" && Array.isArray(state.transactions)) ? state.transactions : [];
        let created = null;
        try { created = typeof getAccountCreationDate === "function" ? getAccountCreationDate() : null; } catch (e) { /* ignorar */ }
        const last = raw[raw.length - 1];
        const key = [c, state.token ? 1 : 0, acc ? acc.balance_decimal : "x", raw.length, raw[0] ? raw[0].id : "", last ? last.id : "", created ? +created : ""].join("|");
        if (S.series && S.seriesKey === key) return S.series;

        const empty = !state.token || !acc;
        const ev = [];
        raw.forEach((tx, i) => {
            if ((tx.currency || "AOA") !== c || /fail|falh/i.test(String(tx.status || ""))) return;
            const t = parseTxDate(tx.created_at);
            if (isNaN(t)) return;
            ev.push({ t: +t, v: Number(tx.amount_decimal) || 0, i, id: tx.id, desc: String(tx.description || "").trim() });
        });
        // Mais antigo primeiro. Com a mesma hora, a ordem do extrato (do mais novo para o mais antigo) inverte-se.
        ev.sort((a, b) => (a.t - b.t) || (Number(a.id) - Number(b.id)) || (b.i - a.i));

        const bal = empty ? 0 : (Number(acc.balance_decimal) || 0);
        let run = bal;
        for (let k = ev.length - 1; k >= 0; k--) { ev[k].after = run; ev[k].before = run - ev[k].v; run = ev[k].before; }

        let first = ev.length ? ev[0].t : Date.now();
        if (created && !isNaN(created) && +created < first) first = +created;
        first = Math.min(first, Date.now() - MIN_HISTORY);
        first = Math.floor(first / HOUR) * HOUR;

        S.series = { curr: c, empty, ev, open0: run, final: bal, first, key };
        S.seriesKey = key;
        return S.series;
    }

    /** Quantos movimentos aconteceram até (e incluindo) ao instante t. */
    function countUntil(se, t) {
        let lo = 0, hi = se.ev.length;
        while (lo < hi) { const m = (lo + hi) >> 1; if (se.ev[m].t <= t) lo = m + 1; else hi = m; }
        return lo;
    }
    function balanceAt(se, t) {
        const k = countUntil(se, t);
        return k ? se.ev[k - 1].after : se.open0;
    }

    /** Janela escolhida, em ms. */
    function resolveWindow(se, now) {
        let s, e, follow;
        if (S.period === "custom" && S.custom) {
            s = S.custom.s;
            follow = S.custom.e == null;
            e = follow ? now : S.custom.e;
        } else {
            const days = PRESETS[S.period in PRESETS ? S.period : "30d"];
            e = now; follow = true;
            s = Math.max(se.first, now - days * DAY);
        }
        e = clamp(e, se.first + MIN_SPAN, now);
        s = clamp(s, se.first, e - MIN_SPAN);
        return { s, e, follow };
    }

    function buildModel() {
        const now = Date.now();
        const se = getSeries();
        const w = resolveWindow(se, now);
        const lo = countUntil(se, w.s), hi = countUntil(se, w.e);
        const start = balanceAt(se, w.s);
        const pts = [{ t: w.s, v: start, kind: "start" }];
        for (let k = lo; k < hi; k++) pts.push({ t: se.ev[k].t, v: se.ev[k].after, ev: se.ev[k] });
        const final = pts[pts.length - 1].v;
        // Máximo e mínimo: o saldo inicial do intervalo e o saldo depois de CADA movimento
        let iMax = 0, iMin = 0;
        pts.forEach((p, k) => { if (p.v > pts[iMax].v) iMax = k; if (p.v < pts[iMin].v) iMin = k; });
        return {
            se, now, s: w.s, e: w.e, follow: w.follow, span: w.e - w.s, lo, hi, pts, iMax, iMin,
            start, final, delta: final - start, moves: hi - lo, curr: se.curr, empty: se.empty
        };
    }

    /* ------------------------------ geometria do gráfico ------------------------------ */

    function niceScale(lo, hi, allowNeg) {
        if (hi - lo < 1e-9) { const pad = Math.max(Math.abs(hi) * 0.05, 1); lo -= pad; hi += pad; }
        const range = hi - lo;
        const floorLo = lo;
        lo -= range * 0.1; hi += range * 0.14;
        const raw = (hi - lo) / 4;
        const p = Math.pow(10, Math.floor(Math.log10(raw)));
        const f = raw / p;
        const step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
        let min = Math.floor(lo / step) * step;
        if (!allowNeg && floorLo >= 0 && min < 0) min = 0;
        const max = Math.ceil(hi / step) * step;
        const values = [];
        for (let v = min; v <= max + step / 1000; v += step) values.push(v);
        return { min, max, values, step };
    }

    function axisLabel(v, unit) {
        if (v === 0) return "0";
        const t = String(parseFloat((v / unit).toFixed(2))).replace(".", ",");
        return t + (unit === 1e6 ? "\u00a0M" : unit === 1e3 ? "\u00a0k" : "");
    }

    function geometry(model, w) {
        const h = w < 520 ? 290 : w < 900 ? 330 : 370;
        const m = { l: w < 520 ? 46 : 54, r: 16, t: 24, b: 32 };
        const iw = w - m.l - m.r, ih = h - m.t - m.b;
        let lo = Infinity, hi = -Infinity;
        model.pts.forEach(p => { lo = Math.min(lo, p.v); hi = Math.max(hi, p.v); });
        const sc = niceScale(lo, hi, lo < 0);
        const x = t => m.l + iw * ((t - model.s) / (model.e - model.s));
        const y = v => m.t + ih * (1 - (v - sc.min) / (sc.max - sc.min));
        return { w, h, m, iw, ih, sc, x, y };
    }

    /** Escada: o saldo fica parado até ao próximo movimento e depois muda de uma vez. */
    function stepPath(pts, g, model) {
        let d = `M${r1(g.x(pts[0].t))} ${r1(g.y(pts[0].v))}`;
        for (let i = 1; i < pts.length; i++) d += ` H${r1(g.x(pts[i].t))} V${r1(g.y(pts[i].v))}`;
        return d + ` H${r1(g.x(model.e))}`;
    }

    /** Muitos movimentos numa janela larga: por cada coluna de pixéis guarda o primeiro, o mínimo, o máximo e o último. */
    function decimate(pts, xOf, cols) {
        if (pts.length <= cols * 3) return pts;
        const keep = new Set();
        let col = null, g = null;
        const flush = () => { if (g) [g.f, g.mn, g.mx, g.l].forEach(i => keep.add(i)); };
        pts.forEach((p, i) => {
            const c = Math.floor(xOf(p.t));
            if (c !== col) { flush(); col = c; g = { f: i, mn: i, mx: i, l: i }; }
            else { if (p.v < pts[g.mn].v) g.mn = i; if (p.v > pts[g.mx].v) g.mx = i; g.l = i; }
        });
        flush();
        return Array.from(keep).sort((a, b) => a - b).map(i => pts[i]);
    }

    /* Marcas de tempo "bonitas" (horas redondas, dias, meses) */
    const TSTEPS = [[MIN, "m"], [5 * MIN, "m"], [10 * MIN, "m"], [15 * MIN, "m"], [30 * MIN, "m"], [HOUR, "h"], [2 * HOUR, "h"], [3 * HOUR, "h"],
        [6 * HOUR, "h"], [12 * HOUR, "h"], [DAY, "d"], [2 * DAY, "d"], [7 * DAY, "d"], [14 * DAY, "d"], [30 * DAY, "M", 1], [61 * DAY, "M", 2],
        [91 * DAY, "M", 3], [182 * DAY, "M", 6]];
    function timeTicks(s, e, target) {
        const span = e - s;
        const st = TSTEPS.find(x => span / x[0] <= target) || TSTEPS[TSTEPS.length - 1];
        const out = [];
        if (st[1] === "m" || st[1] === "h") {
            const off = new Date(s).getTimezoneOffset() * MIN;
            for (let t = Math.ceil((s - off) / st[0]) * st[0] + off; t <= e; t += st[0]) {
                const d = new Date(t);
                out.push({ t, label: (d.getHours() === 0 && d.getMinutes() === 0) ? dateShort(d) : hm(d) });
            }
        } else if (st[1] === "d") {
            let d = dayStart(new Date(s));
            if (+d < s) d = addDays(d, 1);
            for (; +d <= e; d = addDays(d, Math.round(st[0] / DAY))) out.push({ t: +d, label: dateShort(d) });
        } else {
            const b = new Date(s);
            let d = new Date(b.getFullYear(), b.getMonth(), 1);
            if (+d < s) d = new Date(b.getFullYear(), b.getMonth() + 1, 1);
            for (; +d <= e; d = new Date(d.getFullYear(), d.getMonth() + st[2], 1)) out.push({ t: +d, label: `${MONTHS[d.getMonth()]} ${String(d.getFullYear()).slice(2)}` });
        }
        return out;
    }

    function trend(model) {
        return model.delta > 0.004 ? "up" : model.delta < -0.004 ? "down" : "flat";
    }

    function svgMarkup(model, w, hide) {
        const g = geometry(model, w);
        const { m, sc, x, y } = g;
        const tr = trend(model);
        const color = tr === "up" ? C_UP : tr === "down" ? C_DOWN : C_FLAT;
        const line = stepPath(decimate(model.pts, x, g.iw), g, model);
        const base = y(sc.min);
        const area = `${line} V${r1(base)} H${r1(x(model.s))} Z`;

        const grid = sc.values.map((v, i) => `<line class="${i === 0 ? "base" : ""}" x1="${m.l}" x2="${w - m.r}" y1="${r1(y(v))}" y2="${r1(y(v))}"/>`).join("");
        const maxAbs = Math.max(Math.abs(sc.min), Math.abs(sc.max));
        const unit = maxAbs >= 1e6 ? 1e6 : maxAbs >= 1e4 ? 1e3 : 1;
        const yl = hide ? "" : sc.values.map(v => `<text x="${m.l - 8}" y="${r1(y(v)) + 3.5}" text-anchor="end">${axisLabel(v, unit)}</text>`).join("");

        const ticks = timeTicks(model.s, model.e, w < 520 ? 4 : 6);
        const vt = ticks.map(k => `<line x1="${r1(x(k.t))}" x2="${r1(x(k.t))}" y1="${m.t}" y2="${m.t + g.ih}"/>`).join("");
        const xl = ticks.map(k => {
            const px = x(k.t);
            const anchor = px < m.l + 18 ? "start" : px > w - m.r - 18 ? "end" : "middle";
            return `<text x="${r1(px)}" y="${g.h - 9}" text-anchor="${anchor}">${k.label}</text>`;
        }).join("");

        // Pontos dos movimentos (só quando são poucos, para se ver onde o saldo mudou)
        let evDots = "";
        if (model.moves > 0 && model.moves <= 80) {
            evDots = model.pts.slice(1).map(p => `<circle class="bc-ev ${p.ev.v >= 0 ? "up" : "down"}" cx="${r1(x(p.t))}" cy="${r1(y(p.v))}" r="3.2"/>`).join("");
        }

        // Máximo e mínimo (do intervalo inteiro, movimento a movimento)
        let marks = "";
        const pMax = model.pts[model.iMax], pMin = model.pts[model.iMin];
        if (pMax.v - pMin.v > 1e-9) {
            const lbl = (p, up) => {
                if (hide) return "";
                const px = x(p.t), anchor = px < m.l + 46 ? "start" : px > w - m.r - 46 ? "end" : "middle";
                const ty = up ? Math.max(11, y(p.v) - 11) : Math.min(g.h - m.b - 4, y(p.v) + 19);
                return `<text class="bc-mark-lbl ${up ? "max" : "min"}" x="${r1(anchor === "start" ? px + 2 : anchor === "end" ? px - 2 : px)}" y="${r1(ty)}" text-anchor="${anchor}">${compactMoney(p.v, model.curr)}</text>`;
            };
            marks = `<circle class="bc-mark bc-mark--max" cx="${r1(x(pMax.t))}" cy="${r1(y(pMax.v))}" r="4.8"/>` +
                `<circle class="bc-mark bc-mark--min" cx="${r1(x(pMin.t))}" cy="${r1(y(pMin.v))}" r="4.8"/>` + lbl(pMax, true) + lbl(pMin, false);
        }
        const ex = x(model.e), ey = y(model.final);

        return `<svg class="cc-svg bc-${tr}" id="ccSvg" viewBox="0 0 ${w} ${g.h}" width="${w}" height="${g.h}" tabindex="0" focusable="true" style="--bc:${color}" aria-label="Gráfico de linhas do saldo. Use as setas para ler cada movimento.">
<defs><linearGradient id="bcGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:var(--bc)" stop-opacity=".34"/><stop offset="1" style="stop-color:var(--bc)" stop-opacity="0"/></linearGradient></defs>
<g class="cc-grid">${grid}</g>
<g class="bc-vgrid">${vt}</g>
<g class="cc-axis">${yl}${xl}</g>
<line class="bc-base" x1="${m.l}" x2="${w - m.r}" y1="${r1(y(model.start))}" y2="${r1(y(model.start))}"/>
<path class="cc-area" d="${area}" fill="url(#bcGrad)"/>
<path class="cc-line" pathLength="1" d="${line}"/>
<g class="bc-marks">${evDots}${marks}</g>
<g class="bc-end"><circle class="bc-end-halo" cx="${r1(ex)}" cy="${r1(ey)}" r="9"/><circle class="bc-end-dot" cx="${r1(ex)}" cy="${r1(ey)}" r="4.4"/></g>
<g id="ccSel" style="display:none"><line class="cc-cursor" id="ccCursor" x1="0" x2="0" y1="${m.t}" y2="${m.t + g.ih}"/><circle class="cc-pt" id="ccPt" r="5.5" cx="0" cy="0"/></g>
<rect class="cc-hit" id="ccHit" x="${m.l - 6}" y="0" width="${g.iw + 12}" height="${g.h}"/>
</svg>`;
    }

    /* ------------------------------ desenho ------------------------------ */

    function drawChart(model, animate) {
        const root = el("ccChart");
        if (!root) return;
        const w = Math.max(280, Math.floor(root.clientWidth));
        S.width = w;
        root.classList.toggle("no-anim", !animate);
        if (model.empty) {
            root.innerHTML = `<div class="cc-empty">${state.token ? "Ainda não há dados desta conta." : "Inicie sessão para ver a evolução do seu saldo."}</div>`;
            S.geom = null;
            return;
        }
        root.innerHTML = svgMarkup(model, w, hidden()) + `<div class="cc-tip" id="ccTip" role="status"></div>`;
        S.geom = geometry(model, w);
        root.setAttribute("aria-label", `Gráfico de linhas da evolução do saldo, ${model.moves} movimentos, de ${dtLong(model.s)} a ${dtLong(model.e)}`);

        const svg = el("ccSvg"), hit = el("ccHit");
        const timeAt = ev => {
            const rc = svg.getBoundingClientRect();
            const px = (ev.clientX - rc.left) * (w / (rc.width || w));
            const g = S.geom;
            return model.s + clamp((px - g.m.l) / g.iw, 0, 1) * (model.e - model.s);
        };
        let hitStartY = 0, hitCancelled = false;
        hit.addEventListener("pointerdown", ev => {
            if (ev.pointerType === "touch") {
                hitCancelled = false;
                hitStartY = ev.clientY;
            }
            select(timeAt(ev), true);
        });
        hit.addEventListener("pointermove", ev => {
            if (ev.pointerType === "touch") {
                if (hitCancelled) return;
                const deltaUp = hitStartY - ev.clientY;
                if (deltaUp > 14 || Math.abs(ev.clientY - hitStartY) > 22) {
                    hitCancelled = true;
                    clearSel();
                    return;
                }
            }
            if (ev.pointerType === "mouse" || ev.buttons) select(timeAt(ev), true);
        });
        hit.addEventListener("pointerup", ev => { if (ev.pointerType === "touch") hitCancelled = false; });
        hit.addEventListener("pointerleave", ev => { if (ev.pointerType === "mouse") clearSel(); });
        svg.addEventListener("keydown", ev => {
            svg.setAttribute("data-kbd", "");
            const T = navTimes();
            let cur = -1;
            if (S.selT != null) { cur = T.findIndex(t => t >= S.selT); if (cur < 0) cur = T.length - 1; }
            const map = { ArrowRight: Math.min(T.length - 1, cur + 1), ArrowLeft: Math.max(0, cur < 0 ? T.length - 1 : cur - 1), Home: 0, End: T.length - 1 };
            if (ev.key in map) { ev.preventDefault(); select(T[map[ev.key]], false); }
            else if (ev.key === "Escape") clearSel();
        });
        svg.addEventListener("blur", () => { svg.removeAttribute("data-kbd"); clearSel(); });

        if (S.selT != null && S.selT >= model.s && S.selT <= model.e && !animate) select(S.selT, false);
        else S.selT = null;
    }

    /** Instantes que o teclado percorre: início, cada movimento e o fim da janela. */
    function navTimes() {
        const m = S.model;
        const T = m.pts.map(p => p.t);
        if (T[T.length - 1] < m.e) T.push(m.e);
        return T;
    }

    function select(t, snap) {
        const g = S.geom, model = S.model;
        if (!g || !model || t == null) return;
        t = clamp(t, model.s, model.e);
        // Perto de um movimento (até ~10 px)? Cola-se a ele e mostra o que aconteceu
        let hitPt = null;
        if (snap) {
            let best = 10;
            model.pts.forEach(p => { const d = Math.abs(g.x(p.t) - g.x(t)); if (d <= best) { best = d; hitPt = p; } });
        } else {
            hitPt = model.pts.find(p => p.t === t) || null;
        }
        if (hitPt) t = hitPt.t;
        const ev = hitPt && hitPt.ev ? hitPt.ev : null;
        S.selT = t;

        const sel = el("ccSel"), cursor = el("ccCursor"), tip = el("ccTip"), pt = el("ccPt");
        if (!sel || !tip) return;
        sel.style.display = "";
        const v = ev ? ev.after : balanceAt(model.se, t);
        const px = g.x(t), py = g.y(v);
        cursor.setAttribute("x1", px); cursor.setAttribute("x2", px);
        pt.setAttribute("cx", px); pt.setAttribute("cy", py);

        const title = (ev || model.span <= 3 * DAY || t === model.s || t === model.e) ? dtLong(t) : dateLong(new Date(t));
        let sub, extra = "";
        if (ev) {
            sub = `${ev.v >= 0 ? "Entrada" : "Saída"}${ev.desc ? " · " + esc(ev.desc.length > 34 ? ev.desc.slice(0, 33) + "…" : ev.desc) : ""}`;
            if (!hidden()) extra = `<span class="bc-tip-d ${ev.v >= 0 ? "up" : "down"}">${ev.v >= 0 ? "+" : "−"}${money(Math.abs(ev.v), model.curr)} neste movimento</span><span class="bc-tip-b">Antes: ${money(ev.before, model.curr)}</span>`;
        } else {
            sub = t === model.s ? "Saldo inicial" : (t === model.e ? (model.follow ? "Saldo atual" : "Saldo final") : "Saldo neste momento");
            const d = v - model.start;
            if (!hidden() && t !== model.s && Math.abs(d) > 0.004) extra = `<span class="bc-tip-d ${d >= 0 ? "up" : "down"}">${d >= 0 ? "+" : "−"}${money(Math.abs(d), model.curr)} desde o início</span>`;
        }
        tip.innerHTML = `<b>${title}</b><small>${sub}</small><strong>${money(v, model.curr)}</strong>${extra}`;
        const tw = tip.offsetWidth || 170;
        const scale = (el("ccChart").clientWidth || g.w) / g.w;
        let left = px * scale + 14;
        if (left + tw > g.w * scale - 2) left = px * scale - tw - 14;
        tip.style.left = Math.max(2, left) + "px";
        tip.style.top = (g.m.t + 4) + "px";
        tip.classList.add("on");
    }

    function clearSel() {
        S.selT = null;
        const sel = el("ccSel"), tip = el("ccTip");
        if (sel) sel.style.display = "none";
        if (tip) tip.classList.remove("on");
    }

    function rangeText(model) {
        const a = new Date(model.s), z = new Date(model.e);
        if (model.span <= 2 * DAY) {
            return a.toDateString() === z.toDateString()
                ? `${dateLong(a)} · ${hm(a)} – ${hm(z)}`
                : `${dateShort(a)}, ${hm(a)} – ${dateLong(z)}, ${hm(z)}`;
        }
        if (model.span <= 8 * DAY) return `${dateShort(a)}, ${hm(a)} – ${dateLong(z)}, ${hm(z)}`;
        return `${dateShort(a)}${a.getFullYear() !== z.getFullYear() ? " " + a.getFullYear() : ""} – ${dateLong(z)}`;
    }

    function drawChrome(model) {
        el("ccCurrency").textContent = model.curr;
        document.querySelectorAll("#ccPeriods .cc-chip").forEach(b => {
            const on = b.dataset.period === S.period;
            b.classList.toggle("active", on);
            b.setAttribute("aria-pressed", String(on));
        });
        document.querySelectorAll("#bcQuick .cc-chip").forEach(b => {
            let on = false;
            if (S.period === "custom" && model.follow) {
                const k = b.dataset.span;
                on = k === "hoje" ? Math.abs(model.s - +dayStart(new Date(model.now))) < 2 * MIN : Math.abs(model.span - QUICK[k]) < 2 * MIN;
            }
            b.classList.toggle("active", on);
            b.setAttribute("aria-pressed", String(on));
        });

        el("ccRange").textContent = rangeText(model);
        el("ccSubtitle").textContent = model.empty
            ? (state.token ? "Ainda não há dados desta conta" : "Inicie sessão para ver o seu saldo")
            : (model.moves === 0 ? "Sem movimentos neste intervalo" : `${model.moves} ${model.moves === 1 ? "movimento" : "movimentos"} neste intervalo`);

        const empty = model.empty, dash = "—";
        const pMax = model.pts[model.iMax], pMin = model.pts[model.iMin];
        el("bcStatStart").textContent = empty ? dash : compactMoney(model.start, model.curr);
        el("bcStatNow").textContent = empty ? dash : compactMoney(model.final, model.curr);
        el("bcStatMax").textContent = empty ? dash : compactMoney(pMax.v, model.curr);
        el("bcStatMin").textContent = empty ? dash : compactMoney(pMin.v, model.curr);
        ["bcStatStart", "bcStatNow", "bcStatMax", "bcStatMin"].forEach((id, k) => {
            if (empty) { el(id).removeAttribute("title"); return; }
            el(id).title = money([model.start, model.final, pMax.v, pMin.v][k], model.curr);
        });
        el("bcStatNowLabel").textContent = model.follow ? "Saldo atual" : "Saldo final";
        // Notas: quando cada valor aconteceu (com hora)
        const when = (p, ctx) => p.kind === "start" ? (ctx === "ext" ? "Já no início" : (model.span <= 8 * DAY ? dtShort(p.t) : dateShort(new Date(p.t)))) : dtShort(p.t);
        el("bcStatStartNote").textContent = empty ? "\u00a0" : when(model.pts[0], "start");
        el("bcStatNowNote").textContent = empty ? "\u00a0" : (model.follow ? "Agora" : dtShort(model.e));
        el("bcStatMaxNote").textContent = empty ? "\u00a0" : when(pMax, "ext");
        el("bcStatMinNote").textContent = empty ? "\u00a0" : when(pMin, "ext");
        el("bcStatMaxBtn").disabled = empty; el("bcStatMinBtn").disabled = empty;

        // Variação no intervalo
        const pill = el("bcDelta");
        const tr = trend(model);
        if (empty || tr === "flat") { pill.hidden = true; }
        else {
            const pct = model.start > 0 ? Math.round(Math.abs(model.delta / model.start) * 1000) / 10 : null;
            const pctTxt = pct == null ? "" : `${String(pct).replace(".", ",")}%`;
            const amt = hidden() ? "" : compactMoney(Math.abs(model.delta), model.curr);
            pill.hidden = !(pctTxt || amt);
            pill.className = "bc-delta " + tr;
            pill.textContent = `${tr === "up" ? "↑" : "↓"} ${[amt, pctTxt && (amt ? `(${pctTxt})` : pctTxt)].filter(Boolean).join(" ")}`;
        }

        const eye = el("ccEye");
        if (eye) {
            eye.textContent = hidden() ? "Mostrar" : "Ocultar";
            eye.setAttribute("aria-label", hidden() ? "Mostrar valores" : "Ocultar valores");
        }
    }

    /* ------------------------------ intervalo flexível (barra com janela) ------------------------------ */

    function drawNavSeries(model) {
        const svg = el("bcNavSvg");
        if (!svg) return;
        const se = model.se, total = Math.max(1, model.now - se.first);
        const W = 1000, Hh = 64;
        const xOf = t => ((t - se.first) / total) * W;
        let pts = [{ t: se.first, v: se.open0 }];
        se.ev.forEach(e => { pts.push({ t: e.t, v: e.after }); });
        if (se.ev.length && se.ev[0].t > se.first) pts[0].v = se.open0;
        pts = decimate(pts, xOf, 300);
        let lo = Infinity, hi = -Infinity;
        pts.forEach(p => { lo = Math.min(lo, p.v); hi = Math.max(hi, p.v); });
        const span = hi - lo || 1;
        const yOf = v => Hh - 8 - ((v - lo) / span) * (Hh - 18);
        let d = `M${r1(xOf(pts[0].t))} ${r1(yOf(pts[0].v))}`;
        for (let i = 1; i < pts.length; i++) d += ` H${r1(xOf(pts[i].t))} V${r1(yOf(pts[i].v))}`;
        d += ` H${W}`;
        svg.setAttribute("viewBox", `0 0 ${W} ${Hh}`);
        svg.innerHTML = `<defs><linearGradient id="bcNavGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#818CF8" stop-opacity=".38"/><stop offset="1" stop-color="#818CF8" stop-opacity="0"/></linearGradient></defs>
<path d="${d} V${Hh} H0 Z" fill="url(#bcNavGrad)"/>
<path d="${d}" fill="none" stroke="#A5B4FC" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>`;

        // Referências de datas por baixo da barra
        const ticks = timeTicks(se.first, model.now, 4);
        el("bcNavTicks").innerHTML = ticks.map(k => `<span style="left:${(((k.t - se.first) / total) * 100).toFixed(2)}%">${k.label}</span>`).join("");
    }

    function positionNav(model) {
        const se = model.se, total = Math.max(1, model.now - se.first);
        const left = ((model.s - se.first) / total) * 100, right = ((model.e - se.first) / total) * 100;
        const win = el("bcWin");
        win.style.left = left + "%";
        win.style.width = (right - left) + "%";
        el("bcShadeL").style.width = left + "%";
        el("bcShadeR").style.width = (100 - right) + "%";

        const hl = el("bcHandleL"), hr = el("bcHandleR");
        hl.setAttribute("aria-valuemin", "0"); hl.setAttribute("aria-valuemax", "100");
        hl.setAttribute("aria-valuenow", String(Math.round(left))); hl.setAttribute("aria-valuetext", dtLong(model.s));
        hr.setAttribute("aria-valuemin", "0"); hr.setAttribute("aria-valuemax", "100");
        hr.setAttribute("aria-valuenow", String(Math.round(right))); hr.setAttribute("aria-valuetext", model.follow ? "Agora" : dtLong(model.e));

        el("bcDateFromTxt").textContent = dtLong(model.s);
        el("bcDateToTxt").textContent = model.follow ? `Agora · ${hm(new Date(model.now))}` : dtLong(model.e);
        const fi = el("bcDateFrom"), ti = el("bcDateTo");
        fi.min = ti.min = inputValue(se.first); fi.max = ti.max = inputValue(model.now);
        fi.value = inputValue(model.s); ti.value = inputValue(model.e);
        el("bcRangeDays").textContent = durLabel(model.span);
        el("bcNav").classList.toggle("disabled", model.empty);
        document.querySelectorAll("#bcTools .bc-tool").forEach(b => { b.disabled = model.empty; });
    }

    /** Aplica uma nova janela (ms) vinda do arrastar, do teclado, da barra, dos campos ou dos botões. */
    function setWindow(s, e, opts) {
        const m = S.model, se = m ? m.se : getSeries();
        const now = Date.now();
        e = clamp(e, se.first + MIN_SPAN, now);
        s = clamp(s, se.first, e - MIN_SPAN);
        const tol = Math.max(2 * MIN, (now - se.first) * 0.004);
        const follow = now - e <= tol;
        S.custom = { s: Math.round(s / MIN) * MIN, e: follow ? null : Math.round(e / MIN) * MIN };
        S.period = "custom";
        schedule(opts || { noAnim: true });
    }

    /** Se a janela acompanha o relógio e tem o tamanho de um filtro rápido, esse filtro volta a acender. */
    function snapToPreset() {
        const m = S.model;
        if (!m || S.period !== "custom" || !m.follow) return;
        const key = Object.keys(PRESETS).find(k => Math.abs(PRESETS[k] * DAY - m.span) <= Math.max(3 * MIN, m.span * 0.003));
        if (key) { S.period = key; S.custom = null; try { localStorage.setItem(STORE_KEY, key); } catch (e) { /* ignorar */ } schedule({ noAnim: true }); }
    }

    function schedule(opts) {
        S.nextOpts = Object.assign({}, S.nextOpts || {}, opts || {});
        if (S.raf) return;
        S.raf = requestAnimationFrame(() => {
            S.raf = 0;
            const o = S.nextOpts; S.nextOpts = null;
            render(o);
        });
    }

    function setQuick(k) {
        const se = getSeries(), now = Date.now();
        const s = k === "hoje" ? +dayStart(new Date(now)) : now - QUICK[k];
        S.custom = { s: Math.max(se.first, s), e: null };
        S.period = "custom";
        S.selT = null;
        render();
    }

    /** Botões: andar para trás/frente (uma janela inteira) e aproximar/afastar (metade/dobro). */
    function tool(act) {
        const m = S.model;
        if (!m || m.empty) return;
        const len = m.e - m.s;
        if (act === "prev") setWindow(m.s - len, m.e - len, { noAnim: false });
        else if (act === "next") setWindow(m.s + len, m.e + len, { noAnim: false });
        else {
            const c = (m.s + m.e) / 2;
            const nl = act === "in" ? Math.max(MIN_SPAN, len / 2) : Math.min(m.now - m.se.first, len * 2);
            let ns = c - nl / 2, ne = c + nl / 2;
            if (ne > m.now) { ns -= ne - m.now; ne = m.now; }
            if (ns < m.se.first) { ne += m.se.first - ns; ns = m.se.first; }
            setWindow(ns, Math.min(ne, m.now), { noAnim: false });
        }
        clearTimeout(S.snapT);
        S.snapT = setTimeout(snapToPreset, 600);
    }

    function bindNav() {
        const nav = el("bcNav"), win = el("bcWin"), hl = el("bcHandleL"), hr = el("bcHandleR");
        win.tabIndex = 0;

        const fracAt = ev => {
            const rc = nav.getBoundingClientRect();
            return clamp((ev.clientX - rc.left) / (rc.width || 1), 0, 1);
        };
        const timeAt = (ev, m) => m.se.first + fracAt(ev) * (m.now - m.se.first);
        const start = (mode, target) => ev => {
            const m = S.model;
            if (!m || m.empty) return;
            if (ev.button != null && ev.button > 0) return;
            ev.preventDefault();
            ev.stopPropagation();
            S.drag = { mode, grab: timeAt(ev, m) - m.s, len: m.e - m.s };
            nav.classList.add("dragging");
            win.classList.add("grabbing");
            try { target.setPointerCapture(ev.pointerId); } catch (e) { /* ignorar */ }
        };
        const move = ev => {
            const d = S.drag, m = S.model;
            if (!d || !m) return;
            const t = timeAt(ev, m);
            if (d.mode === "l") setWindow(Math.min(t, m.e - MIN_SPAN), m.e);
            else if (d.mode === "r") setWindow(m.s, Math.max(t, m.s + MIN_SPAN));
            else {
                const s = clamp(t - d.grab, m.se.first, m.now - d.len);
                setWindow(s, s + d.len);
            }
        };
        const end = () => {
            if (!S.drag) return;
            S.drag = null;
            nav.classList.remove("dragging");
            win.classList.remove("grabbing");
            snapToPreset();
        };
        [[hl, "l"], [hr, "r"], [win, "m"]].forEach(([node, mode]) => {
            node.addEventListener("pointerdown", start(mode, node));
            node.addEventListener("pointermove", move);
            node.addEventListener("pointerup", end);
            node.addEventListener("pointercancel", end);
        });

        // Toque na barra, fora da janela: a janela desliza suavemente para esse ponto
        nav.addEventListener("pointerdown", ev => {
            const m = S.model;
            if (!m || m.empty || ev.target.closest("#bcWin")) return;
            const len = m.e - m.s;
            const c = timeAt(ev, m);
            const s = clamp(c - len / 2, m.se.first, m.now - len);
            setWindow(s, s + len, { noAnim: false });
            setTimeout(snapToPreset, 480);
        });

        // Teclado: setas (1/20 da janela), Shift (1/4), PageUp/PageDown (a janela toda), Home/End
        const onKey = mode => ev => {
            const m = S.model;
            if (!m || m.empty) return;
            const len = m.e - m.s;
            const unit = ev.key === "PageUp" || ev.key === "PageDown" ? len : ev.shiftKey ? len / 4 : Math.max(MIN, len / 20);
            const dir = (ev.key === "ArrowRight" || ev.key === "PageDown" || ev.key === "ArrowUp") ? 1
                : (ev.key === "ArrowLeft" || ev.key === "PageUp" || ev.key === "ArrowDown") ? -1 : 0;
            let s = m.s, e = m.e;
            if (ev.key === "Home") { if (mode === "l") s = m.se.first; else if (mode === "r") e = m.s + MIN_SPAN; else { s = m.se.first; e = s + len; } }
            else if (ev.key === "End") { if (mode === "l") s = m.e - MIN_SPAN; else if (mode === "r") e = m.now; else { e = m.now; s = e - len; } }
            else if (dir) {
                const k = dir * unit;
                if (mode === "l") s = Math.min(s + k, m.e - MIN_SPAN); else if (mode === "r") e = Math.max(e + k, m.s + MIN_SPAN); else { s += k; e += k; }
            } else return;
            ev.preventDefault();
            nav.classList.remove("dragging");
            setWindow(s, e, { noAnim: true });
            clearTimeout(S.snapT);
            S.snapT = setTimeout(snapToPreset, 600);
        };
        hl.addEventListener("keydown", onKey("l"));
        hr.addEventListener("keydown", onKey("r"));
        win.addEventListener("keydown", ev => { if (ev.target === win) onKey("m")(ev); });

        // Campos de data e hora (abrem o calendário/relógio do telemóvel ou do computador)
        const fromIn = el("bcDateFrom"), toIn = el("bcDateTo");
        fromIn.addEventListener("change", () => {
            const m = S.model, d = new Date(fromIn.value);
            if (!m || isNaN(d)) return;
            setWindow(+d, Math.max(m.e, +d + MIN_SPAN), { noAnim: false });
            snapToPreset();
        });
        toIn.addEventListener("change", () => {
            const m = S.model, d = new Date(toIn.value);
            if (!m || isNaN(d)) return;
            setWindow(Math.min(m.s, +d - MIN_SPAN), +d, { noAnim: false });
            snapToPreset();
        });

        document.querySelectorAll("#bcQuick .cc-chip").forEach(b => b.addEventListener("click", () => setQuick(b.dataset.span)));
        document.querySelectorAll("#bcTools .bc-tool").forEach(b => b.addEventListener("click", () => tool(b.dataset.act)));
    }

    /* ------------------------------ Copilot (sempre no fim da página) ------------------------------ */

    function renderCopilot() {
        const list = el("ccCopilotInsights"), chipsEl = el("ccCopilotChips"), title = el("ccCopilotTitle");
        if (!list) return;
        const rows = [], chips = [];
        const row = (tone, icon, h, html) => rows.push(`<div class="sgc-row" data-tone="${tone}"><span class="sgc-ico"><svg><use href="${icon}"/></svg></span><div><h5>${h}</h5><p>${html}</p></div></div>`);
        const b = v => `<b>${money(v, curr())}</b>`;
        const se = getSeries();

        if (S.chart === "balance" && S.model) {
            const m = S.model;
            if (title) title.textContent = "Análise da evolução do seu saldo";
            if (m.empty) {
                row("info", "#i-spark", "Sem dados ainda", state.token ? "Assim que a conta tiver movimentos, o Copilot explica aqui o que mudou no seu saldo." : "Inicie sessão para o Copilot analisar o seu saldo.");
                chips.push("Como acompanhar melhor o meu saldo?");
            } else {
                const pMax = m.pts[m.iMax];
                const tr = trend(m);
                if (tr !== "flat") {
                    const pct = m.start > 0 ? ` (${String(Math.round(Math.abs(m.delta / m.start) * 1000) / 10).replace(".", ",")}%)` : "";
                    row(tr === "up" ? "good" : "warn", "#i-trending", tr === "up" ? "Saldo a subir" : "Saldo a descer",
                        `Neste intervalo (${durLabel(m.span)}) o saldo ${tr === "up" ? "subiu" : "desceu"} ${b(Math.abs(m.delta))}${hidden() ? "" : pct}: de ${b(m.start)} para ${b(m.final)}.`);
                } else {
                    row("info", "#i-trending", "Saldo estável", m.moves ? `Houve ${m.moves} ${m.moves === 1 ? "movimento" : "movimentos"}, mas o saldo terminou onde começou: ${b(m.final)}.` : `Sem movimentos neste intervalo. O saldo manteve-se em ${b(m.final)}.`);
                }
                if (pMax.v - m.final > 0.004 && pMax.v > 0) {
                    const drop = Math.round(((pMax.v - m.final) / pMax.v) * 100);
                    row(drop >= 50 ? "warn" : "info", "#i-award", "Face ao máximo",
                        `O saldo chegou a ${b(pMax.v)} ${pMax.kind === "start" ? "no início do intervalo" : "(" + dtShort(pMax.t) + ")"} e está ${drop}% abaixo desse valor.`);
                }
                const evs = m.pts.slice(1).map(p => p.ev);
                const big = evs.reduce((a, x) => (!a || Math.abs(x.v) > Math.abs(a.v)) ? x : a, null);
                if (big) {
                    row("tip", "#i-spark", "Maior movimento",
                        `${big.v >= 0 ? "Entrada" : "Saída"} de ${b(Math.abs(big.v))} em ${dtShort(big.t)}${big.desc ? " — " + esc(big.desc.length > 60 ? big.desc.slice(0, 59) + "…" : big.desc) : ""}.`);
                }
                chips.push(tr === "down" ? "Porque é que o meu saldo desceu?" : "Como fazer o meu saldo crescer?", "Qual foi o meu maior movimento recente?", "Como evitar ficar com o saldo baixo?");
            }
        } else if (S.chart === "flow") {
            if (title) title.textContent = "Análise das suas entradas e saídas";
            const since = Date.now() - 30 * DAY;
            const last = se.ev.filter(x => x.t >= since);
            let inn = 0, out = 0, bigOut = null;
            last.forEach(x => { if (x.v > 0) inn += x.v; else { out += -x.v; if (!bigOut || -x.v > -bigOut.v) bigOut = x; } });
            if (se.empty || !last.length) {
                row("info", "#i-spark", "Sem movimentos recentes", "Nos últimos 30 dias não há movimentos nesta moeda para comparar entradas e saídas.");
                chips.push("Como organizar as minhas entradas e saídas?");
            } else {
                const net = inn - out;
                row(net >= 0 ? "good" : "warn", "#i-trending", net >= 0 ? "Entrou mais do que saiu" : "Saiu mais do que entrou",
                    `Nos últimos 30 dias entraram ${b(inn)} e saíram ${b(out)}: diferença de ${net < 0 ? "−" : "+"}${b(Math.abs(net))}.`);
                if (inn > 0) {
                    const rate = Math.round((net / inn) * 100);
                    row(rate >= 20 ? "good" : "tip", "#i-target", "Taxa de poupança", hidden() ? "Valores ocultos." : `Guardou cerca de <b>${rate}%</b> do que recebeu nos últimos 30 dias.`);
                }
                if (bigOut) row("tip", "#i-spark", "Maior saída", `${b(-bigOut.v)} em ${dtShort(bigOut.t)}${bigOut.desc ? " — " + esc(bigOut.desc.length > 60 ? bigOut.desc.slice(0, 59) + "…" : bigOut.desc) : ""}.`);
                chips.push("Estou a gastar mais do que recebo?", "Onde posso cortar gastos?");
            }
        } else if (S.chart === "card" && typeof window.cardSpendInsights === "function") {
            window.cardSpendInsights(row, chips, t => { if (title) title.textContent = t; });
        } else if (S.chart === "merchants" && typeof window.merchantInsights === "function") {
            window.merchantInsights(row, chips, t => { if (title) title.textContent = t; });
        } else if (S.chart === "accounts" && typeof window.accountsFlowInsights === "function") {
            window.accountsFlowInsights(row, chips, t => { if (title) title.textContent = t; });
        } else if (S.chart === "forecast" && typeof window.forecastInsights === "function") {
            window.forecastInsights(row, chips, t => { if (title) title.textContent = t; });
        } else {
            rows.length = 0;
        }
        list.innerHTML = rows.join("");
        if (chipsEl) {
            chipsEl.innerHTML = chips.slice(0, 3).map(c =>
                `<button type="button" data-q="${esc(c)}">${esc(c)}</button>`).join("");
        }
    }

    /* ------------------------------ ciclo de vida ------------------------------ */

    function signature() {
        const se = getSeries();
        return [se.key, S.period, S.custom ? S.custom.s + "-" + S.custom.e : "", hidden() ? 1 : 0, S.chart].join("|");
    }

    function render(opts) {
        const view = el("view-card-chart");
        if (!view || !view.classList.contains("active") || !el("ccChart")) return;
        bind();
        S.sig = signature();
        if (S.chart !== "balance") {
            const c = el("ccCurrency"); if (c) c.textContent = curr();
            const eye = el("ccEye");
            if (eye) { eye.textContent = hidden() ? "Mostrar" : "Ocultar"; eye.setAttribute("aria-label", hidden() ? "Mostrar valores" : "Ocultar valores"); }
            const draw = { card: window.renderCardSpend, merchants: window.renderMerchants, accounts: window.renderAccountsFlow, forecast: window.renderForecast }[S.chart] || window.renderFlowChart;
            if (typeof draw === "function") draw(opts);
            renderCopilot();
            return;
        }
        const animate = !(opts && opts.noAnim);
        const model = buildModel();
        S.model = model;
        drawNavSeries(model);
        positionNav(model);
        drawChrome(model);
        drawChart(model, animate);
        renderCopilot();
    }

    /** Chamado depois de cada atualização de dados: só redesenha se algo mudou. */
    function refresh() {
        const view = el("view-card-chart");
        if (!view || !view.classList.contains("active")) return;
        if (S.chart !== "balance") {
            const upd = { card: window.refreshCardSpend, merchants: window.refreshMerchants, accounts: window.refreshAccountsFlow, forecast: window.refreshForecast }[S.chart] || window.refreshFlowChart;
            if (typeof upd === "function") upd();
            if (signature() !== S.sig) { S.sig = signature(); renderCopilot(); }
            return;
        }
        if (signature() !== S.sig) render({ noAnim: true });
    }

    /** Troca o painel visível (1 = Evolução do saldo, 2 = Entradas vs. saídas, 3 = Fluxo de gastos do cartão, 4 = Gastos por comerciante, 5 = Fluxo entre contas). */
    function showChart(name) {
        if (S.chart === name) return;
        S.chart = name;
        document.querySelectorAll("#bcTypes .bc-type").forEach(b => {
            const on = b.dataset.chart === name;
            b.classList.toggle("active", on);
            b.setAttribute("aria-pressed", String(on));
        });
        document.querySelectorAll("#view-card-chart .bc-panel").forEach(p => { p.hidden = p.dataset.chart !== name; });
        if (name === "balance") S.sig = "";
        render();
    }

    function bind() {
        if (S.bound) return;
        S.bound = true;

        // Filtros rápidos
        document.querySelectorAll("#ccPeriods .cc-chip").forEach(btn => btn.addEventListener("click", () => {
            S.period = btn.dataset.period;
            S.custom = null;
            S.selT = null;
            try { localStorage.setItem(STORE_KEY, S.period); } catch (e) { /* ignorar */ }
            render();
        }));

        // Menu dos 6 gráficos: os cinco primeiros estão desenvolvidos
        document.querySelectorAll("#bcTypes .bc-type").forEach(btn => btn.addEventListener("click", () => {
            if (!btn.hasAttribute("data-soon")) { showChart(btn.dataset.chart); return; }
            const badge = btn.querySelector(".bc-soon");
            if (badge) { badge.classList.remove("nudge"); void badge.offsetWidth; badge.classList.add("nudge"); }
            if (typeof toast === "function") toast(`«${SOON_NAMES[btn.dataset.chart] || "Este gráfico"}» chega em breve`, "info");
        }));

        // Máximo / mínimo: tocar leva o cursor ao ponto
        el("bcStatMaxBtn").addEventListener("click", () => { if (S.model) select(S.model.pts[S.model.iMax].t, false); });
        el("bcStatMinBtn").addEventListener("click", () => { if (S.model) select(S.model.pts[S.model.iMin].t, false); });

        const eye = el("ccEye");
        if (eye) eye.addEventListener("click", () => { const b = el("btnToggleDashBalance"); if (b) b.click(); else document.body.classList.toggle("balances-hidden"); });

        // Copilot do fim da página: perguntas rápidas e abrir a conversa
        const chipsEl = el("ccCopilotChips");
        if (chipsEl) chipsEl.addEventListener("click", ev => {
            const btn = ev.target.closest("button[data-q]");
            if (btn && typeof window.askCopilotAbout === "function") window.askCopilotAbout(btn.dataset.q);
        });

        bindNav();

        // Tocar fora do gráfico limpa a seleção (no telemóvel a seleção fica depois de levantar o dedo)
        document.addEventListener("pointerdown", ev => {
            const root = el("ccChart");
            if (root && !root.contains(ev.target)) clearSel();
        });
        // Mostrar/ocultar saldos (olho) e mudança de largura redesenham sem animação
        new MutationObserver(() => refresh()).observe(document.body, { attributes: true, attributeFilter: ["class"] });
        if (typeof ResizeObserver !== "undefined") {
            let raf = 0;
            new ResizeObserver(() => {
                cancelAnimationFrame(raf);
                raf = requestAnimationFrame(() => {
                    const root = el("ccChart");
                    if (root && root.clientWidth && Math.floor(root.clientWidth) !== S.width) render({ noAnim: true });
                });
            }).observe(el("ccChart"));
        }
    }

    // Utilitários partilhados com os outros gráficos
    window.ccShared = { money, compactMoney, hidden, curr, symbol, niceScale, axisLabel, MONTHS, clamp, dayStart, addDays };
    window.renderCardChart = render;
    window.refreshCardChart = refresh;
    window.clearChartHoverDetails = function () {
        clearSel();
        if (typeof window.clearForecastHoverDetails === "function") window.clearForecastHoverDetails();
        if (typeof window.clearWidgetHoverDetails === "function") window.clearWidgetHoverDetails();
    };
    window.refreshCardCopilot = function () { if (S.chart === "card" || S.chart === "merchants" || S.chart === "accounts") renderCopilot(); };
})();
