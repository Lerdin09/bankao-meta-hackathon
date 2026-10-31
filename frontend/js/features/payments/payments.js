/**
 * Vista: Histórico de pagamentos
 * Filtros por período/mês e lista de compras (view-payments).
 */

// ==========================================================================
// VISTA: HISTÓRICO DE PAGAMENTOS (view-payments)
// "em pagamentos ficariam todas as compras, todo dinheiro que saiu da conta, sem ser transferencia"
// ==========================================================================
const DEFAULT_PURCHASES = [
    { id: "p1", title: "Maxi Hipermercado Morro Bento", category: "Supermercado", amount: 48500, currency: "AOA", date: "2026-10-28T16:42:00", method: "Multicaixa POS" },
    { id: "p2", title: "Unitel Net Casa Fibra", category: "Telecomunicações", amount: 25000, currency: "AOA", date: "2026-10-25T11:15:00", method: "Multicaixa Express" },
    { id: "p3", title: "Restaurante Miami Beach Ilha", category: "Restauração", amount: 38200, currency: "AOA", date: "2026-10-22T21:30:00", method: "Cartão VISA Virtual" },
    { id: "p4", title: "ZAP Satélite Mensalidade", category: "Entretenimento", amount: 16500, currency: "AOA", date: "2026-10-18T09:10:00", method: "Pagamento por Referência" },
    { id: "p5", title: "Kero Kilamba Compras", category: "Supermercado", amount: 62400, currency: "AOA", date: "2026-10-14T18:05:00", method: "Multicaixa POS" },
    { id: "p6", title: "Yango Viagens Luanda", category: "Transportes", amount: 12500, currency: "AOA", date: "2026-10-10T14:20:00", method: "Cartão VISA Virtual" },
    { id: "p7", title: "Farmácia Luanda Saúde", category: "Saúde & Bem-Estar", amount: 18900, currency: "AOA", date: "2026-10-05T10:45:00", method: "Multicaixa POS" }
];
let currentPaymentsPeriod = "month";
let currentPaymentsMonth = null;
 // null = sem filtro de mês específico

/**
 * Gera um array de opções mês-a-mês desde o mês de criação da conta
 * até ao mês mais avançado encontrado nos dados (ou mês actual).
 */
