/**
 * BankAO — Lógica da Carteira Digital & Integração com API / Meta Copilot
 * Meta Global AI Developer Hackathon
 */

const API_BASE = "";

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

// Formatação Monetária
function groupDigits(value) {
    const compact = String(value || "").replace(/\s+/g, "");
    return compact.replace(/(.{4})/g, "$1 ").trim();
}

function formatMoney(amount, currency = "AOA") {
    const formatted = new Intl.NumberFormat("pt-AO", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(Number(amount) || 0);

    const cur = (currency || "AOA").toUpperCase();
    if (cur === "AOA" || cur === "KZ") return `${formatted} KZ`;
    if (cur === "EUR") return `${formatted} €`;
    if (cur === "USD") return `${formatted} $`;
    return `${formatted} ${cur}`;
}

function formatTwoTierMoney(amount, currency = "USD") {
    const cur = (currency || "USD").toUpperCase();
    const formatted = new Intl.NumberFormat("pt-AO", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(Number(amount) || 0);

    if (cur === "USD") return `${formatted} $`;
    if (cur === "AOA" || cur === "KZ") return `${formatted} KZ`;
    if (cur === "EUR") return `${formatted} €`;
    return `${formatted} ${cur}`;
}

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

// Inicialização da Aplicação
document.addEventListener("DOMContentLoaded", async () => {
    initTabs();
    initDepositMethodToggle();
    initInternalTransfer();
    initIbanValidation();
    initFxQuoteCalculator();
    initTransferConfirmModalEvents();
    initCopilot();
    initShell();

    // Limpar sessão de conta demo antiga (se existir) — utilizadores devem criar conta própria
    const savedUser = state.user;
    if (savedUser && savedUser.email === 'lerdin.santos@bankao.ao') {
        // Conta demo removida — limpar sessão
        localStorage.removeItem('bankao_token');
        localStorage.removeItem('bankao_user');
        state.token = null;
        state.user  = null;
    }

    // Se já tiver sessão guardada válida, carregar dados; senão mostrar estado visitante
    if (state.token && state.user) {
        updateTopbarUser(state.user);
        await loadUserData();
        // Redirecionar para KYC se pendente
        if (state.user.kyc_status === 'pendente') {
            setTimeout(() => openKYCModal(), 800);
        }
    } else {
        updateTopbarUser(null);
    }

    // Polling suave a cada 15s para atualizar saldos e extrato (só se logado)
    setInterval(() => { if (state.token) loadUserData(); }, 15000);
});

// =====================================================================
//  AUTENTICAÇÃO — Login / Registo / Logout
// =====================================================================

function openAuthModal() {
    const m = document.getElementById('modalAuth');
    m.style.display = 'flex';
    setTimeout(() => m.classList.add('active'), 10);
}
function closeAuthModal() {
    const m = document.getElementById('modalAuth');
    m.classList.remove('active');
    setTimeout(() => m.style.display = 'none', 300);
}

function switchAuthTab(tab) {
    const isLogin = tab === 'login';
    document.getElementById('tabLogin').classList.toggle('active', isLogin);
    document.getElementById('tabRegister').classList.toggle('active', !isLogin);
    document.getElementById('formLogin').style.display = isLogin ? '' : 'none';
    document.getElementById('formRegister').style.display = isLogin ? 'none' : '';
    document.getElementById('loginError').classList.remove('show');
    document.getElementById('registerError').classList.remove('show');
}

function togglePasswordVis(inputId, btn) {
    const inp = document.getElementById(inputId);
    const isNowText = inp.type === 'password';
    inp.type = isNowText ? 'text' : 'password';
    btn.querySelector('.ic-eye').style.display = isNowText ? 'none' : '';
    btn.querySelector('.ic-eye-off').style.display = isNowText ? '' : 'none';
}

async function handleLogin(e) {
    e.preventDefault();
    const errEl = document.getElementById('loginError');
    errEl.classList.remove('show');
    const btn = document.getElementById('btnLoginSubmit');
    btn.disabled = true;
    btn.querySelector('span').textContent = 'A autenticar...';

    try {
        const res = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: document.getElementById('loginEmail').value.trim(),
                password: document.getElementById('loginPassword').value
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Erro ao iniciar sessão.');

        await onAuthSuccess(data);
        closeAuthModal();
    } catch (err) {
        errEl.textContent = err.message;
        errEl.classList.add('show');
    } finally {
        btn.disabled = false;
        btn.querySelector('span').textContent = 'Entrar na minha carteira';
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const errEl = document.getElementById('registerError');
    errEl.classList.remove('show');

    const password = document.getElementById('regPassword').value;
    const confirm  = document.getElementById('regConfirmPassword').value;
    if (password !== confirm) {
        errEl.textContent = 'As palavras-passe não coincidem.';
        errEl.classList.add('show');
        return;
    }
    if (!document.getElementById('regTerms').checked) {
        errEl.textContent = 'Deve aceitar os Termos e Condições.';
        errEl.classList.add('show');
        return;
    }

    const btn = document.getElementById('btnRegisterSubmit');
    btn.disabled = true;
    btn.querySelector('span').textContent = 'A criar conta...';

    try {
        const res = await fetch(`${API_BASE}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: document.getElementById('regEmail').value.trim(),
                telefone: document.getElementById('regPhone').value.trim(),
                password,
                confirm_password: confirm,
                terms_accepted: true
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Erro ao criar conta.');

        await onAuthSuccess(data);
        closeAuthModal();
        // Abre KYC logo após registo
        setTimeout(() => openKYCModal(), 400);
    } catch (err) {
        errEl.textContent = err.message;
        errEl.classList.add('show');
    } finally {
        btn.disabled = false;
        btn.querySelector('span').textContent = 'Criar conta BankAO';
    }
}

async function onAuthSuccess(data) {
    state.token = data.access_token;
    state.user  = data.user;
    localStorage.setItem('bankao_token', state.token);
    localStorage.setItem('bankao_user', JSON.stringify(state.user));
    updateTopbarUser(state.user);
    await loadUserData();
    toast('Sessão iniciada com sucesso! Bem-vindo ao BankAO.', 'success');
}

function logout() {
    state.token = null;
    state.user  = null;
    state.accounts = [];
    state.accountAoa = null;
    state.accountEur = null;
    localStorage.removeItem('bankao_token');
    localStorage.removeItem('bankao_user');
    updateTopbarUser(null);
    toast('Sessão terminada. Até breve!', 'info');
}

function updateTopbarUser(user) {
    const nameEl   = document.getElementById('userNameDisplay');
    const avatarEl = document.getElementById('userAvatar');
    const badgeEl  = document.getElementById('userKycBadge');
    const btnEl    = document.getElementById('btnAuthAction');

    const sideNameEl   = document.getElementById('sidebarUserNameDisplay');
    const sideAvatarEl = document.getElementById('sidebarUserAvatar');
    const sideBadgeEl  = document.getElementById('sidebarUserKycBadge');

    const mobNameEl   = document.getElementById('mobileDrawerUserName');
    const mobAvatarEl = document.getElementById('mobileDrawerAvatar');
    const mobKycEl    = document.getElementById('mobileDrawerKyc');

    if (!user) {
        // Modo visitante: marcar body para esconder elementos desnecessários
        document.body.classList.add('unauthenticated');
        if (nameEl)  nameEl.textContent   = 'Visitante';
        if (avatarEl) avatarEl.textContent = '?';
        if (badgeEl) {
            badgeEl.textContent = '';
            badgeEl.className   = 'kyc-badge';
        }
        if (sideNameEl)   sideNameEl.textContent   = 'Visitante';
        if (sideAvatarEl) sideAvatarEl.textContent = '?';
        if (sideBadgeEl)  sideBadgeEl.textContent  = 'Não autenticado';

        if (mobNameEl)   mobNameEl.textContent   = 'Visitante';
        if (mobAvatarEl) mobAvatarEl.textContent = '?';
        if (mobKycEl)    mobKycEl.textContent    = 'Não autenticado';

        if (btnEl) {
            btnEl.textContent = 'Entrar';
            btnEl.className   = 'btn-auth-action';
            btnEl.onclick     = openAuthModal;
        }
        return;
    }

    // Utilizador autenticado: remover modo visitante
    document.body.classList.remove('unauthenticated');

    const name = user.nome || user.primeiro_nome || 'Utilizador';
    const initials = name.split(' ').filter(Boolean).map(n => n[0]).join('').substring(0, 2).toUpperCase();

    if (nameEl)  nameEl.textContent  = name;
    if (avatarEl) avatarEl.textContent = initials;

    if (sideNameEl)   sideNameEl.textContent   = name;
    if (sideAvatarEl) sideAvatarEl.textContent = initials;

    if (mobNameEl)   mobNameEl.textContent   = name;
    if (mobAvatarEl) mobAvatarEl.textContent = initials;

    // Saudação baseada na hora do dia
    const hour = new Date().getHours();
    const greetEl     = document.getElementById('greetingLine');
    const greetNameEl = document.getElementById('greetingName');
    const greeting = hour < 12 ? '☀️ Bom dia' : hour < 19 ? '🌤️ Boa tarde' : '🌙 Boa noite';
    if (greetEl)     greetEl.textContent     = greeting;
    if (greetNameEl) greetNameEl.textContent = name.split(' ')[0];

    // Badge KYC
    const isVerif = user.kyc_status === 'verificado';
    if (badgeEl) {
        badgeEl.textContent = isVerif ? 'KYC Verificado' : 'KYC Pendente';
        badgeEl.className   = isVerif ? 'kyc-badge verified' : 'kyc-badge pendente';
    }
    if (sideBadgeEl) {
        sideBadgeEl.textContent = isVerif ? 'Cliente Premium' : 'KYC Pendente';
    }
    if (mobKycEl) {
        mobKycEl.textContent = isVerif ? 'Cliente Premium (Verificado)' : 'KYC Pendente';
    }

    // Botão Sair
    if (btnEl) {
        btnEl.textContent = 'Sair';
        btnEl.className   = 'btn-auth-action logout-mode';
        btnEl.onclick     = logout;
    }

    updateDashboardHero();
}


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

// Atualizar Hero Card do Dashboard com Chave, Saldo da moeda de preferência, contas e seletor
function updateDashboardHero() {
    const prefCurr = state.prefCurrency || "AOA";
    const targetAcc = state.accounts ? state.accounts.find(a => a.currency === prefCurr) : null;
    const valEl = document.getElementById("dashPrefBalanceVal");
    const currEl = document.getElementById("dashPrefBalanceCurr");
    const emailEl = document.getElementById("dashAccountEmail");

    if (emailEl) {
        emailEl.textContent = (state.user && state.user.email) ? state.user.email : "conta@bankao.ao";
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

// ==========================================================================
// EXTRATO: INTERVALO DE DATAS + PROCESSAMENTO PROGRESSIVO POR SCROLL
// ==========================================================================
const STATEMENT_PAGE_SIZE = 25;
let statementAllTxs        = [];
let statementFilteredTxs   = [];
let statementRenderedCount = 0;
let statementRangeFrom     = null;  // Date | null
let statementRangeTo       = null;  // Date | null
let statementScrollObserver = null;

/** Converte "YYYY-MM-DD" para Date local ao início do dia */
function parseDateLocal(str) {
    if (!str) return null;
    const parts = str.split("-").map(Number);
    if (parts.length !== 3 || parts.some(isNaN)) return null;
    return new Date(parts[0], parts[1] - 1, parts[2], 0, 0, 0, 0);
}

/** Formata Date para "YYYY-MM-DD" (input[type=date] value) */
function toInputDate(date) {
    if (!date || isNaN(date.getTime())) return "";
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
}

/** Retorna a data de criação da conta do utilizador (ou primeira transação como fallback) */
function getAccountCreationDate() {
    if (state.user && state.user.created_at) {
        const raw = String(state.user.created_at);
        const iso = raw.includes("T") ? raw : raw.replace(" ", "T");
        const d = new Date(iso);
        if (!isNaN(d.getTime())) return d;
    }
    if (statementAllTxs && statementAllTxs.length > 0) {
        const oldest = statementAllTxs[statementAllTxs.length - 1];
        if (oldest && oldest.created_at) {
            const d = new Date(oldest.created_at);
            if (!isNaN(d.getTime())) return d;
        }
    }
    return new Date();
}

function buildTxRow(tx) {
    const date = new Date(tx.created_at);
    const when = date.toLocaleDateString("pt-AO", { day: "2-digit", month: "short" }) + " · " +
                 date.toLocaleTimeString("pt-AO", { hour: "2-digit", minute: "2-digit" });
    const isCredit = (tx.amount_minor > 0) || (tx.amount_decimal > 0);
    const typeLabel = { deposit: "Depósito", transfer_iban: "Envio IBAN", transfer_internal: "Transferência" };
    const label = typeLabel[tx.type] || "Movimento";
    const iconUse = tx.type === "transfer_iban" ? "i-globe" : tx.type === "deposit" ? "i-down" : isCredit ? "i-down" : "i-up";
    const statusMap = { completed: "Concluído", failed: "Falhou" };
    const statusText = statusMap[tx.status] || "Pendente";
    const statusClass = statusMap[tx.status] ? tx.status : "pending";

    return `
        <div class="tx-item">
            <div class="tx-ic ${isCredit ? "credit" : "debit"}"><svg><use href="#${iconUse}"/></svg></div>
            <div class="tx-main">
                <div class="tx-title">${escapeHtml(tx.description || "Operação no BankAO")}</div>
                <div class="tx-sub">${label} · ${when}</div>
            </div>
            <div class="tx-side">
                <span class="tx-amount ${isCredit ? "credit" : "debit"}">${isCredit ? "+" : "−"}${formatMoney(Math.abs(tx.amount_decimal), tx.currency)}</span>
                <span class="status-tag ${statusClass}">${statusText}</span>
            </div>
        </div>`;
}

function applyStatementFilters() {
    statementFilteredTxs = statementAllTxs.filter(tx => {
        const d = new Date(tx.created_at);
        const dayStart = new Date(d.getFullYear(), d.getMonth(), d.getDate());
        if (statementRangeFrom && dayStart < statementRangeFrom) return false;
        if (statementRangeTo) {
            const toEnd = new Date(statementRangeTo);
            toEnd.setHours(23, 59, 59, 999);
            if (d > toEnd) return false;
        }
        return true;
    });
}

function updateStatementActiveBadge() {
    const badge     = document.getElementById("statementActiveBadge");
    const badgeText = document.getElementById("statementActiveBadgeText");
    const btnAll    = document.getElementById("btnSeeAllStatement");

    const hasRange = !!(statementRangeFrom || statementRangeTo);
    if (badge)  badge.style.display = hasRange ? "inline-flex" : "none";
    if (btnAll) btnAll.classList.toggle("active-filter", hasRange);

    if (badgeText && hasRange) {
        const fmt = d => d ? d.toLocaleDateString("pt-AO", { day: "2-digit", month: "short", year: "numeric" }) : "";
        if (statementRangeFrom && statementRangeTo) {
            badgeText.textContent = `${fmt(statementRangeFrom)} → ${fmt(statementRangeTo)}`;
        } else if (statementRangeFrom) {
            badgeText.textContent = `A partir de ${fmt(statementRangeFrom)}`;
        } else if (statementRangeTo) {
            badgeText.textContent = `Até ${fmt(statementRangeTo)}`;
        }
    }
}

function renderStatementBatch() {
    const full = document.getElementById("transactionsList");
    if (!full) return;

    const indicator  = document.getElementById("statementProcessingIndicator");
    const endBadge   = document.getElementById("statementEndBadge");
    const endText    = document.getElementById("statementEndBadgeText");
    const countBadge = document.getElementById("statementCountBadge");

    const slice = statementFilteredTxs.slice(statementRenderedCount, statementRenderedCount + STATEMENT_PAGE_SIZE);

    if (statementRenderedCount === 0) {
        full.innerHTML = "";
        if (statementFilteredTxs.length === 0) {
            full.innerHTML = `<div class="empty">Nenhum movimento encontrado no intervalo selecionado.</div>`;
            if (indicator)  indicator.style.display = "none";
            if (endBadge)   endBadge.style.display  = "flex";
            if (endText)    endText.textContent      = "Nenhum registo para este filtro.";
            if (countBadge) countBadge.textContent   = "0 movimentos";
            return;
        }
    }

    // Separadores visuais por data
    let lastDateStr = statementRenderedCount === 0 ? null
        : new Date(statementFilteredTxs[statementRenderedCount - 1].created_at).toDateString();

    const fragment = document.createDocumentFragment();
    const today     = new Date();
    const yesterday = new Date(); yesterday.setDate(today.getDate() - 1);

    slice.forEach(tx => {
        const d = new Date(tx.created_at);
        const dateStr = d.toDateString();
        if (dateStr !== lastDateStr) {
            const sep = document.createElement("div");
            sep.className = "tx-date-group-header";
            sep.textContent =
                d.toDateString() === today.toDateString()     ? "Hoje"  :
                d.toDateString() === yesterday.toDateString() ? "Ontem" :
                d.toLocaleDateString("pt-AO", { weekday: "long", day: "2-digit", month: "long", year: "numeric" });
            fragment.appendChild(sep);
            lastDateStr = dateStr;
        }
        const wrap = document.createElement("div");
        wrap.innerHTML = buildTxRow(tx).trim();
        while (wrap.firstElementChild) {
            fragment.appendChild(wrap.firstElementChild);
        }
    });
    full.appendChild(fragment);
    statementRenderedCount += slice.length;

    if (countBadge) countBadge.textContent = statementRangeFrom || statementRangeTo
        ? `${statementRenderedCount} / ${statementFilteredTxs.length} movimentos (filtrado)`
        : `${statementRenderedCount} / ${statementFilteredTxs.length} movimentos`;

    if (statementRenderedCount >= statementFilteredTxs.length) {
        if (indicator) indicator.style.display = "none";
        if (endBadge)  endBadge.style.display  = "flex";
        if (endText)   endText.textContent = `${statementFilteredTxs.length} movimento${statementFilteredTxs.length === 1 ? "" : "s"} — livro-razão completo e auditado.`;
        if (statementScrollObserver) statementScrollObserver.disconnect();
    } else {
        if (indicator) indicator.style.display = "flex";
        if (endBadge)  endBadge.style.display  = "none";
    }
}

function initStatementScroll() {
    const sentinel = document.getElementById("statementScrollSentinel");
    if (!sentinel) return;
    if (statementScrollObserver) statementScrollObserver.disconnect();
    statementScrollObserver = new IntersectionObserver(entries => {
        if (entries[0].isIntersecting && statementRenderedCount < statementFilteredTxs.length) {
            renderStatementBatch();
        }
    }, { rootMargin: "300px" });
    statementScrollObserver.observe(sentinel);
}

/**
 * Chamado quando o utilizador navega para o extrato OU quando muda os filtros.
 * Não refaz fetch — usa statementAllTxs já carregado.
 */
function refreshStatement() {
    statementRenderedCount = 0;
    const indicator = document.getElementById("statementProcessingIndicator");
    const endBadge  = document.getElementById("statementEndBadge");
    if (indicator) indicator.style.display = "none";
    if (endBadge)  endBadge.style.display  = "none";
    updateStatementActiveBadge();
    applyStatementFilters();
    renderStatementBatch();
    initStatementScroll();
}

/** Chamado pelo input "De" e "Até" */
function applyStatementDateRange() {
    const fromInp = document.getElementById("statementDateFrom");
    const toInp   = document.getElementById("statementDateTo");
    const fromVal = fromInp?.value;
    const toVal   = toInp?.value;

    const creationDate = getAccountCreationDate();
    const minDay = new Date(creationDate.getFullYear(), creationDate.getMonth(), creationDate.getDate());
    const today = new Date();
    today.setHours(23, 59, 59, 999);

    let parsedFrom = parseDateLocal(fromVal);
    let parsedTo   = parseDateLocal(toVal);

    // Se o utilizador tentar uma data anterior à criação da conta, ajusta para o dia da criação
    if (parsedFrom && parsedFrom < minDay) {
        parsedFrom = minDay;
        if (fromInp) fromInp.value = toInputDate(minDay);
        toast("A data de início não pode ser anterior à criação da sua conta.", "info");
    }

    // Se o utilizador tentar uma data no futuro além de hoje
    if (parsedTo && parsedTo > today) {
        parsedTo = new Date();
        if (toInp) toInp.value = toInputDate(parsedTo);
    }

    // Garantir coerência: "Até" não pode ser anterior a "De"
    if (parsedFrom && parsedTo && parsedTo < parsedFrom) {
        parsedTo = null;
        if (toInp) toInp.value = "";
        toast("A data final não pode ser anterior à data inicial.", "error");
    }

    statementRangeFrom = parsedFrom;
    statementRangeTo   = parsedTo;

    // Atualizar limites recíprocos nos inputs:
    // "De" não pode ultrapassar "Até"
    if (fromInp) {
        fromInp.max = statementRangeTo ? toInputDate(statementRangeTo) : toInputDate(new Date());
    }
    // "Até" não pode ser antes de "De"
    if (toInp) {
        toInp.min = statementRangeFrom ? toInputDate(statementRangeFrom) : toInputDate(minDay);
    }

    refreshStatement();
}
window.applyStatementDateRange = applyStatementDateRange;

/** "Ver tudo" — limpa filtros e repõe os limites padrão dos inputs */
function clearStatementDateFilter() {
    statementRangeFrom = null;
    statementRangeTo   = null;
    const fromInp = document.getElementById("statementDateFrom");
    const toInp   = document.getElementById("statementDateTo");
    if (fromInp) fromInp.value = "";
    if (toInp)   toInp.value   = "";
    initStatementDateRange();
    refreshStatement();
}
window.clearStatementDateFilter = clearStatementDateFilter;

/** Configura os limites dos inputs de data a partir da data de criação da conta */
function initStatementDateRange() {
    const creationDate = getAccountCreationDate();
    const minDateStr = toInputDate(creationDate);
    const maxDateStr = toInputDate(new Date());

    const fromInp = document.getElementById("statementDateFrom");
    const toInp   = document.getElementById("statementDateTo");
    if (fromInp) {
        fromInp.min = minDateStr;
        fromInp.max = statementRangeTo ? toInputDate(statementRangeTo) : maxDateStr;
    }
    if (toInp) {
        toInp.min = statementRangeFrom ? toInputDate(statementRangeFrom) : minDateStr;
        toInp.max = maxDateStr;
    }
}
window.initStatementDateRange = initStatementDateRange;

// Renderizar Movimentos — guarda tudo e atualiza o extrato se visível
function renderTransactions(txs) {
    const recent = document.getElementById("recentTx");

    statementAllTxs = (txs || []).slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    initStatementDateRange();

    // Se o view de extrato estiver activo, atualiza imediatamente
    const stmtView = document.getElementById("view-statement");
    if (stmtView && stmtView.classList.contains("active")) {
        refreshStatement();
    }

    // Recentes no dashboard — sempre os 3 mais recentes
    if (recent) {
        recent.innerHTML = statementAllTxs.length
            ? statementAllTxs.slice(0, 3).map(buildTxRow).join("")
            : `<div class="empty">Nenhuma transação registada ainda.</div>`;
    }
}

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
let currentPaymentsMonth = null; // null = sem filtro de mês específico

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

// ==========================================================================
// VISTA: POUPANÇA E METAS (view-savings)
// "em poupanças vem as metas que o usuario que atingir poupando, ou como está a poupar, aparece todas informações"
// ==========================================================================
const DEFAULT_SAVINGS_GOALS = [
    { id: "g1", name: "Férias em Portugal", target: 50000, saved: 25000, monthly: 2500, deadline: "Junho 2027", icon: "✈️", status: "on-track" },
    { id: "g2", name: "Fundo de Emergência", target: 100000, saved: 15000, monthly: 5000, deadline: "Dezembro 2026", icon: "🏠", status: "at-risk" },
    { id: "g3", name: "Computador de Trabalho", target: 30000, saved: 10000, monthly: 1500, deadline: "Março 2027", icon: "💻", status: "on-track" }
];

function getSavingsGoals() {
    try {
        const raw = localStorage.getItem("bankao_savings_goals");
        if (raw) return JSON.parse(raw);
    } catch (e) { /* ignore */ }
    return DEFAULT_SAVINGS_GOALS;
}

function saveSavingsGoals(goals) {
    try {
        localStorage.setItem("bankao_savings_goals", JSON.stringify(goals));
    } catch (e) { /* ignore */ }
}

function getSavingsTotal() {
    const goals = getSavingsGoals();
    return goals.reduce((acc, g) => acc + (Number(g.saved) || 0), 0);
}

function renderSavingsView() {
    const goals = getSavingsGoals();
    const totalSaved = goals.reduce((acc, g) => acc + (Number(g.saved) || 0), 0);
    const totalTarget = goals.reduce((acc, g) => acc + (Number(g.target) || 0), 0);
    const globalPct = totalTarget > 0 ? Math.min(100, Math.round((totalSaved / totalTarget) * 100)) : 0;

    const elTotal = document.getElementById("savTotalBalance");
    if (elTotal) elTotal.textContent = formatTwoTierMoney(totalSaved, "AOA");

    const elCountBadge = document.getElementById("savGoalCount");
    if (elCountBadge) elCountBadge.textContent = `${goals.length} meta${goals.length === 1 ? "" : "s"} ativa${goals.length === 1 ? "" : "s"}`;

    // Atualizar anel gráfico de progresso SVG
    const ringChart = document.querySelector(".sav-ring-chart circle:nth-child(2)");
    const ringCenterPct = document.querySelector(".sav-ring-center strong");
    if (ringChart) {
        const circumference = 2 * Math.PI * 38; // ~238.76
        const filled = (globalPct / 100) * circumference;
        ringChart.setAttribute("stroke-dasharray", `${filled} ${circumference}`);
    }
    if (ringCenterPct) ringCenterPct.textContent = `${globalPct}%`;

    const listEl = document.getElementById("savGoalsList");
    if (!listEl) return;

    if (goals.length === 0) {
        listEl.innerHTML = `<div class="empty">Nenhuma meta criada ainda. Clique em "Nova meta" para começar!</div>`;
        return;
    }

    listEl.innerHTML = goals.map(g => {
        const pct = g.target > 0 ? Math.min(100, Math.round((g.saved / g.target) * 100)) : 0;
        const statusLabel = g.status === "at-risk" ? "Em risco" : pct >= 100 ? "Concluído" : "No prazo";
        const statusClass = g.status === "at-risk" ? "at-risk" : "on-track";
        const icon = g.icon || "🎯";

        return `
            <div class="sav-goal-card" id="goal_${g.id}">
                <div class="sav-goal-header">
                    <div class="sav-goal-icon">${icon}</div>
                    <div class="sav-goal-info">
                        <strong class="sav-goal-name">${escapeHtml(g.name)}</strong>
                        <span class="sav-goal-date">Prazo: ${escapeHtml(g.deadline)}</span>
                    </div>
                    <div class="sav-goal-actions-group">
                        <div class="sav-goal-status ${statusClass}">${statusLabel}</div>
                        <button type="button" class="sav-btn-icon edit" title="Editar meta de poupança" onclick="openEditGoalModal('${g.id}')">
                            <svg><use href="#i-edit"/></svg>
                        </button>
                        <button type="button" class="sav-btn-icon delete" title="Apagar meta" onclick="deleteSavingsGoal('${g.id}')">
                            <svg><use href="#i-x"/></svg>
                        </button>
                    </div>
                </div>
                <div class="sav-goal-progress-wrap">
                    <div class="sav-goal-vals">
                        <span class="acc-bal-masked">••••••</span>
                        <span class="sav-prog-saved">${formatTwoTierMoney(g.saved, "AOA")} poupados</span>
                        <span class="sav-prog-target">de ${formatTwoTierMoney(g.target, "AOA")}</span>
                    </div>
                    <div class="sav-progress-track">
                        <div class="sav-progress-fill" style="width:${pct}%;background:linear-gradient(90deg,#38BDF8,#6366F1);"></div>
                    </div>
                    <span class="sav-pct">${pct}%</span>
                </div>
                <div class="sav-goal-monthly">
                    <svg><use href="#i-down"/></svg> Contribuição mensal automática: <strong>${formatTwoTierMoney(g.monthly, "AOA")}</strong>
                </div>
            </div>`;
    }).join("");
}

// Modal de Nova Meta
let selectedGoalIcon = "✈️";
let selectedEditGoalIcon = "✈️";

window.openNewGoalModal = function() {
    const m = document.getElementById("modalNewGoal");
    if (m) m.style.display = "flex";
};

window.closeNewGoalModal = function() {
    const m = document.getElementById("modalNewGoal");
    if (m) m.style.display = "none";
};

// Seletor de ícone emoji no modal de meta
document.querySelectorAll("#goalIconPicker .goal-ico-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll("#goalIconPicker .goal-ico-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        selectedGoalIcon = btn.dataset.icon;
    });
});

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("#editGoalIconPicker .goal-ico-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("#editGoalIconPicker .goal-ico-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            selectedEditGoalIcon = btn.dataset.icon;
        });
    });
});

window.handleCreateGoal = function(e) {
    e.preventDefault();
    const name = document.getElementById("goalName")?.value.trim();
    const target = parseCleanNumber(document.getElementById("goalTarget")?.value || "0");
    const monthly = parseCleanNumber(document.getElementById("goalMonthly")?.value || "0");
    const initial = parseCleanNumber(document.getElementById("goalInitial")?.value || "0");
    const deadlineVal = document.getElementById("goalDeadline")?.value;

    if (!name || target <= 0) {
        return toast("Preencha o nome e um valor de meta válido.", "error");
    }

    let deadlineStr = "Indefinido";
    if (deadlineVal) {
        const parts = deadlineVal.split("-");
        if (parts.length === 2) {
            const months = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
            const mIdx = parseInt(parts[1], 10) - 1;
            deadlineStr = `${months[mIdx] || parts[1]} ${parts[0]}`;
        }
    }

    const goals = getSavingsGoals();
    const newGoal = {
        id: "goal_" + Date.now(),
        name,
        target,
        saved: initial,
        monthly,
        deadline: deadlineStr,
        icon: selectedGoalIcon,
        status: "on-track"
    };

    goals.unshift(newGoal);
    saveSavingsGoals(goals);

    closeNewGoalModal();
    document.getElementById("formNewGoal")?.reset();
    renderSavingsView();
    updateDashboardHero();
    toast(`Meta "${name}" criada com sucesso!`, "success");
};

// ============ EDIÇÃO DE METAS DE POUPANÇA ============
window.openEditGoalModal = function(id) {
    const goals = getSavingsGoals();
    const g = goals.find(x => x.id === id);
    if (!g) return toast("Meta não encontrada.", "error");

    const m = document.getElementById("modalEditGoal");
    if (!m) return;

    document.getElementById("editGoalId").value = g.id;
    document.getElementById("editGoalName").value = g.name || "";
    document.getElementById("editGoalTarget").value = g.target || 0;
    document.getElementById("editGoalSaved").value = g.saved || 0;
    document.getElementById("editGoalMonthly").value = g.monthly || 0;
    document.getElementById("editGoalDeadline").value = g.deadline || "";
    const statusSelect = document.getElementById("editGoalStatus");
    if (statusSelect) statusSelect.value = g.status || "on-track";

    selectedEditGoalIcon = g.icon || "✈️";
    document.querySelectorAll("#editGoalIconPicker .goal-ico-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.icon === selectedEditGoalIcon);
    });

    m.style.display = "flex";
};

window.closeEditGoalModal = function() {
    const m = document.getElementById("modalEditGoal");
    if (m) m.style.display = "none";
};

window.handleUpdateGoal = function(e) {
    e.preventDefault();
    const id = document.getElementById("editGoalId")?.value;
    const name = document.getElementById("editGoalName")?.value.trim();
    const target = parseCleanNumber(document.getElementById("editGoalTarget")?.value || "0");
    const saved = parseCleanNumber(document.getElementById("editGoalSaved")?.value || "0");
    const monthly = parseCleanNumber(document.getElementById("editGoalMonthly")?.value || "0");
    const deadline = document.getElementById("editGoalDeadline")?.value.trim() || "Indefinido";
    const status = document.getElementById("editGoalStatus")?.value || "on-track";

    if (!name || target <= 0) {
        return toast("Preencha o nome e um valor de meta válido.", "error");
    }

    const goals = getSavingsGoals();
    const idx = goals.findIndex(x => x.id === id);
    if (idx === -1) return toast("Meta não encontrada.", "error");

    goals[idx] = {
        ...goals[idx],
        name,
        target,
        saved,
        monthly,
        deadline,
        icon: selectedEditGoalIcon,
        status
    };

    saveSavingsGoals(goals);
    closeEditGoalModal();
    renderSavingsView();
    updateDashboardHero();
    toast(`Meta "${name}" atualizada com sucesso!`, "success");
};

window.deleteSavingsGoal = function(id) {
    const goals = getSavingsGoals();
    const filtered = goals.filter(x => x.id !== id);
    saveSavingsGoals(filtered);
    renderSavingsView();
    updateDashboardHero();
    toast("Meta de poupança removida.", "info");
};

// ==========================================================================
// VISTA: DESPESAS E GASTOS COM GRÁFICO DONUT (view-expenses)
// "no lado esquerdo coloque também despesas, onde ira ficar todos tipos de gastos,
// aí será identificada quais despesas foram feitas, tera um grafico donut separando
// cada uma, o cliente que registra os nomes das despesas, ou pede ao assistente para registrar"
// ==========================================================================

const EXPENSE_CATEGORIES = {
    "Alimentação": { icon: "🛒", color: "#38BDF8", label: "Alimentação & Supermercado" },
    "Transporte": { icon: "🚗", color: "#F59E0B", label: "Transporte & Combustível" },
    "Habitação": { icon: "🏠", color: "#818CF8", label: "Habitação & Renda" },
    "Telecomunicações": { icon: "📱", color: "#EC4899", label: "Telecom & Internet" },
    "Lazer": { icon: "🍽️", color: "#A855F7", label: "Lazer & Restaurantes" },
    "Saúde": { icon: "💊", color: "#10B981", label: "Saúde & Farmácia" },
    "Outros": { icon: "📦", color: "#64748B", label: "Outras Despesas" }
};

const DEFAULT_EXPENSES = [
    { id: "e1", name: "Supermercado Kero Kilamba", category: "Alimentação", amount: 45000, date: "2026-10-29", origin: "manual", notes: "Compras do mês" },
    { id: "e2", name: "Combustível Sonangol Palanca", category: "Transporte", amount: 18000, date: "2026-10-27", origin: "ai", notes: "Gasóleo para a semana" },
    { id: "e3", name: "Renda de Casa & Condomínio", category: "Habitação", amount: 75000, date: "2026-10-25", origin: "manual", notes: "Pagamento mensal" },
    { id: "e4", name: "Unitel Net Casa Fibra", category: "Telecomunicações", amount: 25000, date: "2026-10-22", origin: "ai", notes: "Mensalidade fibra 50Mbps" },
    { id: "e5", name: "Almoço Restaurante Miami Beach", category: "Lazer", amount: 22000, date: "2026-10-19", origin: "manual", notes: "Almoço de domingo com família" },
    { id: "e6", name: "Farmácia Luanda Saúde", category: "Saúde", amount: 9500, date: "2026-10-15", origin: "manual", notes: "Medicamentos e vitaminas" },
    { id: "e7", name: "Yango Táxis Luanda", category: "Transporte", amount: 12500, date: "2026-10-12", origin: "ai", notes: "Deslocações trabalho" },
    { id: "e8", name: "ZAP Satélite Mensalidade", category: "Telecomunicações", amount: 16500, date: "2026-10-08", origin: "manual", notes: "Pacote Max" }
];

let activeExpenseCategoryFilter = "all";
let currentExpensesMonth = null; // null = todos
let selectedSpotlightCategory = null; // categoria em destaque no card central
let selectedCategoriesForChart = new Set(Object.keys(EXPENSE_CATEGORIES)); // categorias visíveis no donut
let currentCategoryBeingEdited = "Alimentação";

const DEFAULT_CATEGORY_BUDGETS = {
    "Alimentação": 45000,
    "Transporte": 25000,
    "Habitação": 80000,
    "Telecomunicações": 25000,
    "Lazer": 20000,
    "Saúde": 15000,
    "Outros": 20000
};

function getCategoryBudgets() {
    try {
        const raw = localStorage.getItem("bankao_category_budgets");
        if (raw) return { ...DEFAULT_CATEGORY_BUDGETS, ...JSON.parse(raw) };
    } catch (e) { /* ignore */ }
    return { ...DEFAULT_CATEGORY_BUDGETS };
}

function saveCategoryBudgets(budgets) {
    try {
        localStorage.setItem("bankao_category_budgets", JSON.stringify(budgets));
    } catch (e) { /* ignore */ }
}

function getExpenses() {
    try {
        const raw = localStorage.getItem("bankao_expenses");
        if (raw) return JSON.parse(raw);
    } catch (e) { /* ignore */ }
    return DEFAULT_EXPENSES;
}

function saveExpenses(expenses) {
    try {
        localStorage.setItem("bankao_expenses", JSON.stringify(expenses));
    } catch (e) { /* ignore */ }
}

function handleExpenseMonthChange(value) {
    currentExpensesMonth = value === "all" ? null : value;
    const badge = document.getElementById("expActivePeriodText");
    if (badge) {
        if (currentExpensesMonth) {
            const [y, m] = currentExpensesMonth.split("-").map(Number);
            const label = new Date(y, m - 1, 1).toLocaleDateString("pt-AO", { month: "long", year: "numeric" });
            badge.textContent = label.charAt(0).toUpperCase() + label.slice(1);
        } else {
            badge.textContent = "Todos os meses";
        }
    }
    renderExpensesView();
}
window.handleExpenseMonthChange = handleExpenseMonthChange;

// Controle de categorias no gráfico (selecionáveis)
window.toggleChartCategory = function(cat) {
    if (selectedCategoriesForChart.has(cat)) {
        selectedCategoriesForChart.delete(cat);
        if (selectedSpotlightCategory === cat) {
            selectedSpotlightCategory = null;
        }
    } else {
        selectedCategoriesForChart.add(cat);
        selectedSpotlightCategory = cat;
    }
    renderExpensesView();
};

window.selectAllCategoriesForChart = function(selectAll) {
    if (selectAll) {
        selectedCategoriesForChart = new Set(Object.keys(EXPENSE_CATEGORIES));
    } else {
        selectedCategoriesForChart.clear();
        selectedSpotlightCategory = null;
    }
    renderExpensesView();
};

window.handleDonutCategoryClick = function(cat) {
    if (!selectedCategoriesForChart.has(cat)) {
        selectedCategoriesForChart.add(cat);
    }
    selectedSpotlightCategory = (selectedSpotlightCategory === cat) ? null : cat;
    renderExpensesView();
};

window.resetDonutCategorySelection = function() {
    selectedSpotlightCategory = null;
    renderExpensesView();
};

window.filterListBySpotlightCategory = function() {
    if (!selectedSpotlightCategory) return;
    activeExpenseCategoryFilter = selectedSpotlightCategory;
    document.querySelectorAll(".exp-cat-pill").forEach(b => {
        b.classList.toggle("active", b.dataset.cat === selectedSpotlightCategory);
    });
    renderExpenseItemsList(getExpenses());
    const listEl = document.getElementById("expensesList");
    if (listEl) {
        listEl.scrollIntoView({ behavior: "smooth", block: "start" });
    }
};

// Modais de Orçamento e Assistente
window.openEditCategoryBudgetModal = function(cat) {
    const targetCat = cat || selectedSpotlightCategory || "Alimentação";
    currentCategoryBeingEdited = targetCat;
    const info = EXPENSE_CATEGORIES[targetCat] || { icon: "📦", label: targetCat };
    const budgets = getCategoryBudgets();
    const currentBudget = budgets[targetCat] || 35000;

    const modal = document.getElementById("modalEditCategoryBudget");
    const iconEl = document.getElementById("budgetEditCatIcon");
    const nameEl = document.getElementById("budgetEditCatName");
    const inputEl = document.getElementById("budgetEditInputAmount");

    if (iconEl) iconEl.textContent = info.icon;
    if (nameEl) nameEl.textContent = `${info.icon} ${targetCat}`;
    if (inputEl) inputEl.value = currentBudget;

    if (modal) modal.style.display = "flex";
};

window.closeEditCategoryBudgetModal = function() {
    const modal = document.getElementById("modalEditCategoryBudget");
    if (modal) modal.style.display = "none";
};

window.handleSaveCategoryBudget = function(e) {
    e.preventDefault();
    const inputEl = document.getElementById("budgetEditInputAmount");
    const newBudget = parseCleanNumber(inputEl?.value || "0");
    if (newBudget <= 0) {
        return toast("Indique um montante habitual válido.", "error");
    }

    const budgets = getCategoryBudgets();
    budgets[currentCategoryBeingEdited] = newBudget;
    saveCategoryBudgets(budgets);

    closeEditCategoryBudgetModal();
    renderExpensesView();
    toast(`Meta habitual de ${currentCategoryBeingEdited} atualizada para ${formatMoney(newBudget, "AOA")}!`, "success");
};

window.openExpenseAssistantHelpModal = function() {
    const m = document.getElementById("modalExpenseAssistantHelp");
    if (m) m.style.display = "flex";
};

window.closeExpenseAssistantHelpModal = function() {
    const m = document.getElementById("modalExpenseAssistantHelp");
    if (m) m.style.display = "none";
};

window.startCopilotExpenseConversation = function() {
    closeExpenseAssistantHelpModal();
    const copilotInput = document.getElementById("copilotUserInput");
    const prompt = currentExpensesMonth 
        ? `Copilot, analisa as minhas despesas de ${currentExpensesMonth} e dá-me recomendações práticas para poupar mais.`
        : "Copilot, ajuda-me a analisar todas as minhas despesas e a otimizar o meu orçamento mensal.";

    // Se estiver em ecrã pequeno e Copilot for uma view separada, mudar para a view
    const wide = window.matchMedia("(min-width: 1280px)").matches;
    if (!wide) {
        const copilotNav = document.querySelector('[data-view="view-copilot"]');
        if (copilotNav) copilotNav.click();
    }
    if (copilotInput) {
        copilotInput.value = prompt;
        copilotInput.focus();
    }
};

// Renderização Principal da Tela Análise das Despesas
function renderExpensesView() {
    let allExpenses = getExpenses();

    // 1. Renderizar Seletor de Mês Horizontal no Topo (ocupa toda a parte horizontal)
    renderExpenseMonthPills();

    // 2. Filtrar despesas pelo mês atual se selecionado
    let periodExpenses = allExpenses;
    if (currentExpensesMonth) {
        const [y, m] = currentExpensesMonth.split("-").map(Number);
        periodExpenses = allExpenses.filter(e => {
            const d = new Date(e.date);
            return d.getFullYear() === y && (d.getMonth() + 1) === m;
        });
    }

    // Calcular estatísticas por categoria
    const categoryTotals = {};
    const categoryCounts = {};
    Object.keys(EXPENSE_CATEGORIES).forEach(c => {
        categoryTotals[c] = 0;
        categoryCounts[c] = 0;
    });

    periodExpenses.forEach(e => {
        const cat = EXPENSE_CATEGORIES[e.category] ? e.category : "Outros";
        categoryTotals[cat] = (categoryTotals[cat] || 0) + Number(e.amount || 0);
        categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
    });

    // Total de todas as despesas do período (incluindo desmarcadas)
    const grandTotalPeriod = Object.values(categoryTotals).reduce((a, b) => a + b, 0);

    // Total ativo no gráfico (apenas categorias selecionadas)
    let activeChartTotal = 0;
    let activePurchasesCount = 0;
    selectedCategoriesForChart.forEach(cat => {
        activeChartTotal += (categoryTotals[cat] || 0);
        activePurchasesCount += (categoryCounts[cat] || 0);
    });

    // 2. Renderizar Donut Chart Central Interativo
    renderInteractiveDonutChart(categoryTotals, activeChartTotal, activePurchasesCount);

    // Renderizar Spotlight Card (ao lado/no centro com detalhes da categoria clicada)
    renderDonutSpotlight(categoryTotals, categoryCounts, activeChartTotal);

    // 3. Renderizar Tipos de Despesas (abaixo do gráfico, com barras de progresso, preços e selecionáveis)
    renderSelectableExpenseTypes(categoryTotals, categoryCounts, activeChartTotal, grandTotalPeriod);

    // 4. Atualizar Texto do Card do Assistente
    updateExpenseAssistantCard(categoryTotals, periodExpenses);

    // 5. Renderizar Gastos Organizados no Final
    renderExpenseItemsList(periodExpenses);
}

function renderExpenseMonthPills() {
    const scrollEl = document.getElementById("expMonthPillsScroll");
    if (!scrollEl) return;

    const opts = buildMonthOptions(getAccountCreationDate());
    const currentVal = currentExpensesMonth || "all";

    scrollEl.innerHTML = opts.map(o => {
        const isAct = o.value === currentVal;
        return `
            <button type="button" class="exp-month-pill-btn ${isAct ? 'active' : ''}" 
                onclick="handleExpenseMonthChange('${o.value}')">
                <span>${escapeHtml(o.label)}</span>
            </button>
        `;
    }).join("");
}

function renderInteractiveDonutChart(catTotals, activeTotal, totalPurchases) {
    const svgEl = document.getElementById("expDonutSvg");
    const hubLbl = document.getElementById("expDonutHubLabel");
    const hubVal = document.getElementById("expTotalGastoVal");
    const hubSub = document.getElementById("expTotalCountVal");
    const resetBtn = document.getElementById("btnResetDonutSelection");

    if (resetBtn) {
        resetBtn.style.display = selectedSpotlightCategory ? "inline-flex" : "none";
    }

    if (!svgEl) return;

    const R = 70;
    const C = 2 * Math.PI * R; // ~439.82
    const strokeW = 26;
    const activeStrokeW = 32;

    if (activeTotal <= 0) {
        svgEl.innerHTML = `
            <circle cx="100" cy="100" r="${R}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="${strokeW}"/>
        `;
        if (hubLbl) hubLbl.textContent = "Sem gastos";
        if (hubVal) hubVal.textContent = "0 KZ";
        if (hubSub) hubSub.textContent = "0 compras";
        return;
    }

    let currentOffset = 0;
    let circlesHtml = `
        <circle cx="100" cy="100" r="${R}" fill="none" stroke="rgba(255,255,255,0.04)" stroke-width="${strokeW}"/>
    `;

    // Ordenar categorias ativas pelo valor
    const activeEntries = Object.entries(catTotals)
        .filter(([cat, amt]) => selectedCategoriesForChart.has(cat) && amt > 0)
        .sort((a, b) => b[1] - a[1]);

    activeEntries.forEach(([cat, amt]) => {
        const pct = amt / activeTotal;
        const arc = pct * C;
        const color = (EXPENSE_CATEGORIES[cat] && EXPENSE_CATEGORIES[cat].color) || "#64748B";
        const isSelected = selectedSpotlightCategory === cat;

        circlesHtml += `
            <circle class="exp-donut-arc ${isSelected ? 'is-selected' : ''}" 
                cx="100" cy="100" r="${R}" fill="none" stroke="${color}" 
                stroke-width="${isSelected ? activeStrokeW : strokeW}"
                stroke-dasharray="${arc} ${C - arc}" stroke-dashoffset="${-currentOffset}"
                data-cat="${cat}" onclick="handleDonutCategoryClick('${cat}')"
                style="cursor:pointer; transform-origin:center;"
                role="button" aria-label="${cat}: ${formatTwoTierMoney(amt, 'AOA')} (${Math.round(pct * 100)}%)">
                <title>${cat}: ${formatTwoTierMoney(amt, 'AOA')} (${Math.round(pct * 100)}%) — Toque para detalhes</title>
            </circle>
        `;

        currentOffset += arc;
    });

    svgEl.innerHTML = circlesHtml;

    // Atualizar Hub Central
    if (selectedSpotlightCategory && catTotals[selectedSpotlightCategory] !== undefined) {
        const catAmt = catTotals[selectedSpotlightCategory] || 0;
        if (hubLbl) hubLbl.textContent = selectedSpotlightCategory;
        if (hubVal) hubVal.textContent = formatTwoTierMoney(catAmt, "AOA");
        if (hubSub) hubSub.textContent = `${Math.round((catAmt / activeTotal) * 100)}% do gráfico`;
    } else {
        if (hubLbl) hubLbl.textContent = "Total Ativo";
        if (hubVal) hubVal.textContent = formatTwoTierMoney(activeTotal, "AOA");
        if (hubSub) hubSub.textContent = `${totalPurchases} compra${totalPurchases === 1 ? '' : 's'}`;
    }
}

function renderDonutSpotlight(catTotals, catCounts, activeTotal) {
    const emptyState = document.getElementById("spotlightEmptyState");
    const content = document.getElementById("spotlightContent");
    if (!emptyState || !content) return;

    if (!selectedSpotlightCategory) {
        emptyState.style.display = "block";
        content.style.display = "none";
        return;
    }

    const cat = selectedSpotlightCategory;
    const amt = catTotals[cat] || 0;
    const count = catCounts[cat] || 0;
    const info = EXPENSE_CATEGORIES[cat] || { icon: "📦", color: "#64748B", label: cat };
    const budgets = getCategoryBudgets();
    const normalBudget = budgets[cat] || 35000;

    emptyState.style.display = "none";
    content.style.display = "block";

    const iconWrap = document.getElementById("spotlightIconWrap");
    const nameEl = document.getElementById("spotlightName");
    const shareBadge = document.getElementById("spotlightShareBadge");
    const purchasesCount = document.getElementById("spotlightPurchasesCount");
    const totalSpent = document.getElementById("spotlightTotalSpent");
    const normalSpent = document.getElementById("spotlightNormalSpent");
    const trendBadge = document.getElementById("spotlightTrendBadge");

    if (iconWrap) {
        iconWrap.textContent = info.icon;
        iconWrap.style.background = `${info.color}22`;
        iconWrap.style.borderColor = `${info.color}55`;
    }
    if (nameEl) nameEl.textContent = info.label || cat;

    const sharePct = activeTotal > 0 ? Math.round((amt / activeTotal) * 100) : 0;
    if (shareBadge) {
        shareBadge.textContent = `${sharePct}% do gráfico`;
        shareBadge.style.color = info.color;
        shareBadge.style.borderColor = `${info.color}55`;
        shareBadge.style.background = `${info.color}15`;
    }

    if (purchasesCount) purchasesCount.textContent = `${count} ${count === 1 ? "compra registada" : "compras registadas"}`;
    if (totalSpent) totalSpent.textContent = formatTwoTierMoney(amt, "AOA");
    if (normalSpent) normalSpent.textContent = formatTwoTierMoney(normalBudget, "AOA");

    if (trendBadge) {
        if (amt > normalBudget) {
            const diffPct = Math.round(((amt - normalBudget) / normalBudget) * 100);
            trendBadge.textContent = `+${diffPct}% acima do limite habitual`;
            trendBadge.className = "spotlight-trend-badge danger";
        } else if (amt === 0) {
            trendBadge.textContent = "Sem gastos no período";
            trendBadge.className = "spotlight-trend-badge neutral";
        } else {
            const diffPct = Math.round(((normalBudget - amt) / normalBudget) * 100);
            trendBadge.textContent = `−${diffPct}% dentro da meta (${formatMoney(normalBudget - amt, "AOA")} livres)`;
            trendBadge.className = "spotlight-trend-badge success";
        }
    }
}

function renderSelectableExpenseTypes(catTotals, catCounts, activeTotal, grandTotal) {
    const listEl = document.getElementById("expTypesList");
    if (!listEl) return;

    const entries = Object.entries(catTotals).sort((a, b) => b[1] - a[1]);

    listEl.innerHTML = entries.map(([cat, amt]) => {
        const info = EXPENSE_CATEGORIES[cat] || { icon: "📦", color: "#64748B", label: cat };
        const isSelected = selectedCategoriesForChart.has(cat);
        const isSpotlight = selectedSpotlightCategory === cat;
        const count = catCounts[cat] || 0;
        
        const pct = isSelected && activeTotal > 0 ? Math.round((amt / activeTotal) * 100) : (grandTotal > 0 ? Math.round((amt / grandTotal) * 100) : 0);

        return `
            <div class="exp-type-row ${!isSelected ? 'is-deselected' : ''} ${isSpotlight ? 'is-spotlight' : ''}" id="type_row_${cat}">
                <div class="exp-type-left">
                    <label class="exp-type-checkbox-wrap" title="${isSelected ? 'Desmarcar para retirar do gráfico' : 'Marcar para incluir no gráfico'}">
                        <input type="checkbox" class="exp-type-checkbox" ${isSelected ? 'checked' : ''} onchange="toggleChartCategory('${cat}')">
                        <span class="exp-type-check-custom" style="${isSelected ? `background:${info.color};border-color:${info.color};` : ''}">
                            <svg><use href="#i-check"/></svg>
                        </span>
                    </label>

                    <div class="exp-type-meta" onclick="handleDonutCategoryClick('${cat}')" style="cursor:pointer;" title="Toque para inspecionar no centro">
                        <span class="exp-type-icon" style="background:${info.color}22;border:1px solid ${info.color}44;">${info.icon}</span>
                        <div>
                            <span class="exp-type-name">${cat}</span>
                            <span class="exp-type-count">${count} ${count === 1 ? 'gasto' : 'gastos'}</span>
                        </div>
                    </div>
                </div>

                <div class="exp-type-bar-container" onclick="handleDonutCategoryClick('${cat}')" style="cursor:pointer;">
                    <div class="exp-type-bar-track">
                        <div class="exp-type-bar-fill" style="width:${isSelected ? pct : 0}%;background:${info.color};"></div>
                    </div>
                </div>

                <div class="exp-type-values" onclick="handleDonutCategoryClick('${cat}')" style="cursor:pointer;">
                    <strong class="exp-type-price">${formatTwoTierMoney(amt, "AOA")}</strong>
                    <span class="exp-type-pct ${!isSelected ? 'off' : ''}">${isSelected ? pct + '%' : 'Excluído'}</span>
                </div>
            </div>
        `;
    }).join("");
}

function updateExpenseAssistantCard(catTotals, periodExpenses) {
    const descEl = document.getElementById("expAssistantDesc");
    if (!descEl) return;

    const entries = Object.entries(catTotals).sort((a, b) => b[1] - a[1]);
    const topEntry = entries.find(([_, amt]) => amt > 0);

    if (!topEntry || topEntry[1] === 0) {
        descEl.innerHTML = `Nenhum gasto registado neste período. As suas contas estão intactas e com saldo protegido! Pode usar o campo abaixo para registar qualquer compra ou pagamento.`;
        return;
    }

    const [topCat, topAmt] = topEntry;
    const totalSpent = Object.values(catTotals).reduce((a, b) => a + b, 0);
    const topPct = Math.round((topAmt / (totalSpent || 1)) * 100);
    const budgets = getCategoryBudgets();
    const topBudget = budgets[topCat] || 40000;

    let advice = `Identifiquei os seus padrões de consumo. A maior fatia das suas despesas está concentrada em <strong>${topCat}</strong> com <strong>${formatMoney(topAmt, "AOA")}</strong> (${topPct}% do total). `;

    if (topAmt > topBudget) {
        const excess = topAmt - topBudget;
        advice += `Esta categoria ultrapassou a sua meta habitual em <strong>${formatMoney(excess, "AOA")}</strong>. Recomendo conter novas saídas em ${topCat} até ao encerramento do mês.`;
    } else {
        const remaining = topBudget - topAmt;
        advice += `Excelente controle! Ainda tem <strong>${formatMoney(remaining, "AOA")}</strong> de margem segura antes de atingir a sua média limite.`;
    }

    descEl.innerHTML = advice;
}

function renderExpenseItemsList(allExpenses) {
    const listEl = document.getElementById("expensesList");
    if (!listEl) return;

    const filtered = allExpenses.filter(e => {
        if (activeExpenseCategoryFilter === "all") return true;
        return e.category === activeExpenseCategoryFilter;
    });

    if (filtered.length === 0) {
        listEl.innerHTML = `<div class="empty">Nenhuma despesa encontrada nesta categoria.</div>`;
        return;
    }

    listEl.innerHTML = filtered.map(e => {
        const catInfo = EXPENSE_CATEGORIES[e.category] || { icon: "📦", color: "#64748B" };
        const dateStr = e.date ? new Date(e.date + (e.date.length === 10 ? "T12:00:00" : "")).toLocaleDateString("pt-AO", { day: "2-digit", month: "short", year: "numeric" }) : "Hoje";
        const isAi = e.origin === "ai";

        return `
            <div class="exp-item" id="exp_${e.id}">
                <div class="exp-item-icon" style="background:${catInfo.color}1f;color:${catInfo.color};border:1px solid ${catInfo.color}44;">
                    ${catInfo.icon}
                </div>
                <div class="exp-item-main">
                    <div class="exp-item-title-row">
                        <span class="exp-item-title">${escapeHtml(e.name)}</span>
                        <span class="exp-origin-tag ${isAi ? "ai" : "manual"}">${isAi ? "✨ Copilot IA" : "👤 Registado por si"}</span>
                    </div>
                    <div class="exp-item-sub">${escapeHtml(e.category)} · ${dateStr}${e.notes ? ` · <em>${escapeHtml(e.notes)}</em>` : ""}</div>
                </div>
                <div class="exp-item-side">
                    <span class="exp-item-amount">−${formatTwoTierMoney(e.amount, e.currency || "AOA")}</span>
                    <div class="exp-actions-wrap">
                        <button type="button" class="exp-action-btn edit" title="Editar despesa" onclick="openEditExpenseModal('${e.id}')">
                            <svg><use href="#i-edit"/></svg>
                        </button>
                        <button type="button" class="exp-action-btn delete" title="Apagar despesa" onclick="deleteExpense('${e.id}')">
                            <svg><use href="#i-x"/></svg>
                        </button>
                    </div>
                </div>
            </div>`;
    }).join("");
}

// Ouvintes para os filtros de categoria de despesas
function initExpenseCategoryFilters() {
    document.querySelectorAll(".exp-cat-pill").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".exp-cat-pill").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            activeExpenseCategoryFilter = btn.dataset.cat;
            let all = getExpenses();
            if (currentExpensesMonth) {
                const [y, m] = currentExpensesMonth.split("-").map(Number);
                all = all.filter(e => {
                    const d = new Date(e.date);
                    return d.getFullYear() === y && (d.getMonth() + 1) === m;
                });
            }
            renderExpenseItemsList(all);
        });
    });
}

// Modal Nova Despesa
window.openNewExpenseModal = function() {
    const m = document.getElementById("modalNewExpense");
    if (m) {
        const dateInput = document.getElementById("expDate");
        if (dateInput && !dateInput.value) {
            dateInput.value = new Date().toISOString().split("T")[0];
        }
        m.style.display = "flex";
    }
};

window.closeNewExpenseModal = function() {
    const m = document.getElementById("modalNewExpense");
    if (m) m.style.display = "none";
};

// Modal Editar Despesa
window.openEditExpenseModal = function(id) {
    const expenses = getExpenses();
    const exp = expenses.find(x => x.id === id);
    if (!exp) return toast("Despesa não encontrada.", "error");

    const m = document.getElementById("modalEditExpense");
    if (!m) return;

    document.getElementById("editExpId").value = exp.id;
    document.getElementById("editExpName").value = exp.name || "";
    document.getElementById("editExpCategory").value = exp.category || "Outros";
    document.getElementById("editExpAmount").value = exp.amount || 0;
    document.getElementById("editExpDate").value = exp.date || new Date().toISOString().split("T")[0];
    document.getElementById("editExpNotes").value = exp.notes || "";

    m.style.display = "flex";
};

window.closeEditExpenseModal = function() {
    const m = document.getElementById("modalEditExpense");
    if (m) m.style.display = "none";
};

window.handleUpdateExpense = function(e) {
    e.preventDefault();
    const id = document.getElementById("editExpId")?.value;
    const name = document.getElementById("editExpName")?.value.trim();
    const category = document.getElementById("editExpCategory")?.value || "Outros";
    const amount = parseCleanNumber(document.getElementById("editExpAmount")?.value || "0");
    const date = document.getElementById("editExpDate")?.value || new Date().toISOString().split("T")[0];
    const notes = document.getElementById("editExpNotes")?.value.trim() || "";

    if (!name || amount <= 0) {
        return toast("Indique o nome e o montante válido da despesa.", "error");
    }

    const expenses = getExpenses();
    const idx = expenses.findIndex(x => x.id === id);
    if (idx === -1) return toast("Despesa não encontrada.", "error");

    expenses[idx] = {
        ...expenses[idx],
        name,
        category,
        amount,
        date,
        notes
    };

    saveExpenses(expenses);
    closeEditExpenseModal();
    renderExpensesView();
    toast(`Despesa "${name}" atualizada com sucesso!`, "success");
};

window.handleCreateExpense = function(e) {
    e.preventDefault();
    const name = document.getElementById("expName")?.value.trim();
    const category = document.getElementById("expCategory")?.value || "Outros";
    const amount = parseCleanNumber(document.getElementById("expAmount")?.value || "0");
    const date = document.getElementById("expDate")?.value || new Date().toISOString().split("T")[0];
    const notes = document.getElementById("expNotes")?.value.trim() || "";

    if (!name || amount <= 0) {
        return toast("Indique o nome e o montante válido da despesa.", "error");
    }

    const expenses = getExpenses();
    const newExp = {
        id: "exp_" + Date.now(),
        name,
        category,
        amount,
        currency: "AOA",
        date,
        origin: "manual",
        notes
    };

    expenses.unshift(newExp);
    saveExpenses(expenses);

    closeNewExpenseModal();
    document.getElementById("formNewExpense")?.reset();
    renderExpensesView();
    toast(`Despesa "${name}" de ${formatMoney(amount, "AOA")} registada!`, "success");
};

window.deleteExpense = function(id) {
    const expenses = getExpenses();
    const filtered = expenses.filter(e => e.id !== id);
    saveExpenses(filtered);
    renderExpensesView();
    toast("Despesa removida.", "info");
};

// Registo de despesa via input rápido do Copilot na página de Despesas
window.handleQuickAiExpense = async function(e) {
    e.preventDefault();
    const input = document.getElementById("expQuickAiInput");
    const text = input ? input.value.trim() : "";
    if (!text) return;

    // Detectar montante (ex: 15.000 ou 15000 ou 5000)
    let amount = 0;
    const amtMatch = text.match(/(\d[\d\s.,]*\d|\d+)\s*(?:kz|kwanza|kwanzas|aoa)?/i);
    if (amtMatch) {
        amount = parseCleanNumber(amtMatch[1]);
    }

    // Detectar categoria
    let category = "Outros";
    const textLower = text.toLowerCase();
    if (/supermercado|mercado|comida|almoço|jantar|lanche|restaurante|kero|maxi|candando|alimenta|pão|refeição/i.test(textLower)) {
        category = "Alimentação";
    } else if (/t[aá]xi|yango|uber|combust[ií]vel|gasolina|gas[oó]leo|sonangol|transporte|carro|viagem/i.test(textLower)) {
        category = "Transporte";
    } else if (/renda|casa|energia|luz|ende|água|epal|condom[ií]nio|habita/i.test(textLower)) {
        category = "Habitação";
    } else if (/unitel|zap|dstv|internet|net|saldo|telefone|telecom/i.test(textLower)) {
        category = "Telecomunicações";
    } else if (/praia|festa|cinema|bar|lazer|balada|show/i.test(textLower)) {
        category = "Lazer";
    } else if (/farm[aá]cia|rem[eé]dio|hospital|cl[ií]nica|sa[uú]de|m[eé]dico/i.test(textLower)) {
        category = "Saúde";
    }

    // Extrair descrição limpa
    let cleanName = text.replace(/(?:gastei|comprei|paguei|regista|anota|despesa|gasto|de|\d+[\d.,]*|\bkz\b|\bkwanzas?\b|\bno\b|\bna\b|\bem\b|\bcom\b|\bpara\b)/gi, " ").replace(/\s+/g, " ").trim();
    if (!cleanName || cleanName.length < 3) {
        cleanName = `Gasto em ${category}`;
    }

    if (amount <= 0) {
        amount = 10000;
    }

    const expenses = getExpenses();
    const newExp = {
        id: "exp_ai_" + Date.now(),
        name: cleanName.charAt(0).toUpperCase() + cleanName.slice(1),
        category,
        amount,
        currency: "AOA",
        date: new Date().toISOString().split("T")[0],
        origin: "ai",
        notes: `Identificado pelo Copilot IA a partir de: "${text.substring(0, 35)}..."`
    };

    expenses.unshift(newExp);
    saveExpenses(expenses);

    if (input) input.value = "";
    renderExpensesView();
    toast(`✨ Copilot registou despesa: ${newExp.name} (${formatTwoTierMoney(amount, "AOA")})`, "success");
};

function registerExpenseFromAction(action) {
    if (!action) return;
    const expenses = getExpenses();
    const newExp = {
        id: "exp_copilot_" + Date.now(),
        name: action.name || "Despesa Copilot",
        category: action.category || "Outros",
        amount: Number(action.amount) || 10000,
        currency: action.currency || "AOA",
        date: new Date().toISOString().split("T")[0],
        origin: "ai",
        notes: action.notes || "Registado via Copilot IA"
    };

    expenses.unshift(newExp);
    saveExpenses(expenses);
    renderExpensesView();
    toast(`✨ Copilot registou a sua despesa de ${formatMoney(newExp.amount, newExp.currency)} em ${newExp.category}!`, "success");
}

// Alternância de Abas
function initTabs() {
    const tabs = document.querySelectorAll(".tab-btn");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

            tab.classList.add("active");
            const targetId = tab.getAttribute("data-tab");
            document.getElementById(targetId).classList.add("active");
        });
    });
}

// Alternância do Método de Depósito
function initDepositMethodToggle() {
    const radios = document.querySelectorAll("input[name='depositMethod']");
    radios.forEach(radio => {
        radio.addEventListener("change", (e) => {
            document.querySelectorAll(".method-card").forEach(c => c.classList.remove("active"));
            e.target.closest(".method-card").classList.add("active");

            const isExpress = e.target.value === "express";
            document.getElementById("formDepositExpress").classList.toggle("active", isExpress);
            document.getElementById("formDepositReferencia").classList.toggle("active", !isExpress);
        });
    });

    // Submissão Depósito Multicaixa Express
    document.getElementById("formDepositExpress").addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!state.accountAoa) return toast("Conta AOA não identificada.");

        const amount = parseFloat(document.getElementById("expressAmount").value);
        const phone = document.getElementById("expressPhone").value;

        try {
            const res = await fetch(`${API_BASE}/api/deposits/multicaixa-express`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${state.token}`
                },
                body: JSON.stringify({
                    account_id: state.accountAoa.id,
                    amount: amount,
                    phone_number: phone
                })
            });

            const data = await res.json();
            if (res.ok) {
                state.currentPendingDepositId = data.deposit_id;
                // Exibir Simulador de Smartphone
                document.getElementById("expressSimAmount").textContent = formatMoney(amount, "AOA");
                document.getElementById("expressSimRef").textContent = `Ref: MCX-${data.deposit_id.substring(0, 8).toUpperCase()}`;
                document.getElementById("modalExpressSim").classList.add("active");
            } else {
                toast(data.detail || "Erro ao solicitar depósito.");
            }
        } catch (err) {
            toast("Erro de conexão com o servidor.");
        }
    });

    // Submissão Depósito por Referência
    document.getElementById("formDepositReferencia").addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!state.accountAoa) return toast("Conta AOA não identificada.");

        const amount = parseFloat(document.getElementById("refAmount").value);

        try {
            const res = await fetch(`${API_BASE}/api/deposits/referencia`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${state.token}`
                },
                body: JSON.stringify({
                    account_id: state.accountAoa.id,
                    amount: amount
                })
            });

            const data = await res.json();
            if (res.ok) {
                state.currentPendingDepositId = data.deposit_id;
                document.getElementById("receiptEntidade").textContent = data.entidade;
                document.getElementById("receiptRefCode").textContent = data.referencia;
                document.getElementById("receiptAmount").textContent = formatMoney(amount, "AOA");
                document.getElementById("modalRefSim").classList.add("active");
            } else {
                toast(data.detail || "Erro ao gerar referência.");
            }
        } catch (err) {
            toast("Erro de conexão.");
        }
    });

    // Botões dos Modais de Depósito
    document.getElementById("btnMcxReject").addEventListener("click", () => {
        document.getElementById("modalExpressSim").classList.remove("active");
    });

    document.getElementById("btnMcxApprove").addEventListener("click", async () => {
        if (!state.currentPendingDepositId) return;
        await confirmDepositPayment(state.currentPendingDepositId);
        document.getElementById("modalExpressSim").classList.remove("active");
    });

    document.getElementById("btnCloseRefModal").addEventListener("click", () => {
        document.getElementById("modalRefSim").classList.remove("active");
    });

    document.getElementById("btnSimulateRefPay").addEventListener("click", async () => {
        if (!state.currentPendingDepositId) return;
        await confirmDepositPayment(state.currentPendingDepositId);
        document.getElementById("modalRefSim").classList.remove("active");
    });
}

// Confirmação de Pagamento Simulado
async function confirmDepositPayment(depositId) {
    try {
        const res = await fetch(`${API_BASE}/api/deposits/simulate-payment`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ deposit_id: depositId })
        });
        const data = await res.json();
        if (res.ok) {
            addCopilotMessage("ai", `🎉 **Depósito Confirmado!** O montante de **${formatMoney(data.data.amount_minor / 100, data.data.currency)}** já está disponível e contabilizado no seu livro-razão.`);
            await loadUserData();
        } else {
            toast(data.detail || "Erro ao confirmar pagamento.");
        }
    } catch (err) {
        toast("Erro ao processar confirmação.");
    }
}

// ==========================================================================
// Modal de Confirmação Resumo de Transferência
// ==========================================================================
let pendingTransferExecution = null;

function openTransferConfirmModal({
    type,
    recipientName,
    recipientDest,
    amountSent,
    feePercent,
    feeAmount,
    amountArrive,
    sendCurrency = "USD",
    destCountryCode = "AO",
    destCurrency = "AOA",
    rateNote = "",
    onConfirm
}) {
    const modal = document.getElementById("modalTransferConfirm");
    if (!modal) return;

    document.getElementById("confirmRecipientName").textContent = recipientName || "Beneficiário";
    const initial = (recipientName || "B").trim().charAt(0).toUpperCase();
    document.getElementById("confirmRecipientAvatar").textContent = initial || "👤";
    document.getElementById("confirmRecipientDest").textContent = recipientDest || "";
    
    document.getElementById("confirmTransferTypeBadge").textContent = 
        type === "internal" ? "Transferência de Conta BankAO" : "Transferência Bancária (IBAN)";
    
    // Moeda primária (topo): o que o utilizador escolheu enviar
    document.getElementById("confirmAmountSent").textContent = formatTwoTierMoney(amountSent, sendCurrency);
    document.getElementById("confirmFeeLabel").textContent = `Taxa BankAO (${feePercent}%)`;
    document.getElementById("confirmAmountFee").textContent = `- ${formatTwoTierMoney(feeAmount, sendCurrency)} (${feePercent}%)`;
    document.getElementById("confirmAmountArrive").textContent = formatTwoTierMoney(amountArrive, sendCurrency);

    // Moeda secundária (em baixo): equivalente na moeda do país de destino (ex: AO KZ, PT EUR)
    const sentSub = convertMoney(amountSent, sendCurrency, destCurrency);
    const feeSub = convertMoney(feeAmount, sendCurrency, destCurrency);
    const arriveSub = convertMoney(amountArrive, sendCurrency, destCurrency);
    const countryLabel = `${destCountryCode} ${destCurrency === 'AOA' ? 'KZ' : destCurrency}`;

    const sentSubEl = document.getElementById("confirmAmountSentSub");
    if (sentSubEl) sentSubEl.textContent = `${formatTwoTierMoney(sentSub, destCurrency)} (${countryLabel})`;

    const feeSubEl = document.getElementById("confirmAmountFeeSub");
    if (feeSubEl) feeSubEl.textContent = `- ${formatTwoTierMoney(feeSub, destCurrency)}`;

    const arriveSubEl = document.getElementById("confirmAmountArriveSub");
    if (arriveSubEl) arriveSubEl.textContent = `${formatTwoTierMoney(arriveSub, destCurrency)} (${countryLabel})`;

    const rateNoteEl = document.getElementById("confirmRateNote");
    if (rateNote && rateNote.trim().length > 0) {
        rateNoteEl.textContent = rateNote;
        rateNoteEl.style.display = "block";
    } else {
        rateNoteEl.style.display = "none";
    }

    pendingTransferExecution = onConfirm;

    modal.style.display = "flex";
    modal.classList.add("active");
}

function closeTransferConfirmModal() {
    const modal = document.getElementById("modalTransferConfirm");
    if (modal) {
        modal.style.display = "none";
        modal.classList.remove("active");
    }
    pendingTransferExecution = null;
}

// Inicializar botões do modal de confirmação
function initTransferConfirmModalEvents() {
    const btnClose = document.getElementById("btnCloseConfirmTransfer");
    const btnCancel = document.getElementById("btnCancelTransferConfirm");
    const btnExecute = document.getElementById("btnExecuteTransferConfirm");

    if (btnClose) btnClose.addEventListener("click", closeTransferConfirmModal);
    if (btnCancel) btnCancel.addEventListener("click", closeTransferConfirmModal);

    if (btnExecute) {
        btnExecute.addEventListener("click", async () => {
            if (typeof pendingTransferExecution === "function") {
                const originalHtml = btnExecute.innerHTML;
                btnExecute.disabled = true;
                btnExecute.innerHTML = `<span>A processar...</span>`;
                try {
                    await pendingTransferExecution();
                } catch (err) {
                    console.error("Erro ao executar transferência:", err);
                    toast("Falha na execução da transferência.");
                } finally {
                    btnExecute.disabled = false;
                    btnExecute.innerHTML = originalHtml;
                }
            }
        });
    }
}

// ==========================================================================
// Transferência de Conta (E-mail do Cliente, Taxa 1%, Mínimo 0.01$)
// ==========================================================================
let verifiedInternalRecipient = null;

function initInternalTransfer() {
    const emailInput = document.getElementById("internalDestEmail");
    const amountInput = document.getElementById("internalAmount");
    const sendCurrSelect = document.getElementById("internalSendCurrency");
    const currSymbolBadge = document.getElementById("internalCurrencySymbol");
    const descInput = document.getElementById("internalDesc");
    const form = document.getElementById("formTransferInternal");
    const statusBadge = document.getElementById("recipientLookupStatus");
    const liveNameBox = document.getElementById("internalRecipientLiveName");
    const liveNameText = document.getElementById("recipientLiveNameText");

    const rtSent = document.getElementById("rtInternalSent");
    const rtSentSub = document.getElementById("rtInternalSentSub");
    const rtFee = document.getElementById("rtInternalFee");
    const rtFeeSub = document.getElementById("rtInternalFeeSub");
    const rtArrive = document.getElementById("rtInternalArrive");
    const rtArriveSub = document.getElementById("rtInternalArriveSub");

    const routeFromFlag = document.getElementById("internalRouteFromFlag");
    const routeFrom = document.getElementById("internalRouteFrom");
    const routeToFlag = document.getElementById("internalRouteToFlag");
    const routeTo = document.getElementById("internalRouteTo");
    const routeRate = document.getElementById("internalRouteRate");

    let lookupTimer = null;

    // Atualização em tempo real dos valores e taxa de 1%
    function updateInternalRealtime() {
        const sendCurr = (sendCurrSelect ? sendCurrSelect.value : "USD") || "USD";
        const currMeta = CURRENCY_INFO[sendCurr] || { symbol: "$", flag: "🇺🇸", label: "USD ($)" };
        if (currSymbolBadge) currSymbolBadge.textContent = currMeta.symbol;

        // Moeda de destino nacional: Angola (AOA / KZ)
        const destCurr = sendCurr === "AOA" ? "USD" : "AOA";
        const destLabel = sendCurr === "AOA" ? "INT $" : "AO KZ";

        const amt = parseFloat(amountInput ? amountInput.value : 0) || 0;
        const fee = amt * 0.01; // Taxa de 1%
        const arrive = Math.max(0, amt - fee);

        const amtSub = convertMoney(amt, sendCurr, destCurr);
        const feeSub = convertMoney(fee, sendCurr, destCurr);
        const arriveSub = convertMoney(arrive, sendCurr, destCurr);

        // Linha 1: Moeda escolhida pelo utilizador (topo)
        // Linha 2: Moeda do país de destino (baixo, ex: AO KZ)
        if (rtSent) rtSent.textContent = formatTwoTierMoney(amt, sendCurr);
        if (rtSentSub) rtSentSub.textContent = `${formatTwoTierMoney(amtSub, destCurr)} (${destLabel})`;

        if (rtFee) rtFee.textContent = `- ${formatTwoTierMoney(fee, sendCurr)}`;
        if (rtFeeSub) rtFeeSub.textContent = `- ${formatTwoTierMoney(feeSub, destCurr)}`;

        if (rtArrive) rtArrive.textContent = formatTwoTierMoney(arrive, sendCurr);
        if (rtArriveSub) rtArriveSub.textContent = `${formatTwoTierMoney(arriveSub, destCurr)} (${destLabel})`;

        // Badges da rota
        if (routeFromFlag) routeFromFlag.textContent = currMeta.flag;
        if (routeFrom) routeFrom.textContent = currMeta.label;
        if (routeToFlag) routeToFlag.textContent = "🇦🇴";
        if (routeTo) routeTo.textContent = "Angola (AOA · KZ)";
        if (routeRate) {
            if (sendCurr === "USD") {
                routeRate.textContent = "Câmbio: 1 $ = 1.000 KZ · Instantâneo entre Contas";
            } else if (sendCurr === "EUR") {
                routeRate.textContent = "Câmbio: 1 € = 1.050 KZ · Instantâneo entre Contas";
            } else {
                routeRate.textContent = "Rede Instantânea BankAO Angola";
            }
        }
    }

    if (amountInput) {
        amountInput.addEventListener("input", updateInternalRealtime);
    }
    if (sendCurrSelect) {
        sendCurrSelect.addEventListener("change", updateInternalRealtime);
    }

    // Busca e validação do e-mail do cliente em tempo real
    if (emailInput) {
        emailInput.addEventListener("input", (e) => {
            clearTimeout(lookupTimer);
            const email = e.target.value.trim().toLowerCase();
            if (!email || !email.includes("@") || email.length < 5) {
                if (statusBadge) {
                    statusBadge.textContent = "Verificar";
                    statusBadge.className = "iban-status-badge";
                }
                if (liveNameBox) liveNameBox.style.display = "none";
                verifiedInternalRecipient = null;
                return;
            }

            if (statusBadge) {
                statusBadge.textContent = "A procurar...";
                statusBadge.className = "iban-status-badge";
            }

            lookupTimer = setTimeout(async () => {
                try {
                    const res = await fetch(`${API_BASE}/api/users/lookup?email=${encodeURIComponent(email)}`, {
                        headers: state.token ? { "Authorization": `Bearer ${state.token}` } : {}
                    });
                    if (res.ok) {
                        const data = await res.json();
                        if (data.found) {
                            verifiedInternalRecipient = { name: data.nome, email: data.email };
                            if (statusBadge) {
                                statusBadge.textContent = "Cliente Verificado";
                                statusBadge.className = "iban-status-badge valid";
                            }
                            if (liveNameBox && liveNameText) {
                                liveNameText.textContent = `Titular: ${data.nome}`;
                                liveNameBox.style.display = "inline-flex";
                            }
                        } else {
                            verifiedInternalRecipient = null;
                            if (statusBadge) {
                                statusBadge.textContent = "Não encontrado";
                                statusBadge.className = "iban-status-badge invalid";
                            }
                            if (liveNameBox) liveNameBox.style.display = "none";
                        }
                    }
                } catch (err) {
                    console.error("Erro na busca de usuário:", err);
                }
            }, 300);
        });
    }

    // Ao submeter: abre o ecrã de confirmação detalhado com moeda no topo e país embaixo
    if (form) {
        form.addEventListener("submit", (e) => {
            e.preventDefault();

            const sendCurr = (sendCurrSelect ? sendCurrSelect.value : "USD") || "USD";
            const fromAccount = getAccountByCurrency(sendCurr);

            if (!fromAccount) {
                toast(`Nenhuma carteira em ${sendCurr} encontrada para débito.`);
                return;
            }

            const email = emailInput ? emailInput.value.trim() : "";
            const amount = parseFloat(amountInput ? amountInput.value : 0) || 0;
            const desc = (descInput ? descInput.value.trim() : "") || "Transferência de conta BankAO";

            if (!email || !email.includes("@")) {
                toast("Por favor, insira um e-mail de cliente válido.");
                if (emailInput) emailInput.focus();
                return;
            }

            // Mínimo de 1 centavo (0.01)
            if (amount < 0.01) {
                toast("Quantia mínima para transferência: 0,01.");
                if (amountInput) amountInput.focus();
                return;
            }

            // Validar saldo
            if (fromAccount.balance_decimal < amount) {
                toast(`Saldo insuficiente na sua carteira ${sendCurr} (${formatTwoTierMoney(fromAccount.balance_decimal, sendCurr)} disponível).`);
                return;
            }

            const recipientName = verifiedInternalRecipient ? verifiedInternalRecipient.name : email.split("@")[0];
            const fee = amount * 0.01;
            const arrive = Math.max(0, amount - fee);
            const destCurr = sendCurr === "AOA" ? "USD" : "AOA";

            openTransferConfirmModal({
                type: "internal",
                recipientName: recipientName,
                recipientDest: email,
                amountSent: amount,
                feePercent: 1.0,
                feeAmount: fee,
                amountArrive: arrive,
                sendCurrency: sendCurr,
                destCountryCode: "AO",
                destCurrency: destCurr,
                rateNote: sendCurr === "USD" ? "Câmbio: 1 $ = 1.000 KZ · Transferência instantânea entre contas BankAO" : "Transferência instantânea entre contas BankAO",
                onConfirm: async () => {
                    const idempotencyKey = "tx_int_" + Date.now();
                    const res = await fetch(`${API_BASE}/api/transfers/internal`, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "Authorization": `Bearer ${state.token}`
                        },
                        body: JSON.stringify({
                            from_account_id: fromAccount.id,
                            to_email: email,
                            amount: amount,
                            description: desc,
                            idempotency_key: idempotencyKey
                        })
                    });
                    const data = await res.json();
                    if (res.ok) {
                        toast(`🎉 Transferência para ${recipientName} enviada com sucesso!`);
                        form.reset();
                        updateInternalRealtime();
                        if (liveNameBox) liveNameBox.style.display = "none";
                        if (statusBadge) {
                            statusBadge.textContent = "Verificar";
                            statusBadge.className = "iban-status-badge";
                        }
                        addCopilotMessage("ai", `⚡ **Transferência de Conta Concluída!**\n- Beneficiário: **${recipientName}** (${email})\n- Quantia enviada: **${formatTwoTierMoney(amount, sendCurr)}**\n- Taxa BankAO (1%): **${formatTwoTierMoney(fee, sendCurr)}**\n- Quantia creditada: **${formatTwoTierMoney(arrive, sendCurr)}**`);
                        await loadUserData();
                        closeTransferConfirmModal();
                    } else {
                        toast(data.detail || "Falha na transferência.");
                    }
                }
            });
        });
    }

    updateInternalRealtime();
}

// ==========================================================================
// Validação de IBAN em Tempo Real (Mod 97)
// ==========================================================================
function initIbanValidation() {
    const ibanInput = document.getElementById("ibanInput");
    const statusBadge = document.getElementById("ibanValidationStatus");
    const feedback = document.getElementById("ibanFeedbackText");
    let timer = null;

    if (!ibanInput) return;

    ibanInput.addEventListener("input", (e) => {
        clearTimeout(timer);
        const value = e.target.value.trim();
        if (value.length < 15) {
            if (statusBadge) {
                statusBadge.textContent = "Aguardando";
                statusBadge.className = "iban-status-badge";
            }
            if (feedback) feedback.textContent = "Validado com algoritmo Mod 97 (ISO 7064).";
            return;
        }

        timer = setTimeout(async () => {
            try {
                const res = await fetch(`${API_BASE}/api/iban/validate?iban=${encodeURIComponent(value)}`);
                const data = await res.json();
                if (data.valid) {
                    if (statusBadge) {
                        statusBadge.textContent = `Válido (${data.country})`;
                        statusBadge.className = "iban-status-badge valid";
                    }
                    if (feedback) feedback.textContent = `✅ IBAN de ${data.country === 'PT' ? 'Portugal (SEPA)' : data.country === 'AO' ? 'Angola' : data.country} verificado pelo algoritmo Mod 97.`;
                } else {
                    if (statusBadge) {
                        statusBadge.textContent = "Inválido";
                        statusBadge.className = "iban-status-badge invalid";
                    }
                    if (feedback) feedback.textContent = `❌ Dígitos de controlo matematicamente incorretos. Verifique o número.`;
                }
            } catch (err) {
                console.error(err);
            }
        }, 300);
    });
}

// ==========================================================================
// Transferência Bancária (IBAN, Taxa 2.5%, Mínimo 1$) & Câmbio Dinâmico
// ==========================================================================
function initFxQuoteCalculator() {
    const amountInput = document.getElementById("ibanSendAmount");
    const sendCurrSelect = document.getElementById("ibanSendCurrency");
    const currSymbolBadge = document.getElementById("ibanCurrencySymbol");
    const destCurrSelect = document.getElementById("ibanDestCurrency");
    const ibanInput = document.getElementById("ibanInput");
    const beneficiaryInput = document.getElementById("beneficiaryName");
    const form = document.getElementById("formTransferIban");

    const rtSent = document.getElementById("rtIbanSent");
    const rtSentSub = document.getElementById("rtIbanSentSub");
    const rtFee = document.getElementById("rtIbanFee");
    const rtFeeSub = document.getElementById("rtIbanFeeSub");
    const rtArrive = document.getElementById("rtIbanArrive");
    const rtArriveSub = document.getElementById("rtIbanArriveSub");

    const routeFromFlag = document.getElementById("ibanRouteFromFlag");
    const routeFrom = document.getElementById("ibanRouteFrom");
    const routeToFlag = document.getElementById("ibanRouteToFlag");
    const routeTo = document.getElementById("ibanRouteTo");
    const routeRate = document.getElementById("ibanRouteRate");

    let timer = null;

    // Detectar país e moeda correspondente a partir do IBAN
    function detectCountryFromIban() {
        const raw = (ibanInput ? ibanInput.value : "").replace(/\s+/g, "").toUpperCase();
        if (raw.length >= 2) {
            const cc = raw.substring(0, 2);
            if (cc === "AO") {
                if (destCurrSelect && destCurrSelect.value !== "AOA") destCurrSelect.value = "AOA";
                return "AO";
            } else if (["PT", "ES", "FR", "DE", "IT"].includes(cc)) {
                if (destCurrSelect && destCurrSelect.value !== "EUR") destCurrSelect.value = "EUR";
                return cc;
            } else if (cc === "US") {
                if (destCurrSelect && destCurrSelect.value !== "USD") destCurrSelect.value = "USD";
                return "US";
            }
            return cc;
        }
        // Fallback baseado no select de destino
        const curr = destCurrSelect ? destCurrSelect.value : "AOA";
        return curr === "EUR" ? "PT" : curr === "USD" ? "US" : "AO";
    }

    function updateIbanRealtime() {
        const sendCurr = (sendCurrSelect ? sendCurrSelect.value : "USD") || "USD";
        const currMeta = CURRENCY_INFO[sendCurr] || { symbol: "$", flag: "🇺🇸", label: "USD ($)" };
        if (currSymbolBadge) currSymbolBadge.textContent = currMeta.symbol;

        const destCountryCode = detectCountryFromIban();
        const destCurr = (destCurrSelect ? destCurrSelect.value : "AOA") || "AOA";
        const destInfo = COUNTRY_INFO[destCountryCode] || {
            name: destCountryCode,
            currLabel: destCurr === "AOA" ? "KZ" : destCurr,
            flag: destCountryCode === "AO" ? "🇦🇴" : destCountryCode === "PT" ? "🇵🇹" : "🌐"
        };
        const countryLabel = `${destCountryCode} ${destInfo.currLabel || (destCurr === "AOA" ? "KZ" : destCurr)}`;

        const amount = parseFloat(amountInput ? amountInput.value : 0) || 0;
        const fee = amount * 0.025; // Taxa bancária de 2.5%
        const arrive = Math.max(0, amount - fee);

        // Equivalentes na moeda do país de destino
        const amtSub = convertMoney(amount, sendCurr, destCurr);
        const feeSub = convertMoney(fee, sendCurr, destCurr);
        const arriveSub = convertMoney(arrive, sendCurr, destCurr);

        // Linha 1: Moeda escolhida para enviar (topo)
        // Linha 2: Moeda do país de destino (baixo, ex: AO KZ, PT EUR)
        if (rtSent) rtSent.textContent = formatTwoTierMoney(amount, sendCurr);
        if (rtSentSub) rtSentSub.textContent = `${formatTwoTierMoney(amtSub, destCurr)} (${countryLabel})`;

        if (rtFee) rtFee.textContent = `- ${formatTwoTierMoney(fee, sendCurr)}`;
        if (rtFeeSub) rtFeeSub.textContent = `- ${formatTwoTierMoney(feeSub, destCurr)}`;

        if (rtArrive) rtArrive.textContent = formatTwoTierMoney(arrive, sendCurr);
        if (rtArriveSub) rtArriveSub.textContent = `${formatTwoTierMoney(arriveSub, destCurr)} (${countryLabel})`;

        // Badges da rota
        if (routeFromFlag) routeFromFlag.textContent = currMeta.flag;
        if (routeFrom) routeFrom.textContent = currMeta.label;
        if (routeToFlag) routeToFlag.textContent = destInfo.flag;
        if (routeTo) routeTo.textContent = `${destInfo.name} (${countryLabel})`;

        if (routeRate) {
            if (sendCurr === "USD" && destCurr === "AOA") {
                routeRate.textContent = "Câmbio: 1 $ = 1.000 KZ · Taxa: 2,5% · Rede Bancária";
            } else if (sendCurr === "USD" && destCurr === "EUR") {
                routeRate.textContent = "Câmbio: 1 $ = 0,925 € · Taxa: 2,5% · Rede Bancária SEPA";
            } else if (sendCurr === "EUR" && destCurr === "AOA") {
                routeRate.textContent = "Câmbio: 1 € = 1.050 KZ · Taxa: 2,5% · Rede Bancária";
            } else if (sendCurr === "AOA" && destCurr === "EUR") {
                routeRate.textContent = "Câmbio: 1 € = 1.050 KZ · Taxa: 2,5% · Rede Bancária SEPA";
            } else if (sendCurr === "AOA" && destCurr === "USD") {
                routeRate.textContent = "Câmbio: 1 $ = 1.000 KZ · Taxa: 2,5% · Rede Bancária";
            } else {
                routeRate.textContent = `Taxa Bancária: 2,5% · Rede Internacional / SEPA`;
            }
        }
    }

    if (amountInput) {
        amountInput.addEventListener("input", () => {
            clearTimeout(timer);
            timer = setTimeout(updateIbanRealtime, 150);
        });
    }
    if (sendCurrSelect) {
        sendCurrSelect.addEventListener("change", updateIbanRealtime);
    }
    if (destCurrSelect) {
        destCurrSelect.addEventListener("change", updateIbanRealtime);
    }
    if (ibanInput) {
        ibanInput.addEventListener("input", () => {
            clearTimeout(timer);
            timer = setTimeout(updateIbanRealtime, 200);
        });
    }

    updateIbanRealtime();

    // Botão Pedir Explicação ao Copilot
    const btnAskAi = document.getElementById("btnAskAiExplain");
    if (btnAskAi) {
        btnAskAi.addEventListener("click", async () => {
            const sendCurr = (sendCurrSelect ? sendCurrSelect.value : "USD") || "USD";
            const destCurr = (destCurrSelect ? destCurrSelect.value : "AOA") || "AOA";
            const amount = parseFloat(amountInput ? amountInput.value : 0) || 100;
            const iban = ibanInput ? ibanInput.value.trim() : "AO06 0040 0000 0000 0000 0000 0";
            const beneficiary = beneficiaryInput ? beneficiaryInput.value.trim() : "Beneficiário Internacional";

            addCopilotMessage("user", `Por favor, explica-me os custos e o câmbio para enviar ${formatTwoTierMoney(amount, sendCurr)} para ${beneficiary}.`);

            try {
                const res = await fetch(`${API_BASE}/api/ai/explain-transfer`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        source_amount: amount,
                        source_currency: sendCurr,
                        dest_amount: convertMoney(amount * 0.975, sendCurr, destCurr),
                        dest_currency: destCurr,
                        fx_rate: convertMoney(1, sendCurr, destCurr),
                        fee: amount * 0.025,
                        dest_iban: iban,
                        beneficiary_name: beneficiary
                    })
                });
                const data = await res.json();
                addCopilotMessage("ai", data.explanation);
            } catch (err) {
                addCopilotMessage("ai", "Não foi possível gerar a explicação no momento.");
            }
        });
    }

    // Submissão do Envio para IBAN com tela de Confirmação estilizada
    if (form) {
        form.addEventListener("submit", (e) => {
            e.preventDefault();

            const sendCurr = (sendCurrSelect ? sendCurrSelect.value : "USD") || "USD";
            const fromAccount = getAccountByCurrency(sendCurr);

            if (!fromAccount) {
                toast(`Nenhuma carteira em ${sendCurr} disponível para efetuar o débito.`);
                return;
            }

            const iban = ibanInput ? ibanInput.value.trim() : "";
            const beneficiary = beneficiaryInput ? beneficiaryInput.value.trim() : "";
            const amount = parseFloat(amountInput ? amountInput.value : 0) || 0;
            const destCurr = destCurrSelect ? destCurrSelect.value : "AOA";
            const destCountryCode = detectCountryFromIban();

            if (!iban || iban.length < 15) {
                toast("Por favor, introduza um IBAN válido.");
                if (ibanInput) ibanInput.focus();
                return;
            }
            if (!beneficiary || beneficiary.length < 3) {
                toast("Por favor, introduza o nome completo do titular.");
                if (beneficiaryInput) beneficiaryInput.focus();
                return;
            }
            // Mínimo de 1.00
            if (amount < 1.00) {
                toast("A quantia mínima de transferência bancária é de 1.00.");
                if (amountInput) amountInput.focus();
                return;
            }

            // Validar saldo
            if (fromAccount.balance_decimal < amount) {
                toast(`Saldo insuficiente na sua carteira ${sendCurr} (${formatTwoTierMoney(fromAccount.balance_decimal, sendCurr)} disponível).`);
                return;
            }

            const fee = amount * 0.025;
            const arriveAmount = Math.max(0, amount - fee);
            const rateNote = sendCurr === "USD" && destCurr === "AOA"
                ? "Câmbio: 1 $ = 1.000 KZ · Taxa: 2,5% · Rede Bancária Nacional"
                : `Taxa: 2,5% · Rede de Liquidação Bancária (${destCountryCode})`;

            openTransferConfirmModal({
                type: "iban",
                recipientName: beneficiary,
                recipientDest: iban,
                amountSent: amount,
                feePercent: 2.5,
                feeAmount: fee,
                amountArrive: arriveAmount,
                sendCurrency: sendCurr,
                destCountryCode: destCountryCode,
                destCurrency: destCurr,
                rateNote: rateNote,
                onConfirm: async () => {
                    const idempotencyKey = "tx_iban_" + Date.now();
                    const res = await fetch(`${API_BASE}/api/transfers/iban`, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "Authorization": `Bearer ${state.token}`
                        },
                        body: JSON.stringify({
                            from_account_id: fromAccount.id,
                            to_iban: iban,
                            beneficiary_name: beneficiary,
                            amount: amount,
                            dest_currency: destCurr,
                            idempotency_key: idempotencyKey
                        })
                    });

                    const data = await res.json();
                    if (res.ok) {
                        toast(`Sucesso! Envio bancário de ${formatTwoTierMoney(amount, sendCurr)} para ${beneficiary} processado.`);
                        form.reset();
                        updateIbanRealtime();
                        addCopilotMessage("ai", `🌍 **Transferência Bancária Concluída!**\n- Titular: **${beneficiary}**\n- IBAN: \`${iban}\`\n- Quantia enviada: **${formatTwoTierMoney(amount, sendCurr)}**\n- Taxa bancária (2.5%): **${formatTwoTierMoney(fee, sendCurr)}**\n- Creditado ao destino: **${data.dest_amount_decimal} ${destCurr}**`);
                        await loadUserData();
                        closeTransferConfirmModal();
                    } else {
                        toast(data.detail || "Erro na transferência para IBAN.");
                    }
                }
            });
        });
    }
}

