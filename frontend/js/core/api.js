/**
 * Cliente da API
 * Pedidos autenticados ao backend. Os dados da aplicação vêm todos da base de dados.
 */

async function apiRequest(method, path, body) {
    const headers = {};
    if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const res = await fetch(`${API_BASE}${path}`, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined
    });
    if (res.status === 401 && state.token && typeof logout === "function") {
        logout();
        throw new Error("Sessão expirada.");
    }
    let data = null;
    try { data = await res.json(); } catch (e) { /* sem corpo */ }
    if (!res.ok) {
        const detail = data && data.detail;
        const msg = Array.isArray(detail) ? detail.map(d => d.msg).join("; ") : (detail || `Erro ${res.status}`);
        throw new Error(msg);
    }
    return data;
}

/** Taxas de câmbio de referência, guardadas na base de dados (tabela fx_rates). */
async function loadFxRates() {
    try {
        const rates = await apiRequest("GET", "/api/fx/rates");
        Object.keys(FX_RATES).forEach(k => delete FX_RATES[k]);
        Object.assign(FX_RATES, rates);
    } catch (e) {
        console.error("Não foi possível carregar as taxas de câmbio:", e);
    }
}
