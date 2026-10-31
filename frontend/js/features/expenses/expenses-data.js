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
const DEFAULT_EXPENSES = [
    { id: "e1", name: "Supermercado Kero Kilamba", category: "Alimentação", amount: 45000, date: "2026-10-29", origin: "manual", notes: "Compras do mês" },
    { id: "e2", name: "Combustível Sonangol Palanca", category: "Transporte", amount: 18000, date: "2026-10-27", origin: "ai", notes: "Gasóleo para a semana" },
    { id: "e3", name: "Renda de Casa & Condomínio", category: "Habitação", amount: 75000, date: "2026-10-25", origin: "manual", notes: "Pagamento mensal" },
    { id: "e4", name: "Unitel Net Casa Fibra", category: "Telecomunicações", amount: 25000, date: "2026-10-22", origin: "ai", notes: "Mensalidade fibra 50Mbps" },
    { id: "e5", name: "Almoço Restaurante Miami Beach", category: "Lazer", amount: 22000, date: "2026-10-19", origin: "manual", notes: "Almoço de domingo com família" },
    { id: "e6", name: "Farmácia Luanda Saúde", category: "Saúde", amount: 9500, date: "2026-10-15", origin: "manual", notes: "Medicamentos e vitaminas" },
    { id: "e7", name: "Yango Táxis Luanda", category: "Transporte", amount: 12500, date: "2026-10-12", origin: "ai", notes: "Deslocações trabalho" },
    { id: "e8", name: "ZAP Satélite Mensalidade", category: "Telecomunicações", amount: 16500, date: "2026-10-08", origin: "manual", notes: "Pacote Max" }
];
let activeExpenseCategoryFilter = "all";
let currentExpensesMonth = null;          // null = todos os meses, senão "AAAA-MM"
let selectedSpotlightCategory = null;     // categoria em destaque no card do gráfico
let selectedCategoriesForChart = new Set(Object.keys(EXPENSE_CATEGORIES)); // categorias visíveis no donut
let currentCategoryBeingEdited = "Alimentação";
const DEFAULT_CATEGORY_BUDGETS = {
    "Alimentação": 45000,
    "Transporte": 25000,
    "Habitação": 80000,
    "Telecomunicações": 25000,
    "Lazer": 20000,
    "Saúde": 15000,
    "Poupança": 30000,
    "Outros": 20000
};
function getCategoryBudgets() {
    try {
        const raw = localStorage.getItem("bankao_category_budgets");
        if (raw) return { ...DEFAULT_CATEGORY_BUDGETS, ...JSON.parse(raw) };
    } catch (e) { /* ignore */ }
    return { ...DEFAULT_CATEGORY_BUDGETS };
}
function saveCategoryBudgets(budgets) {
    try {
        localStorage.setItem("bankao_category_budgets", JSON.stringify(budgets));
    } catch (e) { /* ignore */ }
}
function getExpenses() {
    try {
        const raw = localStorage.getItem("bankao_expenses");
        if (raw) return JSON.parse(raw);
    } catch (e) { /* ignore */ }
    return DEFAULT_EXPENSES;
}
function saveExpenses(expenses) {
    try {
        localStorage.setItem("bankao_expenses", JSON.stringify(expenses));
    } catch (e) { /* ignore */ }
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
