/**
 * Vista: Histórico de pagamentos
 * Filtros por período/mês e lista de compras (view-payments).
 */

// ==========================================================================
// VISTA: HISTÓRICO DE PAGAMENTOS (view-payments)
// "em pagamentos ficariam todas as compras, todo dinheiro que saiu da conta, sem ser transferencia"
// ==========================================================================
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

    // Movimentos de débito do extrato (base de dados) que não sejam transferência
    const realDebits = (state.transactions || []).filter(tx => {
        const isTransfer = tx.type === "transfer_internal" || tx.type === "transfer_iban" || tx.type === "transfer";
        const isOutgoing = tx.amount_minor < 0 || tx.amount_decimal < 0;
        return isOutgoing && !isTransfer;
    }).map(tx => ({
        id: tx.id,
        title: tx.description || "Pagamento",
        category: tx.type === "fx_exchange" ? "Câmbio" : "Pagamento",
        amount: Math.abs(tx.amount_decimal),
        currency: tx.currency || "AOA",
        date: tx.created_at,
        method: "BankAO"
    }));

    const allPurchases = realDebits;

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
    const totalSpent = filtered.reduce((acc, p) => acc + convertMoney(p.amount, p.currency, "AOA"), 0);
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
