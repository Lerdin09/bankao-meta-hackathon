/**
 * Gráficos da conta — 5. Fluxo entre contas (diagrama de Sankey)
 *   • Três colunas: ORIGEM do dinheiro (depósitos, transferências recebidas, resgates…) → CONTAS (AOA, EUR, USD)
 *     → DESTINO (compras, levantamentos, poupanças, transferências, taxas, o que ficou na conta…).
 *   • A largura de cada faixa é proporcional ao valor; as cores mostram de onde vem e para onde vai o dinheiro.
 *   • Transferências entre as suas contas e conversões cambiais aparecem como «Vindo de / Enviado para outra conta»
 *     (faixas tracejadas = houve câmbio). As taxas e comissões têm o seu próprio destino.
 *   • O que sobrou no fim do intervalo aparece em «Ficou na conta»; o que veio de saldo anterior, em «Saldo anterior».
 *     Assim cada conta fecha as contas: o que entra é igual ao que sai.
 *   • Tocar num bloco ou numa faixa mostra o detalhe (valor, peso, ligações) e as operações, que abrem o extrato.
 *   • Filtros: moeda de apresentação (os valores das outras moedas são convertidos às taxas de referência)
 *     e intervalo (30 dias a Tudo).
 * Usa só os movimentos reais do extrato (concluídos). Sem sessão ou sem dados mostra um estado vazio.
 * Depende de card-chart.js (window.ccShared) e é chamado por ele quando este painel está aberto.
 * O cálculo (accountsFlowBuild) e a disposição (accountsFlowLayout) não tocam no DOM: podem ser testados à parte.
 */
