/**
 * Gráfico do cartão
 * Página aberta ao tocar no cartão de saldo do início. Três linhas suaves no mesmo eixo:
 *   verde = dinheiro recebido · vermelho = dinheiro que saiu · azul = ritmo ideal (IA).
 * O azul é o gasto recomendado para cumprir as metas de poupança: o servidor (Meta Model API)
 * propõe o valor em /api/ai/ideal-pace e, sem sessão, sem chave ou sem rede, usa-se o mesmo
 * cálculo localmente. Intervalos: 7 dias, 30 dias, 3 meses, 6 meses, 1 ano e Total.
 * Funciona com toque (arrastar para ler valores) e com rato (passar o cursor) e com o teclado.
 */

const CC_KEYS = ["in", "out", "ideal"];
const CC_LABELS = { in: "Recebido", out: "Saído", ideal: "Ideal (IA)" };
const CC_COLORS = { in: "#34D399", out: "#F87171", ideal: "#38BDF8" };
const CC_PERIODS = { "7d": 7, "30d": 30, "3m": 90, "6m": 182, "1a": 365, "total": null };
const CC_MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
const CC_DAY_MS = 86400000;
const CC_MONTH_DAYS = 30.4375;

const ccState = {
    period: (function () {
        try { const p = localStorage.getItem("bankao_cc_period"); if (p && p in CC_PERIODS) return p; } catch (e) { /* ignorar */ }
        return "30d";
    })(),
    hidden: { in: false, out: false, ideal: false },
    sel: null,          // índice do ponto selecionado
    geom: null,         // medidas do último desenho (para ponteiro/teclado)
    model: null,
    ai: null,           // última resposta válida da IA
    aiKey: "",          // chave dos dados a que a resposta corresponde
    aiPending: "",
    aiFailed: "",
    sig: "",
    width: 0,
    bound: false
};

/* ------------------------------ utilitários ------------------------------ */

function ccDayStart(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 0, 0, 0, 0); }
function ccAddDays(d, n) { return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n, 0, 0, 0, 0); }
function ccEl(id) { return document.getElementById(id); }
function ccRound(n) { return Math.round(n * 10) / 10; }
function ccCurr() { return (typeof state !== "undefined" && state.prefCurrency) || "AOA"; }
function ccSymbol(curr) {
    const info = typeof CURRENCY_INFO !== "undefined" ? CURRENCY_INFO[curr] : null;
    return info ? info.symbol : curr;
}
function ccHidden() { return document.body.classList.contains("balances-hidden"); }
const CC_MASK = "••••••";

/** 1250000 -> "1.250.000 KZ" (ou máscara quando os saldos estão ocultos) */
function ccMoney(n, curr) {
    if (ccHidden()) return CC_MASK;
    return formatNumberWithDots(Math.round(n)) + "\u00a0" + ccSymbol(curr || ccCurr());
}
/** 1250000 -> "1,25 M" · 45000 -> "45 k" (sem moeda, para eixos e cartões pequenos) */
function ccCompact(n) {
    const a = Math.abs(n);
    const fix = (v, d) => String(parseFloat(v.toFixed(d))).replace(".", ",");
    if (a >= 1e6) return fix(n / 1e6, a >= 1e7 ? 1 : 2) + "\u00a0M";
    if (a >= 1e4) return fix(n / 1e3, 0) + "\u00a0k";
    if (a >= 1e3) return fix(n / 1e3, 1) + "\u00a0k";
    return String(Math.round(n));
}
function ccCompactMoney(n, curr) {
    if (ccHidden()) return CC_MASK;
    return ccCompact(n) + "\u00a0" + ccSymbol(curr || ccCurr());
}

/* ------------------------------ dados ------------------------------ */

/** Movimentos reais do extrato, já convertidos para a moeda escolhida (valor com sinal). */
function ccCollectTxs(curr) {
    const raw = (typeof state !== "undefined" && Array.isArray(state.transactions)) ? state.transactions : [];
    const out = [];
    raw.forEach(tx => {
        if (/fail|falh|cancel|recus/i.test(String(tx.status || ""))) return;
        const t = parseTxDate(tx.created_at);
        if (isNaN(t)) return;
        const v = convertMoney(Number(tx.amount_decimal) || 0, tx.currency || "AOA", curr);
        if (v) out.push({ t, v });
    });
    return out;
}

