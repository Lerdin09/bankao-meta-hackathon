/**
 * Moedas e contas
 * Conversão entre moedas e acesso às contas por moeda.
 */

function convertMoney(amount, fromCurr, toCurr) {
    const from = (fromCurr || "USD").toUpperCase();
    const to = (toCurr || "AOA").toUpperCase();
    if (from === to) return Number(amount) || 0;
    const key = `${from}_${to}`;
    if (FX_RATES[key] !== undefined) return (Number(amount) || 0) * FX_RATES[key];
    const invKey = `${to}_${from}`;
    if (FX_RATES[invKey] !== undefined && FX_RATES[invKey] > 0) return (Number(amount) || 0) / FX_RATES[invKey];
    const fromToUsd = FX_RATES[`${from}_USD`] || (1 / (FX_RATES[`USD_${from}`] || 1));
    const usdToDest = FX_RATES[`USD_${to}`] || (1 / (FX_RATES[`${to}_USD`] || 1));
    return (Number(amount) || 0) * fromToUsd * usdToDest;
}
function getAccountByCurrency(curr) {
    const c = (curr || "USD").toUpperCase();
    if (c === "USD" && state.accountUsd) return state.accountUsd;
    if (c === "EUR" && state.accountEur) return state.accountEur;
    if (c === "AOA" && state.accountAoa) return state.accountAoa;
    return state.accounts.find(a => a.currency === c) || state.accountAoa || state.accounts[0];
}
