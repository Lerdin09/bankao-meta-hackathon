/**
 * Poupança — metas
 * Criar, editar e apagar metas de poupança (modais e ações).
 */

// Modal de Nova Meta
// Modal de Nova Meta
let selectedGoalIcon = "travel";
let selectedEditGoalIcon = "travel";

const EMOJI_TO_KEY = {
    "✈️": "travel", "🏠": "home", "🚗": "car", "💻": "laptop",
    "🎓": "education", "💍": "award", "🛡️": "shield", "🏖️": "travel", "🎯": "target"
};

window.openNewGoalModal = function() {
    const m = document.getElementById("modalNewGoal");
    if (m) {
        m.style.display = "flex";
        calculateSavingsSimulation();
    }
};
window.closeNewGoalModal = function() {
    const m = document.getElementById("modalNewGoal");
    if (m) m.style.display = "none";
};

window.setGoalFieldValue = function(fieldId, val) {
    const el = document.getElementById(fieldId);
    if (el) {
        el.value = formatNumberWithDots(val);
        calculateSavingsSimulation();
    }
};

window.calculateSavingsSimulation = function() {
    const target = parseCleanNumber(document.getElementById("goalTarget")?.value || "0");
    const monthly = parseCleanNumber(document.getElementById("goalMonthly")?.value || "0");
    const initial = parseCleanNumber(document.getElementById("goalInitial")?.value || "0");
    const simMonthsEl = document.getElementById("newGoalSimMonths");
    const simInterestEl = document.getElementById("newGoalSimInterest");
    const simAdviceEl = document.getElementById("newGoalSimAdvice");

    const remaining = Math.max(0, target - initial);
    let months = 0;
    if (monthly > 0 && remaining > 0) {
        months = Math.ceil(remaining / monthly);
    }

    if (simMonthsEl) {
        simMonthsEl.textContent = months > 0 ? `${months} ${months === 1 ? 'mês' : 'meses'}` : "Imediato";
    }

    // Taxa garantida de 4,5% ao ano (0.375% ao mês)
    const annualRate = 0.045;
    const estimatedInterest = Math.round((target * annualRate * (Math.max(1, months) / 12)));
    if (simInterestEl) {
        simInterestEl.textContent = `+${formatMoney(estimatedInterest, "AOA")}`;
    }

    if (simAdviceEl) {
        if (monthly <= 0 && remaining > 0) {
            simAdviceEl.textContent = "Defina um depósito mensal para projetar a data de conquista da sua meta.";
        } else if (months <= 6) {
            simAdviceEl.textContent = `Ritmo acelerado! Atingirá ${formatMoney(target, "AOA")} em apenas ${months} meses.`;
        } else {
            const suggested = Math.round(monthly * 1.25);
            simAdviceEl.textContent = `Ao aumentar o depósito para ${formatMoney(suggested, "AOA")}/mês, poupa até ${Math.max(1, Math.round(months * 0.2))} meses de espera.`;
        }
    }
};

// Seletor de ícone no modal de meta
function initGoalIconPickers() {
    document.querySelectorAll("#goalIconPicker button").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("#goalIconPicker button").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            selectedGoalIcon = btn.dataset.icon;
        });
    });
    document.querySelectorAll("#editGoalIconPicker button").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("#editGoalIconPicker button").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            selectedEditGoalIcon = btn.dataset.icon;
        });
    });
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initGoalIconPickers);
} else {
    initGoalIconPickers();
}

