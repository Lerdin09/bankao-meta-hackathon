/**
 * Vista: As suas contas
 * Lista de contas e IBANs (view-accounts).
 */

// ==========================================================================
// VISTA: AS SUAS CONTAS (view-accounts)
// ==========================================================================
function renderAccountsView() {
    const aoaAcc = state.accounts ? state.accounts.find(a => a.currency === "AOA") : null;
    const eurAcc = state.accounts ? state.accounts.find(a => a.currency === "EUR") : null;
    const usdAcc = state.accounts ? state.accounts.find(a => a.currency === "USD") : null;

    const elAoaBal = document.getElementById("accViewBalanceAoa");
    const elAoaNum = document.getElementById("accViewNumAoa");
    const elAoaIban = document.getElementById("accViewIbanAoa");
    if (elAoaBal && aoaAcc) {
        elAoaBal.textContent = formatTwoTierMoney(aoaAcc.balance_decimal, "AOA");
        if (elAoaNum) elAoaNum.textContent = groupDigits(aoaAcc.account_number);
        if (elAoaIban) elAoaIban.textContent = groupDigits(aoaAcc.iban_virtual);
    }

    const elEurBal = document.getElementById("accViewBalanceEur");
    const elEurNum = document.getElementById("accViewNumEur");
    const elEurIban = document.getElementById("accViewIbanEur");
    if (elEurBal && eurAcc) {
        elEurBal.textContent = formatTwoTierMoney(eurAcc.balance_decimal, "EUR");
        if (elEurNum) elEurNum.textContent = groupDigits(eurAcc.account_number);
        if (elEurIban) elEurIban.textContent = groupDigits(eurAcc.iban_virtual);
    }

    const elUsdBal = document.getElementById("accViewBalanceUsd");
    const elUsdNum = document.getElementById("accViewNumUsd");
    const elUsdIban = document.getElementById("accViewIbanUsd");
    if (elUsdBal && usdAcc) {
        elUsdBal.textContent = formatTwoTierMoney(usdAcc.balance_decimal, "USD");
        if (elUsdNum) elUsdNum.textContent = groupDigits(usdAcc.account_number);
        if (elUsdIban) elUsdIban.textContent = groupDigits(usdAcc.iban_virtual);
    }

    const elSavBal = document.getElementById("accViewBalanceSavings");
    if (elSavBal) {
        elSavBal.textContent = formatTwoTierMoney(getSavingsTotal(), "AOA");
    }
}