// Inicialização do BankAO AI Copilot
function initCopilot() {
    const inputForm = document.getElementById("copilotInputForm");
    const userInput = document.getElementById("copilotUserInput");

    inputForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (!message) return;

        addCopilotMessage("user", message);
        userInput.value = "";

        // Enviar para o backend com Meta Model API
        const typing = showTyping();
        try {
            const res = await fetch(`${API_BASE}/api/ai/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: message,
                    history: state.chatHistory
                })
            });
            const data = await res.json();
            typing.remove();
            
            // Exibir resposta da IA com o card de ação se houver
            addCopilotMessage("ai", data.reply, data.action);

            // Se a IA gerou uma ação de transferência/depósito, pré-preencher o painel imediatamente
            if (data.action) {
                applyCopilotAction(data.action, true);
            }
        } catch (err) {
            typing.remove();
            addCopilotMessage("ai", "Desculpe, ocorreu uma instabilidade ao conectar ao modelo da Meta.");
        }
    });

    // Botões de Perguntas Rápidas
    document.querySelectorAll(".quick-prompt-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const prompt = btn.getAttribute("data-prompt");
            userInput.value = prompt;
            inputForm.dispatchEvent(new Event("submit"));
        });
    });
}

// Executar Ação Preparada pelo Copilot (Abrir painel, preencher campos e destacar confirmação)
function applyCopilotAction(action, autoSwitch = true) {
    if (!action) return;

    if (action.type === "TRANSFER_IBAN") {
        if (autoSwitch && window.showView && window.showTab) {
            window.showTab("tab-transfer-iban");
            window.showView("view-ops");
        }

        const ibanInput = document.getElementById("ibanInput");
        const beneficiaryInput = document.getElementById("beneficiaryName");
        const amountInput = document.getElementById("ibanSendAmount");
        const sendCurrSelect = document.getElementById("ibanSendCurrency");
        const submitBtn = document.getElementById("btnSubmitIban");
        const form = document.getElementById("formTransferIban");

        if (sendCurrSelect && action.currency) {
            sendCurrSelect.value = action.currency;
            sendCurrSelect.dispatchEvent(new Event("change"));
        }
        if (ibanInput) {
            ibanInput.value = action.to_iban || "";
            ibanInput.dispatchEvent(new Event("input"));
        }
        if (beneficiaryInput) {
            beneficiaryInput.value = action.beneficiary_name || "";
        }
        if (amountInput) {
            amountInput.value = action.amount || 100;
            amountInput.dispatchEvent(new Event("input"));
        }

        // Atualizar painel de explicação e detalhamento do Copilot
        const aiBox = document.getElementById("aiTransferHelperBox");
        const aiText = document.getElementById("aiTransferSummaryText");
        if (aiText) {
            aiText.innerHTML = `<strong>✨ Transferência preparada pelo Copilot:</strong><br>` +
                `• <strong>Beneficiário:</strong> ${escapeHtml(action.beneficiary_name)} (${action.country_name || action.country_code})<br>` +
                `• <strong>Quantia a debitar:</strong> ${formatMoney(action.amount, action.currency)}<br>` +
                `• <strong>Taxa de serviço (${action.fee_percent || 2.5}%):</strong> ${formatMoney(action.fee_amount || (action.amount * 0.025), action.currency)}<br>` +
                `• <strong>Valor líquido a receber:</strong> <span class="text-success" style="font-weight:700;">${formatMoney(action.net_amount || (action.amount * 0.975), action.currency)}</span>`;
        }
        if (aiBox) {
            aiBox.classList.add("action-prefilled-active");
        }

        // Destaque visual pulsante no formulário e foco no botão Confirmar
        if (form) {
            form.classList.remove("form-highlight-pulse");
            void form.offsetWidth;
            form.classList.add("form-highlight-pulse");
        }
        if (submitBtn) {
            submitBtn.classList.add("btn-highlight-pulse");
            submitBtn.scrollIntoView({ behavior: "smooth", block: "center" });
        }

        toast(`✨ Transferência para ${action.beneficiary_name} preenchida! Clique em Confirmar e enviar.`, "success");
    } else if (action.type === "TRANSFER_INTERNAL") {
        if (autoSwitch && window.showView && window.showTab) {
            window.showTab("tab-transfer-internal");
            window.showView("view-ops");
        }
        const emailInput = document.getElementById("internalDestEmail");
        const amtInput = document.getElementById("internalAmount");
        const sendCurrSelect = document.getElementById("internalSendCurrency");
        const descInput = document.getElementById("internalDesc");
        const submitBtn = document.getElementById("btnSubmitInternal");
        const form = document.getElementById("formTransferInternal");

        if (sendCurrSelect && action.currency) {
            sendCurrSelect.value = action.currency;
            sendCurrSelect.dispatchEvent(new Event("change"));
        }
        if (emailInput) {
            emailInput.value = action.to_email || action.to_account_number || "";
            emailInput.dispatchEvent(new Event("input"));
        }
        if (amtInput) {
            amtInput.value = action.amount || "";
            amtInput.dispatchEvent(new Event("input"));
        }
        if (descInput) {
            descInput.value = `Transferência Copilot para ${action.beneficiary_name || "cliente"}`;
        }
        if (form) {
            form.classList.remove("form-highlight-pulse");
            void form.offsetWidth;
            form.classList.add("form-highlight-pulse");
        }
        if (submitBtn) {
            submitBtn.classList.add("btn-highlight-pulse");
            submitBtn.scrollIntoView({ behavior: "smooth", block: "center" });
        }

        toast(`✨ Transferência interna preparada! Clique em Confirmar transferência.`, "success");
    } else if (action.type === "DEPOSIT_EXPRESS") {
        if (autoSwitch && window.showView && window.showTab) {
            window.showTab("tab-deposit");
            window.showView("view-ops");
        }
        const phoneInput = document.getElementById("expressPhone");
        const amtInput = document.getElementById("expressAmount");
        const submitBtn = document.getElementById("btnSubmitExpress");

        if (phoneInput) phoneInput.value = action.phone_number || "";
        if (amtInput) amtInput.value = action.amount || "";
        if (submitBtn) submitBtn.classList.add("btn-highlight-pulse");

        toast(`✨ Depósito Express preparado! Clique para solicitar aprovação.`, "success");
    } else if (action.type === "REGISTER_EXPENSE") {
        registerExpenseFromAction(action);
    }
}

// Adicionar Mensagem no Chat do Copilot (com suporte a Action Cards interativos)
function addCopilotMessage(sender, text, action = null) {
    const chatContainer = document.getElementById("copilotChatMessages");
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${sender}`;

    const avatar = sender === "ai" ? `<svg><use href="#i-spark"/></svg>` : "Eu";
    // Escapar HTML e aplicar markdown básico (negrito, itálico, quebras de linha)
    const formatted = escapeHtml(String(text ?? ""))
        .replace(/\n\n/g, "<br><br>")
        .replace(/\n/g, "<br>")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>");

    bubble.innerHTML = `
        <div class="bubble-avatar">${avatar}</div>
        <div class="bubble-content">
            <p>${formatted}</p>
        </div>
    `;

    // Se houver um Action Card estruturado, renderizar dentro da bolha da IA
    if (action && action.type === "TRANSFER_IBAN") {
        const actionCard = document.createElement("div");
        actionCard.className = "copilot-action-card";
        actionCard.innerHTML = `
            <div class="action-card-header">
                <span class="action-badge">🤖 Operação Pronta</span>
                <span class="country-pill">${action.country_name || action.country_code}</span>
            </div>
            <div class="action-summary-grid">
                <div class="action-grid-row">
                    <span class="act-label">Beneficiário</span>
                    <strong class="act-val">${escapeHtml(action.beneficiary_name)}</strong>
                </div>
                <div class="action-grid-row">
                    <span class="act-label">IBAN de Destino</span>
                    <span class="act-val mono">${escapeHtml(action.to_iban)}</span>
                </div>
                <div class="action-grid-row">
                    <span class="act-label">Quantia</span>
                    <span class="act-val">${formatMoney(action.amount, action.currency)}</span>
                </div>
                <div class="action-grid-row">
                    <span class="act-label">Taxa (2%)</span>
                    <span class="act-val text-warning">${formatMoney(action.fee_amount || (action.amount * 0.02), action.currency)}</span>
                </div>
                <div class="action-grid-row highlight-net">
                    <span class="act-label">Quanto vai (Líquido)</span>
                    <strong class="act-val text-success">${formatMoney(action.net_amount || (action.amount * 0.98), action.currency)}</strong>
                </div>
            </div>
            <div class="action-card-btn-wrap">
                <button type="button" class="btn btn-sm btn-action-confirm">
                    <span>Revisar no Painel & Confirmar</span>
                    <svg><use href="#i-arrow-right"/></svg>
                </button>
            </div>
        `;

        const btnConfirm = actionCard.querySelector(".btn-action-confirm");
        btnConfirm.addEventListener("click", () => {
            applyCopilotAction(action, true);
        });

        bubble.querySelector(".bubble-content").appendChild(actionCard);
    } else if (action && action.type === "REGISTER_EXPENSE") {
        const actionCard = document.createElement("div");
        actionCard.className = "copilot-action-card";
        actionCard.innerHTML = `
            <div class="action-card-header">
                <span class="action-badge">📊 Despesa Registada</span>
                <span class="country-pill">${escapeHtml(action.category || "Gasto")}</span>
            </div>
            <div class="action-summary-grid">
                <div class="action-grid-row">
                    <span class="act-label">Estabelecimento/Nome</span>
                    <strong class="act-val">${escapeHtml(action.name || "Despesa")}</strong>
                </div>
                <div class="action-grid-row">
                    <span class="act-label">Valor do Gasto</span>
                    <strong class="act-val debit" style="color:#FB7185;">−${formatTwoTierMoney(action.amount, action.currency || "AOA")}</strong>
                </div>
            </div>
            <div class="action-card-btn-wrap">
                <button type="button" class="btn btn-sm btn-outline" style="width:100%;margin-top:6px;" onclick="showView('view-expenses')">
                    <span>Ver Gráfico Donut de Despesas →</span>
                </button>
            </div>
        `;
        bubble.querySelector(".bubble-content").appendChild(actionCard);
    }

    chatContainer.appendChild(bubble);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // Guardar no histórico
    state.chatHistory.push({
        role: sender === "ai" ? "assistant" : "user",
        content: text
    });
}

function showTyping() {
    const chatContainer = document.getElementById("copilotChatMessages");
    const el = document.createElement("div");
    el.className = "chat-bubble ai";
    el.innerHTML = `<div class="bubble-avatar"><svg><use href="#i-spark"/></svg></div><div class="bubble-content"><span class="typing"><i></i><i></i><i></i></span></div>`;
    chatContainer.appendChild(el);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return el;
}

// Utilitários de interface
function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function toast(message, type) {
    const stack = document.getElementById("toastStack");
    if (!stack) return;
    const kind = type || (/sucesso|enviada|confirmado|copiado/i.test(message) ? "success" : "error");
    const el = document.createElement("div");
    el.className = `toast ${kind}`;
    el.setAttribute("role", "status");
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 260); }, 4200);
}