window.handleCreateGoal = function(e) {
    e.preventDefault();
    const name = document.getElementById("goalName")?.value.trim();
    const target = parseCleanNumber(document.getElementById("goalTarget")?.value || "0");
    const monthly = parseCleanNumber(document.getElementById("goalMonthly")?.value || "0");
    const initial = parseCleanNumber(document.getElementById("goalInitial")?.value || "0");
    const deadlineVal = document.getElementById("goalDeadline")?.value;

    if (!name || target <= 0) {
        return toast("Preencha o nome e um valor de meta válido.", "error");
    }

    let deadlineStr = "Indefinido";
    if (deadlineVal) {
        const parts = deadlineVal.split("-");
        if (parts.length === 2) {
            const months = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
            const mIdx = parseInt(parts[1], 10) - 1;
            deadlineStr = `${months[mIdx] || parts[1]} ${parts[0]}`;
        }
    }

    const goals = getSavingsGoals();
    const newGoal = {
        id: "goal_" + Date.now(),
        name,
        target,
        saved: initial,
        monthly,
        deadline: deadlineStr,
        iconKey: selectedGoalIcon,
        status: "on-track"
    };

    goals.unshift(newGoal);
    saveSavingsGoals(goals);

    closeNewGoalModal();
    document.getElementById("formNewGoal")?.reset();
    renderSavingsView();
    updateDashboardHero();
    toast(`Meta "${name}" criada com sucesso!`, "success");
};
// ============ EDIÇÃO DE METAS DE POUPANÇA ============
window.openEditGoalModal = function(id) {
    const goals = getSavingsGoals();
    const g = goals.find(x => x.id === id);
    if (!g) return toast("Meta não encontrada.", "error");

    const m = document.getElementById("modalEditGoal");
    if (!m) return;

    document.getElementById("editGoalId").value = g.id;
    document.getElementById("editGoalName").value = g.name || "";
    document.getElementById("editGoalTarget").value = formatNumberWithDots(g.target || 0);
    document.getElementById("editGoalSaved").value = formatNumberWithDots(g.saved || 0);
    document.getElementById("editGoalMonthly").value = formatNumberWithDots(g.monthly || 0);
    document.getElementById("editGoalDeadline").value = g.deadline || "";
    setEditGoalStatus(g.status || "on-track");

    selectedEditGoalIcon = g.iconKey || EMOJI_TO_KEY[g.icon] || "travel";
    document.querySelectorAll("#editGoalIconPicker button").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.icon === selectedEditGoalIcon);
    });

    updateEditGoalPreview();
    m.style.display = "flex";
};
window.closeEditGoalModal = function() {
    const m = document.getElementById("modalEditGoal");
    if (m) m.style.display = "none";
};
window.handleUpdateGoal = function(e) {
    e.preventDefault();
    const id = document.getElementById("editGoalId")?.value;
    const name = document.getElementById("editGoalName")?.value.trim();
    const target = parseCleanNumber(document.getElementById("editGoalTarget")?.value || "0");
    const saved = parseCleanNumber(document.getElementById("editGoalSaved")?.value || "0");
    const monthly = parseCleanNumber(document.getElementById("editGoalMonthly")?.value || "0");
    const deadline = document.getElementById("editGoalDeadline")?.value.trim() || "Indefinido";
    const status = document.getElementById("editGoalStatus")?.value || "on-track";

    if (!name || target <= 0) {
        return toast("Preencha o nome e um valor de meta válido.", "error");
    }

    const goals = getSavingsGoals();
    const idx = goals.findIndex(x => x.id === id);
    if (idx === -1) return toast("Meta não encontrada.", "error");

    goals[idx] = {
        ...goals[idx],
        name,
        target,
        saved,
        monthly,
        deadline,
        iconKey: selectedEditGoalIcon,
        status
    };

    saveSavingsGoals(goals);
    closeEditGoalModal();
    renderSavingsView();
    updateDashboardHero();
    toast(`Meta "${name}" atualizada com sucesso!`, "success");
};
window.deleteSavingsGoal = async function(id) {
    const goals = getSavingsGoals();
    const g = goals.find(x => x.id === id);
    if (!g) return;
    const saved = Number(g.saved) || 0;
    const ok = await confirmDialog({
        title: "Apagar esta meta?",
        message: "A meta e o seu progresso serão eliminados e esta ação não pode ser desfeita.",
        details: [
            { label: "Meta", value: g.name },
            { label: "Poupado", value: formatMoney(saved, "AOA") },
            { label: "Objetivo", value: formatMoney(Number(g.target) || 0, "AOA") }
        ],
        note: saved > 0 ? `Atenção: os ${formatMoney(saved, "AOA")} poupados nesta meta deixam de contar no seu total poupado.` : "",
        confirmText: "Sim, apagar meta"
    });
    if (!ok) return;
    saveSavingsGoals(goals.filter(x => x.id !== id));
    renderSavingsView();
    updateDashboardHero();
    toast("Meta de poupança removida.", "info");
};

// ---- Edição: estado (botões) e pré-visualização do progresso ----
window.setEditGoalStatus = function(v) {
    const i = document.getElementById("editGoalStatus");
    if (i) i.value = v;
    document.querySelectorAll("#editGoalStatusSeg button").forEach(b => {
        const on = b.dataset.status === v;
        b.classList.toggle("active", on);
        b.setAttribute("aria-pressed", String(on));
    });
};
window.updateEditGoalPreview = function() {
    const target = parseCleanNumber(document.getElementById("editGoalTarget")?.value || "0");
    const saved = parseCleanNumber(document.getElementById("editGoalSaved")?.value || "0");
    const pct = target > 0 ? Math.min(100, Math.round((saved / target) * 100)) : 0;
    const bar = document.getElementById("editGoalPrevBar");
    const pc = document.getElementById("editGoalPrevPct");
    const tx = document.getElementById("editGoalPrevText");
    if (bar) bar.style.width = pct + "%";
    if (pc) pc.textContent = pct + "%";
    if (tx) tx.textContent = target > 0
        ? (saved >= target ? "Meta atingida" : `Faltam ${formatMoney(target - saved, "AOA")}`)
        : "Defina o valor da meta";
};
