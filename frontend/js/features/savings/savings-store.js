/**
 * Poupança — dados
 * Metas de poupança guardadas na base de dados (API /api/savings). A cache em memória
 * (financeStore.goals) é carregada por loadFinanceData() e atualizada a cada operação.
 */

function getSavingsGoals() {
    return financeStore.goals;
}
function getSavingsTotal() {
    return getSavingsGoals().reduce((acc, g) => acc + (Number(g.saved) || 0), 0);
}
