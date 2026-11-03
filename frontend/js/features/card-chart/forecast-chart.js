/**
 * Gráficos da conta — 6. Previsão do saldo
 *
 * Funcionalidades:
 *   • Gráfico de linhas contínuo combinando valores históricos reais e projetados futuros.
 *   • Projeção baseada no saldo atual, despesas e receitas estimadas (lookback de 90 dias)
 *     e compromissos agendados de poupança/pagamentos.
 *   • Identifica claramente as previsões como estimativas (badges, avisos, notas legais).
 *   • Antecipa visualmente períodos em que o saldo poderá ficar reduzido (zona de alerta e avisos).
 *   • Interativo: cursor/crosshair, tooltip com detalhe de data, valor e tipo (histórico vs. projeção).
 *   • Suporte a horizontes de 30, 60, 90 e 180 dias e alternância de moeda (AOA, EUR, USD).
 *   • Recomendações e ritmo ideal de gastos assistido pela IA.
 */
(function () {
    "use strict";

    const PRESETS = { "7d": 7, "30d": 30, "90d": 90, "6m": 182, "1a": 365 };
    const STORE_PERIOD_KEY = "bankao_bc_period";
    const STORE_HORIZON_KEY = "bankao_fc_horizon";
    const STORE_START_KEY = "bankao_fc_start";
    const DAY = 86400000;
    const MONTHS_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

    const F = {
        cur: null,
        period: (function () {
            try {
                const p = localStorage.getItem(STORE_PERIOD_KEY);
                if (p && p in PRESETS) return p;
            } catch (e) { /* ignorar */ }
            return "90d";
        })(),
        days: (function () {
            try {
                const p = localStorage.getItem(STORE_PERIOD_KEY);
                if (p && p in PRESETS) return PRESETS[p];
                const h = Number(localStorage.getItem(STORE_HORIZON_KEY));
                if (h && h > 0) return h;
            } catch (e) { /* ignorar */ }
            return 90;
        })(),
        start: (function () {
            try {
                const v = Number(localStorage.getItem(STORE_START_KEY));
                if (isFinite(v) && v <= 0 && v >= -29 && localStorage.getItem(STORE_START_KEY) !== null) return Math.round(v);
            } catch (e) { /* ignorar */ }
            return -29;
        })(),
        data: null,
        model: null,
        sig: "",
        bound: false,
        paceKey: "",
        clearHover: null
    };

    const el = id => document.getElementById(id);
    const sh = () => window.ccShared;
    const esc = s => (typeof escapeHtml === "function" ? escapeHtml(String(s)) : String(s).replace(/[&<>"']/g, c => "&#" + c.charCodeAt(0) + ";"));
    const cur = () => F.cur || (F.cur = (typeof state !== "undefined" && state.prefCurrency) || "AOA");
    const p2 = n => String(n).padStart(2, "0");

    function formatDateShort(isoDate) {
        if (!isoDate) return "";
        const parts = String(isoDate).slice(0, 10).split("-");
        if (parts.length === 3) {
            const m = parseInt(parts[1], 10) - 1;
            return `${parseInt(parts[2], 10)} ${MONTHS_PT[m] || parts[1]}`;
        }
        return isoDate;
    }

    function formatDateFull(isoDate) {
        if (!isoDate) return "";
        const parts = String(isoDate).slice(0, 10).split("-");
        if (parts.length === 3) {
            const m = parseInt(parts[1], 10) - 1;
            return `${parseInt(parts[2], 10)} de ${MONTHS_PT[m] || parts[1]} de ${parts[0]}`;
        }
        return isoDate;
    }

    /* ------------------------------ dados ------------------------------ */

    function localForecastData(targetCur, projectionDays) {
        const S = sh();
        const rawTxs = (typeof state !== "undefined" && Array.isArray(state.transactions)) ? state.transactions : [];
        const rawAccs = (typeof state !== "undefined" && Array.isArray(state.accounts)) ? state.accounts : [];
        const matchingAcc = rawAccs.find(a => a.currency === targetCur);

        let currentBal = matchingAcc ? (Number(matchingAcc.balance_decimal) || 0) : 0;
        const validTxs = rawTxs.filter(t => (t.currency || "AOA") === targetCur && !/fail|falh/i.test(String(t.status || "")));

        // Calcular histórico dos últimos 30 dias
        const now = Date.now();
        const start30 = now - 30 * DAY;
        const byDay = {};
        let net30 = 0;

        validTxs.forEach(t => {
            const d = parseTxDate(t.created_at);
            if (isNaN(d)) return;
            const ms = +d;
            if (ms >= start30 && ms <= now) {
                const k = d.toISOString().slice(0, 10);
                const amt = Number(t.amount_decimal) || 0;
                byDay[k] = (byDay[k] || 0) + amt;
                net30 += amt;
            }
        });

        // Reconstruir saldos diários
        let runBal = currentBal - net30;
        const balanceSeries = [];
        for (let i = 29; i >= 0; i--) {
            const d = new Date(now - i * DAY);
            const k = d.toISOString().slice(0, 10);
            runBal += (byDay[k] || 0);
            balanceSeries.push({ date: k, balance: Math.round(runBal) });
        }

        // Estimativa a partir dos últimos 90 dias
        const start90 = now - 90 * DAY;
        let inc90 = 0, exp90 = 0;
        validTxs.forEach(t => {
            const d = parseTxDate(t.created_at);
            if (isNaN(d)) return;
            const ms = +d;
            if (ms >= start90 && ms <= now) {
                const amt = Number(t.amount_decimal) || 0;
                if (amt > 0) inc90 += amt;
                else exp90 += -amt;
            }
        });

        const monthlyIncome = Math.round(inc90 * 30 / 90);
        const monthlyExpense = Math.round(exp90 * 30 / 90);

        // Metas de poupança agendadas
        const goals = (typeof state !== "undefined" && Array.isArray(state.savingsGoals)) ? state.savingsGoals : [];
        const scheduledSavings = goals.reduce((acc, g) => acc + (Number(g.monthly_minor ? g.monthly_minor / 100 : g.monthly_decimal) || 0), 0);

        const dailyNet = (monthlyIncome - monthlyExpense - scheduledSavings) / 30.0;
        const threshold = currentBal * 0.10;
        const points = [];
        const alerts = [];
        let curBal = currentBal;

        for (let day = 1; day <= projectionDays; day++) {
            curBal += dailyNet;
            const pDate = new Date(now + day * DAY).toISOString().slice(0, 10);
            const rBal = Math.round(curBal);
            points.push({ date: pDate, balance: rBal, projected: true });
            if (rBal < threshold || rBal < 0) {
                alerts.push({ date: pDate, balance: rBal });
            }
        }

        return {
            currency: targetCur,
            summary: { current_balance: currentBal },
            balance_series: balanceSeries,
            projection: {
                points: points,
                assumptions: {
                    monthly_income_estimate: monthlyIncome,
                    monthly_expense_estimate: monthlyExpense,
                    scheduled_savings_monthly: scheduledSavings,
                    lookback_days: 90,
                    projection_days: projectionDays
                },
                low_balance_alerts: alerts,
                is_estimate: true
            }
        };
    }

    async function loadForecastData() {
        const c = cur();
        const days = F.days;
        let data = null;

        if (typeof state !== "undefined" && state.token && typeof apiRequest === "function") {
            try {
                const q = new URLSearchParams({
                    range_days: "30",
                    granularity: "day",
                    period_unit: "month",
                    projection_days: String(days)
                });
                const acc = (state.accounts || []).find(a => a.currency === c);
                if (acc && acc.id) q.set("account_id", acc.id);

                data = await apiRequest("GET", "/api/accounts/analytics?" + q.toString());
            } catch (err) {
                console.warn("[ForecastChart] Erro ao carregar da API, a recorrer a dados locais:", err);
                data = null;
            }
        }

        if (!data || !data.projection || !data.balance_series) {
            data = localForecastData(c, days);
        }

        F.data = data;
        return data;
    }

    /* ------------------------------ desenho ------------------------------ */

    function buildModel(data) {
        const S = sh();
        const c = data.currency || cur();
        const hist = (data.balance_series || []).map(p => ({
            date: p.date,
            val: Number(p.balance),
            projected: false
        }));
        const proj = ((data.projection && data.projection.points) || []).map(p => ({
            date: p.date,
            val: Number(p.balance),
            projected: true
        }));
        const alerts = (data.projection && data.projection.low_balance_alerts) || [];
        const assumptions = (data.projection && data.projection.assumptions) || {};
        const combined = hist.concat(proj);

        const allVals = combined.map(p => p.val);
        let minVal = Math.min.apply(null, allVals.concat([0]));
        let maxVal = Math.max.apply(null, allVals);
        if (maxVal === minVal) { maxVal += 100; minVal -= 50; }

        return {
            currency: c,
            currentBalance: Number((data.summary && data.summary.current_balance) || 0),
            historical: hist,
            projected: proj,
            combined: combined,
            alerts: alerts,
            assumptions: assumptions,
            minVal: minVal,
            maxVal: maxVal,
            histLen: hist.length
        };
    }

    function renderStats(m) {
        const S = sh();
        const c = m.currency;
        const balEl = el("fcStatBalance");
        if (balEl) balEl.textContent = S.money(m.currentBalance, c);

        const inc = Number(m.assumptions.monthly_income_estimate || 0);
        const exp = Number(m.assumptions.monthly_expense_estimate || 0);
        const sav = Number(m.assumptions.scheduled_savings_monthly || 0);

        const incEl = el("fcStatIncome");
        if (incEl) incEl.textContent = "+" + S.compactMoney(inc, c);

        const expEl = el("fcStatExpense");
        if (expEl) expEl.textContent = "−" + S.compactMoney(exp, c);

        const savEl = el("fcStatSavings");
        if (savEl) savEl.textContent = S.compactMoney(sav, c);
    }

    /** Recorta o modelo à janela escolhida na barra de intervalo. */
    function windowView(m) {
        const si = Math.max(0, (m.histLen - 1) + F.start);
        const comb = m.combined.slice(si);
        const startDate = comb.length ? comb[0].date : null;
        const vals = comb.map(p => p.val);
        let minVal = Math.min.apply(null, vals.concat([0]));
        let maxVal = Math.max.apply(null, vals);
        if (!vals.length || maxVal === minVal) { maxVal = (vals.length ? maxVal : 0) + 100; minVal -= 50; }
        return Object.assign({}, m, {
            combined: comb,
            histLen: Math.max(0, m.histLen - si),
            minVal: minVal,
            maxVal: maxVal,
            alerts: m.alerts.filter(a => !startDate || a.date >= startDate)
        });
    }

    function renderSvgChart(m) {
        const root = el("fcFullChart");
        if (!root) return;
        m = windowView(m);

        const combined = m.combined;
        if (combined.length < 2) {
            root.innerHTML = `<div class="fc-empty">Sem histórico suficiente para gerar projeção. Efetue movimentos na conta para projetar.</div>`;
            return;
        }

        const panel = el("bcPanelForecast");
        const viewEl = el("view-card-chart");
        let w = root.clientWidth;
        if (!w && panel && panel.clientWidth) w = panel.clientWidth - 28;
        if (!w && viewEl && viewEl.clientWidth) w = viewEl.clientWidth - 36;
        if (!w) w = Math.min(window.innerWidth - 32, 900);
        w = Math.max(280, Math.floor(w));

        const chartW = w;
        const chartH = chartW < 520 ? 340 : chartW < 900 ? 380 : 430;
        const PAD = {
            t: 36,
            r: chartW < 520 ? 14 : 26,
            b: 44,
            l: chartW < 520 ? 46 : 64
        };
        const W = chartW - PAD.l - PAD.r;
        const H = chartH - PAD.t - PAD.b;

        const span = m.maxVal - m.minVal || 1;
        const xOf = i => PAD.l + (i / (combined.length - 1)) * W;
        const yOf = v => PAD.t + H - ((v - m.minVal) / span) * H;

        const coords = combined.map((p, i) => [xOf(i), yOf(p.val)]);
        const histCoords = coords.slice(0, m.histLen);
        const projCoords = coords.slice(Math.max(0, m.histLen - 1));

        // Caminhos SVG
        const pathD = pts => pts.map((pt, i) => `${i ? "L" : "M"}${pt[0].toFixed(1)},${pt[1].toFixed(1)}`).join(" ");
        const histPath = pathD(histCoords);
        const projPath = pathD(projCoords);

        // Preenchimento gradiente histórico
        const hFill = histCoords.length >= 2
            ? histPath + ` L${histCoords[histCoords.length - 1][0].toFixed(1)},${(PAD.t + H).toFixed(1)} L${PAD.l.toFixed(1)},${(PAD.t + H).toFixed(1)} Z`
            : "";

        // Linha do zero
        const zeroY = yOf(0);
        const zeroLine = (zeroY >= PAD.t && zeroY <= PAD.t + H)
            ? `<line x1="${PAD.l}" y1="${zeroY.toFixed(1)}" x2="${(PAD.l + W).toFixed(1)}" y2="${zeroY.toFixed(1)}" stroke="rgba(239,68,68,0.5)" stroke-width="1.5" stroke-dasharray="5 4"/>`
            : "";

        // Zonas de alerta de saldo reduzido (banda avermelhada)
        let alertBands = "";
        const alertSet = new Set(m.alerts.map(a => a.date));
        let firstAlertIdx = -1;
        for (let i = 0; i < combined.length; i++) {
            if (alertSet.has(combined[i].date)) { firstAlertIdx = i; break; }
        }
        if (firstAlertIdx >= 0) {
            const ax1 = xOf(firstAlertIdx);
            const ax2 = PAD.l + W;
            alertBands = `
                <rect x="${ax1.toFixed(1)}" y="${PAD.t}" width="${(ax2 - ax1).toFixed(1)}" height="${H}" fill="url(#alertBandGradFull)" rx="6"/>
                <text x="${(ax1 + 8).toFixed(1)}" y="${(PAD.t + 16).toFixed(1)}" fill="#EF4444" font-size="11" font-weight="700" letter-spacing="0.03em">ZONA DE SALDO REDUZIDO</text>
            `;
        }

        // Ponto de transição (Hoje)
        let junctionDot = "";
        let splitLine = "";
        if (m.histLen > 0 && m.histLen < combined.length) {
            const jx = coords[m.histLen - 1][0].toFixed(1);
            const jy = coords[m.histLen - 1][1].toFixed(1);
            junctionDot = `
                <circle cx="${jx}" cy="${jy}" r="6.5" fill="#38BDF8" stroke="#0F172A" stroke-width="3" class="fc-junction"/>
                <text x="${jx}" y="${PAD.t - 10}" text-anchor="middle" fill="#38BDF8" font-size="11.5" font-weight="800" letter-spacing="0.04em">HOJE</text>
            `;
            splitLine = `<line x1="${jx}" y1="${PAD.t}" x2="${jx}" y2="${(PAD.t + H).toFixed(1)}" stroke="rgba(56,189,248,0.4)" stroke-width="2" stroke-dasharray="4 4"/>`;
        }

        // Linhas de grelha e etiquetas do eixo Y (5 níveis)
        let yGridSvg = "";
        const S = sh();
        const yTicks = [
            m.minVal,
            m.minVal + span * 0.25,
            m.minVal + span * 0.5,
            m.minVal + span * 0.75,
            m.maxVal
        ];
        yTicks.forEach(val => {
            const y = yOf(val).toFixed(1);
            yGridSvg += `
                <line x1="${PAD.l}" y1="${y}" x2="${(PAD.l + W).toFixed(1)}" y2="${y}" stroke="rgba(255,255,255,0.07)" stroke-width="1"/>
                <text x="${PAD.l - 10}" y="${y}" text-anchor="end" dominant-baseline="middle" class="fc-axis-lbl">${esc(S.compactMoney(val, m.currency))}</text>
            `;
        });

        // Etiquetas do eixo X: igualmente espaçadas, sempre com a primeira e a última data
        let xLabelsSvg = "";
        const maxLabels = chartW < 420 ? 4 : chartW < 640 ? 5 : chartW < 900 ? 6 : 8;
        const nLabels = Math.max(2, Math.min(maxLabels, combined.length));
        const labelIdx = [];
        for (let k = 0; k < nLabels; k++) {
            const idx = Math.round((k * (combined.length - 1)) / (nLabels - 1));
            if (!labelIdx.length || idx !== labelIdx[labelIdx.length - 1]) labelIdx.push(idx);
        }
        labelIdx.forEach((i, k) => {
            const pt = combined[i];
            const cx = coords[i][0];
            const cls = pt.projected ? "fc-axis-lbl fc-proj-lbl" : "fc-axis-lbl";
            const anchor = k === 0 ? "start" : k === labelIdx.length - 1 ? "end" : "middle";
            const tx = k === 0 ? Math.max(cx, PAD.l - 6) : k === labelIdx.length - 1 ? Math.min(cx, chartW - 4) : cx;
            xLabelsSvg += `<line x1="${cx.toFixed(1)}" y1="${(PAD.t + H).toFixed(1)}" x2="${cx.toFixed(1)}" y2="${(PAD.t + H + 5).toFixed(1)}" stroke="rgba(255,255,255,0.18)" stroke-width="1"/>`
                + `<text x="${tx.toFixed(1)}" y="${(PAD.t + H + 22).toFixed(1)}" text-anchor="${anchor}" class="${cls}">${esc(formatDateShort(pt.date))}</text>`;
        });

        // Construir SVG
        root.innerHTML = `
            <div class="fc-chart-area" style="position:relative; width:100%;">
                <svg id="fcSvgFull" class="cc-svg" viewBox="0 0 ${chartW} ${chartH}" width="100%" height="${chartH}" role="img" aria-label="Previsão do saldo histórico e projetado">
                    <defs>
                        <linearGradient id="histFillFull" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stop-color="#38BDF8" stop-opacity="0.30"/>
                            <stop offset="100%" stop-color="#38BDF8" stop-opacity="0.01"/>
                        </linearGradient>
                        <linearGradient id="histLineFull" x1="0" y1="0" x2="1" y2="0">
                            <stop offset="0%" stop-color="#38BDF8"/>
                            <stop offset="100%" stop-color="#818CF8"/>
                        </linearGradient>
                        <linearGradient id="alertBandGradFull" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stop-color="rgba(239,68,68,0.18)"/>
                            <stop offset="100%" stop-color="rgba(239,68,68,0.03)"/>
                        </linearGradient>
                        <filter id="fcGlowFull">
                            <feGaussianBlur stdDeviation="3.5" result="glow"/>
                            <feMerge>
                                <feMergeNode in="glow"/>
                                <feMergeNode in="SourceGraphic"/>
                            </feMerge>
                        </filter>
                    </defs>
                    ${alertBands}
                    ${zeroLine}
                    ${yGridSvg}
                    ${splitLine}
                    ${hFill ? `<path d="${hFill}" fill="url(#histFillFull)"/>` : ""}
                    ${histPath ? `<path d="${histPath}" fill="none" stroke="url(#histLineFull)" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>` : ""}
                    ${projPath ? `<path d="${projPath}" fill="none" stroke="#818CF8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="8 5" opacity="0.9)"/>` : ""}
                    ${junctionDot}
                    <line id="fcFullCrosshair" x1="0" y1="${PAD.t}" x2="0" y2="${(PAD.t + H).toFixed(1)}" stroke="rgba(255,255,255,0.35)" stroke-width="1.2" stroke-dasharray="4 3" opacity="0"/>
                    <circle id="fcFullHoverDot" cx="0" cy="0" r="6" fill="#818CF8" stroke="#0F172A" stroke-width="2.5" filter="url(#fcGlowFull)" opacity="0"/>
                    ${xLabelsSvg}
                    <rect id="fcFullOverlay" x="${PAD.l}" y="${PAD.t}" width="${W}" height="${H}" fill="transparent" style="cursor:crosshair;"/>
                </svg>
                <div class="fc-tooltip" id="fcFullTooltip" role="tooltip" aria-hidden="true"></div>
            </div>
        `;

        bindSvgInteractions(chartW, chartH, combined, coords, PAD, W, H, m.currency);
    }

    function bindSvgInteractions(chartW, chartH, combined, coords, PAD, W, H, currency) {
        const svg = el("fcSvgFull");
        const overlay = el("fcFullOverlay");
        const crosshair = el("fcFullCrosshair");
        const hoverDot = el("fcFullHoverDot");
        const tooltip = el("fcFullTooltip");
        const S = sh();

        if (!svg || !overlay || !tooltip) return;

        function onPointer(ev) {
            const svgRect = svg.getBoundingClientRect();
            const scale = chartW / svgRect.width;
            const svgX = (ev.clientX - svgRect.left) * scale;

            let best = 0, bestDist = Infinity;
            for (let i = 0; i < coords.length; i++) {
                const dist = Math.abs(coords[i][0] - svgX);
                if (dist < bestDist) { bestDist = dist; best = i; }
            }

            const pt = combined[best];
            const cx = coords[best][0];
            const cy = coords[best][1];

            if (crosshair) {
                crosshair.setAttribute("x1", cx.toFixed(1));
                crosshair.setAttribute("x2", cx.toFixed(1));
                crosshair.style.opacity = "1";
            }
            if (hoverDot) {
                hoverDot.setAttribute("cx", cx.toFixed(1));
                hoverDot.setAttribute("cy", cy.toFixed(1));
                hoverDot.setAttribute("fill", pt.projected ? "#818CF8" : "#38BDF8");
                hoverDot.style.opacity = "1";
            }

            const isProj = pt.projected;
            const badgeCls = isProj ? "fc-tip-badge proj" : "fc-tip-badge";
            const badgeTxt = isProj ? "Projeção (Estimativa)" : "Histórico Real";

            tooltip.innerHTML = `
                <div class="fc-tip-date">
                    <span>${esc(formatDateFull(pt.date))}</span>
                    <span class="${badgeCls}">${badgeTxt}</span>
                </div>
                <div class="fc-tip-bal">${esc(S.money(pt.val, currency))}</div>
            `;

            // Posicionar tooltip
            const tipW = tooltip.offsetWidth || 150;
            const screenX = (cx / chartW) * svgRect.width;
            const screenY = (cy / chartH) * svgRect.height;
            let leftPos = screenX + 14;
            if (leftPos + tipW > svgRect.width - 10) leftPos = screenX - tipW - 14;

            tooltip.style.left = Math.max(8, leftPos) + "px";
            tooltip.style.top = Math.max(10, screenY - 24) + "px";
            tooltip.classList.add("visible");
            tooltip.setAttribute("aria-hidden", "false");
        }

        function onLeave() {
            if (crosshair) crosshair.style.opacity = "0";
            if (hoverDot) hoverDot.style.opacity = "0";
            if (tooltip) {
                tooltip.classList.remove("visible");
                tooltip.setAttribute("aria-hidden", "true");
            }
        }

        F.clearHover = onLeave;

        let touchStartY = null;
        let touchCancelled = false;

        function handlePointerMove(ev) {
            if (ev.pointerType === "touch") {
                if (touchCancelled) return;
                if (touchStartY != null) {
                    const deltaUp = touchStartY - ev.clientY;
                    if (deltaUp > 14 || Math.abs(ev.clientY - touchStartY) > 22) {
                        touchCancelled = true;
                        onLeave();
                        document.documentElement.classList.remove("chart-touch-locked");
                        document.body.classList.remove("chart-touch-locked");
                        return;
                    }
                }
            }
            if (ev.pointerType === "mouse" || ev.buttons || ev.pointerType === "touch") {
                onPointer(ev);
            }
        }

        overlay.addEventListener("pointerdown", ev => {
            if (ev.pointerType === "touch") {
                touchCancelled = false;
                touchStartY = ev.clientY;
            }
            onPointer(ev);
        });
        overlay.addEventListener("pointermove", handlePointerMove);
        overlay.addEventListener("pointerleave", ev => {
            if (ev.pointerType === "mouse") onLeave();
        });
        overlay.addEventListener("pointercancel", () => {
            touchStartY = null;
            onLeave();
        });
        overlay.addEventListener("pointerup", ev => {
            if (ev.pointerType === "touch") {
                touchStartY = null;
            }
        });
    }

    function renderDetailsAndAssumptions(m) {
        const S = sh();
        const c = m.currency;
        const ass = m.assumptions;
        const lookback = ass.lookback_days || 90;

        // Intervalo no topo
        updateRangeText();

        // Badge de alerta de saldo baixo
        const alertBadge = el("fcAlertBadge");
        if (alertBadge) {
            if (m.alerts.length > 0) {
                alertBadge.hidden = false;
                alertBadge.textContent = `Atenção: Saldo reduzido estimado a partir de ${formatDateShort(m.alerts[0].date)}`;
            } else {
                alertBadge.hidden = true;
            }
        }

        // Descrição das premissas
        const assTextEl = el("fcAssumpText");
        if (assTextEl) {
            const inc = S.money(Number(ass.monthly_income_estimate || 0), c);
            const exp = S.money(Number(ass.monthly_expense_estimate || 0), c);
            const sav = S.money(Number(ass.scheduled_savings_monthly || 0), c);
            const curBal = S.money(m.currentBalance, c);

            assTextEl.innerHTML = `
                Esta projeção utiliza o seu <strong>saldo atual real (${curBal})</strong>, combinado com a média mensal de
                <strong>receitas previstas (${inc}/mês)</strong> e <strong>despesas ponderadas (${exp}/mês)</strong> calculadas sobre
                os últimos ${lookback} dias, subtraindo os compromissos de <strong>poupanças agendadas (${sav}/mês)</strong>.
                <br><br>
                <em>Nota importante: Todos os valores futuros são estimativas matemáticas projetadas e não constituem garantias bancárias.</em>
            `;
        }

        // Caixa de risco / antecipação
        const riskEl = el("fcRiskNotice");
        if (riskEl) {
            if (m.alerts.length > 0) {
                const first = m.alerts[0];
                riskEl.innerHTML = `
                    <div style="background:rgba(239,68,68,0.12); border:1px solid rgba(239,68,68,0.3); border-radius:12px; padding:12px 14px; color:#FCA5A5;">
                        <strong style="display:block; margin-bottom:4px; color:#EF4444; font-size:0.88rem;">⚠️ Período Crítico Antecipado</strong>
                        A projeção prevê que o seu saldo poderá descer para valores reduzidos (< 10% do saldo atual ou negativo) por volta de
                        <strong>${formatDateFull(first.date)}</strong> (${S.money(first.balance, c)}).
                        Recomenda-se antecipar pagamentos, reduzir gastos discricionários ou transferir fundos para prevenir descobertos.
                    </div>
                `;
            } else {
                riskEl.innerHTML = `
                    <div style="background:rgba(16,185,129,0.12); border:1px solid rgba(16,185,129,0.3); border-radius:12px; padding:12px 14px; color:#6EE7B7;">
                        <strong style="display:block; margin-bottom:4px; color:#10B981; font-size:0.88rem;">✅ Saldo Estável e Sustentável</strong>
                        Para o horizonte de <strong>${F.days} dias</strong>, a projeção estima que o saldo permanecerá acima da margem de segurança, com liquidez suficiente para cobrir despesas e compromissos agendados.
                    </div>
                `;
            }
        }

        // Ritmo ideal pela IA
        renderIdealPace(m);
    }

    async function renderIdealPace(m) {
        const paceEl = el("fcPaceContent");
        if (!paceEl) return;

        const S = sh();
        const c = m.currency;
        const inc = Number(m.assumptions.monthly_income_estimate || 0);
        const exp = Number(m.assumptions.monthly_expense_estimate || 0);
        const key = [c, inc, exp, F.days].join("|");

        if (F.paceKey === key && paceEl.dataset.rendered === "1") return;

        paceEl.innerHTML = `<span style="color:rgba(255,255,255,0.45);">A calcular ritmo ideal assistido por IA...</span>`;

        if (typeof state !== "undefined" && state.token && typeof apiRequest === "function") {
            try {
                const goals = (state.savingsGoals || []).map(g => ({
                    name: g.name,
                    target: Number(g.target_decimal || g.target || 0),
                    saved: Number(g.saved_decimal || 0),
                    monthly: Number(g.monthly_decimal || g.monthly_minor / 100 || 0)
                }));

                const res = await apiRequest("POST", "/api/ai/ideal-pace", {
                    currency: c,
                    income_month: inc,
                    expense_month: exp,
                    budget_month: exp,
                    goals: goals
                });

                F.paceKey = key;
                paceEl.dataset.rendered = "1";
                paceEl.innerHTML = `
                    <div style="display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:6px;">
                        <strong style="font-size:1.15rem; color:#38BDF8; font-family:'JetBrains Mono',monospace;">
                            ${S.money(Number(res.ideal_spend_month || exp), c)}/mês
                        </strong>
                        <span style="font-size:0.82rem; color:rgba(255,255,255,0.5);">(${S.money(Math.round(Number(res.ideal_spend_month || exp) / 30), c)}/dia)</span>
                    </div>
                    <p style="margin:0; font-size:0.82rem; color:rgba(255,255,255,0.72); line-height:1.45;">
                        ${esc(res.tip || "Mantenha o ritmo de gastos diário controlado para assegurar a reserva de segurança recomendada.")}
                    </p>
                `;
                return;
            } catch (e) {
                console.warn("[ForecastChart] Ritmo ideal fallback:", e);
            }
        }

        // Fallback local do ritmo ideal
        const idealMonthly = Math.max(0, inc > 0 ? Math.round(inc * 0.75) : Math.round(exp * 0.9));
        paceEl.innerHTML = `
            <div style="display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:6px;">
                <strong style="font-size:1.15rem; color:#38BDF8; font-family:'JetBrains Mono',monospace;">
                    ${S.money(idealMonthly, c)}/mês
                </strong>
                <span style="font-size:0.82rem; color:rgba(255,255,255,0.5);">(${S.money(Math.round(idealMonthly / 30), c)}/dia)</span>
            </div>
            <p style="margin:0; font-size:0.82rem; color:rgba(255,255,255,0.72); line-height:1.45;">
                Recomenda-se manter as despesas abaixo de ${S.money(idealMonthly, c)} mensais para preservar a liquidez e proteger a sua margem de poupança.
            </p>
        `;
    }

    /* ------------------------------ ciclo de vida e intervalo flexível ------------------------------ */

    /* Janela em dias relativos a «hoje»: início (−29 … ) e fim (… 365). Igual à barra do gráfico 1. */
    const MIN_START = -29, MAX_END = 365, MIN_SPAN = 7, TOTAL = MAX_END - MIN_START;
    const SNAP = [7, 30, 90, 182, 365];
    const clampN = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
    const posPct = d => ((d - MIN_START) / TOTAL) * 100;
    const isoOff = o => new Date(Date.now() + o * DAY).toISOString().slice(0, 10);
    const offOf = iso => Math.round((Date.parse(iso + "T00:00:00Z") - Date.parse(isoOff(0) + "T00:00:00Z")) / DAY);
    const dayLbl = o => (o === 0 ? "Hoje" : formatDateShort(isoOff(o)));

    function snapToPreset(days) {
        const found = Object.keys(PRESETS).find(k => Math.abs(PRESETS[k] - days) <= Math.max(2, PRESETS[k] * 0.05));
        return found || null;
    }

    function normWin(s, e) {
        e = clampN(Math.round(e), MIN_START + MIN_SPAN, MAX_END);
        s = clampN(Math.round(s), MIN_START, e - MIN_SPAN);
        return [s, e];
    }
    function shiftWin(s, e, delta) {
        const len = e - s;
        const ns = clampN(s + delta, MIN_START, MAX_END - len);
        return [ns, ns + len];
    }

    /** Aplica a janela. Só volta a pedir dados se o fim mudou; mudar o início apenas redesenha. */
    function setWindow(s, e) {
        [s, e] = normWin(s, e);
        const endChanged = e !== F.days;
        F.start = s;
        F.days = e;
        const matched = snapToPreset(e);
        if (matched) {
            F.period = matched;
            try { localStorage.setItem(STORE_PERIOD_KEY, matched); } catch (err) { /* ignorar */ }
        }
        try {
            localStorage.setItem(STORE_HORIZON_KEY, String(e));
            localStorage.setItem(STORE_START_KEY, String(s));
        } catch (err) { /* ignorar */ }
        syncHorizonControls();
        if (endChanged || !F.model) render({ force: true });
        else { renderSvgChart(F.model); updateRangeText(); }
    }

    function setHorizon(days) { setWindow(F.start, days); }

    function setPeriod(p) {
        if (!p || !(p in PRESETS)) return;
        F.period = p;
        try { localStorage.setItem(STORE_PERIOD_KEY, p); } catch (e) { /* ignorar */ }
        setWindow(F.start, PRESETS[p]);
    }

    function updateRangeText() {
        const rangeEl = el("fcRange");
        if (rangeEl) rangeEl.textContent = `${dayLbl(F.start)} – ${dayLbl(F.days)} (${F.days - F.start} dias)`;
    }

    function paintNav(s, e) {
        const l = posPct(s), r = posPct(e);
        const win = el("fcWin");
        if (win) { win.style.left = l + "%"; win.style.width = (r - l) + "%"; }
        const sl = el("fcShadeL"), sr = el("fcShadeR");
        if (sl) sl.style.width = l + "%";
        if (sr) sr.style.width = (100 - r) + "%";
        const hl = el("fcHandleL"), hr = el("fcHandleR");
        if (hl) { hl.setAttribute("aria-valuemin", String(MIN_START)); hl.setAttribute("aria-valuemax", String(e - MIN_SPAN)); hl.setAttribute("aria-valuenow", String(s)); hl.setAttribute("aria-valuetext", dayLbl(s)); }
        if (hr) { hr.setAttribute("aria-valuemin", String(s + MIN_SPAN)); hr.setAttribute("aria-valuemax", String(MAX_END)); hr.setAttribute("aria-valuenow", String(e)); hr.setAttribute("aria-valuetext", dayLbl(e)); }

        const span = e - s;
        const sLbl = el("fcStartLbl"); if (sLbl) sLbl.textContent = dayLbl(s);
        const eLbl = el("fcEndLbl"); if (eLbl) eLbl.textContent = dayLbl(e);
        const mid = el("fcSliderLabel"); if (mid) mid.textContent = `${span} dias`;
        const badge = el("fcRangeDays"); if (badge) badge.textContent = `${span} dias`;

        const fromInput = el("fcDateFrom"), toInput = el("fcDateTo");
        if (fromInput) { fromInput.min = isoOff(MIN_START); fromInput.max = isoOff(e - MIN_SPAN); fromInput.value = isoOff(s); }
        if (toInput) { toInput.min = isoOff(s + MIN_SPAN); toInput.max = isoOff(MAX_END); toInput.value = isoOff(e); }
        const fTxt = el("fcDateFromTxt"); if (fTxt) fTxt.textContent = dayLbl(s);
        const tTxt = el("fcDateToTxt"); if (tTxt) tTxt.textContent = dayLbl(e);
    }

    function syncHorizonControls() {
        // Atalhos de período do gráfico 1 e horizonte flexível
        const activePreset = snapToPreset(F.days);
        document.querySelectorAll("#fcHorizon .cc-chip, #fcQuick .cc-chip").forEach(b => {
            const p = b.dataset.period;
            const on = p ? (p === activePreset || PRESETS[p] === F.days) : (Number(b.dataset.days) === F.days);
            b.classList.toggle("active", !!on);
            b.setAttribute("aria-pressed", String(!!on));
        });
        paintNav(F.start, F.days);
    }

    /** Pequena curva do saldo dentro da barra (histórico + projeção já calculada). */
    function drawNavSeries(m) {
        const svg = el("fcNavSvg");
        if (!svg || !m || m.combined.length < 2) return;
        const W = 1000, Hh = 64, base = m.histLen - 1;
        const vals = m.combined.map(p => p.val);
        const lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), sp = hi - lo || 1;
        const xs = m.combined.map((p, i) => (posPct(i - base) / 100) * W);
        const ys = m.combined.map(p => Hh - 8 - ((p.val - lo) / sp) * (Hh - 18));
        const d = xs.map((x, i) => `${i ? "L" : "M"}${x.toFixed(1)} ${ys[i].toFixed(1)}`).join(" ");
        svg.setAttribute("viewBox", `0 0 ${W} ${Hh}`);
        svg.innerHTML = `<defs><linearGradient id="fcNavGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#818CF8" stop-opacity=".38"/><stop offset="1" stop-color="#818CF8" stop-opacity="0"/></linearGradient></defs>`
            + `<path d="${d} L${xs[xs.length - 1].toFixed(1)} ${Hh} L${xs[0].toFixed(1)} ${Hh} Z" fill="url(#fcNavGrad)"/>`
            + `<path d="${d}" fill="none" stroke="#A5B4FC" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>`;
    }

    function bindNav() {
        const nav = el("fcNav"), win = el("fcWin"), hl = el("fcHandleL"), hr = el("fcHandleR");
        if (!nav || !win || !hl || !hr) return;
        win.tabIndex = 0;

        let drag = null, timer = 0, pend = null;
        const offAt = ev => {
            const rc = nav.getBoundingClientRect();
            return MIN_START + clampN((ev.clientX - rc.left) / (rc.width || 1), 0, 1) * TOTAL;
        };
        const flush = () => { clearTimeout(timer); if (pend) { const p = pend; pend = null; setWindow(p[0], p[1]); } };
        // Pré-visualiza a barra já; o gráfico atualiza logo a seguir (e só pede dados se o fim mudou)
        const queue = (s, e) => {
            [s, e] = normWin(s, e);
            pend = [s, e];
            paintNav(s, e);
            clearTimeout(timer);
            timer = setTimeout(flush, e !== F.days ? 160 : 0);
        };
        const snapEnd = v => { const r = Math.round(v); return SNAP.find(x => Math.abs(x - r) <= 2) || r; };

        const start = (mode, target) => ev => {
            if (ev.button != null && ev.button > 0) return;
            ev.preventDefault();
            ev.stopPropagation();
            drag = { mode, grab: offAt(ev) - F.start, len: F.days - F.start };
            nav.classList.add("dragging");
            win.classList.add("grabbing");
            try { target.setPointerCapture(ev.pointerId); } catch (e) { /* ignorar */ }
        };
        const move = ev => {
            if (!drag) return;
            const t = offAt(ev), s0 = pend ? pend[0] : F.start, e0 = pend ? pend[1] : F.days;
            if (drag.mode === "l") queue(Math.min(t, e0 - MIN_SPAN), e0);
            else if (drag.mode === "r") queue(s0, Math.max(snapEnd(t), s0 + MIN_SPAN));
            else {
                const s = clampN(t - drag.grab, MIN_START, MAX_END - drag.len);
                queue(s, s + drag.len);
            }
        };
        const end = () => {
            if (!drag) return;
            drag = null;
            nav.classList.remove("dragging");
            win.classList.remove("grabbing");
            flush();
        };
        [[hl, "l"], [hr, "r"], [win, "m"]].forEach(([node, mode]) => {
            node.addEventListener("pointerdown", start(mode, node));
            node.addEventListener("pointermove", move);
            node.addEventListener("pointerup", end);
            node.addEventListener("pointercancel", end);
        });

        // Toque fora da janela: a janela desliza para esse ponto
        nav.addEventListener("pointerdown", ev => {
            if (ev.target.closest("#fcWin")) return;
            const len = F.days - F.start;
            const s = clampN(offAt(ev) - len / 2, MIN_START, MAX_END - len);
            setWindow(s, s + len);
        });

        // Sem scroll da página enquanto o dedo está na barra
        const stopScroll = ev => { if (ev.cancelable) ev.preventDefault(); };
        nav.addEventListener("touchstart", stopScroll, { passive: false });
        nav.addEventListener("touchmove", stopScroll, { passive: false });

        // Teclado: setas ±1 dia (Shift ±15), PageUp/PageDown ±30, Home/End
        const onKey = mode => ev => {
            const k = ev.key;
            const unit = k === "PageUp" || k === "PageDown" ? 30 : ev.shiftKey ? 15 : 1;
            const dir = (k === "ArrowRight" || k === "PageUp" || k === "ArrowUp") ? 1 : (k === "ArrowLeft" || k === "PageDown" || k === "ArrowDown") ? -1 : 0;
            let s = F.start, e = F.days;
            if (k === "Home") { if (mode === "l") s = MIN_START; else if (mode === "r") e = s + MIN_SPAN; else [s, e] = shiftWin(s, e, -1e9); }
            else if (k === "End") { if (mode === "l") s = e - MIN_SPAN; else if (mode === "r") e = MAX_END; else [s, e] = shiftWin(s, e, 1e9); }
            else if (dir) {
                if (mode === "l") s += dir * unit; else if (mode === "r") e += dir * unit; else [s, e] = shiftWin(s, e, dir * unit);
            } else return;
            ev.preventDefault();
            setWindow(s, e);
        };
        hl.addEventListener("keydown", onKey("l"));
        hr.addEventListener("keydown", onKey("r"));
        win.addEventListener("keydown", ev => { if (ev.target === win) onKey("m")(ev); });
    }

    function bindEvents() {
        if (F.bound) return;
        F.bound = true;

        // Seletor de moeda
        const currBox = el("fcCurr");
        if (currBox) {
            currBox.querySelectorAll(".cc-chip").forEach(btn => btn.addEventListener("click", () => {
                F.cur = btn.dataset.cur;
                currBox.querySelectorAll(".cc-chip").forEach(b => {
                    const on = b.dataset.cur === F.cur;
                    b.classList.toggle("active", on);
                    b.setAttribute("aria-checked", String(on));
                });
                render({ force: true });
            }));
        }

        // Atalhos de horizonte (topo e seção de intervalo flexível)
        const bindChips = boxId => {
            const box = el(boxId);
            if (box) {
                box.querySelectorAll(".cc-chip").forEach(btn => btn.addEventListener("click", () => {
                    const period = btn.dataset.period;
                    if (period && period in PRESETS) {
                        setPeriod(period);
                    } else if (btn.dataset.days) {
                        setHorizon(Number(btn.dataset.days));
                    }
                }));
            }
        };
        bindChips("fcHorizon");
        bindChips("fcQuick");

        // Barra de intervalo flexível (arrastar a pega, tocar na barra ou usar o teclado)
        bindNav();

        // Datas «De» e «Até»
        const fromInput = el("fcDateFrom"), toInput = el("fcDateTo");
        if (fromInput) fromInput.addEventListener("change", () => { if (fromInput.value) setWindow(offOf(fromInput.value), F.days); });
        if (toInput) toInput.addEventListener("change", () => { if (toInput.value) setWindow(F.start, offOf(toInput.value)); });

        // Anterior / Aproximar / Afastar / Seguinte (como no gráfico 1)
        const toolsBox = el("fcTools");
        if (toolsBox) {
            toolsBox.querySelectorAll(".bc-tool").forEach(btn => btn.addEventListener("click", () => {
                const act = btn.dataset.act, s = F.start, e = F.days, len = e - s;
                if (act === "prev") { const w = shiftWin(s, e, -len); setWindow(w[0], w[1]); }
                else if (act === "next") { const w = shiftWin(s, e, len); setWindow(w[0], w[1]); }
                else {
                    const c = (s + e) / 2;
                    const nl = act === "in" ? Math.max(MIN_SPAN, len / 2) : Math.min(TOTAL, len * 2);
                    let ns = c - nl / 2, ne = c + nl / 2;
                    if (ne > MAX_END) { ns -= ne - MAX_END; ne = MAX_END; }
                    if (ns < MIN_START) { ne += MIN_START - ns; ns = MIN_START; }
                    setWindow(ns, Math.min(ne, MAX_END));
                }
            }));
        }

        // ResizeObserver para redesenhar SVG responsivamente
        const panel = el("bcPanelForecast");
        const rootChart = el("fcFullChart");
        if (typeof ResizeObserver !== "undefined") {
            let raf = 0;
            const ro = new ResizeObserver(() => {
                cancelAnimationFrame(raf);
                raf = requestAnimationFrame(() => {
                    if (panel && !panel.hidden && F.model) {
                        renderSvgChart(F.model);
                    }
                });
            });
            if (panel) ro.observe(panel);
            if (rootChart) ro.observe(rootChart);
        }
    }

    async function render(opts) {
        const panel = el("bcPanelForecast");
        if (!panel || panel.hidden) return;

        bindEvents();

        // Atualizar estado visual dos botões de moeda e horizonte
        const c = cur();
        const currBox = el("fcCurr");
        if (currBox) {
            currBox.querySelectorAll(".cc-chip").forEach(b => {
                const on = b.dataset.cur === c;
                b.classList.toggle("active", on);
                b.setAttribute("aria-checked", String(on));
            });
        }
        syncHorizonControls();

        const seq = (F.seq = (F.seq || 0) + 1);
        const data = await loadForecastData();
        if (!data || seq !== F.seq) return;

        const model = buildModel(data);
        F.model = model;

        drawNavSeries(model);
        renderStats(model);
        renderSvgChart(model);
        renderDetailsAndAssumptions(model);
    }

    function refresh() {
        const panel = el("bcPanelForecast");
        if (!panel || panel.hidden) return;
        render();
    }

    function insights(row, chips, setTitle) {
        if (typeof setTitle === "function") setTitle("Análise da Previsão do Saldo");
        const m = F.model;
        if (!m) {
            row("info", "#i-spark", "A carregar", "A calcular projeção futura e análise de risco.");
            return;
        }

        const S = sh();
        const c = m.currency;

        if (m.alerts.length > 0) {
            const first = m.alerts[0];
            row("warn", "#i-bell", "Alerta de saldo reduzido (Estimativa)",
                `A projeção indica que o saldo poderá descer para ${S.money(first.balance, c)} em ${formatDateShort(first.date)}. Recomenda-se antecipar liquidez.`);
        } else {
            row("good", "#i-trending", "Projeção favorável",
                `Para o horizonte de ${F.days} dias, o saldo projetado mantém-se sustentável e acima da margem mínima de segurança.`);
        }

        const inc = Number(m.assumptions.monthly_income_estimate || 0);
        const exp = Number(m.assumptions.monthly_expense_estimate || 0);
        if (inc > 0 && exp > 0) {
            const ratio = Math.round((exp / inc) * 100);
            row(ratio > 85 ? "warn" : "tip", "#i-target", "Pressão sobre receitas",
                `As despesas estimadas consomem cerca de ${ratio}% das receitas mensais previstas.`);
        }

        chips.push("Como evitar saldo reduzido?", "Qual a minha margem de segurança?", "Como atingir metas sem comprometer o saldo?");
    }

    window.renderForecast = render;
    window.refreshForecast = refresh;
    window.forecastInsights = insights;
    window.clearForecastHoverDetails = () => {
        if (typeof F.clearHover === "function") F.clearHover();
    };
})();
