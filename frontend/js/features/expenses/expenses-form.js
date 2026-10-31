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
            dateInput.value = new Date().toISOString().split("T")[0];
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
    document.getElementById("editExpDate").value = exp.date || new Date().toISOString().split("T")[0];
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
        const bVal = budgets[cat] || 35000;
        hintEl.textContent = `Meta: ${formatMoney(bVal, "AOA")}/mês`;
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
    if (el) {
        const d = new Date();
        d.setDate(d.getDate() - daysAgo);
        el.value = d.toISOString().split("T")[0];
    }
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
window.handleUpdateExpense = function(e) {
    e.preventDefault();
    const id = document.getElementById("editExpId")?.value;
    const name = document.getElementById("editExpName")?.value.trim();
    const category = document.getElementById("editExpCategory")?.value || "Outros";
    const amount = parseCleanNumber(document.getElementById("editExpAmount")?.value || "0");
    const date = document.getElementById("editExpDate")?.value || new Date().toISOString().split("T")[0];
    const notes = document.getElementById("editExpNotes")?.value.trim() || "";

    if (!name || amount <= 0) {
        return toast("Indique o nome e o montante válido da despesa.", "error");
    }

    const expenses = getExpenses();
    const idx = expenses.findIndex(x => x.id === id);
    if (idx === -1) return toast("Despesa não encontrada.", "error");

    const previous = expenses[idx];
    expenses[idx] = {
        ...previous,
        name,
        category,
        amount,
        date,
        notes
    };

    // Depósito numa poupança: ajusta a meta pela diferença de valor
    if (previous.goalId && amount !== previous.amount) {
        const goals = getSavingsGoals();
        const gi = goals.findIndex(x => x.id === previous.goalId);
        if (gi !== -1) {
            goals[gi].saved = Math.max(0, (Number(goals[gi].saved) || 0) + (amount - previous.amount));
            saveSavingsGoals(goals);
            renderSavingsView();
            if (typeof updateDashboardHero === "function") updateDashboardHero();
        }
    }

    saveExpenses(expenses);
    closeEditExpenseModal();
    renderExpensesView();
    toast(`Despesa "${name}" atualizada com sucesso!`, "success");
};
window.handleCreateExpense = function(e) {
    e.preventDefault();
    const name = document.getElementById("expName")?.value.trim();
    const category = document.getElementById("expCategory")?.value || "Outros";
    const amount = parseCleanNumber(document.getElementById("expAmount")?.value || "0");
    const date = document.getElementById("expDate")?.value || new Date().toISOString().split("T")[0];
    const notes = document.getElementById("expNotes")?.value.trim() || "";

    if (!name || amount <= 0) {
        return toast("Indique o nome e o montante válido da despesa.", "error");
    }

    const expenses = getExpenses();
    const newExp = {
        id: "exp_" + Date.now(),
        name,
        category,
        amount,
        currency: "AOA",
        date,
        origin: "manual",
        notes
    };

    expenses.unshift(newExp);
    saveExpenses(expenses);

    // Se o filtro de mês estiver ativo, atualiza para o mês da despesa para ela aparecer logo
    if (date) {
        const expMonth = date.substring(0, 7); // YYYY-MM
        if (currentExpensesMonth && currentExpensesMonth !== expMonth) currentExpensesMonth = expMonth;
        activeExpenseCategoryFilter = "all";
    }

    closeNewExpenseModal();
    document.getElementById("formNewExpense")?.reset();
    renderExpensesView();
    toast(`Despesa "${name}" de ${formatMoney(amount, "AOA")} registada!`, "success");
};
window.deleteExpense = async function(id) {
    const expenses = getExpenses();
    const removed = expenses.find(e => e.id === id);
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
    const filtered = expenses.filter(e => e.id !== id);
    saveExpenses(filtered);

    // Depósito numa poupança: retira o valor da meta correspondente
    if (removed && removed.goalId) {
        const goals = getSavingsGoals();
        const gi = goals.findIndex(x => x.id === removed.goalId);
        if (gi !== -1) {
            goals[gi].saved = Math.max(0, (Number(goals[gi].saved) || 0) - (Number(removed.amount) || 0));
            saveSavingsGoals(goals);
            renderSavingsView();
            if (typeof updateDashboardHero === "function") updateDashboardHero();
            renderExpensesView();
            return toast(`Depósito removido e ${formatMoney(removed.amount, "AOA")} retirados da meta "${goals[gi].name}".`, "info");
        }
    }

    renderExpensesView();
    toast("Despesa removida.", "info");
};
