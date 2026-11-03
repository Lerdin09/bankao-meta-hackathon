/**
 * Moedas e contas
 * Conversão entre moedas e acesso às contas por moeda.
 */

function convertMoney(amount, fromCurr, toCurr) {
    const from = (fromCurr || "USD").toUpperCase();
    const to = (toCurr || "AOA").toUpperCase();
    const value = Number(amount) || 0;
    if (from === to) return value;
    // Só usa taxas da base de dados; sem taxa conhecida não há conversão (0)
    const direct = FX_RATES[`${from}_${to}`];
    if (direct !== undefined) return value * direct;
    const inverse = FX_RATES[`${to}_${from}`];
    if (inverse !== undefined && inverse > 0) return value / inverse;
    const viaFrom = FX_RATES[`${from}_USD`] ?? (FX_RATES[`USD_${from}`] > 0 ? 1 / FX_RATES[`USD_${from}`] : undefined);
    const viaTo = FX_RATES[`USD_${to}`] ?? (FX_RATES[`${to}_USD`] > 0 ? 1 / FX_RATES[`${to}_USD`] : undefined);
    if (viaFrom !== undefined && viaTo !== undefined) return value * viaFrom * viaTo;
    return 0;
}
/** "Câmbio: 1 $ = 1.000 KZ" a partir das taxas da base de dados ("" se o par não existir) */
function fxRateLabel(from, to) {
    const r = convertMoney(1, from, to);
    if (!(r > 0)) return "";
    const sym = c => (CURRENCY_INFO[c] ? CURRENCY_INFO[c].symbol : c);
    const txt = r >= 100 ? formatNumberWithDots(Math.round(r)) : String(parseFloat(r.toFixed(4))).replace(".", ",");
    return `Câmbio: 1 ${sym(from)} = ${txt} ${sym(to)}`;
}
function getAccountByCurrency(curr) {
    const c = (curr || "USD").toUpperCase();
    if (c === "USD" && state.accountUsd) return state.accountUsd;
    if (c === "EUR" && state.accountEur) return state.accountEur;
    if (c === "AOA" && state.accountAoa) return state.accountAoa;
    return state.accounts.find(a => a.currency === c) || state.accountAoa || state.accounts[0];
}
