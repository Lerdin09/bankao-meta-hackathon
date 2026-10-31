/**
 * Configuração global
 * URL base da API, taxas de câmbio de referência e tabelas de países/moedas.
 */

const API_BASE = "";
// Tabelas de Taxas de Câmbio & Informação por País
const FX_RATES = {
    "USD_AOA": 1000.0,
    "AOA_USD": 0.001,
    "EUR_AOA": 1050.0,
    "AOA_EUR": 0.000952,
    "EUR_USD": 1.08,
    "USD_EUR": 0.925,
    "USD_USD": 1.0,
    "AOA_AOA": 1.0,
    "EUR_EUR": 1.0
};
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
