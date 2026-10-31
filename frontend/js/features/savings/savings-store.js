/**
 * Poupança — dados
 * Metas de poupança guardadas em localStorage e total poupado.
 */

// ==========================================================================
// VISTA: POUPANÇA E METAS (view-savings)
// "em poupanças vem as metas que o usuario que atingir poupando, ou como está a poupar, aparece todas informações"
// ==========================================================================
const DEFAULT_SAVINGS_GOALS = [
    { id: "g1", name: "Férias em Portugal", target: 50000, saved: 25000, monthly: 2500, deadline: "Junho 2027", iconKey: "travel", status: "on-track" },
    { id: "g2", name: "Fundo de Emergência", target: 100000, saved: 15000, monthly: 5000, deadline: "Dezembro 2026", iconKey: "shield", status: "at-risk" },
    { id: "g3", name: "Computador de Trabalho", target: 30000, saved: 10000, monthly: 1500, deadline: "Março 2027", iconKey: "laptop", status: "on-track" }
];
function getSavingsGoals() {
    try {
        const raw = localStorage.getItem("bankao_savings_goals");
        if (raw) return JSON.parse(raw);
    } catch (e) { /* ignore */ }
    return DEFAULT_SAVINGS_GOALS;
}
function saveSavingsGoals(goals) {
    try {
        localStorage.setItem("bankao_savings_goals", JSON.stringify(goals));
    } catch (e) { /* ignore */ }
}
function getSavingsTotal() {
    const goals = getSavingsGoals();
    return goals.reduce((acc, g) => acc + (Number(g.saved) || 0), 0);
}
