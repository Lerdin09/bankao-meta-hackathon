/**
 * Despesas — registo por IA
 * Registo rápido por texto livre e despesas criadas pelo Copilot.
 */

// Registo de despesa via input rápido do Copilot na página de Despesas
window.fillQuickAiExample = function(text) {
    const input = document.getElementById("expQuickAiInput");
    if (input) { input.value = text; input.focus(); }
};

window.handleQuickAiExpense = async function(e) {
    e.preventDefault();
    const input = document.getElementById("expQuickAiInput");
    const text = input ? input.value.trim() : "";
    if (!text) return;

    // Detectar montante (ex: 15.000 ou 15000 ou 5000)
    let amount = 0;
    const amtMatch = text.match(/(\d[\d\s.,]*\d|\d+)\s*(?:kz|kwanza|kwanzas|aoa)?/i);
    if (amtMatch) {
        amount = parseCleanNumber(amtMatch[1]);
    }

    // Detectar categoria
    let category = "Outros";
    const textLower = text.toLowerCase();
    if (/supermercado|mercado|comida|almoço|jantar|lanche|restaurante|kero|maxi|candando|alimenta|pão|refeição/i.test(textLower)) {
        category = "Alimentação";
    } else if (/t[aá]xi|yango|uber|combust[ií]vel|gasolina|gas[oó]leo|sonangol|transporte|carro|viagem/i.test(textLower)) {
        category = "Transporte";
    } else if (/renda|casa|energia|luz|ende|água|epal|condom[ií]nio|habita/i.test(textLower)) {
        category = "Habitação";
    } else if (/unitel|zap|dstv|internet|net|saldo|telefone|telecom/i.test(textLower)) {
        category = "Telecomunicações";
    } else if (/praia|festa|cinema|bar|lazer|balada|show/i.test(textLower)) {
        category = "Lazer";
    } else if (/farm[aá]cia|rem[eé]dio|hospital|cl[ií]nica|sa[uú]de|m[eé]dico/i.test(textLower)) {
        category = "Saúde";
    }

    // Extrair descrição limpa
    let cleanName = text.replace(/(?:gastei|comprei|paguei|regista|anota|despesa|gasto|de|\d+[\d.,]*|\bkz\b|\bkwanzas?\b|\bno\b|\bna\b|\bem\b|\bcom\b|\bpara\b|\bhoje\b|\bontem\b|\banteontem\b)/gi, " ").replace(/\s+/g, " ").trim();
    if (!cleanName || cleanName.length < 3) {
        cleanName = `Gasto em ${category}`;
    }

    if (amount <= 0) {
        return toast("Não encontrei o valor. Ex: \"Gastei 15.000 KZ no supermercado\".", "error");
    }

    // Data: hoje, ontem ou anteontem
    let date = localISODate(0);
    if (/anteontem/i.test(text)) date = localISODate(-2);
    else if (/ontem/i.test(text)) date = localISODate(-1);

    const name = cleanName.charAt(0).toUpperCase() + cleanName.slice(1);
    let created;
    try {
        created = await apiRequest("POST", "/api/expenses", {
            name, category, amount, currency: "AOA", date, origin: "ai",
            notes: `Registado pelo Copilot: "${text.length > 40 ? text.substring(0, 40) + "…" : text}"`
        });
        financeStore.expenses.unshift(created);
    } catch (err) {
        return toast(err.message, "error");
    }

    if (input) input.value = "";
    // Mostrar logo a despesa: muda para o mês dela se o filtro for outro
    if (currentExpensesMonth && currentExpensesMonth !== date.substring(0, 7)) currentExpensesMonth = date.substring(0, 7);
    activeExpenseCategoryFilter = "all";
    renderExpensesView();
    refreshHomeFinance();
    toast(`✨ Copilot registou despesa: ${created.name} (${formatTwoTierMoney(amount, "AOA")})`, "success");
};
async function registerExpenseFromAction(action) {
    if (!action) return;
    const amount = Number(action.amount);
    if (!(amount > 0)) return toast("O Copilot não encontrou o valor da despesa. Indique-o na mensagem.", "error");
    try {
        const created = await apiRequest("POST", "/api/expenses", {
            name: action.name || "Despesa",
            category: action.category || "Outros",
            amount,
            currency: action.currency || "AOA",
            date: localISODate(0),
            origin: "ai",
            notes: action.notes || "Registado via Copilot IA"
        });
        financeStore.expenses.unshift(created);
        renderExpensesView();
        refreshHomeFinance();
        toast(`✨ Copilot registou a sua despesa de ${formatMoney(created.amount, created.currency)} em ${created.category}!`, "success");
    } catch (err) {
        toast(err.message, "error");
    }
}
