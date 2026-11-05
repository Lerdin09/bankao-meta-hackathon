/**
 * Poupança — depósito manual
 * Depósito extra numa meta; fica registado nas despesas (categoria Poupança).
 */

// ============ DEPÓSITO MANUAL NUMA META (fora da contribuição automática) ============
let depSubmitting = false;
let depIdemKey = "";
// Validação em tempo real: botão só activo com valor válido e dentro do saldo
function validateDeposit(silent) {
    const input = document.getElementById("depAmount");
    const btn = document.getElementById("btnDepSubmit");
    const err = document.getElementById("depError");
    if (!input || !btn) return false;
    const amount = parseCleanNumber(input.value || "0");
    const balance = Number(state.accountAoa && state.accountAoa.balance_decimal);
    let msg = "";
    if (amount > 0 && Number.isFinite(balance) && amount > balance) {
        msg = `Saldo insuficiente. Disponível: ${formatTwoTierMoney(balance, "AOA")}.`;
    }
    const ok = amount > 0 && !msg;
    btn.disabled = !ok || depSubmitting;
    input.setAttribute("aria-invalid", msg ? "true" : "false");
    if (err) { err.textContent = silent ? "" : msg; err.hidden = silent || !msg; }
    return ok;
}
document.addEventListener("input", e => { if (e.target && e.target.id === "depAmount") validateDeposit(); });
document.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    const m = document.getElementById("modalDepositGoal");
    if (m && m.style.display === "flex" && !depSubmitting) closeDepositGoalModal();
});

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
    document.getElementById("depDate").value = localISODate(0);

    // Atualiza o saldo disponível da conta principal de débito
    const balEl = document.getElementById("depSourceAccountBalance");
    if (balEl) {
        balEl.textContent = formatTwoTierMoney(state.accountAoa ? state.accountAoa.balance_decimal : 0, "AOA");
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

    m.querySelector(".dep-more")?.removeAttribute("open");
    depSubmitting = false;
    depIdemKey = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    validateDeposit(true);
    m.style.display = "flex";
    setTimeout(() => document.getElementById("depAmount")?.focus({ preventScroll: true }), 50);
};
window.closeDepositGoalModal = function() {
    const m = document.getElementById("modalDepositGoal");
    if (m) m.style.display = "none";
};
window.fillDepositRemaining = function() {
    const btn = document.getElementById("depFillRemaining") || document.getElementById("depFillRemainingChip");
    const v = Number(btn && btn.dataset.value) || 0;
    if (v > 0) { document.getElementById("depAmount").value = formatNumberWithDots(v); validateDeposit(); }
};
window.setDepositQuickAmount = function(val) {
    const input = document.getElementById("depAmount");
    if (input) {
        const current = parseCleanNumber(input.value || "0");
        input.value = formatNumberWithDots(current + val);
        validateDeposit();
    }
};
window.setDepositDateToday = function() {
    const el = document.getElementById("depDate");
    if (el) el.value = localISODate(0);
};
window.handleDepositGoal = async function(e) {
    e.preventDefault();
    if (depSubmitting || !validateDeposit()) { validateDeposit(); return; }
    const id = document.getElementById("depGoalId")?.value;
    const amount = parseCleanNumber(document.getElementById("depAmount")?.value || "0");
    const date = document.getElementById("depDate")?.value || localISODate(0);
    const notes = document.getElementById("depNotes")?.value.trim() || "";

    if (!(amount > 0)) {
        return toast("Indique um valor de depósito válido.", "error");
    }
    const idx = financeStore.goals.findIndex(x => x.id === id);
    if (idx === -1) return toast("Meta não encontrada.", "error");

    // Exigir confirmação por PIN antes de alocar fundos na meta de poupança
    if (typeof window.requirePinAuthorization === "function") {
        const goalName = financeStore.goals[idx]?.name || "Meta de Poupança";
        const desc = `Depositar ${formatMoney(amount, "AOA")} na meta "${goalName}"`;
        const authorized = await window.requirePinAuthorization(desc);
        if (!authorized) return;
    }

    // A base de dados soma o valor à meta e regista a despesa (categoria Poupança) numa só operação
    let result;
    depSubmitting = true;
    const submitBtn = document.getElementById("btnDepSubmit");
    if (submitBtn) { submitBtn.disabled = true; submitBtn.querySelector("span").textContent = "A depositar..."; }
    try {
        result = await apiRequest("POST", `/api/savings/goals/${encodeURIComponent(id)}/deposit`, { amount, date, notes, idempotency_key: depIdemKey });
    } catch (err) {
        depSubmitting = false;
        if (submitBtn) submitBtn.querySelector("span").textContent = "Depositar";
        validateDeposit();
        return toast(err.message, "error");
    }
    depSubmitting = false;
    if (submitBtn) submitBtn.querySelector("span").textContent = "Depositar";
    const goal = result.goal;
    financeStore.goals[idx] = goal;
    financeStore.expenses.unshift(result.expense);
    if (state.accountAoa && typeof result.balance === "number") state.accountAoa.balance_decimal = result.balance;

    closeDepositGoalModal();
    document.getElementById("formDepositGoal")?.reset();
    renderSavingsView();
    renderExpensesView();
    if (typeof updateDashboardHero === "function") updateDashboardHero();
    refreshHomeFinance();
    loadUserData();   // saldo da conta e extrato (sem esperar)

    const done = goal.saved >= (Number(goal.target) || 0);
    const msg = done
        ? `Meta "${goal.name}" atingida! Depósito de ${formatMoney(amount, "AOA")} registado.`
        : `Depósito de ${formatMoney(amount, "AOA")} em "${goal.name}" registado!`;
    toast(msg, "success");

    // Notificação do sistema (respeita definições n_savings e ch_push)
    if (typeof window.bkNotify === "function") {
        window.bkNotify(msg, "success", "n_savings");
    }
};