// Navegação entre vistas, atalhos, saldos ocultos, copiar IBAN
function initShell() {
    const wide = window.matchMedia("(min-width: 1280px)");

    function showView(id) {
        // No ecrã largo o Copilot está sempre visível ao lado
        if (id === "view-copilot" && wide.matches) {
            document.getElementById("copilotUserInput").focus();
            return;
        }
        document.querySelectorAll(".views > .view").forEach(v => v.classList.toggle("active", v.id === id));
        document.querySelectorAll("[data-view]").forEach(b => b.classList.toggle("active", b.dataset.view === id));
        window.scrollTo({ top: 0, behavior: "smooth" });
        if (id === "view-accounts") renderAccountsView();
        if (id === "view-payments") renderPayments();
        if (id === "view-expenses") renderExpensesView();
        if (id === "view-savings") renderSavingsView();
        if (id === "view-statement") {
            initStatementDateRange();
            refreshStatement();
        }
        if (id === "view-copilot") {
            const box = document.getElementById("copilotChatMessages");
            box.scrollTop = box.scrollHeight;
        }
    }

    // Scroll progressivo contínuo ao descer a página no Extrato
    window.addEventListener("scroll", () => {
        const stmt = document.getElementById("view-statement");
        if (stmt && stmt.classList.contains("active") && statementRenderedCount < statementFilteredTxs.length) {
            const scrollBottom = window.innerHeight + window.scrollY;
            if (scrollBottom >= document.documentElement.scrollHeight - 400) {
                renderStatementBatch();
            }
        }
    }, { passive: true });

    initExpenseCategoryFilters();

    function showTab(tabId) {
        document.querySelectorAll(".tab-btn").forEach(t => t.classList.toggle("active", t.dataset.tab === tabId));
        document.querySelectorAll(".tab-pane").forEach(p => p.classList.toggle("active", p.id === tabId));
    }

    window.showView = showView;
    window.showTab = showTab;

    window.toggleMobileMenu = function() {
        const overlay = document.getElementById("mobileMenuOverlay");
        if (!overlay) return;
        const isHidden = overlay.style.display === "none" || !overlay.style.display;
        overlay.style.display = isHidden ? "flex" : "none";
        document.body.style.overflow = isHidden ? "hidden" : "";
    };

    window.closeMobileMenu = function() {
        const overlay = document.getElementById("mobileMenuOverlay");
        if (overlay) overlay.style.display = "none";
        document.body.style.overflow = "";
    };

    window.mobileNavTo = function(viewId) {
        window.closeMobileMenu();
        showView(viewId);
    };

    document.querySelectorAll("[data-view]").forEach(btn => btn.addEventListener("click", () => showView(btn.dataset.view)));
    document.querySelectorAll("[data-goto]").forEach(btn => btn.addEventListener("click", () => {
        if (btn.dataset.gotoTab) showTab(btn.dataset.gotoTab);
        showView(btn.dataset.goto);
    }));
    document.getElementById("btnToggleCopilot").addEventListener("click", () => showView("view-copilot"));

    // Ocultar / mostrar saldos — SEMPRE começa oculto por padrão
    document.body.classList.add("balances-hidden");
    function toggleBalancesVisibility() {
        document.body.classList.toggle("balances-hidden");
    }
    const btnEyeTop = document.getElementById("btnToggleBalance");
    if (btnEyeTop) btnEyeTop.addEventListener("click", toggleBalancesVisibility);
    const btnEyeDash = document.getElementById("btnToggleDashBalance");
    if (btnEyeDash) btnEyeDash.addEventListener("click", toggleBalancesVisibility);

    // Seletor de moeda de preferência no Dashboard Hero
    document.querySelectorAll(".dash-curr-tag").forEach(tag => {
        tag.addEventListener("click", () => {
            const curr = tag.getAttribute("data-curr");
            state.prefCurrency = curr;
            localStorage.setItem("bankao_pref_currency", curr);
            updateDashboardHero();
        });
    });

    // Copiar chave da conta (e-mail)
    const btnCopyKey = document.getElementById("btnCopyDashEmail");
    if (btnCopyKey) {
        btnCopyKey.addEventListener("click", async () => {
            const email = document.getElementById("dashAccountEmail")?.textContent.trim();
            if (email && email !== "carregando...") {
                try { await navigator.clipboard.writeText(email); } catch (e) { /* ignore */ }
                toast("Chave da conta copiada: " + email, "success");
            }
        });
    }

    // Copiar conta / IBAN com um toque
    document.querySelectorAll(".copyable").forEach(el => el.addEventListener("click", async () => {
        const text = el.textContent.trim();
        try { await navigator.clipboard.writeText(text); } catch (e) { /* ignorar */ }
        el.classList.add("copied");
        setTimeout(() => el.classList.remove("copied"), 1200);
    }));

    // Fechar modais ao tocar fora
    document.querySelectorAll(".modal-overlay").forEach(m => m.addEventListener("click", e => {
        if (e.target === m && !m.classList.contains('kyc-overlay')) {
            m.classList.remove("active");
            if (m.id === "modalReceiveQr") closeReceiveQrModal();
            else setTimeout(() => { m.style.display = "none"; }, 250);
        }
    }));
}

