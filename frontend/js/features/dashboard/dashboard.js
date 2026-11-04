/**
 * Dashboard (início)
 * Carrega contas e extrato da API, desenha os cartões de saldo e o hero do dashboard.
 */

// Carregar Dados das Contas e Extrato
async function loadUserData() {
    if (!state.token) return;

    try {
        // Buscar Contas
        const resAcc = await fetch(`${API_BASE}/api/accounts`, {
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        if (resAcc.status === 401) {
            // Token expirado, limpar sessão
            logout();
            return;
        }
        if (resAcc.ok) {
            state.accounts = await resAcc.json();
            renderAccounts();
            renderAccountsView();
        }

        // Buscar Extrato
        const resTx = await fetch(`${API_BASE}/api/transactions`, {
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        if (resTx.ok) {
            const txs = await resTx.json();
            state.transactions = txs;
            renderTransactions(txs);
            renderPayments();
        }
        // Despesas, metas e orçamentos do utilizador (base de dados)
        await loadFinanceData();
        updateDashboardHero();
        renderSavingsView();
        renderExpensesView();
        renderHomeExpenses();
        renderHomeTrend();
        if (typeof refreshCardChart === "function") refreshCardChart();
        if (typeof loadForecastData === "function") loadForecastData();

        // Preencher seletores de mês a partir da data de criação da conta
        const createdAt = state.user && state.user.created_at ? state.user.created_at : null;
        populateMonthSelect("payMonthSelect", createdAt, "all");
        populateMonthSelect("expMonthSelect", createdAt, "all");
        // Definições do utilizador: aplicar (1.ª vez) e verificar alertas
        if (typeof loadUserSettings === "function" && !ST.loaded) await loadUserSettings();
        if (typeof checkAlerts === "function") checkAlerts();
    } catch (err) {
        console.error("Erro ao carregar dados:", err);
    }
}
// Renderizar Cartões de Saldo
function renderAccounts() {
    state.accountAoa = state.accounts.find(a => a.currency === "AOA");
    state.accountEur = state.accounts.find(a => a.currency === "EUR");
    state.accountUsd = state.accounts.find(a => a.currency === "USD");

    if (state.accountAoa) {
        document.getElementById("balanceAoa").innerHTML = `${formatTwoTierMoney(state.accountAoa.balance_decimal, "AOA").replace(" KZ", "")} <span class="curr">KZ</span>`;
        document.getElementById("accNumberAoa").textContent = groupDigits(state.accountAoa.account_number);
        document.getElementById("ibanAoa").textContent = groupDigits(state.accountAoa.iban_virtual);
    }

    if (state.accountEur) {
        document.getElementById("balanceEur").innerHTML = `${formatTwoTierMoney(state.accountEur.balance_decimal, "EUR").replace(" €", "")} <span class="curr">€</span>`;
        document.getElementById("accNumberEur").textContent = groupDigits(state.accountEur.account_number);
        document.getElementById("ibanEur").textContent = groupDigits(state.accountEur.iban_virtual);
    }

    if (state.accountUsd) {
        const balEl = document.getElementById("balanceUsd");
        const accEl = document.getElementById("accNumberUsd");
        const ibanEl = document.getElementById("ibanUsd");
        if (balEl) balEl.innerHTML = `${formatTwoTierMoney(state.accountUsd.balance_decimal, "USD").replace(" $", "")} <span class="curr">$</span>`;
        if (accEl) accEl.textContent = groupDigits(state.accountUsd.account_number);
        if (ibanEl) ibanEl.textContent = groupDigits(state.accountUsd.iban_virtual);
    }

    updateDashboardHero();
    renderAccountsView();
}
// Saudação do início: nome + frase conforme a hora do dia
function updateHomeGreeting(user) {
    const u = user === undefined ? state.user : user;
    const nameEl = document.getElementById("greetingName");
    const lineEl = document.getElementById("greetingLine");
    const hour = new Date().getHours();
    const text = hour < 5 ? "🌙 Boa noite"
        : hour < 12 ? "☀️ Bom dia"
        : hour < 19 ? "🌤️ Boa tarde"
        : "🌙 Boa noite";
    if (lineEl && lineEl.textContent !== text) lineEl.textContent = text;
    if (nameEl) {
        const full = u ? (u.nome || u.primeiro_nome || "Utilizador") : "Visitante";
        const first = String(full).trim().split(/\s+/)[0];
        if (nameEl.textContent !== first) nameEl.textContent = first;
    }
}
// Atualizar Hero Card do Dashboard com Chave, Saldo da moeda de preferência, contas e seletor
function updateDashboardHero() {
    const prefCurr = state.prefCurrency || "AOA";
    const targetAcc = state.accounts ? state.accounts.find(a => a.currency === prefCurr) : null;
    const valEl = document.getElementById("dashPrefBalanceVal");
    const currEl = document.getElementById("dashPrefBalanceCurr");
    const emailEl = document.getElementById("dashAccountEmail");

    if (emailEl) {
        const key = (state.user && state.user.email) ? state.user.email : "—";
        emailEl.textContent = key;
        emailEl.title = key;   // se for cortada com "…", o valor completo aparece ao passar o cursor
    }

    if (valEl && currEl) {
        const dec = targetAcc ? targetAcc.balance_decimal : 0;
        if (prefCurr === "AOA") {
            valEl.textContent = formatTwoTierMoney(dec, "AOA").replace(" KZ", "").trim();
            currEl.textContent = "KZ";
        } else if (prefCurr === "USD") {
            valEl.textContent = formatTwoTierMoney(dec, "USD").replace(" $", "").trim();
            currEl.textContent = "$";
        } else if (prefCurr === "EUR") {
            valEl.textContent = formatTwoTierMoney(dec, "EUR").replace(" €", "").trim();
            currEl.textContent = "€";
        }
    }

    // Atualizar Linhas da lista "As suas contas"
    const aoaAcc = state.accounts ? state.accounts.find(a => a.currency === "AOA") : null;
    const rowAoa = document.getElementById("balanceAoaRow");
    if (rowAoa) {
        rowAoa.textContent = aoaAcc ? formatTwoTierMoney(aoaAcc.balance_decimal, "AOA") : "0,00 KZ";
    }

    const rowSavings = document.getElementById("balanceSavingsRow");
    if (rowSavings) {
        rowSavings.textContent = formatTwoTierMoney(getSavingsTotal(), "AOA");
    }

    // Atualizar Widget lateral de saldo se existir
    const widgetAmt = document.getElementById("nbWidgetAmount");
    if (widgetAmt) {
        const dec = targetAcc ? targetAcc.balance_decimal : (aoaAcc ? aoaAcc.balance_decimal : 0);
        widgetAmt.textContent = formatTwoTierMoney(dec, prefCurr);
    }

    // Atualizar estado ativo dos botões de moeda
    document.querySelectorAll(".dash-curr-tag").forEach(tag => {
        tag.classList.toggle("active", tag.getAttribute("data-curr") === prefCurr);
    });
}
// Alternar acordeão de contas e IBANs detalhados
window.toggleWalletsDetail = function() {
    const details = document.getElementById("walletsDetailsToggle");
    if (details) {
        details.open = !details.open;
        if (details.open) {
            details.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }
};

// ==========================================================================
// Início: tendência do saldo e despesas do mês, sempre calculadas a partir da base de dados
// ==========================================================================

/** Saldo no fim de cada um dos últimos `days` dias (moeda de preferência), recuado a partir do saldo atual. */
function computeBalanceSeries(days = 30) {
    const curr = state.prefCurrency || "AOA";
    const acc = (state.accounts || []).find(a => a.currency === curr);
    if (!acc) return null;
    const txs = (state.transactions || []).filter(t => (t.currency || "AOA") === curr && !/fail|falh/i.test(String(t.status || "")));
    const now = new Date();
    const dayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate() - (days - 1));
    const points = [];
    for (let i = 0; i < days; i++) {
        const end = new Date(dayStart.getFullYear(), dayStart.getMonth(), dayStart.getDate() + i + 1);
        const after = txs.filter(t => parseTxDate(t.created_at) >= end).reduce((a, t) => a + (Number(t.amount_decimal) || 0), 0);
        points.push({ date: new Date(end.getFullYear(), end.getMonth(), end.getDate() - 1), value: acc.balance_decimal - after });
    }
    const before = points[0].value - txs.filter(t => {
        const d = parseTxDate(t.created_at);
        return d >= dayStart && d < new Date(dayStart.getFullYear(), dayStart.getMonth(), dayStart.getDate() + 1);
    }).reduce((a, t) => a + (Number(t.amount_decimal) || 0), 0);
    const hasMovement = txs.some(t => parseTxDate(t.created_at) >= dayStart);
    return { curr, points, before, now: acc.balance_decimal, hasMovement };
}

function seriesPath(points, w, top, bottom) {
    const vals = points.map(p => p.value);
    const min = Math.min(...vals), max = Math.max(...vals);
    const span = max - min;
    const xy = points.map((p, i) => [
        (i / (points.length - 1)) * w,
        span === 0 ? (top + bottom) / 2 : bottom - ((p.value - min) / span) * (bottom - top)
    ]);
    const line = xy.map((c, i) => `${i ? "L" : "M"} ${c[0].toFixed(1)} ${c[1].toFixed(1)}`).join(" ");
    return { line, xy };
}

function renderHomeTrend() {
    const setPill = (el, text, up) => {
        if (!el) return;
        el.hidden = !text;
        if (text) el.textContent = text;
        if (text) el.classList.toggle("down", !up);
    };
    const s = computeBalanceSeries(30);
    const hero = document.getElementById("dashTrendPill");
    const heroText = document.getElementById("dashTrendText");
    const widgetPill = document.getElementById("widgetTrendPill");
    const sparkLine = document.getElementById("sparkLine");
    const sparkFill = document.getElementById("sparkFill");
    const sparkDot = document.getElementById("sparkDot");
    const wLine = document.getElementById("widgetLine");
    const wFill = document.getElementById("widgetFill");
    const wDot = document.getElementById("widgetDot");
    const wDates = document.getElementById("widgetDates");

    if (!s || !s.hasMovement) {
        if (hero) hero.hidden = true;
        setPill(widgetPill, "", true);
        [sparkLine, sparkFill, wLine, wFill].forEach(el => el && el.setAttribute("d", ""));
        if (sparkDot) sparkDot.hidden = true;
        if (wDot) wDot.hidden = true;
        if (wDates) wDates.innerHTML = "";
        return;
    }

    // Variação face ao início da janela de 30 dias
    const delta = s.now - s.before;
    let label = "";
    if (Math.abs(delta) >= 0.005) {
        label = s.before > 0
            ? `${delta >= 0 ? "+" : "−"}${Math.abs(Math.round((delta / s.before) * 100))}%`
            : `${delta >= 0 ? "+" : "−"}${formatMoney(Math.abs(delta), s.curr)}`;
    }
    const up = delta >= 0;
    if (hero) {
        hero.hidden = !label;
        if (heroText) heroText.textContent = `${label} este mês`;
        hero.classList.toggle("down", !up);
        const arrow = document.getElementById("dashTrendArrow");
        if (arrow) arrow.setAttribute("d", up ? "M2 8l4-4 4 4" : "M2 4l4 4 4-4");
    }
    setPill(widgetPill, label ? `${up ? "↑" : "↓"} ${label}` : "", up);

    // Linha do cartão (320×64) e do widget (280×120)
    const a = seriesPath(s.points, 312, 10, 54);
    if (sparkLine) sparkLine.setAttribute("d", a.line);
    if (sparkFill) sparkFill.setAttribute("d", `${a.line} L 320 ${a.xy[a.xy.length - 1][1].toFixed(1)} L 320 64 L 0 64 Z`);
    if (sparkDot) {
        sparkDot.hidden = false;
        sparkDot.style.top = `${(a.xy[a.xy.length - 1][1] / 64) * 100}%`;
    }
    const b = seriesPath(s.points, 250, 15, 105);
    const last = b.xy[b.xy.length - 1];
    if (wLine) wLine.setAttribute("d", b.line);
    if (wFill) wFill.setAttribute("d", `${b.line} L 280 ${last[1].toFixed(1)} L 280 120 L 0 120 Z`);
    if (wDot) { wDot.hidden = false; wDot.setAttribute("cx", last[0].toFixed(1)); wDot.setAttribute("cy", last[1].toFixed(1)); }
    if (wDates) {
        const idx = [0, 7, 14, 22, 29];
        wDates.innerHTML = idx.map(i => `<span>${s.points[i].date.toLocaleDateString("pt-AO", { day: "2-digit", month: "short" })}</span>`).join("");
    }
}

function renderHomeExpenses() {
    const svg = document.getElementById("homeDonut");
    const legend = document.getElementById("homeExpenseLegend");
    const totalEl = document.getElementById("homeDonutTotal");
    if (!svg || !legend || !totalEl) return;

    const mk = localISODate(0).slice(0, 7);
    const byCat = {};
    getExpenses().filter(e => expenseMonthKey(e) === mk).forEach(e => {
        byCat[e.category] = (byCat[e.category] || 0) + (Number(e.amount) || 0);
    });
    const entries = Object.entries(byCat).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
    const total = entries.reduce((a, [, v]) => a + v, 0);
    totalEl.textContent = formatNumberWithDots(Math.round(total));

    const C = 2 * Math.PI * 38;
    let rings = `<circle cx="50" cy="50" r="38" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="12"/>`;
    if (!total) {
        svg.innerHTML = rings;
        legend.innerHTML = `<div class="nb-leg-item"><span>Sem gastos registados este mês</span></div>`;
        return;
    }
    // Até 3 categorias + "Outras" para o resto
    const top = entries.slice(0, 3);
    const rest = entries.slice(3).reduce((a, [, v]) => a + v, 0);
    const slices = top.map(([cat, v]) => ({ label: cat, v, color: (EXPENSE_CATEGORIES[cat] || {}).color || "#64748B" }));
    if (rest > 0) slices.push({ label: "Outras", v: rest, color: "#64748B" });
    let offset = 0;
    slices.forEach(sl => {
        const len = (sl.v / total) * C;
        rings += `<circle cx="50" cy="50" r="38" fill="none" stroke="${sl.color}" stroke-width="12" stroke-dasharray="${len.toFixed(2)} ${(C - len).toFixed(2)}" stroke-dashoffset="${(-offset).toFixed(2)}"/>`;
        offset += len;
    });
    svg.innerHTML = rings;
    legend.innerHTML = slices.map(sl =>
        `<div class="nb-leg-item"><span class="dot" style="background:${sl.color};box-shadow:0 0 6px ${sl.color}"></span><span>${escapeHtml(sl.label)}</span><strong>${Math.round((sl.v / total) * 100)}%</strong></div>`
    ).join("");
}

/** Atualiza os blocos do início depois de qualquer alteração a despesas, metas ou movimentos */
function refreshHomeFinance() {
    renderHomeExpenses();
    renderHomeTrend();
}
