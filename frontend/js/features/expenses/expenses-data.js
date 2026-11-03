/**
 * Despesas — dados
 * Categorias, orçamentos por categoria e armazenamento das despesas em localStorage.
 */

// ==========================================================================
// VISTA: DESPESAS E GASTOS COM GRÁFICO DONUT (view-expenses)
// "no lado esquerdo coloque também despesas, onde ira ficar todos tipos de gastos,
// aí será identificada quais despesas foram feitas, tera um grafico donut separando
// cada uma, o cliente que registra os nomes das despesas, ou pede ao assistente para registrar"
// ==========================================================================

const EXPENSE_CATEGORIES = {
    "Alimentação": { icon: "#i-cart", color: "#38BDF8", label: "Alimentação & Supermercado" },
    "Transporte": { icon: "#i-car", color: "#F59E0B", label: "Transporte & Combustível" },
    "Habitação": { icon: "#i-home", color: "#818CF8", label: "Habitação & Renda" },
    "Telecomunicações": { icon: "#i-phone", color: "#EC4899", label: "Telecom & Internet" },
    "Lazer": { icon: "#i-spark", color: "#A855F7", label: "Lazer & Restaurantes" },
    "Saúde": { icon: "#i-heart", color: "#10B981", label: "Saúde & Farmácia" },
    "Poupança": { icon: "#i-piggy", color: "#4ADE80", label: "Depósitos em Poupança" },
    "Outros": { icon: "#i-receipt", color: "#64748B", label: "Outras Despesas" }
};
// Dados financeiros do utilizador: vêm da base de dados (API) e ficam em cache enquanto a sessão está aberta
const financeStore = { expenses: [], goals: [], budgets: {}, loaded: false };

async function loadFinanceData() {
    if (!state.token) return;
    const [expenses, goals, budgets] = await Promise.all([
        apiRequest("GET", "/api/expenses"),
        apiRequest("GET", "/api/savings/goals"),
        apiRequest("GET", "/api/budgets")
    ]);
    financeStore.expenses = expenses;
    financeStore.goals = goals;
    financeStore.budgets = budgets;
    financeStore.loaded = true;
}
function clearFinanceData() {
    financeStore.expenses = [];
    financeStore.goals = [];
    financeStore.budgets = {};
    financeStore.loaded = false;
}
let activeExpenseCategoryFilter = "all";
let currentExpensesMonth = null;          // null = todos os meses, senão "AAAA-MM"
let selectedSpotlightCategory = null;     // categoria em destaque no card do gráfico
let selectedCategoriesForChart = new Set(Object.keys(EXPENSE_CATEGORIES)); // categorias visíveis no donut
let currentCategoryBeingEdited = "Alimentação";
/** Metas habituais por categoria definidas pelo utilizador (só as que existem na base de dados) */
function getCategoryBudgets() {
    return financeStore.budgets;
}
/** Meta mensal da categoria; 0 = o utilizador ainda não definiu nenhuma */
function getCategoryBudget(cat) {
    return Number(financeStore.budgets[cat]) || 0;
}
function getExpenses() {
    return financeStore.expenses;
}

// ==========================================================================
// Helpers partilhados pela página de despesas
// ==========================================================================

/** "1250000" -> "1.250.000 KZ" (sem casas decimais, nunca quebra a meio) */
function fmtKz(n) {
    return formatNumberWithDots(Math.round(Number(n) || 0)) + "\u00a0KZ";
}

/** Chave "AAAA-MM" de uma despesa (lida do texto, sem conversões de fuso) */
function expenseMonthKey(e) {
    return String((e && e.date) || "").slice(0, 7);
}

function monthKeyLabel(key) {
    const [y, m] = String(key).split("-").map(Number);
    if (!y || !m) return key;
    const l = new Date(y, m - 1, 1).toLocaleDateString("pt-AO", { month: "long", year: "numeric" });
    return l.charAt(0).toUpperCase() + l.slice(1);
}

function localISODate(offsetDays = 0) {
    const d = new Date();
    d.setDate(d.getDate() + offsetDays);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Despesas do mês selecionado (ou todas) */
function getPeriodExpenses() {
    const all = getExpenses();
    return currentExpensesMonth ? all.filter(e => expenseMonthKey(e) === currentExpensesMonth) : all;
}

/** Todos os meses disponíveis para escolher, do mais recente para o mais antigo */
function getExpenseMonths() {
    const keys = new Set(getExpenses().map(expenseMonthKey).filter(k => /^\d{4}-\d{2}$/.test(k)));
    // Mês atual + os 5 anteriores (para poder escolher mesmo sem gastos)
    for (let i = 0; i < 6; i++) {
        const d = new Date();
        d.setDate(1);
        d.setMonth(d.getMonth() - i);
        keys.add(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
    }
    try {
        const since = typeof getAccountCreationDate === "function" ? getAccountCreationDate() : null;
        if (since instanceof Date && !isNaN(since)) {
            keys.add(`${since.getFullYear()}-${String(since.getMonth() + 1).padStart(2, "0")}`);
        }
    } catch (e) { /* sem data de criação */ }

    const sorted = [...keys].sort();
    const out = [];
    let [y, m] = sorted[0].split("-").map(Number);
    const [ey, em] = sorted[sorted.length - 1].split("-").map(Number);
    while ((y < ey || (y === ey && m <= em)) && out.length < 60) {
        out.push(`${y}-${String(m).padStart(2, "0")}`);
        m++; if (m > 12) { m = 1; y++; }
    }
    return out.reverse();
}

/** As metas são mensais: em "Todos os meses" multiplicam-se pelos meses com gastos */
function getBudgetFactor() {
    if (currentExpensesMonth) return 1;
    return Math.max(1, new Set(getExpenses().map(expenseMonthKey)).size);
}