// =====================================================================
//  MODAL: RECEBER TRANSFERÊNCIA / CÓDIGO QR & CHAVE DA CONTA
// =====================================================================

function buildBankAoQrSvg(payload) {
    const N = 29;
    const grid = Array.from({ length: N }, () => Array(N).fill(0));

    function fillRect(r0, c0, h, w, val) {
        for (let r = r0; r < r0 + h; r++) {
            for (let c = c0; c < c0 + w; c++) {
                if (r >= 0 && r < N && c >= 0 && c < N) grid[r][c] = val;
            }
        }
    }

    function drawFinder(r0, c0) {
        fillRect(r0, c0, 7, 7, 1);
        fillRect(r0 + 1, c0 + 1, 5, 5, 0);
        fillRect(r0 + 2, c0 + 2, 3, 3, 1);
    }

    drawFinder(0, 0);
    drawFinder(0, 22);
    drawFinder(22, 0);

    fillRect(7, 0, 1, 8, 0);
    fillRect(0, 7, 8, 1, 0);
    fillRect(7, 21, 1, 8, 0);
    fillRect(0, 21, 8, 1, 0);
    fillRect(21, 0, 1, 8, 0);
    fillRect(21, 7, 8, 1, 0);

    for (let i = 8; i < 21; i++) {
        grid[6][i] = (i % 2 === 0) ? 1 : 0;
        grid[i][6] = (i % 2 === 0) ? 1 : 0;
    }

    fillRect(20, 20, 5, 5, 1);
    fillRect(21, 21, 3, 3, 0);
    grid[22][22] = 1;

    let hash = 0x811c9dc5;
    for (let i = 0; i < payload.length; i++) {
        hash ^= payload.charCodeAt(i);
        hash = Math.imul(hash, 0x01000193);
    }

    function pseudoRandom() {
        hash = (hash ^ (hash << 13)) >>> 0;
        hash = (hash ^ (hash >> 17)) >>> 0;
        hash = (hash ^ (hash << 5)) >>> 0;
        return (hash & 0xFF) / 255;
    }

    for (let r = 0; r < N; r++) {
        for (let c = 0; c < N; c++) {
            if (r <= 7 && c <= 7) continue;
            if (r <= 7 && c >= 21) continue;
            if (r >= 21 && c <= 7) continue;
            if (r === 6 || c === 6) continue;
            if (r >= 20 && r <= 24 && c >= 20 && c <= 24) continue;
            if (r >= 11 && r <= 17 && c >= 11 && c <= 17) continue;
            grid[r][c] = (pseudoRandom() > 0.48) ? 1 : 0;
        }
    }

    const cellSize = 6;
    const padding = 9;
    const totalSize = N * cellSize + padding * 2;

    let paths = "";
    for (let r = 0; r < N; r++) {
        for (let c = 0; c < N; c++) {
            if (grid[r][c] === 1) {
                const x = padding + c * cellSize;
                const y = padding + r * cellSize;
                paths += `<rect x="${x}" y="${y}" width="${cellSize}" height="${cellSize}" fill="#0A1128"/>`;
            }
        }
    }

    return `<svg viewBox="0 0 ${totalSize} ${totalSize}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;background:#FFF;border-radius:8px;">${paths}</svg>`;
}

