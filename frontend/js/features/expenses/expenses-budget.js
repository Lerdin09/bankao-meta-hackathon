/**
 * Despesas — orçamento e assistente
 * Modal da meta habitual por categoria e ajuda do Copilot.
 */

// Modais de Orçamento e Assistente
window.openEditCategoryBudgetModal = function(cat) {
    const targetCat = cat || selectedSpotlightCategory || "Alimentação";
    currentCategoryBeingEdited = targetCat;
    const info = EXPENSE_CATEGORIES[targetCat] || { icon: "📦", label: targetCat };
    const budgets = getCategoryBudgets();
    const currentBudget = budgets[targetCat] || 35000;

    const modal = document.getElementById("modalEditCategoryBudget");
    const iconEl = document.getElementById("budgetEditCatIcon");
    const nameEl = document.getElementById("budgetEditCatName");
    const inputEl = document.getElementById("budgetEditInputAmount");

    const CAT_SVG_ICONS = {
        "Alimentação": "#i-cart", "Transporte": "#i-car", "Habitação": "#i-home",
        "Telecomunicações": "#i-phone", "Lazer": "#i-spark", "Saúde": "#i-heart",
        "Poupança": "#i-piggy", "Outros": "#i-receipt"
    };
    const iconHref = (info.icon && info.icon.startsWith("#")) ? info.icon : (CAT_SVG_ICONS[targetCat] || "#i-receipt");

    if (iconEl) iconEl.innerHTML = `<svg><use href="${iconHref}"/></svg>`;
    if (nameEl) nameEl.textContent = targetCat;
    if (inputEl) inputEl.value = formatNumberWithDots(currentBudget);

    if (modal) modal.style.display = "flex";
};
window.setBudgetQuickAmount = function(val) {
    const el = document.getElementById("budgetEditInputAmount");
    if (el) el.value = formatNumberWithDots(val);
};
window.closeEditCategoryBudgetModal = function() {
    const modal = document.getElementById("modalEditCategoryBudget");
    if (modal) modal.style.display = "none";
};
window.handleSaveCategoryBudget = function(e) {
    e.preventDefault();
    const inputEl = document.getElementById("budgetEditInputAmount");
    const newBudget = parseCleanNumber(inputEl?.value || "0");
    if (newBudget <= 0) {
        return toast("Indique um montante habitual válido.", "error");
    }

    const budgets = getCategoryBudgets();
    budgets[currentCategoryBeingEdited] = newBudget;
    saveCategoryBudgets(budgets);

    closeEditCategoryBudgetModal();
    renderExpensesView();
    toast(`Meta habitual de ${currentCategoryBeingEdited} atualizada para ${formatMoney(newBudget, "AOA")}!`, "success");
};
window.openExpenseAssistantHelpModal = function() {
    const m = document.getElementById("modalExpenseAssistantHelp");
    if (m) m.style.display = "flex";
};
window.closeExpenseAssistantHelpModal = function() {
    const m = document.getElementById("modalExpenseAssistantHelp");
    if (m) m.style.display = "none";
};
window.startCopilotExpenseConversation = function() {
    closeExpenseAssistantHelpModal();
    const copilotInput = document.getElementById("copilotUserInput");
    const prompt = currentExpensesMonth 
        ? `Copilot, analisa as minhas despesas de ${currentExpensesMonth} e dá-me recomendações práticas para poupar mais.`
        : "Copilot, ajuda-me a analisar todas as minhas despesas e a otimizar o meu orçamento mensal.";

    // Se estiver em ecrã pequeno e Copilot for uma view separada, mudar para a view
    const wide = window.matchMedia("(min-width: 1280px)").matches;
    if (!wide) {
        const copilotNav = document.querySelector('[data-view="view-copilot"]');
        if (copilotNav) copilotNav.click();
    }
    if (copilotInput) {
        copilotInput.value = prompt;
        copilotInput.focus();
    }
};
