/**
 * Poupança — metas
 * Criar, editar e apagar metas de poupança (modais e ações).
 */

// Modal de Nova Meta
// Modal de Nova Meta
let selectedGoalIcon = "travel";
let selectedEditGoalIcon = "travel";
let goalSubmitting = false;

const EMOJI_TO_KEY = {
    "✈️": "travel", "🏠": "home", "🚗": "car", "💻": "laptop",
    "🎓": "education", "💍": "award", "🛡️": "shield", "🏖️": "travel", "🎯": "target"
};

// ---- Débito automático: dia do mês + mês de início ----
function goalFirstDebit(ym, day) {
    const [y, m] = ym.split("-").map(Number);
    const last = new Date(y, m, 0).getDate();
    return new Date(y, m - 1, Math.min(day, last));
}
function goalIsoDate(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
window.syncGoalSchedule = function(pfx, fromStart) {
    const daySel = document.getElementById(`${pfx}DebitDay`);
    const row = document.getElementById(`${pfx}StartRow`);
    const startEl = document.getElementById(`${pfx}Start`);
    const hint = document.getElementById(`${pfx}AutoHint`);
    if (!daySel || !row || !startEl || !hint) return;
    const day = Number(daySel.value) || 0;
    row.hidden = !day;
    if (!day) { hint.hidden = true; startEl.value = ""; return; }
    const today = new Date(); today.setHours(0, 0, 0, 0);
    if (!startEl.value || !fromStart) {
        // mês de início sugerido: este mês se o dia ainda não passou, senão o próximo
        const cur = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
        if (!startEl.value || goalFirstDebit(startEl.value, day) < today) {
            const first = goalFirstDebit(cur, day);
            const d = first >= today ? today : new Date(today.getFullYear(), today.getMonth() + 1, 1);
            startEl.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
        }
    }
    startEl.min = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
    const first = goalFirstDebit(startEl.value, day);
    const label = first.toLocaleDateString("pt-AO", { day: "numeric", month: "long", year: "numeric" });
    hint.textContent = first < today
        ? "Essa data já passou. Escolha um mês de início futuro."
        : `1.º débito a ${label}, depois todos os meses no dia ${day}. Fica registado em Despesas.`;
    hint.hidden = false;
};
// Lê o débito automático do formulário → { debit_day, start_date } | null | false (inválido)
function readGoalSchedule(pfx) {
    const day = Number(document.getElementById(`${pfx}DebitDay`)?.value) || 0;
    if (!day) return null;
    const ym = document.getElementById(`${pfx}Start`)?.value;
    if (!ym) return false;
    return { debit_day: day, start_date: goalIsoDate(goalFirstDebit(ym, day)) };
}

window.openNewGoalModal = function() {
    const m = document.getElementById("modalNewGoal");
    if (m) {
        const d = document.getElementById("goalDebitDay"); if (d) d.value = "";
        syncGoalSchedule("goal");
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

window.handleCreateGoal = async function(e) {
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

    const sched = readGoalSchedule("goal");
    if (sched === false) return toast("Escolha o mês de início do débito automático.", "error");
    if (sched && !(monthly > 0)) return toast("Defina o depósito mensal para ativar o débito automático.", "error");
    if (sched && goalFirstDebit(document.getElementById("goalStart").value, sched.debit_day) < new Date(new Date().setHours(0, 0, 0, 0))) {
        return toast("A data de início do débito automático não pode estar no passado.", "error");
    }
    if (goalSubmitting) return;
    goalSubmitting = true;
    const btn = document.querySelector("#formNewGoal button[type=submit]");
    if (btn) btn.disabled = true;
    try {
        const created = await apiRequest("POST", "/api/savings/goals", {
            name, target, saved: initial, monthly, deadline: deadlineStr, icon_key: selectedGoalIcon, status: "on-track",
            ...(sched || {})
        });
        financeStore.goals.unshift(created);
    } catch (err) {
        return toast(err.message, "error");
    } finally {
        goalSubmitting = false;
        if (btn) btn.disabled = false;
    }
    await loadUserData();   // saldo, extrato e despesas (o saldo inicial sai da conta)

    closeNewGoalModal();
    document.getElementById("formNewGoal")?.reset();
    renderSavingsView();
    updateDashboardHero();
    if (typeof refreshCardChart === "function") refreshCardChart();
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
    document.getElementById("editGoalDebitDay").value = g.debitDay || "";
    document.getElementById("editGoalStart").value = g.startDate ? g.startDate.slice(0, 7) : "";
    syncGoalSchedule("editGoal", true);
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
window.handleUpdateGoal = async function(e) {
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
    const idx = financeStore.goals.findIndex(x => x.id === id);
    if (idx === -1) return toast("Meta não encontrada.", "error");

    const sched = readGoalSchedule("editGoal");
    if (sched === false) return toast("Escolha o mês de início do débito automático.", "error");
    if (sched && !(monthly > 0)) return toast("Defina o depósito mensal para ativar o débito automático.", "error");
    const orig = financeStore.goals[idx];
    // só reenvia a data de início se o cliente a alterou (evita rejeitar datas antigas já em curso)
    const schedChanged = sched && (sched.debit_day !== orig.debitDay || sched.start_date.slice(0, 7) !== (orig.startDate || "").slice(0, 7));
    try {
        financeStore.goals[idx] = await apiRequest("PUT", `/api/savings/goals/${encodeURIComponent(id)}`, {
            name, target, saved, monthly, deadline, icon_key: selectedEditGoalIcon, status,
            ...(sched ? (schedChanged ? sched : { debit_day: sched.debit_day }) : {})
        });
    } catch (err) {
        return toast(err.message, "error");
    }

    closeEditGoalModal();
    renderSavingsView();
    updateDashboardHero();
    if (typeof refreshCardChart === "function") refreshCardChart();
    toast(`Meta "${name}" atualizada com sucesso!`, "success");
};
window.deleteSavingsGoal = async function(id) {
    const g = getSavingsGoals().find(x => x.id === id);
    if (!g) return;
    const saved = Number(g.saved) || 0;
    const ok = await confirmDialog({
        title: "Apagar esta meta?",
        message: "A meta será eliminada e o valor poupado volta para a sua conta.",
        details: [
            { label: "Meta", value: g.name },
            { label: "Poupado", value: formatMoney(saved, "AOA") },
            { label: "Objetivo", value: formatMoney(Number(g.target) || 0, "AOA") }
        ],
        note: saved > 0 ? `Os ${formatMoney(saved, "AOA")} poupados voltam para a sua conta e as despesas de poupança desta meta são anuladas.` : "",
        confirmText: "Sim, apagar meta"
    });
    if (!ok) return;
    try {
        await apiRequest("DELETE", `/api/savings/goals/${encodeURIComponent(id)}`);
        financeStore.goals = financeStore.goals.filter(x => x.id !== id);
    } catch (err) {
        return toast(err.message, "error");
    }
    await loadUserData();   // saldo devolvido, extrato e despesas
    renderSavingsView();
    renderExpensesView();
    updateDashboardHero();
    if (typeof refreshCardChart === "function") refreshCardChart();
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