function buildMonthOptions(sinceDate) {
    const options = [{ value: "all", label: "Todos os meses" }];
    const start = sinceDate ? new Date(sinceDate) : new Date();
    start.setDate(1);
    // Mês final: o actual + 1 para incluir movimentos futuros próximos
    const end = new Date();
    end.setDate(1);
    end.setMonth(end.getMonth() + 1);

    const cur = new Date(start);
    while (cur <= end) {
        const y = cur.getFullYear();
        const m = cur.getMonth();
        const label = cur.toLocaleDateString("pt-AO", { month: "long", year: "numeric" });
        const value = `${y}-${String(m + 1).padStart(2, "0")}`;
        options.push({ value, label: label.charAt(0).toUpperCase() + label.slice(1) });
        cur.setMonth(cur.getMonth() + 1);
    }
    // Ordenar mais recentes primeiro (excepto o "Todos")
    const allOpt = options.shift();
    options.reverse();
    return [allOpt, ...options];
}
function populateMonthSelect(selectId, sinceDate, currentValue) {
    const el = document.getElementById(selectId);
    if (!el) return;
    const opts = buildMonthOptions(sinceDate);
    el.innerHTML = opts.map(o => {
        const sel = o.value === (currentValue || "all") ? " selected" : "";
        return `<option value="${o.value}"${sel}>${escapeHtml(o.label)}</option>`;
    }).join("");
}
function handlePaymentMonthChange(value) {
    currentPaymentsMonth = value === "all" ? null : value;
    // Desactivar filtros de período quando escolhido mês específico
    if (currentPaymentsMonth) {
        document.querySelectorAll(".pay-filter-btn").forEach(btn => btn.classList.remove("active"));
    } else {
        document.querySelectorAll(".pay-filter-btn").forEach(btn =>
            btn.classList.toggle("active", btn.dataset.period === currentPaymentsPeriod));
    }
    renderPayments(currentPaymentsPeriod);
}
window.handlePaymentMonthChange = handlePaymentMonthChange;
function renderPayments(period = currentPaymentsPeriod) {
    currentPaymentsPeriod = period;
    const listEl = document.getElementById("paymentsList");
    if (!listEl) return;

    // Movimentos reais de débito que não sejam transferência
    const realDebits = (state.transactions || []).filter(tx => {
        const isTransfer = tx.type === "transfer_internal" || tx.type === "transfer_iban" || tx.type === "transfer";
        const isOutgoing = tx.amount_minor < 0 || tx.amount_decimal < 0;
        return isOutgoing && !isTransfer;
    }).map(tx => ({
        id: tx.id,
        title: tx.description || "Pagamento Comercial",
        category: "Compras & Serviços",
        amount: Math.abs(tx.amount_decimal),
        currency: tx.currency || "AOA",
        date: tx.created_at,
        method: "BankAO Pay"
    }));

    // Combinar com as compras padrão
    const allPurchases = [...realDebits, ...DEFAULT_PURCHASES];

    // Filtrar pelo mês específico ou pelo período genérico
    const now = new Date();
    const filtered = allPurchases.filter(p => {
        const d = new Date(p.date);
        if (currentPaymentsMonth) {
            const [y, m] = currentPaymentsMonth.split("-").map(Number);
            return d.getFullYear() === y && (d.getMonth() + 1) === m;
        }
        if (period === "all") return true;
        const diffDays = (now - d) / (1000 * 60 * 60 * 24);
        if (period === "month") return diffDays <= 31;
        if (period === "3months") return diffDays <= 92;
        return true;
    });

    // Calcular estatísticas
    const totalSpent = filtered.reduce((acc, p) => acc + p.amount, 0);
    const count = filtered.length;
    const daysInPeriod = currentPaymentsMonth ? new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()
        : (period === "month" ? 30 : period === "3months" ? 90 : 120);
    const avgDay = daysInPeriod > 0 ? (totalSpent / daysInPeriod) : 0;

    const elTotal = document.getElementById("payTotalMonth");
    const elCount = document.getElementById("payCountMonth");
    const elAvg = document.getElementById("payAvgDay");

    if (elTotal) elTotal.textContent = formatTwoTierMoney(totalSpent, "AOA");
    if (elCount) elCount.textContent = `${count} transaç${count === 1 ? "ão" : "ões"}`;
    if (elAvg) elAvg.textContent = formatTwoTierMoney(avgDay, "AOA");

    // Atualizar botões de filtro
    if (!currentPaymentsMonth) {
        document.querySelectorAll(".pay-filter-btn").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.period === period);
        });
    }

    if (filtered.length === 0) {
        listEl.innerHTML = `<div class="empty">Nenhum pagamento registado neste período.</div>`;
        return;
    }

    listEl.innerHTML = filtered.map(p => {
        const d = new Date(p.date);
        const when = d.toLocaleDateString("pt-AO", { day: "2-digit", month: "short" }) + " · " +
                     d.toLocaleTimeString("pt-AO", { hour: "2-digit", minute: "2-digit" });
        return `
            <div class="tx-item">
                <div class="tx-ic debit"><svg><use href="#i-receipt"/></svg></div>
                <div class="tx-main">
                    <div class="tx-title">${escapeHtml(p.title)}</div>
                    <div class="tx-sub">${escapeHtml(p.category)} · ${when}</div>
                </div>
                <div class="tx-side">
                    <span class="tx-amount debit">−${formatTwoTierMoney(p.amount, p.currency)}</span>
                    <span class="status-tag completed">${escapeHtml(p.method)}</span>
                </div>
            </div>`;
    }).join("");
}
// Configurar ouvintes dos filtros de pagamentos
document.querySelectorAll(".pay-filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        currentPaymentsMonth = null; // limpar filtro de mês ao clicar num período
        const sel = document.getElementById("payMonthSelect");
        if (sel) sel.value = "all";
        renderPayments(btn.dataset.period);
    });
});
