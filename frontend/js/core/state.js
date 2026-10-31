/**
 * Estado da aplicação
 * Objeto único `state` com sessão, contas e preferências do utilizador.
 */

// Estado da Aplicação
const state = {
    token: localStorage.getItem("bankao_token") || null,
    user: JSON.parse(localStorage.getItem("bankao_user") || "null"),
    accounts: [],
    accountAoa: null,
    accountEur: null,
    accountUsd: null,
    prefCurrency: localStorage.getItem("bankao_pref_currency") || "AOA",
    currentPendingDepositId: null,
    chatHistory: []
};