/** Movimentos de demonstração (sem sessão ou sem histórico): determinísticos, para o gráfico nunca ficar vazio. */
function ccDemoTxs(curr, now) {
    let seed = 20261031;
    const rnd = () => {
        seed = (seed + 0x6D2B79F5) | 0;
        let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    const today = ccDayStart(now);
    const list = [];
    for (let d = 364; d >= 0; d--) {
        const day = ccAddDays(today, -d);
        const at = new Date(day.getFullYear(), day.getMonth(), day.getDate(), 12);
        const dom = day.getDate();
        const add = aoa => list.push({ t: at, v: convertMoney(aoa, "AOA", curr) });
        if (dom === 25) add(260000 + Math.round(rnd() * 30000));       // salário
        if (day.getDay() === 5 && rnd() < 0.8) add(30000 + Math.round(rnd() * 40000));   // pagamentos semanais
        if (dom === 1) add(-60000);                                    // renda
        if (dom === 5) add(-26000);                                    // internet
        if (rnd() < 0.07) add(20000 + Math.round(rnd() * 70000));      // depósitos
        if (rnd() < 0.5) add(-(3000 + Math.round(rnd() * 15000)));     // gastos do dia a dia
        if (rnd() < 0.04) add(-(30000 + Math.round(rnd() * 30000)));   // gastos maiores
    }
    return list;
}

/** Metas e orçamento do utilizador (guardados em AOA) na moeda do gráfico. */
function ccPlan(curr) {
    const toCurr = v => convertMoney(Number(v) || 0, "AOA", curr);
    const all = typeof getSavingsGoals === "function" ? getSavingsGoals() : [];
    const goals = all.filter(g => (Number(g.saved) || 0) < (Number(g.target) || Infinity));
    const goalsMonth = goals.reduce((a, g) => a + toCurr(g.monthly), 0);
    let budgetMonth = 0;
    if (typeof getCategoryBudgets === "function") {
        const b = getCategoryBudgets();
        Object.keys(b).forEach(k => { if (k !== "Poupança") budgetMonth += toCurr(b[k]); });
    }
    return { all, goals, goalsMonth, budgetMonth, toCurr };
}

/** Receita e despesa médias por mês (janela de 30 a 90 dias, independente do intervalo escolhido). */
function ccMonthlyStats(txs, now) {
    const today = ccDayStart(now);
    let first = today;
    txs.forEach(x => { if (x.t < first) first = x.t; });
    const span = Math.round((today - ccDayStart(first)) / CC_DAY_MS) + 1;
    const windowDays = Math.min(90, Math.max(30, span));
    const from = ccAddDays(today, -(windowDays - 1));
    let inc = 0, exp = 0;
    txs.forEach(x => { if (x.t >= from) { if (x.v > 0) inc += x.v; else exp += -x.v; } });
    const k = CC_MONTH_DAYS / windowDays;
    return { income: inc * k, expense: exp * k };
}

/** Mesmo cálculo do servidor (backend/ai/ideal_pace.py: local_ideal). */
function ccLocalIdeal(income, budget, goals) {
    income = Math.max(0, income); budget = Math.max(0, budget); goals = Math.max(0, goals);
    const ideal = income <= 0 ? budget : (budget > 0 ? Math.min(budget, income - goals) : income - goals);
    return Math.max(budget > 0 ? 0.3 * budget : 0, ideal, 0);
}
function ccStatus(expense, ideal) {
    if (!(ideal > 0)) return "sem-dados";
    const r = expense / ideal;
    return r <= 1 ? "dentro" : (r <= 1.2 ? "atencao" : "acima");
}
const CC_STATUS_TEXT = { "dentro": "Dentro do ritmo", "atencao": "Atenção", "acima": "Acima do ideal" };
const CC_GENERIC_TIP = {
    "dentro": "Está dentro do ritmo ideal para cumprir as suas metas. Continue assim.",
    "atencao": "Os gastos estão um pouco acima do ideal. Pequenos cortes já aproximam as metas.",
    "acima": "Os gastos estão bem acima do ideal. Rever as despesas maiores ajuda a cumprir as metas.",
    "sem-dados": "Ainda há poucos movimentos. Com mais histórico, o ritmo ideal fica mais preciso."
};
function ccLocalTip(status, curr, expense, ideal, goals) {
    const fmt = v => formatNumberWithDots(Math.round(v)) + "\u00a0" + ccSymbol(curr);
    const first = goals.length ? goals[0].name : "";
    if (status === "dentro") return `Está dentro do ritmo: gasta cerca de ${fmt(expense)} por mês e o ideal é até ${fmt(ideal)}.` + (first ? ` Continue assim para chegar a «${first}».` : "");
    if (status === "atencao" || status === "acima") return `Está a gastar mais ${fmt(Math.max(0, expense - ideal))} por mês do que o ideal (${fmt(ideal)}).` + (first ? ` Reduzir este valor aproxima-o de «${first}».` : " Rever as despesas maiores ajuda.");
    return CC_GENERIC_TIP["sem-dados"];
}

/** Divide o intervalo em colunas (dia, semana ou mês) e soma recebido/saído em cada uma. */
function ccBuildBuckets(txs, periodKey, now, createdAt) {
    const today = ccDayStart(now);
    const days = CC_PERIODS[periodKey];
    let start;
    if (days) {
        start = ccAddDays(today, -(days - 1));
    } else {
        let first = today;
        txs.forEach(x => { if (x.t < first) first = x.t; });
        if (createdAt && !isNaN(createdAt) && createdAt < first) first = createdAt;
        start = ccDayStart(first);
        if (Math.round((today - start) / CC_DAY_MS) < 6) start = ccAddDays(today, -6);
    }
    const end = ccAddDays(today, 1);
    const spanDays = Math.round((end - start) / CC_DAY_MS);
    const gran = spanDays <= 45 ? "day" : spanDays <= 200 ? "week" : "month";
    const buckets = [];
    let cur = new Date(start);
    while (cur < end) {
        let next = gran === "day" ? ccAddDays(cur, 1) : gran === "week" ? ccAddDays(cur, 7) : new Date(cur.getFullYear(), cur.getMonth() + 1, 1);
        if (next > end) next = end;
        buckets.push({ start: new Date(cur), end: new Date(next), in: 0, out: 0, ideal: 0 });
        cur = next;
    }
    txs.forEach(x => {
        if (x.t < start || x.t >= end) return;
        const b = buckets.find(k => x.t >= k.start && x.t < k.end);
        if (!b) return;
        if (x.v > 0) b.in += x.v; else b.out += -x.v;
    });
    return { buckets, gran, start, end, spanDays };
}

function ccBucketLabel(b, gran, long) {
    const d = b.start;
    const day = `${d.getDate()} ${CC_MONTHS[d.getMonth()]}`;
    if (gran === "month") return long ? `${CC_MONTHS[d.getMonth()]} ${d.getFullYear()}` : CC_MONTHS[d.getMonth()];
    if (gran === "week" && long) {
        const last = ccAddDays(b.end, -1);
        return last.getTime() === d.getTime() ? day : `${day} – ${last.getDate()} ${CC_MONTHS[last.getMonth()]}`;
    }
    return long ? `${day} ${d.getFullYear()}` : day;
}

/** Junta tudo num modelo pronto a desenhar. */
function ccCompute(opts) {
    const now = (opts && opts.now) || new Date();
    const curr = ccCurr();
    const real = ccCollectTxs(curr);
    const demo = !(typeof state !== "undefined" && state.token) || real.length === 0;
    const txs = demo ? ccDemoTxs(curr, now) : real;

    let createdAt = null;
    try { createdAt = typeof getAccountCreationDate === "function" ? getAccountCreationDate() : null; } catch (e) { /* ignorar */ }

    const plan = ccPlan(curr);
    const monthly = ccMonthlyStats(txs, now);
    const localIdeal = ccLocalIdeal(monthly.income, plan.budgetMonth, plan.goalsMonth);
    const aiKey = JSON.stringify([curr, Math.round(monthly.income), Math.round(monthly.expense), Math.round(plan.budgetMonth), Math.round(plan.goalsMonth), plan.goals.length]);
    const useAi = !demo && ccState.ai && ccState.aiKey === aiKey;
    const idealMonth = useAi ? Number(ccState.ai.ideal_spend_month) : localIdeal;

    const built = ccBuildBuckets(txs, ccState.period, now, demo ? null : createdAt);
    built.buckets.forEach(b => {
        const days = Math.max(1, Math.round((b.end - b.start) / CC_DAY_MS));
        b.ideal = idealMonth * days / CC_MONTH_DAYS;
    });

    const totals = { in: 0, out: 0, ideal: 0 };
    built.buckets.forEach(b => CC_KEYS.forEach(k => { totals[k] += b[k]; }));

    const status = ccStatus(monthly.expense, idealMonth);
    return {
        curr, demo, now, plan, monthly, idealMonth, status, totals, aiKey, useAi,
        savingsMonth: Math.max(0, monthly.income - idealMonth),
        tip: useAi && ccState.ai.tip ? String(ccState.ai.tip) : ccLocalTip(status, curr, monthly.expense, idealMonth, plan.goals),
        aiMeta: useAi ? ccState.ai : null,
        aiPayload: {
            currency: curr,
            income_month: Math.round(monthly.income),
            expense_month: Math.round(monthly.expense),
            budget_month: Math.round(plan.budgetMonth),
            goals: plan.goals.slice(0, 12).map(g => ({
                name: String(g.name || "").slice(0, 60),
                target: Math.round(plan.toCurr(g.target)),
                saved: Math.round(plan.toCurr(g.saved)),
                monthly: Math.round(plan.toCurr(g.monthly)),
                deadline: g.deadline ? String(g.deadline).slice(0, 30) : null
            }))
        },
        ...built
    };
}

/* ------------------------------ geometria ------------------------------ */

/** Eixo Y "redondo": passos de 1, 2, 2,5, 5 × 10ⁿ. */
function ccNiceTicks(maxV) {
    if (!(maxV > 0)) return { max: 1, values: [0, 1] };
    const raw = maxV * 1.08 / 4;
    const p = Math.pow(10, Math.floor(Math.log10(raw)));
    const f = raw / p;
    const step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
    const top = Math.ceil(maxV * 1.04 / step) * step;
    const values = [];
    for (let v = 0; v <= top + step / 1000; v += step) values.push(v);
    return { max: top, values };
}

/** Curva suave que nunca ultrapassa os pontos (interpolação cúbica monótona), sem "ondas" abaixo de zero. */
function ccSmoothPath(pts) {
    const n = pts.length;
    if (!n) return "";
    const r = ccRound;
    if (n === 1) return `M${r(pts[0][0])} ${r(pts[0][1])}`;
    const dx = [], m = [];
    for (let i = 0; i < n - 1; i++) {
        dx[i] = pts[i + 1][0] - pts[i][0];
        m[i] = dx[i] === 0 ? 0 : (pts[i + 1][1] - pts[i][1]) / dx[i];
    }
    const t = [m[0]];
    for (let i = 1; i < n - 1; i++) t[i] = m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2;
    t[n - 1] = m[n - 2];
    for (let i = 0; i < n - 1; i++) {
        if (m[i] === 0) { t[i] = 0; t[i + 1] = 0; continue; }
        const a = t[i] / m[i], b = t[i + 1] / m[i], s = a * a + b * b;
        if (s > 9) { const k = 3 / Math.sqrt(s); t[i] = k * a * m[i]; t[i + 1] = k * b * m[i]; }
    }
    let d = `M${r(pts[0][0])} ${r(pts[0][1])}`;
    for (let i = 0; i < n - 1; i++) {
        const h = dx[i] / 3;
        d += ` C${r(pts[i][0] + h)} ${r(pts[i][1] + t[i] * h)} ${r(pts[i + 1][0] - h)} ${r(pts[i + 1][1] - t[i + 1] * h)} ${r(pts[i + 1][0])} ${r(pts[i + 1][1])}`;
    }
    return d;
}

/** Medidas do desenho para uma largura em pixéis. */
function ccGeometry(model, w) {
    const h = w < 520 ? 250 : w < 900 ? 300 : 340;
    const m = { l: w < 520 ? 42 : 50, r: 12, t: 12, b: 28 };
    const iw = w - m.l - m.r, ih = h - m.t - m.b, n = model.buckets.length;
    const visible = CC_KEYS.filter(k => !ccState.hidden[k]);
    const keys = visible.length ? visible : CC_KEYS;
    let maxV = 0;
    model.buckets.forEach(b => keys.forEach(k => { if (b[k] > maxV) maxV = b[k]; }));
    const ticks = ccNiceTicks(maxV);
    const x = i => m.l + (n === 1 ? iw / 2 : iw * i / (n - 1));
    const y = v => m.t + ih * (1 - Math.min(v, ticks.max) / ticks.max);
    return { w, h, m, iw, ih, n, ticks, x, y };
}

/** Markup do SVG (função pura: facilita testar). `hide` oculta os valores do eixo Y. */
function ccSvgMarkup(model, w, hide) {
    const g = ccGeometry(model, w);
    const { m, n, ticks, x, y } = g;
    const B = model.buckets;
    const base = y(0);
    const pts = k => B.map((b, i) => [x(i), y(b[k])]);
    const line = {}, area = {};
    CC_KEYS.forEach(k => {
        line[k] = ccSmoothPath(pts(k));
        area[k] = n > 1 ? `${line[k]} L${ccRound(x(n - 1))} ${ccRound(base)} L${ccRound(x(0))} ${ccRound(base)} Z` : "";
    });

    const grid = ticks.values.map((v, i) => `<line class="${i === 0 ? "base" : ""}" x1="${m.l}" x2="${w - m.r}" y1="${ccRound(y(v))}" y2="${ccRound(y(v))}"/>`).join("");
    const yl = hide ? "" : ticks.values.map(v => `<text x="${m.l - 8}" y="${ccRound(y(v)) + 3.5}" text-anchor="end">${ccCompact(v)}</text>`).join("");
    const count = Math.min(n, w < 520 ? 4 : 6);
    let xl = "";
    for (let j = 0; j < count; j++) {
        const i = count === 1 ? 0 : Math.round(j * (n - 1) / (count - 1));
        const anchor = j === 0 ? "start" : j === count - 1 ? "end" : "middle";
        xl += `<text x="${ccRound(x(i))}" y="${g.h - 8}" text-anchor="${anchor}">${ccBucketLabel(B[i], model.gran, false)}</text>`;
    }
    const topY = m.t - 4;
    const aboveIdeal = n > 1 ? `${line.ideal} L${ccRound(x(n - 1))} ${topY} L${ccRound(x(0))} ${topY} Z` : "";
    const on = k => ccState.hidden[k] ? "off" : "";

    return `<svg class="cc-svg" id="ccSvg" viewBox="0 0 ${w} ${g.h}" width="${w}" height="${g.h}" tabindex="0" focusable="true" aria-label="Gráfico de linhas. Use as setas para ler cada ponto.">
<defs>
<linearGradient id="ccGradIn" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${CC_COLORS.in}" stop-opacity=".34"/><stop offset="1" stop-color="${CC_COLORS.in}" stop-opacity="0"/></linearGradient>
<linearGradient id="ccGradOut" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${CC_COLORS.out}" stop-opacity=".30"/><stop offset="1" stop-color="${CC_COLORS.out}" stop-opacity="0"/></linearGradient>
<clipPath id="ccClipAbove"><path d="${aboveIdeal}"/></clipPath>
</defs>
<g class="cc-grid">${grid}</g>
<g class="cc-axis">${yl}${xl}</g>
<g class="cc-series ${on("in")}" id="ccSerIn"><path class="cc-area" d="${area.in}" fill="url(#ccGradIn)"/><path class="cc-line cc-line--in" pathLength="1" d="${line.in}"/></g>
<g class="cc-series ${on("out")}" id="ccSerOut"><path class="cc-area" d="${area.out}" fill="url(#ccGradOut)"/>${(!ccState.hidden.out && !ccState.hidden.ideal && n > 1) ? `<path class="cc-over" d="${area.out}" clip-path="url(#ccClipAbove)"/>` : ""}<path class="cc-line cc-line--out" pathLength="1" d="${line.out}"/></g>
<g class="cc-series ${on("ideal")}" id="ccSerIdeal"><path class="cc-line cc-line--ideal" pathLength="1" d="${line.ideal}"/></g>
<g id="ccSel" style="display:none"><line class="cc-cursor" id="ccCursor" x1="0" x2="0" y1="${m.t}" y2="${m.t + g.ih}"/>${CC_KEYS.map(k => `<circle class="cc-pt" id="ccPt-${k}" r="5" fill="${CC_COLORS[k]}" cx="0" cy="0"/>`).join("")}</g>
<rect class="cc-hit" id="ccHit" x="${m.l - 6}" y="0" width="${g.iw + 12}" height="${g.h}"/>
</svg>`;
}

/* ------------------------------ desenho ------------------------------ */

function ccDrawChart(model, animate) {
    const root = ccEl("ccChart");
    if (!root) return;
    const w = Math.max(280, Math.floor(root.clientWidth));
    ccState.width = w;
    root.classList.toggle("no-anim", !animate);
    root.innerHTML = ccSvgMarkup(model, w, ccHidden()) + `<div class="cc-tip" id="ccTip" role="status"></div>`;
    ccState.geom = ccGeometry(model, w);
    root.setAttribute("aria-label", `Gráfico de linhas de ${CC_LABELS.in.toLowerCase()}, ${CC_LABELS.out.toLowerCase()} e ritmo ideal, ${model.buckets.length} pontos`);

    const svg = ccEl("ccSvg"), hit = ccEl("ccHit");
    const idxAt = ev => {
        const r = svg.getBoundingClientRect();
        const px = (ev.clientX - r.left) * (w / (r.width || w));
        const g = ccState.geom;
        return Math.max(0, Math.min(g.n - 1, Math.round(((px - g.m.l) / g.iw) * (g.n - 1))));
    };
    hit.addEventListener("pointerdown", ev => ccSelect(idxAt(ev)));
    hit.addEventListener("pointermove", ev => { if (ev.pointerType === "mouse" || ev.buttons) ccSelect(idxAt(ev)); });
    hit.addEventListener("pointerleave", ev => { if (ev.pointerType === "mouse") ccClear(); });
    svg.addEventListener("keydown", ev => {
        svg.setAttribute("data-kbd", "");
        const n = ccState.geom.n, cur = ccState.sel == null ? -1 : ccState.sel;
        const map = { ArrowRight: Math.min(n - 1, cur + 1), ArrowLeft: Math.max(0, cur < 0 ? n - 1 : cur - 1), Home: 0, End: n - 1 };
        if (ev.key in map) { ev.preventDefault(); ccSelect(map[ev.key]); }
        else if (ev.key === "Escape") ccClear();
    });
    svg.addEventListener("blur", () => { svg.removeAttribute("data-kbd"); ccClear(); });

    if (ccState.sel != null && ccState.sel < model.buckets.length && !animate) ccSelect(ccState.sel);
    else ccState.sel = null;
}

function ccSelect(i) {
    const g = ccState.geom, model = ccState.model;
    if (!g || !model || i == null || i < 0 || i >= g.n) return;
    ccState.sel = i;
    const b = model.buckets[i];
    const sel = ccEl("ccSel"), cursor = ccEl("ccCursor"), tip = ccEl("ccTip");
    if (!sel || !tip) return;
    sel.style.display = "";
    const px = g.x(i);
    cursor.setAttribute("x1", px); cursor.setAttribute("x2", px);
    CC_KEYS.forEach(k => {
        const c = ccEl("ccPt-" + k);
        const show = !ccState.hidden[k];
        c.style.display = show ? "" : "none";
        c.setAttribute("cx", px); c.setAttribute("cy", g.y(b[k]));
    });
    const rows = CC_KEYS.filter(k => !ccState.hidden[k]).map(k =>
        `<div><span><i style="background:${CC_COLORS[k]}"></i>${CC_LABELS[k]}</span><strong>${ccMoney(b[k], model.curr)}</strong></div>`).join("");
    tip.innerHTML = `<b>${ccBucketLabel(b, model.gran, true)}</b>${rows}`;
    const tw = tip.offsetWidth || 160;
    const scale = (ccEl("ccChart").clientWidth || g.w) / g.w;
    let left = px * scale + 14;
    if (left + tw > g.w * scale - 2) left = px * scale - tw - 14;
    tip.style.left = Math.max(2, left) + "px";
    tip.style.top = (g.m.t + 4) + "px";
    tip.classList.add("on");
}

function ccClear() {
    ccState.sel = null;
    const sel = ccEl("ccSel"), tip = ccEl("ccTip");
    if (sel) sel.style.display = "none";
    if (tip) tip.classList.remove("on");
}

function ccDrawChrome(model) {
    const curr = model.curr;
    ccEl("ccCurrency").textContent = curr;
    document.querySelectorAll("#ccPeriods .cc-chip").forEach(b => {
        const on = b.dataset.period === ccState.period;
        b.classList.toggle("active", on);
        b.setAttribute("aria-pressed", String(on));
    });
    document.querySelectorAll("#ccStats .cc-stat").forEach(b => b.setAttribute("aria-pressed", String(!ccState.hidden[b.dataset.series])));

    const a = model.buckets[0], z = model.buckets[model.buckets.length - 1];
    const lastDay = ccAddDays(z.end, -1);
    const per = { day: "por dia", week: "por semana", month: "por mês" }[model.gran];
    ccEl("ccRange").textContent = `${a.start.getDate()} ${CC_MONTHS[a.start.getMonth()]} – ${lastDay.getDate()} ${CC_MONTHS[lastDay.getMonth()]} ${lastDay.getFullYear()} · ${per}`;
    ccEl("ccDemoBadge").hidden = !model.demo;
    ccEl("ccSubtitle").textContent = model.demo ? "Exemplo com dados de demonstração" : "Entradas, saídas e o ritmo ideal para as suas metas";

    const hide = ccHidden();
    const t = model.totals;
    ccEl("ccStatIn").textContent = ccCompactMoney(t.in, curr);
    ccEl("ccStatOut").textContent = ccCompactMoney(t.out, curr);
    ccEl("ccStatIdeal").textContent = ccCompactMoney(t.ideal, curr);
    ccEl("ccStatIn").title = ccMoney(t.in, curr);
    ccEl("ccStatOut").title = ccMoney(t.out, curr);
    ccEl("ccStatIdeal").title = ccMoney(t.ideal, curr);

    const net = t.in - t.out;
    const nIn = ccEl("ccStatInNote");
    nIn.textContent = hide ? "Saldo do período" : `Saldo ${net >= 0 ? "+" : "−"}${ccCompact(Math.abs(net))}`;
    nIn.className = "cc-stat-note " + (hide ? "" : net >= 0 ? "good" : "bad");

    const nOut = ccEl("ccStatOutNote");
    if (t.ideal > 0) {
        const pct = Math.round(Math.abs(t.out / t.ideal - 1) * 100);
        const under = t.out <= t.ideal;
        nOut.textContent = pct === 0 ? "No ideal" : `${under ? "↓" : "↑"} ${pct}% ${under ? "abaixo" : "acima"}`;
        nOut.className = "cc-stat-note " + (under ? "good" : "bad");
    } else { nOut.textContent = "\u00a0"; nOut.className = "cc-stat-note"; }

    ccEl("ccStatIdealNote").textContent = hide ? "Gasto recomendado" : `≈ ${ccCompact(model.idealMonth)} / mês`;

    const eye = ccEl("ccEye");
    if (eye) eye.textContent = hide ? "Mostrar" : "Ocultar";
    if (eye) eye.setAttribute("aria-label", hide ? "Mostrar valores" : "Ocultar valores");
}

function ccDrawInsight(model) {
    const hide = ccHidden();
    const status = model.status;
    const st = ccEl("ccAiStatus");
    st.hidden = !CC_STATUS_TEXT[status];
    st.textContent = CC_STATUS_TEXT[status] || "";
    st.className = "cc-status " + (status || "");

    let src = "Cálculo local";
    if (model.demo) src = "Demonstração · cálculo local";
    else if (model.useAi) src = "IA · " + (model.aiMeta.model || "Meta Model API");
    else if (ccState.aiPending === model.aiKey) src = "A consultar a IA…";
    ccEl("ccAiSource").textContent = src;

    ccEl("ccAiTip").textContent = hide ? (CC_GENERIC_TIP[status] || CC_GENERIC_TIP["sem-dados"]) : model.tip;
    ccEl("ccFactIdeal").textContent = ccMoney(model.idealMonth, model.curr);
    ccEl("ccFactSave").textContent = ccMoney(model.savingsMonth, model.curr);

    const list = ccEl("ccGoals");
    const goals = model.plan.all.slice(0, 3);
    if (!goals.length) {
        list.innerHTML = `<p class="cc-goals-empty">Ainda não tem metas. Crie uma em Poupança para o ritmo ideal contar com ela.</p>`;
        return;
    }
    list.innerHTML = goals.map(g => {
        const pct = Math.max(0, Math.min(100, Math.round((Number(g.saved) || 0) / (Number(g.target) || 1) * 100)));
        return `<div class="cc-goal-row"><div>${escapeHtml(g.name || "Meta")}<span>${pct}%</span></div><i><b style="width:${pct}%"></b></i></div>`;
    }).join("");
}

/* ------------------------------ ciclo de vida ------------------------------ */

function ccSignature() {
    const txs = (typeof state !== "undefined" && Array.isArray(state.transactions)) ? state.transactions : [];
    return [ccCurr(), state.token ? 1 : 0, txs.length, txs[0] ? txs[0].id : "", ccState.period, ccHidden() ? 1 : 0, JSON.stringify(ccState.hidden)].join("|");
}

function renderCardChart(opts) {
    const view = ccEl("view-card-chart");
    if (!view || !view.classList.contains("active") || !ccEl("ccChart")) return;
    ccBind();
    const animate = !(opts && opts.noAnim);
    const model = ccCompute();
    ccState.model = model;
    ccState.sig = ccSignature();
    ccDrawChrome(model);
    ccDrawChart(model, animate);
    ccDrawInsight(model);
    ccFetchAi(model);
}

/** Chamado depois de cada atualização de dados: só redesenha se algo mudou. */
function refreshCardChart() {
    const view = ccEl("view-card-chart");
    if (!view || !view.classList.contains("active")) return;
    if (ccSignature() !== ccState.sig) renderCardChart({ noAnim: true });
}

async function ccFetchAi(model) {
    if (model.demo || !state.token) return;
    const key = model.aiKey;
    if (ccState.aiKey === key || ccState.aiPending === key || ccState.aiFailed === key) return;
    ccState.aiPending = key;
    ccDrawInsight(model);
    const ctl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = setTimeout(() => ctl && ctl.abort(), 9000);
    try {
        const res = await fetch(`${API_BASE}/api/ai/ideal-pace`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "Authorization": `Bearer ${state.token}` },
            body: JSON.stringify(model.aiPayload),
            signal: ctl ? ctl.signal : undefined
        });
        if (!res.ok) throw new Error("HTTP " + res.status);
        const data = await res.json();
        if (!isFinite(data.ideal_spend_month) || data.ideal_spend_month < 0) throw new Error("resposta inválida");
        ccState.ai = data;
        ccState.aiKey = key;
    } catch (err) {
        ccState.aiFailed = key;   // fica com o cálculo local; não insiste enquanto os dados forem os mesmos
    } finally {
        clearTimeout(timer);
        ccState.aiPending = "";
        const view = ccEl("view-card-chart");
        if (view && view.classList.contains("active")) renderCardChart({ noAnim: true });
    }
}

