/**
 * Despesas — controlos
 * Mês ativo (lista), categorias visíveis no donut, destaque e filtro do histórico.
 */

// ---------- Mês ----------
function handleExpenseMonthChange(value) {
    currentExpensesMonth = value === "all" ? null : value;
    activeExpenseCategoryFilter = "all";
    closeExpensePeriodMenu();
    renderExpensesView();
}
window.handleExpenseMonthChange = handleExpenseMonthChange;

window.stepExpenseMonth = function(dir) {
    const months = getExpenseMonths(); // do mais recente para o mais antigo
    if (!currentExpensesMonth) {
        if (dir < 0 && months.length) handleExpenseMonthChange(months[0]);
        return;
    }
    const idx = months.indexOf(currentExpensesMonth);
    const target = months[idx - dir]; // dir -1 = mais antigo (índice maior)
    if (target) handleExpenseMonthChange(target);
};

window.toggleExpensePeriodMenu = function(ev) {
    if (ev) ev.stopPropagation();
    const menu = document.getElementById("xpPeriodMenu");
    const trigger = document.getElementById("xpPeriodTrigger");
    if (!menu || !trigger) return;
    const open = menu.hidden;
    menu.hidden = !open;
    trigger.setAttribute("aria-expanded", String(open));
    if (open) {
        const act = menu.querySelector(".xp-period-opt.active");
        if (act) menu.scrollTop = Math.max(0, act.offsetTop - 60);
    }
};
function closeExpensePeriodMenu() {
    const menu = document.getElementById("xpPeriodMenu");
    const trigger = document.getElementById("xpPeriodTrigger");
    if (menu) menu.hidden = true;
    if (trigger) trigger.setAttribute("aria-expanded", "false");
}
document.addEventListener("click", (e) => {
    if (!e.target.closest || !e.target.closest("#xpPeriodPicker")) closeExpensePeriodMenu();
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeExpensePeriodMenu(); });

// ---------- Categorias no gráfico ----------
window.toggleChartCategory = function(cat) {
    if (selectedCategoriesForChart.has(cat)) {
        selectedCategoriesForChart.delete(cat);
        if (selectedSpotlightCategory === cat) selectedSpotlightCategory = null;
    } else {
        selectedCategoriesForChart.add(cat);
        selectedSpotlightCategory = cat;
    }
    renderExpensesView();
};
window.selectAllCategoriesForChart = function(selectAll) {
    if (selectAll) {
        selectedCategoriesForChart = new Set(Object.keys(EXPENSE_CATEGORIES));
    } else {
        selectedCategoriesForChart.clear();
        selectedSpotlightCategory = null;
    }
    renderExpensesView();
};
window.handleDonutCategoryClick = function(cat) {
    selectedCategoriesForChart.add(cat);
    selectedSpotlightCategory = (selectedSpotlightCategory === cat) ? null : cat;
    renderExpensesView();
};
window.resetDonutCategorySelection = function() {
    selectedSpotlightCategory = null;
    renderExpensesView();
};

// ---------- Histórico: filtro por categoria ----------
window.setExpenseCategoryFilter = function(cat) {
    activeExpenseCategoryFilter = cat;
    renderExpenseItemsList(getPeriodExpenses());
};
window.filterListBySpotlightCategory = function() {
    if (!selectedSpotlightCategory) return;
    setExpenseCategoryFilter(selectedSpotlightCategory);
    const listEl = document.getElementById("expensesList");
    if (listEl) listEl.scrollIntoView({ behavior: "smooth", block: "start" });
};