function renderReceiveQr(dataString) {
    const container = document.getElementById("qrCanvasContainer");
    if (!container) return;

    const encodedData = encodeURIComponent(dataString);
    const qrApiUrl = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodedData}&format=svg`;

    container.innerHTML = `
        <img id="qrRealImg" src="${qrApiUrl}" alt="Código QR BankAO" width="192" height="192"
             onerror="this.style.display='none'; document.getElementById('qrFallbackSvgWrap').style.display='block';">
        <div id="qrFallbackSvgWrap" style="display:none;width:192px;height:192px;">
            ${buildBankAoQrSvg(dataString)}
        </div>
        <div class="qr-canvas-badge">
            <span>B</span>
        </div>
    `;
}

function openReceiveQrModal() {
    const m = document.getElementById("modalReceiveQr");
    if (!m) return;

    const user = state.user || {};
    const name = user.nome || user.email?.split("@")[0] || "Cliente BankAO";
    const email = user.email || "cliente@bankao.ao";
    const aoaAcc = state.accountAoa || (state.accounts && state.accounts.find(a => a.currency === "AOA")) || null;
    const iban = aoaAcc ? groupDigits(aoaAcc.iban_virtual) : "AO06 0055 0000 0000 0000 0000 0";

    const nameEl = document.getElementById("qrModalUserName");
    const emailEl = document.getElementById("qrModalUserEmail");
    const ibanEl = document.getElementById("qrModalUserIban");
    const avatarEl = document.getElementById("qrModalUserAvatar");
    const statusEl = document.getElementById("qrModalUserStatus");

    if (nameEl) nameEl.textContent = name;
    if (emailEl) emailEl.textContent = email;
    if (ibanEl) ibanEl.textContent = iban;
    if (avatarEl) {
        const initials = name.split(" ").map(w => w[0]).filter(Boolean).slice(0, 2).join("").toUpperCase();
        avatarEl.textContent = initials || "B";
    }
    if (statusEl) {
        statusEl.textContent = (user.kyc_status === "verificado") ? "Conta Verificada BankAO" : "Conta Ativa BankAO";
    }

    const qrPayload = `BANKAO:PAY?email=${encodeURIComponent(email)}&name=${encodeURIComponent(name)}&iban=${encodeURIComponent(aoaAcc ? aoaAcc.iban_virtual : '')}&account=${encodeURIComponent(aoaAcc ? aoaAcc.account_number : '')}`;
    renderReceiveQr(qrPayload);

    m.style.display = "flex";
    setTimeout(() => m.classList.add("active"), 10);
}
window.openReceiveQrModal = openReceiveQrModal;

function closeReceiveQrModal() {
    const m = document.getElementById("modalReceiveQr");
    if (m) {
        m.classList.remove("active");
        setTimeout(() => m.style.display = "none", 250);
    }
}
window.closeReceiveQrModal = closeReceiveQrModal;

async function copyQrAccountEmail() {
    const email = document.getElementById("qrModalUserEmail")?.textContent.trim();
    if (email && email !== "carregando...") {
        try { await navigator.clipboard.writeText(email); } catch (e) { /* ignore */ }
        toast("Chave copiada: " + email, "success");
    }
}
window.copyQrAccountEmail = copyQrAccountEmail;

async function copyQrAccountIban() {
    const iban = document.getElementById("qrModalUserIban")?.textContent.trim();
    if (iban && iban !== "carregando...") {
        try { await navigator.clipboard.writeText(iban); } catch (e) { /* ignore */ }
        toast("IBAN copiado: " + iban, "success");
    }
}
window.copyQrAccountIban = copyQrAccountIban;

async function shareQrDetails() {
    const name = document.getElementById("qrModalUserName")?.textContent.trim();
    const email = document.getElementById("qrModalUserEmail")?.textContent.trim();
    const iban = document.getElementById("qrModalUserIban")?.textContent.trim();

    const fullInfo = 
`🏦 Dados para Transferência BankAO
• Titular: ${name}
• Chave (E-mail): ${email}
• IBAN (AOA): ${iban}
• Instituição: BankAO Digital`;

    try {
        if (navigator.clipboard) {
            await navigator.clipboard.writeText(fullInfo);
            toast("✅ Dados completos copiados para partilhar!", "success");
        } else {
            toast("Chave copiada: " + email, "success");
        }
    } catch (err) {
        toast("Chave copiada: " + email, "success");
    }
}
window.shareQrDetails = shareQrDetails;

// =====================================================================
//  KYC — Verificação de Identidade por IA (4 Passos)
// =====================================================================

const kycState = {
    docType: null,
    fotoFrente: null,
    fotoVerso: null,
    extracted: null
};

function openKYCModal() {
    kycState.docType = null;
    kycState.fotoFrente = null;
    kycState.fotoVerso = null;
    kycState.extracted = null;
    // Reset visual
    ['optBI','optPassaporte'].forEach(id => document.getElementById(id).classList.remove('selected'));
    document.getElementById('btnKycStep1Next').disabled = true;
    document.getElementById('btnKycStep2Next').disabled = true;
    resetPhotoZone('frente');
    resetPhotoZone('verso');
    // Reset progress dots
    for (let i = 1; i <= 4; i++) {
        const d = document.getElementById(`kycStepDot${i}`);
        d.classList.remove('active','done');
    }
    document.getElementById('kycStepDot1').classList.add('active');

    const m = document.getElementById('modalKYC');
    m.style.display = 'flex';
    setTimeout(() => m.classList.add('active'), 10);
    kycShowPanel(1);
}

function closeKYCModal() {
    const m = document.getElementById('modalKYC');
    m.classList.remove('active');
    setTimeout(() => m.style.display = 'none', 300);
}

function kycShowPanel(n) {
    for (let i = 1; i <= 4; i++) {
        document.getElementById(`kycPanel${i}`).style.display = i === n ? '' : 'none';
    }
}

function kycUpdateStepDots(currentStep) {
    for (let i = 1; i <= 4; i++) {
        const d = document.getElementById(`kycStepDot${i}`);
        d.classList.remove('active','done');
        if (i < currentStep) d.classList.add('done');
        else if (i === currentStep) d.classList.add('active');
    }
}

function selectDocType(type) {
    kycState.docType = type;
    document.getElementById('optBI').classList.toggle('selected', type === 'bilhete');
    document.getElementById('optPassaporte').classList.toggle('selected', type === 'passaporte');
    document.getElementById('btnKycStep1Next').disabled = false;

    // Adaptar rótulos do passo 2
    const isPassaporte = type === 'passaporte';
    document.getElementById('kycUploadTitle').textContent = isPassaporte ? 'Fotografias do Passaporte' : 'Fotografias do Bilhete de Identidade';
    document.getElementById('kycUploadDesc').textContent = isPassaporte
        ? 'Tire ou carregue fotografias da página de dados (com foto) e da página de assinatura.'
        : 'Tire ou carregue fotografias da frente e do verso do Bilhete de Identidade.';
    document.getElementById('labelFrente').textContent = isPassaporte ? 'Página de dados (com foto)' : 'Frente do BI';
    document.getElementById('labelVerso').textContent = isPassaporte ? 'Página de assinatura' : 'Verso do BI';
    document.getElementById('kycDocNumLabel').textContent = isPassaporte ? 'N.º do Passaporte' : 'NIF / N.º do Bilhete';
}

async function kycGoToStep(step) {
    if (step === 3) {
        // Validar fotos antes de avançar
        if (!kycState.fotoFrente || !kycState.fotoVerso) {
            toast('Carregue as duas fotografias do documento antes de continuar.', 'error');
            return;
        }
        kycShowPanel(3);
        kycUpdateStepDots(3);
        // Reiniciar animação de progresso
        const fill = document.getElementById('kycProgressFill');
        fill.style.animation = 'none';
        fill.offsetHeight; // reflow
        fill.style.animation = '';
        // Chamar extração por IA
        await extractKYCData();
        return;
    }
    kycShowPanel(step);
    kycUpdateStepDots(step);
}

function resetPhotoZone(side) {
    const placeholder = document.getElementById(`placeholder${side.charAt(0).toUpperCase() + side.slice(1)}`);
    const preview = document.getElementById(`preview${side.charAt(0).toUpperCase() + side.slice(1)}`);
    const zone = document.getElementById(`zone${side.charAt(0).toUpperCase() + side.slice(1)}`);
    placeholder.style.display = '';
    preview.style.display = 'none';
    preview.src = '';
    zone.classList.remove('has-photo');
}

function handleDocPhoto(side, input) {
    const file = input.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
        const b64 = e.target.result;
        const capSide = side.charAt(0).toUpperCase() + side.slice(1);
        const preview = document.getElementById(`preview${capSide}`);
        const placeholder = document.getElementById(`placeholder${capSide}`);
        const zone = document.getElementById(`zone${capSide}`);
        preview.src = b64;
        preview.style.display = 'block';
        placeholder.style.display = 'none';
        zone.classList.add('has-photo');
        if (side === 'frente') kycState.fotoFrente = b64;
        else kycState.fotoVerso = b64;
        // Habilitar botão quando ambas estiverem carregadas
        document.getElementById('btnKycStep2Next').disabled = !(kycState.fotoFrente && kycState.fotoVerso);
    };
    reader.readAsDataURL(file);
}

async function loadSampleDocument() {
    const btn = document.getElementById('btnUseSample');
    const origText = btn.textContent;
    btn.textContent = 'A carregar amostra...';
    btn.disabled = true;
    try {
        const docType = kycState.docType || 'bilhete';
        const res = await fetch(`${API_BASE}/api/kyc/samples/${docType}`, {
            headers: state.token ? { 'Authorization': `Bearer ${state.token}` } : {}
        });
        if (!res.ok) throw new Error('Amostra não disponível.');
        const data = await res.json();

        // Preencher frente
        kycState.fotoFrente = data.foto_frente;
        const previewF = document.getElementById('previewFrente');
        previewF.src = data.foto_frente;
        previewF.style.display = 'block';
        document.getElementById('placeholderFrente').style.display = 'none';
        document.getElementById('zoneFrente').classList.add('has-photo');

        // Preencher verso
        kycState.fotoVerso = data.foto_verso;
        const previewV = document.getElementById('previewVerso');
        previewV.src = data.foto_verso;
        previewV.style.display = 'block';
        document.getElementById('placeholderVerso').style.display = 'none';
        document.getElementById('zoneVerso').classList.add('has-photo');

        document.getElementById('btnKycStep2Next').disabled = false;
        toast('Documento de amostra carregado. Pronto para validar com IA!', 'success');
    } catch (err) {
        toast('Erro ao carregar amostra: ' + err.message, 'error');
    } finally {
        btn.textContent = origText;
        btn.disabled = false;
    }
}

async function extractKYCData() {
    const statusEl = document.getElementById('kycAiStatus');
    statusEl.innerHTML = 'A comprimir e enviar imagens ao modelo de IA...<br>Aguarde, este processo pode demorar alguns segundos.';
    try {
        const res = await fetch(`${API_BASE}/api/kyc/extract`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${state.token}`
            },
            body: JSON.stringify({
                doc_type: kycState.docType,
                foto_frente: kycState.fotoFrente,
                foto_verso: kycState.fotoVerso
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Erro na extração de dados.');

        kycState.extracted = data.extracted;
        statusEl.innerHTML = 'Dados extraídos com sucesso! A preparar a confirmação...';

        // Preencher campos do passo 4
        const ext = data.extracted;
        document.getElementById('kycNomeCompleto').value  = ext.nome_completo || '';
        document.getElementById('kycPrimeiroNome').value  = ext.primeiro_nome || '';
        document.getElementById('kycUltimoNome').value    = ext.ultimo_nome || '';
        document.getElementById('kycNomePai').value       = ext.nome_pai || '';
        document.getElementById('kycNomeMae').value       = ext.nome_mae || '';
        document.getElementById('kycDocNumero').value     = ext.doc_numero || '';
        document.getElementById('kycDataEmissao').value   = ext.data_emissao || '';
        document.getElementById('kycMorada').value        = ext.morada || '';

        // Avançar para passo 4 com pequeno delay para feedback visual
        setTimeout(() => {
            document.getElementById('kycProgressFill').style.width = '100%';
            setTimeout(() => {
                kycShowPanel(4);
                kycUpdateStepDots(4);
            }, 600);
        }, 800);
    } catch (err) {
        statusEl.innerHTML = `<span style="color:var(--red)">Erro: ${err.message}</span><br><br><button class="btn btn-ghost" onclick="kycGoToStep(2)">← Voltar e tentar novamente</button>`;
    }
}

