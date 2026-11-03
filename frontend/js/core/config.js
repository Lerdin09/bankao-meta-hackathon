/**
 * Configuração global
 * URL base da API, taxas de câmbio de referência e tabelas de países/moedas.
 */

const API_BASE = "";
// Taxas de câmbio: preenchidas a partir da base de dados (GET /api/fx/rates) por loadFxRates()
const FX_RATES = {};
// Informação por país (dados de referência da interface)
const COUNTRY_INFO = {
    "AO": { name: "Angola", currency: "AOA", currLabel: "KZ", flag: "🇦🇴" },
    "PT": { name: "Portugal", currency: "EUR", currLabel: "EUR", flag: "🇵🇹" },
    "ES": { name: "Espanha", currency: "EUR", currLabel: "EUR", flag: "🇪🇸" },
    "FR": { name: "França", currency: "EUR", currLabel: "EUR", flag: "🇫🇷" },
    "DE": { name: "Alemanha", currency: "EUR", currLabel: "EUR", flag: "🇩🇪" },
    "IT": { name: "Itália", currency: "EUR", currLabel: "EUR", flag: "🇮🇹" },
    "US": { name: "Estados Unidos", currency: "USD", currLabel: "USD", flag: "🇺🇸" },
    "EU": { name: "Europa (SEPA)", currency: "EUR", currLabel: "EUR", flag: "🇪🇺" }
};
const CURRENCY_INFO = {
    "USD": { symbol: "$", flag: "🇺🇸", label: "USD ($)", name: "Dólar" },
    "AOA": { symbol: "KZ", flag: "🇦🇴", label: "AOA (KZ)", name: "Kwanza" },
    "EUR": { symbol: "€", flag: "🇪🇺", label: "EUR (€)", name: "Euro" }
};