function ccBind() {
    if (ccState.bound) return;
    ccState.bound = true;
    document.querySelectorAll("#ccPeriods .cc-chip").forEach(btn => btn.addEventListener("click", () => {
        ccState.period = btn.dataset.period;
        try { localStorage.setItem("bankao_cc_period", ccState.period); } catch (e) { /* ignorar */ }
        renderCardChart();
    }));
    document.querySelectorAll("#ccStats .cc-stat").forEach(btn => btn.addEventListener("click", () => {
        const k = btn.dataset.series;
        const visible = CC_KEYS.filter(s => !ccState.hidden[s]).length;
        if (!ccState.hidden[k] && visible === 1) return;   // pelo menos uma linha fica sempre visível
        ccState.hidden[k] = !ccState.hidden[k];
        renderCardChart({ noAnim: true });
    }));
    const eye = ccEl("ccEye");
    if (eye) eye.addEventListener("click", () => { const b = ccEl("btnToggleDashBalance"); if (b) b.click(); else document.body.classList.toggle("balances-hidden"); });

    // Tocar fora do gráfico limpa a seleção (no telemóvel a seleção fica depois de levantar o dedo)
    document.addEventListener("pointerdown", ev => {
        const root = ccEl("ccChart");
        if (root && !root.contains(ev.target)) ccClear();
    });
    // Mostrar/ocultar saldos (olho) e mudança de largura redesenham sem animação
    new MutationObserver(() => refreshCardChart()).observe(document.body, { attributes: true, attributeFilter: ["class"] });
    if (typeof ResizeObserver !== "undefined") {
        let raf = 0;
        new ResizeObserver(() => {
            cancelAnimationFrame(raf);
            raf = requestAnimationFrame(() => {
                const root = ccEl("ccChart");
                if (root && root.clientWidth && Math.floor(root.clientWidth) !== ccState.width) renderCardChart({ noAnim: true });
            });
        }).observe(ccEl("ccChart"));
    }
}

window.renderCardChart = renderCardChart;
window.refreshCardChart = refreshCardChart;
