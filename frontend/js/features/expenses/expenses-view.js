/**
 * Despesas — vista principal
 * Orquestra a página: período, resumo, gráfico, tipos, Copilot e histórico.
 */

function renderExpensesView() {
    const periodExpenses = getPeriodExpenses();

    // Totais e contagens por categoria (apenas do período)
    const categoryTotals = {};
    const categoryCounts = {};
    Object.keys(EXPENSE_CATEGORIES).forEach(c => { categoryTotals[c] = 0; categoryCounts[c] = 0; });
    periodExpenses.forEach(e => {
        const cat = EXPENSE_CATEGORIES[e.category] ? e.category : "Outros";
        categoryTotals[cat] += Number(e.amount || 0);
        categoryCounts[cat] += 1;
    });

    const grandTotalPeriod = Object.values(categoryTotals).reduce((a, b) => a + b, 0);

    // Total ativo no gráfico (apenas categorias marcadas)
    let activeChartTotal = 0;
    let activePurchasesCount = 0;
    selectedCategoriesForChart.forEach(cat => {
        activeChartTotal += categoryTotals[cat] || 0;
        activePurchasesCount += categoryCounts[cat] || 0;
    });

    renderExpensePeriodPicker();
    renderExpenseKpis(periodExpenses, grandTotalPeriod);
    renderInteractiveDonutChart(categoryTotals, activeChartTotal, activePurchasesCount);
    renderDonutSpotlight(categoryTotals, categoryCounts, activeChartTotal);
    renderSelectableExpenseTypes(categoryTotals, categoryCounts, activeChartTotal, grandTotalPeriod);
    updateExpenseAssistantCard(categoryTotals, periodExpenses);
    renderExpenseItemsList(periodExpenses);
}

// ---------- Período: lista de meses ----------
function renderExpensePeriodPicker() {
    const menu = document.getElementById("xpPeriodMenu");
    const label = document.getElementById("xpPeriodLabel");
    if (!menu || !label) return;

    const all = getExpenses();
    const stats = {};
    all.forEach(e => {
        const k = expenseMonthKey(e);
        (stats[k] = stats[k] || { n: 0, t: 0 });
        stats[k].n += 1;
        stats[k].t += Number(e.amount || 0);
    });
    const grand = all.reduce((a, e) => a + Number(e.amount || 0), 0);
    const months = getExpenseMonths();
    const current = currentExpensesMonth || "all";

    const row = (value, title, n, total) => {
        const active = value === current;
        const meta = n ? `${n} ${n === 1 ? "gasto" : "gastos"} · ${fmtKz(total)}` : "Sem gastos";
        return `
            <button type="button" role="option" aria-selected="${active}" data-value="${value}"
                class="xp-period-opt ${active ? "active" : ""} ${n ? "" : "is-empty"}"
                onclick="handleExpenseMonthChange('${value}')">
                <span class="xp-period-opt-main"><b>${escapeHtml(title)}</b><small>${meta}</small></span>
                <svg class="xp-period-opt-check"><use href="#i-check"/></svg>
            </button>`;
    };

    menu.innerHTML =
        row("all", "Todos os meses", all.length, grand) +
        `<div class="xp-period-sep">Por mês</div>` +
        months.map(k => row(k, monthKeyLabel(k), (stats[k] || {}).n || 0, (stats[k] || {}).t || 0)).join("");

    label.textContent = currentExpensesMonth ? monthKeyLabel(currentExpensesMonth) : "Todos os meses";

    // Setas: anterior = mês mais antigo, seguinte = mais recente
    const idx = currentExpensesMonth ? months.indexOf(currentExpensesMonth) : -1;
    const prev = document.getElementById("xpPeriodPrev");
    const next = document.getElementById("xpPeriodNext");
    if (prev) prev.disabled = currentExpensesMonth ? idx >= months.length - 1 : false;
    if (next) next.disabled = currentExpensesMonth ? idx <= 0 : true;
}

// ---------- Resumo do período ----------
function renderExpenseKpis(periodExpenses, grandTotal) {
    const el = document.getElementById("xpKpis");
    if (!el) return;

    const n = periodExpenses.length;
    const avg = n ? grandTotal / n : 0;
    const biggest = periodExpenses.reduce((b, e) => (!b || Number(e.amount) > Number(b.amount) ? e : b), null);

    // Variação face ao mês anterior (só com um mês selecionado)
    let delta = "";
    if (currentExpensesMonth) {
        const [y, m] = currentExpensesMonth.split("-").map(Number);
        const pk = m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, "0")}`;
        const prevTotal = getExpenses().filter(e => expenseMonthKey(e) === pk).reduce((a, e) => a + Number(e.amount || 0), 0);
        if (prevTotal > 0) {
            const pct = Math.round(((grandTotal - prevTotal) / prevTotal) * 100);
            delta = `<small class="${pct > 0 ? "up" : "down"}">${pct > 0 ? "▲" : "▼"} ${Math.abs(pct)}% vs mês anterior</small>`;
        } else {
            delta = `<small>Sem mês anterior para comparar</small>`;
        }
    } else {
        const months = new Set(getExpenses().map(expenseMonthKey)).size;
        delta = `<small>${months} ${months === 1 ? "mês" : "meses"} com gastos</small>`;
    }

    el.innerHTML = `
        <div class="xp-kpi primary">
            <span class="xp-kpi-lbl">Total gasto</span>
            <strong>${fmtKz(grandTotal)}</strong>
            ${delta}
        </div>
        <div class="xp-kpi">
            <span class="xp-kpi-lbl">Compras</span>
            <strong>${n}</strong>
            <small>${n ? "no período" : "nenhuma ainda"}</small>
        </div>
        <div class="xp-kpi">
            <span class="xp-kpi-lbl">Média por compra</span>
            <strong>${fmtKz(avg)}</strong>
            <small>&nbsp;</small>
        </div>
        <div class="xp-kpi">
            <span class="xp-kpi-lbl">Maior gasto</span>
            <strong>${biggest ? fmtKz(biggest.amount) : "—"}</strong>
            <small class="trunc">${biggest ? escapeHtml(biggest.name) : "&nbsp;"}</small>
        </div>`;
}
