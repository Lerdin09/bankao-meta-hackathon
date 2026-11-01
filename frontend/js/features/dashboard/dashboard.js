/**
 * Dashboard (início)
 * Carrega contas e extrato da API, desenha os cartões de saldo e o hero do dashboard.
 */

// Carregar Dados das Contas e Extrato
async function loadUserData() {
    if (!state.token) return;

    try {
        // Buscar Contas
        const resAcc = await fetch(`${API_BASE}/api/accounts`, {
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        if (resAcc.status === 401) {
            // Token expirado, limpar sessão
            logout();
            return;
        }
        if (resAcc.ok) {
            state.accounts = await resAcc.json();
            renderAccounts();
            renderAccountsView();
        }

        // Buscar Extrato
        const resTx = await fetch(`${API_BASE}/api/transactions`, {
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        if (resTx.ok) {
            const txs = await resTx.json();
            state.transactions = txs;
            renderTransactions(txs);
            renderPayments();
        }
        renderSavingsView();
        renderExpensesView();
        if (typeof refreshCardChart === "function") refreshCardChart();

        // Preencher seletores de mês a partir da data de criação da conta
        const createdAt = state.user && state.user.created_at ? state.user.created_at : null;
        populateMonthSelect("payMonthSelect", createdAt, "all");
        populateMonthSelect("expMonthSelect", createdAt, "all");
    } catch (err) {
        console.error("Erro ao carregar dados:", err);
    }
}
// Renderizar Cartões de Saldo
function renderAccounts() {
    state.accountAoa = state.accounts.find(a => a.currency === "AOA");
    state.accountEur = state.accounts.find(a => a.currency === "EUR");
    state.accountUsd = state.accounts.find(a => a.currency === "USD");

    if (state.accountAoa) {
        document.getElementById("balanceAoa").innerHTML = `${formatTwoTierMoney(state.accountAoa.balance_decimal, "AOA").replace(" KZ", "")} <span class="curr">KZ</span>`;
        document.getElementById("accNumberAoa").textContent = groupDigits(state.accountAoa.account_number);
        document.getElementById("ibanAoa").textContent = groupDigits(state.accountAoa.iban_virtual);
    }

    if (state.accountEur) {
        document.getElementById("balanceEur").innerHTML = `${formatTwoTierMoney(state.accountEur.balance_decimal, "EUR").replace(" €", "")} <span class="curr">€</span>`;
        document.getElementById("accNumberEur").textContent = groupDigits(state.accountEur.account_number);
        document.getElementById("ibanEur").textContent = groupDigits(state.accountEur.iban_virtual);
    }

    if (state.accountUsd) {
        const balEl = document.getElementById("balanceUsd");
        const accEl = document.getElementById("accNumberUsd");
        const ibanEl = document.getElementById("ibanUsd");
        if (balEl) balEl.innerHTML = `${formatTwoTierMoney(state.accountUsd.balance_decimal, "USD").replace(" $", "")} <span class="curr">$</span>`;
        if (accEl) accEl.textContent = groupDigits(state.accountUsd.account_number);
        if (ibanEl) ibanEl.textContent = groupDigits(state.accountUsd.iban_virtual);
    }

    updateDashboardHero();
    renderAccountsView();
}
// Saudação do início: nome + frase conforme a hora do dia
function updateHomeGreeting(user) {
    const u = user === undefined ? state.user : user;
    const nameEl = document.getElementById("greetingName");
    const lineEl = document.getElementById("greetingLine");
    const hour = new Date().getHours();
    const text = hour < 5 ? "🌙 Boa noite"
        : hour < 12 ? "☀️ Bom dia"
        : hour < 19 ? "🌤️ Boa tarde"
        : "🌙 Boa noite";
    if (lineEl && lineEl.textContent !== text) lineEl.textContent = text;
    if (nameEl) {
        const full = u ? (u.nome || u.primeiro_nome || "Utilizador") : "Visitante";
        const first = String(full).trim().split(/\s+/)[0];
        if (nameEl.textContent !== first) nameEl.textContent = first;
    }
}
// Atualizar Hero Card do Dashboard com Chave, Saldo da moeda de preferência, contas e seletor
function updateDashboardHero() {
    const prefCurr = state.prefCurrency || "AOA";
    const targetAcc = state.accounts ? state.accounts.find(a => a.currency === prefCurr) : null;
    const valEl = document.getElementById("dashPrefBalanceVal");
    const currEl = document.getElementById("dashPrefBalanceCurr");
    const emailEl = document.getElementById("dashAccountEmail");

    if (emailEl) {
        const key = (state.user && state.user.email) ? state.user.email : "conta@bankao.ao";
        emailEl.textContent = key;
        emailEl.title = key;   // se for cortada com "…", o valor completo aparece ao passar o cursor
    }

    if (valEl && currEl) {
        const dec = targetAcc ? targetAcc.balance_decimal : 0;
        if (prefCurr === "AOA") {
            valEl.textContent = formatTwoTierMoney(dec, "AOA").replace(" KZ", "").trim();
            currEl.textContent = "KZ";
        } else if (prefCurr === "USD") {
            valEl.textContent = formatTwoTierMoney(dec, "USD").replace(" $", "").trim();
            currEl.textContent = "$";
        } else if (prefCurr === "EUR") {
            valEl.textContent = formatTwoTierMoney(dec, "EUR").replace(" €", "").trim();
            currEl.textContent = "€";
        }
    }

    // Atualizar Linhas da lista "As suas contas"
    const aoaAcc = state.accounts ? state.accounts.find(a => a.currency === "AOA") : null;
    const rowAoa = document.getElementById("balanceAoaRow");
    if (rowAoa) {
        rowAoa.textContent = aoaAcc ? formatTwoTierMoney(aoaAcc.balance_decimal, "AOA") : "0,00 KZ";
    }

    const rowSavings = document.getElementById("balanceSavingsRow");
    if (rowSavings) {
        rowSavings.textContent = formatTwoTierMoney(getSavingsTotal(), "AOA");
    }

    // Atualizar Widget lateral de saldo se existir
    const widgetAmt = document.getElementById("nbWidgetAmount");
    if (widgetAmt) {
        const dec = targetAcc ? targetAcc.balance_decimal : (aoaAcc ? aoaAcc.balance_decimal : 0);
        widgetAmt.textContent = formatTwoTierMoney(dec, prefCurr);
    }

    // Atualizar estado ativo dos botões de moeda
    document.querySelectorAll(".dash-curr-tag").forEach(tag => {
        tag.classList.toggle("active", tag.getAttribute("data-curr") === prefCurr);
    });
}
// Alternar acordeão de contas e IBANs detalhados
window.toggleWalletsDetail = function() {
    const details = document.getElementById("walletsDetailsToggle");
    if (details) {
        details.open = !details.open;
        if (details.open) {
            details.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }
};
