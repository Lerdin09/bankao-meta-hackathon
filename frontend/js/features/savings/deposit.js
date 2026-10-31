/**
 * Poupança — depósito manual
 * Depósito extra numa meta; fica registado nas despesas (categoria Poupança).
 */

// ============ DEPÓSITO MANUAL NUMA META (fora da contribuição automática) ============
window.openDepositGoalModal = function(id) {
    const g = getSavingsGoals().find(x => x.id === id);
    if (!g) return toast("Meta não encontrada.", "error");

    const m = document.getElementById("modalDepositGoal");
    if (!m) return;

    const remaining = Math.max(0, (Number(g.target) || 0) - (Number(g.saved) || 0));
    const GOAL_ICONS = {
        travel: "#i-plane", home: "#i-home", car: "#i-car", laptop: "#i-laptop",
        education: "#i-book", target: "#i-target", shield: "#i-shield", award: "#i-award",
        savings: "#i-piggy", health: "#i-heart", default: "#i-target"
    };
    const EMOJI_TO_KEY = {
        "✈️": "travel", "🏠": "home", "🚗": "car", "💻": "laptop",
        "🎓": "education", "💍": "award", "🛡️": "shield", "🏖️": "travel", "🎯": "target"
    };
    const key = g.iconKey || EMOJI_TO_KEY[g.icon] || "default";
    const href = GOAL_ICONS[key] || GOAL_ICONS.default;

    document.getElementById("depGoalId").value = g.id;
    const iconEl = document.getElementById("depGoalIcon");
    if (iconEl) iconEl.innerHTML = `<svg><use href="${href}"/></svg>`;
    document.getElementById("depGoalName").textContent = g.name;
    document.getElementById("depGoalProgress").textContent =
        `${formatTwoTierMoney(g.saved, "AOA")} de ${formatTwoTierMoney(g.target, "AOA")}`;
    document.getElementById("depGoalRemaining").textContent =
        remaining > 0 ? formatTwoTierMoney(remaining, "AOA") : "Meta atingida";
    document.getElementById("depAmount").value = "";
    document.getElementById("depNotes").value = "";
    document.getElementById("depDate").value = new Date().toISOString().split("T")[0];

    // Atualiza o saldo disponível da conta principal de débito
    const balEl = document.getElementById("depSourceAccountBalance");
    if (balEl) {
        const aoaBal = (window.APP_STATE && window.APP_STATE.accounts && window.APP_STATE.accounts.aoa)
            ? window.APP_STATE.accounts.aoa.balance
            : 1250000;
        balEl.textContent = formatTwoTierMoney(aoaBal, "AOA");
    }

    const restBtn = document.getElementById("depFillRemaining");
    if (restBtn) {
        restBtn.dataset.value = remaining;
        restBtn.style.display = remaining > 0 ? "" : "none";
    }
    const restChip = document.getElementById("depFillRemainingChip");
    if (restChip) {
        restChip.dataset.value = remaining;
        restChip.style.display = remaining > 0 ? "" : "none";
    }

    m.style.display = "flex";
    setTimeout(() => document.getElementById("depAmount")?.focus(), 50);
};
window.closeDepositGoalModal = function() {
    const m = document.getElementById("modalDepositGoal");
    if (m) m.style.display = "none";
};
window.fillDepositRemaining = function() {
    const btn = document.getElementById("depFillRemaining") || document.getElementById("depFillRemainingChip");
    const v = Number(btn && btn.dataset.value) || 0;
    if (v > 0) document.getElementById("depAmount").value = formatNumberWithDots(v);
};
window.setDepositQuickAmount = function(val) {
    const input = document.getElementById("depAmount");
    if (input) {
        const current = parseCleanNumber(input.value || "0");
        input.value = formatNumberWithDots(current + val);
    }
};
window.setDepositDateToday = function() {
    const el = document.getElementById("depDate");
    if (el) el.value = new Date().toISOString().split("T")[0];
};
window.handleDepositGoal = function(e) {
    e.preventDefault();
    const id = document.getElementById("depGoalId")?.value;
    const amount = parseCleanNumber(document.getElementById("depAmount")?.value || "0");
    const date = document.getElementById("depDate")?.value || new Date().toISOString().split("T")[0];
    const notes = document.getElementById("depNotes")?.value.trim() || "";

    if (!(amount > 0)) {
        return toast("Indique um valor de depósito válido.", "error");
    }

    const goals = getSavingsGoals();
    const idx = goals.findIndex(x => x.id === id);
    if (idx === -1) return toast("Meta não encontrada.", "error");
    const goal = goals[idx];

    // 1) Atualiza o valor poupado da meta
    goal.saved = (Number(goal.saved) || 0) + amount;
    if (goal.saved >= (Number(goal.target) || 0)) goal.status = "on-track";
    goals[idx] = goal;
    saveSavingsGoals(goals);

    // 2) Regista o depósito nas despesas (categoria Poupança)
    const expenses = getExpenses();
    expenses.unshift({
        id: "exp_sav_" + Date.now(),
        name: `Depósito na poupança: ${goal.name}`,
        category: "Poupança",
        amount,
        currency: "AOA",
        date,
        origin: "savings",
        goalId: goal.id,
        notes: notes || "Depósito manual (fora da contribuição automática)"
    });
    saveExpenses(expenses);

    closeDepositGoalModal();
    document.getElementById("formDepositGoal")?.reset();
    renderSavingsView();
    renderExpensesView();
    if (typeof updateDashboardHero === "function") updateDashboardHero();

    const done = goal.saved >= (Number(goal.target) || 0);
    toast(done
        ? `Meta "${goal.name}" atingida! Depósito de ${formatMoney(amount, "AOA")} registado.`
        : `Depósito de ${formatMoney(amount, "AOA")} em "${goal.name}" registado!`, "success");
};