(function () {
    "use strict";

    const PERIOD_KEY = "bankao_af_period";
    const DAY = 86400000;
    const PERIODS = { "30d": 30, "90d": 90, "6m": 182, "1a": 365, all: 0 };
    const PERIOD_TXT = { "30d": "Últimos 30 dias", "90d": "Últimos 90 dias", "6m": "Últimos 6 meses", "1a": "Último ano", all: "Todo o histórico" };
    const EPS = 1e-6;

    /** Blocos fixos. col: 0 origem · 1 conta · 2 destino. Os depósitos e as contas criam-se dinamicamente. */
    const NODES = {
        "in:xfer": { label: "Transferências recebidas", col: 0, color: "#2DD4BF", ic: "i-down" },
        "in:sav": { label: "Resgates de poupança", col: 0, color: "#A3E635", ic: "i-piggy" },
        "in:own": { label: "Vindo de outra conta", col: 0, color: "#38BDF8", ic: "i-swap" },
        "in:other": { label: "Outras entradas", col: 0, color: "#64748B", ic: "i-down" },
        "in:prior": { label: "Saldo anterior", col: 0, color: "#94A3B8", ic: "i-wallet" },
        "out:sav": { label: "Poupanças", col: 2, color: "#FBBF24", ic: "i-piggy" },
        "out:buy": { label: "Compras e pagamentos", col: 2, color: "#F87171", ic: "i-cart" },
        "out:wd": { label: "Levantamentos", col: 2, color: "#FB923C", ic: "i-up" },
        "out:xfer": { label: "Transferências BankAO", col: 2, color: "#A78BFA", ic: "i-send" },
        "out:iban": { label: "Envios por IBAN", col: 2, color: "#C084FC", ic: "i-globe" },
        "out:fx": { label: "Envios com câmbio", col: 2, color: "#22D3EE", ic: "i-globe" },
        "out:own": { label: "Enviado para outra conta", col: 2, color: "#38BDF8", ic: "i-swap" },
        "out:fee": { label: "Taxas e comissões", col: 2, color: "#F472B6", ic: "i-receipt" },
        "out:other": { label: "Outras saídas", col: 2, color: "#94A3B8", ic: "i-up" },
        "out:keep": { label: "Ficou na conta", col: 2, color: "#34D399", ic: "i-wallet" }
    };
    /** Nomes curtos para ecrãs estreitos (o rótulo completo continua no detalhe e no leitor de ecrã). */
    const SHORT = {
        "in:xfer": "Transf. receb.", "in:sav": "Resgates", "in:own": "De outra conta", "in:prior": "Saldo anterior",
        "out:buy": "Compras", "out:xfer": "Transf. BankAO", "out:iban": "Envios IBAN", "out:fx": "Com câmbio",
        "out:own": "A outra conta", "out:fee": "Taxas", "out:keep": "Ficou na conta"
    };
    const DEP_COLOR = "#34D399";
    const ACC_COLOR = { AOA: "#E6B85C", EUR: "#818CF8", USD: "#6C9BFF" };
    const ACC_ORDER = ["AOA", "EUR", "USD"];

    const A = {
        cur: null,
        period: (function () {
            try { const p = localStorage.getItem(PERIOD_KEY); if (p && p in PERIODS) return p; } catch (e) { /* ignorar */ }
            return "90d";
        })(),
        sel: null,          // { t: "n" | "l", id } — bloco ou faixa escolhidos
        model: null,
        geom: null,
        width: 0,
        sig: "",
        bound: false
    };

    const el = id => document.getElementById(id);
    const sh = () => window.ccShared;
    const esc = s => (typeof escapeHtml === "function" ? escapeHtml(String(s)) : String(s).replace(/[&<>"']/g, c => "&#" + c.charCodeAt(0) + ";"));
    const cur = () => A.cur || (A.cur = (typeof state !== "undefined" && state.prefCurrency) || "AOA");
    const hm = d => `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    const norm = s => String(s).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, " ").trim();
    const pct = (v, t) => (t > 0 ? Math.round((v / t) * 100) : 0);
    const r1 = n => Math.round(n * 10) / 10;
    const trunc = (s, n) => (String(s).length > n ? String(s).slice(0, n - 1) + "…" : String(s));

    /* ------------------------------ dados ------------------------------ */

    const isDone = tx => /^(completed|conclu)/i.test(String(tx.status || ""));
    const typeOf = tx => String(tx.type || "").toLowerCase();
    const isSavings = tx => /savings|poupan/.test(typeOf(tx));
    const isFxType = tx => /fx_|c[aâ]mbio|exchange/.test(typeOf(tx));
    const isTransfer = tx => typeOf(tx).startsWith("transfer");
    const isWithdrawal = tx => /levant|saque|withdraw|\batm\b/i.test(`${typeOf(tx)} ${tx.description || ""}`);

    /** Taxa cobrada numa transferência, na moeda de origem (já incluída no valor debitado). */
    function feeOf(tx) {
        const f = tx.transfer && Number(tx.transfer.fee_decimal);
        return f > 0 ? f : 0;
    }

    /** Destino de uma saída (id do bloco). */
    function outNode(tx) {
        if (isSavings(tx)) return "out:sav";
        if (typeOf(tx) === "transfer_iban") {
            const t = tx.transfer;
            return t && t.source_currency && t.dest_currency && t.source_currency !== t.dest_currency ? "out:fx" : "out:iban";
        }
        if (isFxType(tx)) return "out:fx";
        if (isTransfer(tx)) return "out:xfer";
        if (isWithdrawal(tx)) return "out:wd";
        if (typeof classifyStatementTx === "function" && classifyStatementTx(tx) === "purchases") return "out:buy";
        return "out:other";
    }

    /** Origem de uma entrada: { id, label? } (depósitos têm um bloco por método). */
    function inNode(tx) {
        if (isSavings(tx)) return { id: "in:sav" };
        if (isTransfer(tx)) return { id: "in:xfer" };
        if (typeOf(tx).includes("deposit")) {
            const name = String((tx.counterparty && tx.counterparty.name) || "Depósitos").trim() || "Depósitos";
            return { id: "in:dep:" + norm(name), label: name };
        }
        return { id: "in:other" };
    }

    const OP_ICON = { "out:sav": "i-piggy", "out:buy": "i-cart", "out:fee": "i-receipt", "out:own": "i-swap", "in:own": "i-swap", "out:keep": "i-wallet" };

    /**
     * Constrói o modelo a partir dos movimentos do extrato (um por lançamento do livro-razão).
     * ctx: { cur, since (ms; 0 = tudo), convert(valor, de, para) }
     */
    function buildModel(raw, ctx) {
        const c = ctx.cur, since = ctx.since || 0;
        const conv = (v, from) => (from === c ? v : ctx.convert(v, from, c));
        const nodes = new Map(), links = new Map();
        const st = { skipped: 0, fxCount: 0, nOps: 0 };

        const node = (id, label, col, color) => {
            if (!nodes.has(id)) {
                const def = NODES[id] || {};
                nodes.set(id, { id, label: label || def.label || id, col: col != null ? col : def.col, color: color || def.color || "#94A3B8", ic: def.ic || "i-wallet", ins: [], outs: [], sumIn: 0, sumOut: 0 });
            }
            return nodes.get(id);
        };
        const acc = cur => node("acc:" + cur, "Conta " + cur, 1, ACC_COLOR[cur] || "#A5B4FC");
        const link = (s, t, v, op, fx) => {
            if (!(v > EPS)) return;
            const key = s + ">" + t;
            let l = links.get(key);
            if (!l) { l = { key, s, t, v: 0, ops: [], fx: false, sn: null, tn: null }; links.set(key, l); }
            l.v += v;
            if (op) l.ops.push(op);
            if (fx) l.fx = true;
        };

        // 1) lançamentos concluídos, na moeda e no intervalo
        const ents = [];
        raw.forEach(tx => {
            if (!isDone(tx)) return;
            const v = Number(tx.amount_decimal) || 0;
            if (!v) return;
            const t = typeof parseTxDate === "function" ? parseTxDate(tx.created_at) : new Date(tx.created_at);
            if (isNaN(t) || (since && +t < since)) return;
            ents.push({ tx, v, t, cu: tx.currency || "AOA", gid: String(tx.transaction_id || tx.id) });
        });
        const groups = new Map();
        ents.forEach(e => { if (!groups.has(e.gid)) groups.set(e.gid, []); groups.get(e.gid).push(e); });

        // 2) cada transação vira faixas
        groups.forEach(g => {
            const outs = g.filter(e => e.v < 0), ins = g.filter(e => e.v > 0);
            const mk = (e, kind, extra) => Object.assign({ id: String(e.tx.id), t: e.t, native: Math.abs(e.v), cur: e.cu, tx: e.tx, kind }, extra || {});

            if (outs.length === 1 && ins.length === 1) {
                // Dinheiro que passou de uma conta sua para outra (mesma moeda ou com câmbio)
                const d = outs[0], k = ins[0];
                const dv = conv(-d.v, d.cu), kv = conv(k.v, k.cu);
                if ((d.cu !== c && !dv) || (k.cu !== c && !kv)) { st.skipped++; return; }
                const fx = d.cu !== k.cu;
                let fee = feeOf(d.tx);
                if (!fee && !fx) fee = Math.max(0, -d.v - k.v);
                const feeV = fee ? conv(fee, d.cu) : 0;
                const to = fx ? { amount: k.v, cur: k.cu } : null;
                link(acc(d.cu).id, "out:own", Math.max(0, dv - feeV), mk(d, "out:own", { v: Math.max(0, dv - feeV), fxTo: to }), fx);
                if (feeV) link(acc(d.cu).id, "out:fee", feeV, mk(d, "out:fee", { v: feeV, native: fee }), false);
                link("in:own", acc(k.cu).id, kv, mk(k, "in:own", { v: kv, fxFrom: fx ? { amount: -d.v, cur: d.cu } : null }), fx);
                node("out:own"); node("in:own");
                if (fx) st.fxCount++;
                st.nOps++;
                return;
            }

            g.forEach(e => {
                const a = acc(e.cu);
                const val = conv(Math.abs(e.v), e.cu);
                if (e.cu !== c && !val) { st.skipped++; return; }
                st.nOps++;
                if (e.v > 0) {
                    const src = inNode(e.tx);
                    node(src.id, src.label, 0, src.id.startsWith("in:dep:") ? DEP_COLOR : null);
                    link(src.id, a.id, val, mk(e, src.id, { v: val }), false);
                } else {
                    const dest = outNode(e.tx);
                    const fee = isTransfer(e.tx) ? Math.min(feeOf(e.tx), -e.v) : 0;
                    const feeV = fee ? conv(fee, e.cu) : 0;
                    const fx = dest === "out:fx";
                    node(dest);
                    link(a.id, dest, Math.max(0, val - feeV), mk(e, dest, { v: Math.max(0, val - feeV), fxTo: fx && e.tx.transfer ? { amount: e.tx.transfer.dest_amount_decimal, cur: e.tx.transfer.dest_currency } : null }), fx);
                    if (feeV) { node("out:fee"); link(a.id, "out:fee", feeV, mk(e, "out:fee", { v: feeV, native: fee }), false); }
                    if (fx) st.fxCount++;
                }
            });
        });

        // 3) cada conta fecha as contas: sobra → «Ficou na conta» · falta → «Saldo anterior»
        [...nodes.values()].filter(n => n.col === 1).forEach(n => {
            let i = 0, o = 0;
            links.forEach(l => { if (l.t === n.id) i += l.v; if (l.s === n.id) o += l.v; });
            if (i - o > EPS) { node("out:keep"); link(n.id, "out:keep", i - o, null, false); }
            else if (o - i > EPS) { node("in:prior"); link("in:prior", n.id, o - i, null, false); }
        });

        // 4) ligações aos blocos e totais
        const L = [...links.values()].filter(l => l.v > EPS);
        L.forEach(l => {
            l.sn = nodes.get(l.s); l.tn = nodes.get(l.t);
            l.sn.outs.push(l); l.sn.sumOut += l.v;
            l.tn.ins.push(l); l.tn.sumIn += l.v;
            l.ops.sort((a, b) => b.t - a.t);
        });
        const N = [...nodes.values()].filter(n => n.ins.length || n.outs.length);
        N.forEach(n => { n.value = n.col === 0 ? n.sumOut : n.sumIn; });
        const sum = f => L.filter(f).reduce((a, l) => a + l.v, 0);
        const total = N.filter(n => n.col === 0).reduce((a, n) => a + n.value, 0);
        const out = {
            c, nodes: N, links: L, byId: new Map(N.map(n => [n.id, n])), total, skipped: st.skipped, fxCount: st.fxCount, nOps: st.nOps,
            income: sum(l => l.s.startsWith("in:") && l.s !== "in:own" && l.s !== "in:prior"),
            spent: sum(l => l.t.startsWith("out:") && l.t !== "out:own" && l.t !== "out:keep"),
            moved: sum(l => l.s === "in:own"),
            fees: sum(l => l.t === "out:fee"),
            saved: sum(l => l.t === "out:sav"),
            kept: sum(l => l.t === "out:keep"),
            empty: !L.length
        };
        return out;
    }

    /* ------------------------------ disposição ------------------------------ */

    /** Posições dos blocos e das faixas para uma largura w. Não toca no DOM. */
    function layout(model, w) {
        const narrow = w < 520;
        const nw = narrow ? 10 : 14, labelW = narrow ? 94 : 152;
        const xs = [labelW, Math.round((w - nw) / 2), w - labelW - nw];
        const slotMin = [narrow ? 30 : 32, 14, narrow ? 30 : 32];
        const gap = [narrow ? 8 : 10, narrow ? 34 : 38, narrow ? 8 : 10];
        const top1 = 18, padT = 10, padB = 10;
        const cols = [[], [], []];
        model.nodes.forEach(n => cols[n.col].push(n));

        cols[1].sort((a, b) => b.value - a.value || ACC_ORDER.indexOf(a.label.slice(6)) - ACC_ORDER.indexOf(b.label.slice(6)));
        cols[1].forEach((n, i) => { n.rank = i; });
        const bary = (n, ls, other) => {
            let s = 0, t = 0;
            ls.forEach(l => { s += other(l).rank * l.v; t += l.v; });
            return t ? s / t : 0;
        };
        cols[0].forEach(n => { n.bary = bary(n, n.outs, l => l.tn); });
        cols[2].forEach(n => { n.bary = bary(n, n.ins, l => l.sn); });
        [0, 2].forEach(ci => cols[ci].sort((a, b) => a.bary - b.bary || b.value - a.value));

        const need = ci => cols[ci].length * slotMin[ci] + gap[ci] * Math.max(0, cols[ci].length - 1) + (ci === 1 ? top1 : 0);
        const h = Math.max(narrow ? 380 : 360, Math.ceil(Math.max(need(0), need(1), need(2)) + padT + padB + 70));
        const innerH = h - padT - padB;
        const used = (ci, k) => cols[ci].reduce((a, n) => a + Math.max(n.value * k, slotMin[ci]), 0) + gap[ci] * Math.max(0, cols[ci].length - 1) + (ci === 1 ? top1 : 0);

        let lo = 0, hi = innerH / (model.total || 1);
        for (let i = 0; i < 32; i++) {
            const mid = (lo + hi) / 2;
            if ([0, 1, 2].every(ci => used(ci, mid) <= innerH)) lo = mid; else hi = mid;
        }
        const k = lo;

        cols.forEach((col, ci) => {
            let y = padT + (innerH - used(ci, k)) / 2 + (ci === 1 ? top1 : 0);
            col.forEach(n => {
                const slot = Math.max(n.value * k, slotMin[ci]);
                n.h = Math.max(n.value * k, 4);
                n.y = y + (slot - n.h) / 2;
                n.x = xs[ci]; n.w = nw;
                y += slot + gap[ci];
            });
        });

        // Posição das faixas dentro de cada bloco (ordenadas pelo outro extremo, para cruzar menos)
        const mid = n => n.y + n.h / 2;
        model.nodes.forEach(n => {
            n.outs.sort((a, b) => mid(a.tn) - mid(b.tn) || b.v - a.v);
            n.ins.sort((a, b) => mid(a.sn) - mid(b.sn) || b.v - a.v);
            let o = 0;
            n.outs.forEach(l => { l.sh = n.sumOut > 0 ? Math.max(1, (l.v / n.sumOut) * n.h) : 0; l.sy = n.y + o; o += (l.v / n.sumOut) * n.h; });
            let i = 0;
            n.ins.forEach(l => { l.th = n.sumIn > 0 ? Math.max(1, (l.v / n.sumIn) * n.h) : 0; l.ty = n.y + i; i += (l.v / n.sumIn) * n.h; });
        });
        model.links.forEach(l => {
            const x0 = l.sn.x + l.sn.w, x1 = l.tn.x, xm = (x0 + x1) / 2;
            l.x0 = x0; l.x1 = x1;
            l.d = `M${r1(x0)} ${r1(l.sy)}C${r1(xm)} ${r1(l.sy)} ${r1(xm)} ${r1(l.ty)} ${r1(x1)} ${r1(l.ty)}`
                + `V${r1(l.ty + l.th)}C${r1(xm)} ${r1(l.ty + l.th)} ${r1(xm)} ${r1(l.sy + l.sh)} ${r1(x0)} ${r1(l.sy + l.sh)}Z`;
        });
        return { w, h, k, narrow, nw, xs };
    }

    /* ------------------------------ desenho ------------------------------ */

    const linkLabel = l => `${l.sn.label} → ${l.tn.label}`;
    const nodeFlow = n => (n.col === 0 ? n.sumOut : n.sumIn);

    function svgMarkup(model, g, animate) {
        const S = sh(), c = model.c;
        const defs = model.links.map((l, i) =>
            `<linearGradient id="afg${i}" gradientUnits="userSpaceOnUse" x1="${r1(l.x0)}" x2="${r1(l.x1)}" y1="0" y2="0"><stop offset="0" stop-color="${l.sn.color}"/><stop offset="1" stop-color="${l.tn.color}"/></linearGradient>`).join("");
        const lk = model.links.map((l, i) =>
            `<path class="af-link${l.fx ? " fx" : ""}" data-i="${i}" d="${l.d}" fill="url(#afg${i})" style="--d:${Math.min(i, 24) * 30}ms" tabindex="0" role="button" aria-label="${esc(linkLabel(l))}: ${esc(S.hidden() ? "valor oculto" : S.money(l.v, c))}${l.fx ? ", com câmbio" : ""}"/>`).join("");
        const maxName = g.narrow ? 14 : 24;
        const bars = model.nodes.map(n =>
            `<g class="af-node" data-id="${esc(n.id)}" tabindex="0" role="button" aria-label="${esc(n.label)}: ${esc(S.hidden() ? "valor oculto" : S.money(n.value, c))}, ${pct(n.value, model.total)}% do total">`
            + `<rect class="af-node-hit" x="${n.x - (n.col === 1 ? 6 : 0)}" y="${r1(n.y - 4)}" width="${n.w + (n.col === 1 ? 12 : 0)}" height="${r1(n.h + 8)}"/>`
            + `<rect class="af-bar" x="${n.x}" y="${r1(n.y)}" width="${n.w}" height="${r1(n.h)}" rx="${g.narrow ? 3 : 4}" fill="${n.color}"/></g>`).join("");
        // Os rótulos ficam numa camada própria, por cima de blocos e faixas (nunca ficam tapados)
        const lbls = model.nodes.map(n => {
            const cx = n.x + n.w / 2, cy = n.y + n.h / 2;
            const nm = g.narrow ? (SHORT[n.id] || n.label) : n.label;
            const d = esc(n.id);
            if (n.col === 0) return `<text class="af-lbl" data-id="${d}" x="${n.x - 8}" y="${r1(cy - 2)}" text-anchor="end"><tspan class="af-nm">${esc(trunc(nm, maxName))}</tspan><tspan class="af-vl" x="${n.x - 8}" dy="13">${esc(S.compactMoney(n.value, c))}</tspan></text>`;
            if (n.col === 2) return `<text class="af-lbl" data-id="${d}" x="${n.x + n.w + 8}" y="${r1(cy - 2)}" text-anchor="start"><tspan class="af-nm">${esc(trunc(nm, maxName))}</tspan><tspan class="af-vl" x="${n.x + n.w + 8}" dy="13">${esc(S.compactMoney(n.value, c))}</tspan></text>`;
            const accName = g.narrow ? n.label.slice(6) : n.label;   // «AOA» no telemóvel, «Conta AOA» nos ecrãs largos
            return `<text class="af-lbl af-lbl--acc" data-id="${d}" x="${r1(cx)}" y="${r1(n.y - 7)}" text-anchor="middle"><tspan class="af-nm">${esc(accName)}</tspan><tspan class="af-vl"> · ${esc(S.compactMoney(n.value, c))}</tspan></text>`;
        }).join("");
        return `<svg class="cc-svg af-svg" id="afSvg" viewBox="0 0 ${g.w} ${g.h}" width="${g.w}" height="${g.h}" role="group" aria-label="Diagrama de Sankey do fluxo entre contas">`
            + `<defs>${defs}</defs><g class="af-links">${lk}</g><g class="af-nodes">${bars}</g><g class="af-lbls">${lbls}</g></svg>`;
    }

    function drawChrome(model) {
        const S = sh(), c = model.c, e = model.empty;
        const pill = el("ccCurrency"); if (pill) pill.textContent = c;
        el("ccSubtitle").textContent = e ? (state.token ? "Ainda não há movimentos neste intervalo" : "Inicie sessão para ver o fluxo do seu dinheiro") : "De onde vem e para onde vai o seu dinheiro";
        el("afRange").textContent = PERIOD_TXT[A.period];
        document.querySelectorAll("#afCurr .cc-chip").forEach(b => {
            const on = b.dataset.cur === c;
            b.classList.toggle("active", on);
            b.setAttribute("aria-checked", String(on));
        });
        document.querySelectorAll("#afPeriods .cc-chip").forEach(b => {
            const on = b.dataset.p === A.period;
            b.classList.toggle("active", on);
            b.setAttribute("aria-pressed", String(on));
        });
        const dash = "—", nb = "\u00a0";
        const set = (id, v, title) => { const n = el(id); n.textContent = e ? dash : v; n.title = e ? "" : (title || ""); };
        set("afStatIn", S.compactMoney(model.income, c), S.money(model.income, c));
        el("afStatInNote").textContent = e ? nb : (model.total ? `${model.nodes.filter(n => n.col === 0 && n.id !== "in:own" && n.id !== "in:prior").length} origens` : nb);
        set("afStatOut", S.compactMoney(model.spent, c), S.money(model.spent, c));
        el("afStatOutNote").textContent = e ? nb : (S.hidden() ? "valores ocultos" : (model.saved > EPS ? `${S.compactMoney(model.saved, c)} em poupanças` : "sem poupanças"));
        set("afStatOwn", S.compactMoney(model.moved, c), S.money(model.moved, c));
        el("afStatOwnNote").textContent = e ? nb : (model.fxCount ? `${model.fxCount} com câmbio` : "sem conversões");
        set("afStatFee", S.compactMoney(model.fees, c), S.money(model.fees, c));
        el("afStatFeeNote").textContent = e ? nb : (model.spent > 0 ? `${String(Math.round((model.fees / model.spent) * 1000) / 10).replace(".", ",")}% do que saiu` : nb);
        const note = el("afNote");
        if (note) {
            note.hidden = !model.skipped;
            note.textContent = model.skipped ? `${model.skipped} ${model.skipped === 1 ? "operação ficou" : "operações ficaram"} de fora por não haver taxa de câmbio para ${c}.` : "";
        }
    }

    function drawChart(model, animate) {
        const root = el("afChart");
        root.classList.toggle("no-anim", !animate);
        if (model.empty) {
            root.innerHTML = `<div class="cc-empty">${state.token ? "Ainda não há movimentos concluídos neste intervalo." : "Inicie sessão para ver como o dinheiro circula entre as suas contas."}</div>`;
            A.geom = null;
            return;
        }
        const w = Math.max(280, Math.floor(root.clientWidth));
        A.width = w;
        const g = layout(model, w);
        A.geom = g;
        root.innerHTML = svgMarkup(model, g, animate) + `<div class="cc-tip af-tip" id="afTip" role="status"></div>`;
        applySel();
    }

    /** Realça a seleção (bloco ou faixa) e esbate o resto. Não redesenha. */
    function applySel() {
        const svg = el("afSvg"), m = A.model;
        if (!svg || !m) return;
        const on = new Set(), onNodes = new Set();
        if (A.sel) {
            if (A.sel.t === "n") {
                const n = m.byId.get(A.sel.id);
                if (n) { onNodes.add(n.id); n.ins.concat(n.outs).forEach(l => { on.add(l); onNodes.add(l.s); onNodes.add(l.t); }); }
            } else {
                const l = m.links.find(x => x.key === A.sel.id);
                if (l) { on.add(l); onNodes.add(l.s); onNodes.add(l.t); }
            }
        }
        svg.classList.toggle("has-sel", !!A.sel && on.size > 0);
        svg.querySelectorAll(".af-link").forEach(p => p.classList.toggle("on", on.has(m.links[+p.dataset.i])));
        svg.querySelectorAll(".af-node").forEach(g => {
            g.classList.toggle("on", onNodes.has(g.dataset.id));
            g.classList.toggle("sel", !!A.sel && A.sel.t === "n" && A.sel.id === g.dataset.id);
        });
        const dim = svg.classList.contains("has-sel");
        svg.querySelectorAll(".af-lbl").forEach(t => t.classList.toggle("dim", dim && !onNodes.has(t.dataset.id)));
    }

    const whenTxt = t => { const S = sh(); return `${t.getDate()} ${S.MONTHS[t.getMonth()]} · ${hm(t)}`; };

    function opRow(o, c) {
        const S = sh();
        const inflow = o.kind.startsWith("in:");
        const def = NODES[o.kind];
        const label = def ? def.label : (o.tx.counterparty && o.tx.counterparty.name) || "Depósito";
        let fx = "";
        if (o.fxTo) fx = `<small class="af-fx">→ ${S.money(o.fxTo.amount, o.fxTo.cur)}</small>`;
        else if (o.fxFrom) fx = `<small class="af-fx">← ${S.money(o.fxFrom.amount, o.fxFrom.cur)}</small>`;
        return `<div class="cs-op" role="button" tabindex="0" data-id="${esc(o.id)}">
            <span class="cs-op-ic ${inflow ? "refund" : ""}"><svg aria-hidden="true"><use href="#${OP_ICON[o.kind] || (inflow ? "i-down" : "i-up")}"/></svg></span>
            <span class="cs-op-main"><b>${esc(o.tx.description || label)}</b><small>${esc(label)} · ${whenTxt(o.t)}</small></span>
            <span class="cs-op-side"><strong class="${inflow ? "in" : ""}">${inflow ? "+" : "−"}${S.money(o.native, o.cur)}</strong>${fx}</span>
        </div>`;
    }

    function connRow(l, side, total, text) {
        const S = sh(), other = side === "in" ? l.sn : l.tn;
        return `<button type="button" class="af-conn" data-l="${esc(l.key)}" style="--c:${other.color};--w:${Math.max(3, pct(l.v, total))}%">
            <i class="af-conn-dot"></i>
            <span class="af-conn-main"><b>${esc(text || other.label)}${l.fx ? ' <em class="af-fxtag">câmbio</em>' : ""}</b><span class="af-conn-bar"><i></i></span></span>
            <span class="af-conn-val"><strong>${S.money(l.v, A.model.c)}</strong><small>${pct(l.v, total)}%</small></span>
        </button>`;
    }

    function drawDetail(model) {
        const S = sh(), c = model.c;
        const title = el("afDetTitle"), sub = el("afDetSub"), badge = el("afDetBadge"), conns = el("afConns"), ops = el("afOps");
        const ids = ["afDetTotal", "afDetCount", "afDetShare", "afDetAvg"];
        const clear = () => { ids.forEach(i => { el(i).textContent = "—"; }); conns.innerHTML = ""; ops.innerHTML = ""; badge.hidden = true; };
        if (model.empty) {
            title.textContent = "Sem fluxo para mostrar";
            sub.textContent = "Quando houver movimentos, toque num bloco ou numa faixa para ver o detalhe";
            clear();
            return;
        }
        const set = (a, b, d, e) => { [a, b, d, e].forEach((v, i) => { el(ids[i]).textContent = v; }); };

        if (!A.sel) {
            title.textContent = "Visão geral";
            sub.textContent = "Toque num bloco ou numa faixa para ver o detalhe";
            set(S.money(model.total, c), String(model.nOps), "100%", S.money(model.nOps ? model.total / model.nOps : 0, c));
            badge.hidden = true;
            const top = [...model.links].sort((a, b) => b.v - a.v).slice(0, 5);
            conns.innerHTML = `<h6 class="af-h">Maiores fluxos</h6>` + top.map(l => connRow(l, "out", model.total, linkLabel(l))).join("");
            ops.innerHTML = "";
            return;
        }

        if (A.sel.t === "n") {
            const n = model.byId.get(A.sel.id);
            title.textContent = n.label;
            const kinds = n.col === 0 ? "Origem do dinheiro" : n.col === 1 ? "Conta" : "Destino do dinheiro";
            sub.textContent = n.id === "in:own" || n.id === "out:own" ? `${kinds} · transferências e conversões entre as suas contas` : kinds;
            const all = new Map();
            n.ins.concat(n.outs).forEach(l => l.ops.forEach(o => { if (!all.has(o.id)) all.set(o.id, o); }));
            const list = [...all.values()].sort((a, b) => b.t - a.t);
            const nOps = list.length;
            set(S.money(n.value, c), nOps ? String(nOps) : "—", `${pct(n.value, model.total)}%`, nOps ? S.money(n.value / nOps, c) : "—");
            badge.hidden = false; badge.className = "bc-delta"; badge.textContent = `${pct(n.value, model.total)}% do total`;
            conns.innerHTML = (n.ins.length ? `<h6 class="af-h">De onde veio</h6>` + n.ins.map(l => connRow(l, "in", n.sumIn)).join("") : "")
                + (n.outs.length ? `<h6 class="af-h">Para onde foi</h6>` + n.outs.map(l => connRow(l, "out", n.sumOut)).join("") : "");
            drawOps(list);
        } else {
            const l = model.links.find(x => x.key === A.sel.id);
            if (!l) { A.sel = null; drawDetail(model); return; }
            title.textContent = linkLabel(l);
            sub.textContent = l.fx ? "Inclui conversão cambial" : "Fluxo entre estes dois blocos";
            const n = l.ops.length;
            set(S.money(l.v, c), n ? String(n) : "—", `${pct(l.v, model.total)}%`, n ? S.money(l.v / n, c) : "—");
            badge.hidden = false; badge.className = "bc-delta"; badge.textContent = `${pct(l.v, model.total)}% do total`;
            conns.innerHTML = "";
            drawOps(l.ops);
        }

        function drawOps(list) {
            if (!list.length) { ops.innerHTML = `<div class="cs-empty af-more-note">Este valor é a diferença entre o que entrou e o que saiu da conta no intervalo.</div>`; return; }
            ops.innerHTML = `<h6 class="af-h">Operações</h6>` + list.slice(0, 5).map(o => opRow(o, c)).join("")
                + (list.length > 5 ? `<div class="cs-empty af-more-note">+ ${list.length - 5} operações anteriores</div>` : "");
            if (typeof statementTxById !== "undefined") list.slice(0, 5).forEach(o => statementTxById.set(o.id, o.tx));
        }
    }

    /* ------------------------------ Copilot ------------------------------ */

    function insights(row, chips, setTitle) {
        setTitle("Análise do fluxo entre as suas contas");
        const m = A.model;
        if (!m || m.empty) {
            row("info", "#i-spark", "Sem fluxo para analisar", state.token ? "Neste intervalo não há movimentos concluídos para mostrar como o dinheiro circula." : "Inicie sessão para o Copilot analisar o caminho do seu dinheiro.");
            chips.push("Como organizar o dinheiro entre as minhas contas?");
            return;
        }
        const S = sh(), b = v => `<b>${S.money(v, m.c)}</b>`;
        const srcs = m.nodes.filter(n => n.col === 0 && n.id !== "in:prior" && n.id !== "in:own").sort((a, z) => z.value - a.value);
        const dests = m.nodes.filter(n => n.col === 2 && n.id !== "out:keep" && n.id !== "out:own").sort((a, z) => z.value - a.value);
        const range = PERIOD_TXT[A.period].toLowerCase();
        if (srcs[0]) row("tip", "#i-down", "Principal origem", `${esc(srcs[0].label)} trouxe ${b(srcs[0].value)}${m.income > 0 ? `: ${pct(srcs[0].value, m.income)}% de tudo o que entrou` : ""} (${range}).`);
        if (dests[0]) row("info", "#i-up", "Principal destino", `${esc(dests[0].label)} recebeu ${b(dests[0].value)}${m.spent > 0 ? `: ${pct(dests[0].value, m.spent)}% de tudo o que saiu` : ""}.`);
        if (m.income > 0) {
            const keep = m.kept + m.saved, rate = Math.round((keep / m.income) * 100);
            row(rate >= 20 ? "good" : "tip", "#i-target", "O que ficou de parte", S.hidden() ? "Valores ocultos." : `Entre saldo que ficou nas contas e poupanças, guardou cerca de <b>${rate}%</b> do que recebeu.`);
        }
        if (m.fxCount) row("info", "#i-swap", "Conversões cambiais", `Fez ${m.fxCount} ${m.fxCount === 1 ? "operação com câmbio" : "operações com câmbio"} neste intervalo. As faixas tracejadas mostram onde.`);
        if (m.spent > 0 && m.fees / m.spent >= 0.02) row("warn", "#i-receipt", "Taxas a pesar", `Pagou ${b(m.fees)} em taxas e comissões: ${String(Math.round((m.fees / m.spent) * 1000) / 10).replace(".", ",")}% do que saiu.`);
        chips.push("Para onde vai o meu dinheiro?", "Como reduzir as taxas que pago?", "Vale a pena converter moeda?");
    }

    /* ------------------------------ ciclo de vida ------------------------------ */

    function context() {
        const days = PERIODS[A.period];
        return {
            cur: cur(), since: days ? Date.now() - days * DAY : 0,
            convert: (v, from, to) => (typeof convertMoney === "function" ? convertMoney(v, from, to) : (from === to ? v : 0))
        };
    }
    function rawTxs() { return (typeof state !== "undefined" && Array.isArray(state.transactions)) ? state.transactions : []; }

    function signature() {
        const raw = rawTxs();
        return [cur(), state.token ? 1 : 0, raw.length, raw[0] ? raw[0].id : "", A.period, A.sel ? A.sel.t + A.sel.id : "", sh().hidden() ? 1 : 0].join("|");
    }
    function visible() {
        const v = el("view-card-chart"), p = el("bcPanelAccounts");
        return !!(v && p && v.classList.contains("active") && !p.hidden);
    }

    function render(opts) {
        if (!visible()) return;
        bind();
        const model = buildModel(rawTxs(), context());
        A.model = model;
        if (A.sel && (A.sel.t === "n" ? !model.byId.has(A.sel.id) : !model.links.some(l => l.key === A.sel.id))) A.sel = null;
        drawChrome(model);
        drawChart(model, !(opts && opts.noAnim));
        drawDetail(model);
        A.sig = signature();
        if (typeof window.refreshCardCopilot === "function") window.refreshCardCopilot();
    }
    function refresh() { if (visible() && signature() !== A.sig) render({ noAnim: true }); }

    function select(sel, scroll) {
        const same = A.sel && sel && A.sel.t === sel.t && A.sel.id === sel.id;
        A.sel = same ? null : sel;
        applySel();
        drawDetail(A.model);
        A.sig = signature();
        if (typeof window.refreshCardCopilot === "function") window.refreshCardCopilot();
    }

    function showTip(ev, html) {
        const tip = el("afTip"), root = el("afChart");
        if (!tip || !root) return;
        tip.innerHTML = html;
        const r = root.getBoundingClientRect(), tw = tip.offsetWidth || 190, th = tip.offsetHeight || 70;
        let x = ev.clientX - r.left + 14, y = ev.clientY - r.top - th - 10;
        if (x + tw > r.width - 2) x = ev.clientX - r.left - tw - 14;
        if (y < 2) y = ev.clientY - r.top + 16;
        tip.style.left = Math.max(2, x) + "px";
        tip.style.top = y + "px";
        tip.classList.add("on");
    }
    function hideTip() { const t = el("afTip"); if (t) t.classList.remove("on"); }

    function tipFor(target) {
        const m = A.model, S = sh();
        if (!m) return "";
        const nd = target.closest(".af-node");
        if (nd) {
            const n = m.byId.get(nd.dataset.id);
            return n ? `<b>${esc(n.label)}</b><strong>${S.money(n.value, m.c)}</strong><span class="bc-tip-d">${pct(n.value, m.total)}% do total</span>` : "";
        }
        const lp = target.closest(".af-link");
        if (lp) {
            const l = m.links[+lp.dataset.i];
            return l ? `<b>${esc(linkLabel(l))}</b><strong>${S.money(l.v, m.c)}</strong><span class="bc-tip-d">${pct(l.v, m.total)}% do total${l.fx ? " · com câmbio" : ""}</span>` : "";
        }
        return "";
    }

    function bind() {
        if (A.bound) return;
        A.bound = true;
        el("afCurr").addEventListener("click", ev => {
            const b = ev.target.closest(".cc-chip");
            if (!b || b.dataset.cur === cur()) return;
            A.cur = b.dataset.cur; A.sel = null; render();
        });
        el("afPeriods").addEventListener("click", ev => {
            const b = ev.target.closest(".cc-chip");
            if (!b || b.dataset.p === A.period) return;
            A.period = b.dataset.p; A.sel = null;
            try { localStorage.setItem(PERIOD_KEY, A.period); } catch (e) { /* ignorar */ }
            render();
        });

        const chart = el("afChart");
        const pick = target => {
            const m = A.model;
            if (!m) return null;
            const nd = target.closest(".af-node");
            if (nd) return { t: "n", id: nd.dataset.id };
            const lp = target.closest(".af-link");
            if (lp && m.links[+lp.dataset.i]) return { t: "l", id: m.links[+lp.dataset.i].key };
            return null;
        };
        chart.addEventListener("click", ev => {
            const s = pick(ev.target);
            if (s) select(s, true);
            else if (A.sel && ev.target.closest("#afSvg")) select(A.sel, false);   // tocar no fundo limpa a seleção
            hideTip();
        });
        chart.addEventListener("keydown", ev => {
            if (ev.key !== "Enter" && ev.key !== " ") return;
            const s = pick(ev.target);
            if (s) { ev.preventDefault(); select(s, true); }
        });
        chart.addEventListener("pointermove", ev => {
            if (ev.pointerType !== "mouse") return;
            const html = tipFor(ev.target);
            if (html) showTip(ev, html); else hideTip();
        });
        chart.addEventListener("pointerleave", hideTip);
        chart.addEventListener("focusin", ev => {
            const html = tipFor(ev.target);
            if (!html) return;
            const r = ev.target.getBoundingClientRect();
            showTip({ clientX: r.left + r.width / 2, clientY: r.top }, html);
        });
        chart.addEventListener("focusout", hideTip);

        el("afConns").addEventListener("click", ev => {
            const b = ev.target.closest(".af-conn[data-l]");
            if (b) select({ t: "l", id: b.dataset.l }, false);
        });
        const open = ev => {
            const row = ev.target.closest(".cs-op[data-id]");
            if (!row || (ev.type === "keydown" && ev.key !== "Enter" && ev.key !== " ")) return;
            ev.preventDefault();
            if (typeof openTxDetail === "function") openTxDetail(row.dataset.id);
        };
        el("afOps").addEventListener("click", open);
        el("afOps").addEventListener("keydown", open);

        // Mudança de largura redesenha sem animação
        if (typeof ResizeObserver !== "undefined") {
            let raf = 0;
            new ResizeObserver(() => {
                cancelAnimationFrame(raf);
                raf = requestAnimationFrame(() => {
                    if (visible() && chart.clientWidth && Math.floor(chart.clientWidth) !== A.width && A.model && !A.model.empty) render({ noAnim: true });
                });
            }).observe(chart);
        }
    }

    window.renderAccountsFlow = render;
    window.refreshAccountsFlow = refresh;
    window.accountsFlowInsights = insights;
    window.accountsFlowBuild = buildModel;
    window.accountsFlowLayout = layout;
})();
