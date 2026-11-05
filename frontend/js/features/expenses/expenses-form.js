/**
 * Despesas — registar, editar e apagar
 * Modais e ações para criar, atualizar e remover despesas.
 */

// Modal Nova Despesa
window.openNewExpenseModal = function() {
    const m = document.getElementById("modalNewExpense");
    if (m) {
        const dateInput = document.getElementById("expDate");
        if (dateInput && !dateInput.value) {
            dateInput.value = localISODate(0);
        }
        selectExpenseFormCategory("Alimentação", "new");
        m.style.display = "flex";
    }
};
window.closeNewExpenseModal = function() {
    const m = document.getElementById("modalNewExpense");
    if (m) m.style.display = "none";
};

// Modal Editar Despesa
window.openEditExpenseModal = function(id) {
    const expenses = getExpenses();
    const exp = expenses.find(x => x.id === id);
    if (!exp) return toast("Despesa não encontrada.", "error");

    const m = document.getElementById("modalEditExpense");
    if (!m) return;

    document.getElementById("editExpId").value = exp.id;
    document.getElementById("editExpName").value = exp.name || "";
    document.getElementById("editExpCategory").value = exp.category || "Outros";
    document.getElementById("editExpAmount").value = formatNumberWithDots(exp.amount || 0);
    document.getElementById("editExpDate").value = exp.date || localISODate(0);
    document.getElementById("editExpNotes").value = exp.notes || "";

    selectExpenseFormCategory(exp.category || "Outros", "edit");

    m.style.display = "flex";
};
window.closeEditExpenseModal = function() {
    const m = document.getElementById("modalEditExpense");
    if (m) m.style.display = "none";
};

// Seleção visual de categoria e atalhos rápidos
window.selectExpenseFormCategory = function(cat, mode) {
    const gridId = mode === "edit" ? "editExpCategoryGrid" : "expCategoryGrid";
    const selectId = mode === "edit" ? "editExpCategory" : "expCategory";
    const hintId = mode === "edit" ? "editExpCategoryBudgetHint" : "expCategoryBudgetHint";

    const selectEl = document.getElementById(selectId);
    if (selectEl) selectEl.value = cat;

    const grid = document.getElementById(gridId);
    if (grid) {
        grid.querySelectorAll(".form-cat-btn").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.cat === cat);
        });
    }

    const hintEl = document.getElementById(hintId);
    if (hintEl && typeof getCategoryBudgets === "function") {
        const budgets = getCategoryBudgets();
        const bVal = budgets[cat] || 0;
        hintEl.textContent = bVal > 0 ? `Meta: ${formatMoney(bVal, "AOA")}/mês` : "Sem meta definida";
    }
};

window.addExpenseQuickAmount = function(fieldId, val) {
    const input = document.getElementById(fieldId);
    if (input) {
        const cur = parseCleanNumber(input.value || "0");
        input.value = formatNumberWithDots(cur + val);
    }
};

window.setExpenseDateShortcut = function(fieldId, daysAgo) {
    const el = document.getElementById(fieldId);
    if (el) el.value = localISODate(-daysAgo);
};