async function confirmKYC() {
    const errEl = document.getElementById('kycConfirmError');
    errEl.classList.remove('show');
    const btn = document.getElementById('btnKycConfirm');
    btn.disabled = true;
    btn.querySelector('span').textContent = 'A guardar...';

    try {
        const payload = {
            nome_completo:  document.getElementById('kycNomeCompleto').value.trim(),
            primeiro_nome:  document.getElementById('kycPrimeiroNome').value.trim(),
            ultimo_nome:    document.getElementById('kycUltimoNome').value.trim(),
            nome_pai:       document.getElementById('kycNomePai').value.trim(),
            nome_mae:       document.getElementById('kycNomeMae').value.trim(),
            doc_tipo:       kycState.docType,
            doc_numero:     document.getElementById('kycDocNumero').value.trim(),
            morada:         document.getElementById('kycMorada').value.trim(),
            data_emissao:   document.getElementById('kycDataEmissao').value.trim()
        };
        if (!payload.nome_completo || !payload.doc_numero) {
            throw new Error('Nome completo e número de documento são obrigatórios.');
        }

        const res = await fetch(`${API_BASE}/api/kyc/confirm`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${state.token}`
            },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Erro ao confirmar identidade.');

        // Atualizar estado local
        state.user = { ...state.user, ...data.user, kyc_status: 'verificado' };
        localStorage.setItem('bankao_user', JSON.stringify(state.user));
        updateTopbarUser(state.user);

        closeKYCModal();
        await loadUserData();
        toast('✅ Identidade verificada! A sua carteira BankAO está ativa com 100.000 Kz de bónus.', 'success');
    } catch (err) {
        errEl.textContent = err.message;
        errEl.classList.add('show');
    } finally {
        btn.disabled = false;
        btn.querySelector('span').textContent = 'Confirmar e Ativar Carteira';
    }
}