window.appendExpenseNoteTag = function(fieldId, tag) {
    const input = document.getElementById(fieldId);
    if (input) {
        const cur = input.value.trim();
        if (!cur) {
            input.value = tag;
        } else if (!cur.includes(tag)) {
            input.value = `${cur} · ${tag}`;
        }
    }
};
window.handleUpdateExpense = async function(e) {
    e.preventDefault();
    const id = document.getElementById("editExpId")?.value;
    const name = document.getElementById("editExpName")?.value.trim();
    const category = document.getElementById("editExpCategory")?.value || "Outros";
    const amount = parseCleanNumber(document.getElementById("editExpAmount")?.value || "0");
    const date = document.getElementById("editExpDate")?.value || localISODate(0);
    const notes = document.getElementById("editExpNotes")?.value.trim() || "";

    if (!name || amount <= 0) {
        return toast("Indique o nome e o montante válido da despesa.", "error");
    }
    const previous = getExpenses().find(x => x.id === id);
    if (!previous) return toast("Despesa não encontrada.", "error");

    try {
        const updated = await apiRequest("PUT", `/api/expenses/${encodeURIComponent(id)}`, { name, category, amount, date, notes, currency: previous.currency || "AOA", origin: previous.origin });
        const idx = financeStore.expenses.findIndex(x => x.id === id);
        financeStore.expenses[idx] = updated;
        // Depósito numa meta: a base de dados já ajustou a meta pela diferença; recarrega as metas
        if (previous.goalId) financeStore.goals = await apiRequest("GET", "/api/savings/goals");
    } catch (err) {
        return toast(err.message, "error");
    }

    closeEditExpenseModal();
    renderExpensesView();
    renderSavingsView();
    if (typeof updateDashboardHero === "function") updateDashboardHero();
    refreshHomeFinance();
    toast(`Despesa "${name}" atualizada com sucesso!`, "success");
};
window.handleCreateExpense = async function(e) {
    e.preventDefault();
    const name = document.getElementById("expName")?.value.trim();
    const category = document.getElementById("expCategory")?.value || "Outros";
    const amount = parseCleanNumber(document.getElementById("expAmount")?.value || "0");
    const date = document.getElementById("expDate")?.value || localISODate(0);
    const notes = document.getElementById("expNotes")?.value.trim() || "";

    if (!name || amount <= 0) {
        return toast("Indique o nome e o montante válido da despesa.", "error");
    }

    try {
        const created = await apiRequest("POST", "/api/expenses", { name, category, amount, currency: "AOA", date, origin: "manual", notes });
        financeStore.expenses.unshift(created);
    } catch (err) {
        return toast(err.message, "error");
    }

    // Se o filtro de mês estiver ativo, atualiza para o mês da despesa para ela aparecer logo
    const expMonth = date.substring(0, 7); // YYYY-MM
    if (currentExpensesMonth && currentExpensesMonth !== expMonth) currentExpensesMonth = expMonth;
    activeExpenseCategoryFilter = "all";

    closeNewExpenseModal();
    document.getElementById("formNewExpense")?.reset();
    renderExpensesView();
    refreshHomeFinance();
    toast(`Despesa "${name}" de ${formatMoney(amount, "AOA")} registada!`, "success");

    // Notificação do sistema (respeita definições n_expenses e ch_push)
    if (typeof window.bkNotify === "function") {
        window.bkNotify(`Nova despesa registada: ${name} · ${formatMoney(amount, "AOA")}`, "success", "n_expenses");
    }

    if (typeof copilotOpDone === "function") {
        copilotOpDone("expense", {
            chat: `✅ **Despesa registada!** **${name}** · **${formatMoney(amount, "AOA")}**.\n\nPode vê-la em **Despesas**.`,
            speech: `Concluído. A despesa ${name} de ${formatMoney(amount, "AOA")} foi registada com sucesso.`
        });
    }
};
window.deleteExpense = async function(id) {
    const removed = getExpenses().find(e => e.id === id);
    if (!removed) return;

    const [yy, mm, dd] = String(removed.date || "").split("-");
    const ok = await confirmDialog({
        title: "Remover esta despesa?",
        message: "Esta ação não pode ser desfeita.",
        details: [
            { label: "Despesa", value: removed.name },
            { label: "Categoria", value: removed.category || "Outros" },
            { label: "Data", value: dd ? `${dd}/${mm}/${yy}` : "—" },
            { label: "Valor", value: fmtKz(removed.amount) }
        ],
        note: removed.goalId ? "Este registo é um depósito numa meta de poupança: o valor também será retirado dessa meta." : "",
        confirmText: "Sim, remover"
    });
    if (!ok) return;

    try {
        await apiRequest("DELETE", `/api/expenses/${encodeURIComponent(id)}`);
        financeStore.expenses = financeStore.expenses.filter(e => e.id !== id);
        if (removed.goalId) financeStore.goals = await apiRequest("GET", "/api/savings/goals");
    } catch (err) {
        return toast(err.message, "error");
    }

    renderExpensesView();
    renderSavingsView();
    if (typeof updateDashboardHero === "function") updateDashboardHero();
    refreshHomeFinance();
    toast(removed.goalId ? `Depósito removido e ${formatMoney(removed.amount, "AOA")} retirados da meta.` : "Despesa removida.", "info");
};
