/**
 * Bankão — Lógica da Carteira Digital & Integração com API / Meta Copilot
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
    currentPendingDepositId: null,
    chatHistory: []
};

// Formatação Monetária
function formatMoney(amount, currency = "AOA") {
    const formatted = new Intl.NumberFormat("pt-AO", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);

    if (currency === "AOA") return `${formatted} Kz`;
    if (currency === "EUR") return `${formatted} €`;
    if (currency === "USD") return `$ ${formatted}`;
    return `${formatted} ${currency}`;
}

// Inicialização da Aplicação
document.addEventListener("DOMContentLoaded", async () => {
    initTabs();
    initDepositMethodToggle();
    initIbanValidation();
    initFxQuoteCalculator();
    initCopilot();

    // Se não tiver login prévio, autenticar usuário padrão de demonstração
    if (!state.token || !state.user) {
        await autoLoginDemoUser();
    } else {
        await loadUserData();
    }

    // Polling suave a cada 10s para atualizar saldos e extrato
    setInterval(loadUserData, 10000);
});

// Auto-Login / Registro do Usuário de Demonstração
async function autoLoginDemoUser() {
    try {
        const demoEmail = "lerdin.santos@bankao.ao";
        const demoPass = "HackathonMeta2026!";

        // Tentar login
        let res = await fetch(`${API_BASE}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: demoEmail, password: demoPass })
        });

        if (!res.ok) {
            // Se não existe, registra o usuário com 100.000 Kz de bônus
            res = await fetch(`${API_BASE}/api/auth/register`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    nome: "Lerdin dos Santos",
                    email: demoEmail,
                    password: demoPass,
                    telefone: "923 456 789"
                })
            });
        }

        const data = await res.json();
        if (data.access_token) {
            state.token = data.access_token;
            state.user = data.user;
            localStorage.setItem("bankao_token", state.token);
            localStorage.setItem("bankao_user", JSON.stringify(state.user));
            await loadUserData();
        }
    } catch (err) {
        console.error("Erro na autenticação de demonstração:", err);
    }
}

// Carregar Dados das Contas e Extrato
async function loadUserData() {
    if (!state.token) return;

    try {
        // Atualizar perfil
        if (state.user) {
            document.getElementById("userNameDisplay").textContent = state.user.nome;
            const initials = state.user.nome.split(" ").map(n => n[0]).join("").substring(0, 2).toUpperCase();
            document.getElementById("userAvatar").textContent = initials;
        }

        // Buscar Contas
        const resAcc = await fetch(`${API_BASE}/api/accounts`, {
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        if (resAcc.ok) {
            state.accounts = await resAcc.json();
            renderAccounts();
        }

        // Buscar Extrato
        const resTx = await fetch(`${API_BASE}/api/transactions`, {
            headers: { "Authorization": `Bearer ${state.token}` }
        });
        if (resTx.ok) {
            const txs = await resTx.json();
            renderTransactions(txs);
        }
    } catch (err) {
        console.error("Erro ao carregar dados:", err);
    }
}

// Renderizar Cartões de Saldo
function renderAccounts() {
    state.accountAoa = state.accounts.find(a => a.currency === "AOA");
    state.accountEur = state.accounts.find(a => a.currency === "EUR");

    if (state.accountAoa) {
        document.getElementById("balanceAoa").innerHTML = `${formatMoney(state.accountAoa.balance_decimal, "AOA").replace(" Kz", "")} <span class="curr">Kz</span>`;
        document.getElementById("accNumberAoa").textContent = state.accountAoa.account_number;
        document.getElementById("ibanAoa").textContent = state.accountAoa.iban_virtual;
    }

    if (state.accountEur) {
        document.getElementById("balanceEur").innerHTML = `${formatMoney(state.accountEur.balance_decimal, "EUR").replace(" €", "")} <span class="curr">€</span>`;
        document.getElementById("accNumberEur").textContent = state.accountEur.account_number;
        document.getElementById("ibanEur").textContent = state.accountEur.iban_virtual;
    }
}

// Renderizar Tabela de Extrato
function renderTransactions(txs) {
    const tbody = document.getElementById("transactionsTableBody");
    if (!txs || txs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted" style="padding:24px;">Nenhuma transação registada ainda.</td></tr>`;
        return;
    }

    tbody.innerHTML = txs.map(tx => {
        const date = new Date(tx.created_at);
        const formattedDate = date.toLocaleDateString("pt-AO", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
        const isCredit = tx.amount_minor > 0;
        const sign = isCredit ? "+" : "";
        const amountClass = isCredit ? "credit" : "debit";

        let typeBadge = "Transferência";
        if (tx.type === "deposit") typeBadge = "Depósito";
        if (tx.type === "transfer_iban") typeBadge = "Envio IBAN";

        return `
            <tr>
                <td style="color:var(--text-secondary); font-size:0.8rem;">${formattedDate}</td>
                <td><span style="font-weight:600;">${typeBadge}</span></td>
                <td>${tx.description || "Operação no Bankão"}</td>
                <td class="mono" style="font-size:0.8rem; color:var(--text-muted);">${tx.account_number}</td>
                <td class="tx-amount ${amountClass}">${sign}${formatMoney(Math.abs(tx.amount_decimal), tx.currency)}</td>
                <td><span class="status-tag ${tx.status}">${tx.status === "completed" ? "Concluído" : "Pendente"}</span></td>
            </tr>
        `;
    }).join("");
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
        if (!state.accountAoa) return alert("Conta AOA não identificada.");

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
                alert(data.detail || "Erro ao solicitar depósito.");
            }
        } catch (err) {
            alert("Erro de conexão com o servidor.");
        }
    });

    // Submissão Depósito por Referência
    document.getElementById("formDepositReferencia").addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!state.accountAoa) return alert("Conta AOA não identificada.");

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
                alert(data.detail || "Erro ao gerar referência.");
            }
        } catch (err) {
            alert("Erro de conexão.");
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
            alert(data.detail || "Erro ao confirmar pagamento.");
        }
    } catch (err) {
        alert("Erro ao processar confirmação.");
    }
}

// Submissão de Transferência Interna
document.getElementById("formTransferInternal").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.accountAoa) return;

    const toAcc = document.getElementById("internalDestAcc").value.trim();
    const amount = parseFloat(document.getElementById("internalAmount").value);
    const desc = document.getElementById("internalDesc").value.trim();
    const idempotencyKey = "tx_int_" + Date.now();

    try {
        const res = await fetch(`${API_BASE}/api/transfers/internal`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${state.token}`
            },
            body: JSON.stringify({
                from_account_id: state.accountAoa.id,
                to_account_number: toAcc,
                amount: amount,
                description: desc || "Transferência Interna Bankão",
                idempotency_key: idempotencyKey
            })
        });

        const data = await res.json();
        if (res.ok) {
            alert(`Transferência de ${formatMoney(amount, "AOA")} enviada com sucesso!`);
            document.getElementById("formTransferInternal").reset();
            await loadUserData();
        } else {
            alert(data.detail || "Falha na transferência.");
        }
    } catch (err) {
        alert("Erro ao enviar transferência.");
    }
});

// Validação de IBAN em Tempo Real
function initIbanValidation() {
    const ibanInput = document.getElementById("ibanInput");
    const statusBadge = document.getElementById("ibanValidationStatus");
    const feedback = document.getElementById("ibanFeedbackText");
    let timer = null;

    ibanInput.addEventListener("input", (e) => {
        clearTimeout(timer);
        const value = e.target.value.trim();
        if (value.length < 15) {
            statusBadge.textContent = "Aguardando";
            statusBadge.className = "iban-status-badge";
            feedback.textContent = "Validado com algoritmo Mod 97 (ISO 7064).";
            return;
        }

        timer = setTimeout(async () => {
            try {
                const res = await fetch(`${API_BASE}/api/iban/validate?iban=${encodeURIComponent(value)}`);
                const data = await res.json();
                if (data.valid) {
                    statusBadge.textContent = `Válido (${data.country})`;
                    statusBadge.className = "iban-status-badge valid";
                    feedback.textContent = `✅ IBAN de ${data.country === 'PT' ? 'Portugal (SEPA)' : 'Angola'} verificado pelo algoritmo Mod 97.`;
                } else {
                    statusBadge.textContent = "Inválido";
                    statusBadge.className = "iban-status-badge invalid";
                    feedback.textContent = `❌ Dígitos de controlo matematicamente incorretos. Verifique o número.`;
                }
            } catch (err) {
                console.error(err);
            }
        }, 300);
    });
}

// Simulador Dinâmico de Câmbio & Envio para IBAN
function initFxQuoteCalculator() {
    const amountInput = document.getElementById("ibanSendAmount");
    const receiveDisplay = document.getElementById("quoteReceiveAmount");
    const detailsDisplay = document.getElementById("quoteDetails");
    let timer = null;

    async function updateQuote() {
        const amount = parseFloat(amountInput.value) || 0;
        if (amount <= 0) return;

        try {
            const res = await fetch(`${API_BASE}/api/fx/quote`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    from_currency: "AOA",
                    to_currency: "EUR",
                    amount: amount
                })
            });
            if (res.ok) {
                const quote = await res.json();
                receiveDisplay.textContent = formatMoney(quote.dest_amount_decimal, "EUR");
                detailsDisplay.textContent = `Câmbio: 1€ = ${(1 / quote.rate).toFixed(2)} Kz · Taxa: ${quote.fee_percentage}% (${formatMoney(quote.fee_decimal, "AOA")})`;
            }
        } catch (err) {
            console.error(err);
        }
    }

    amountInput.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(updateQuote, 250);
    });

    updateQuote();

    // Botão Pedir Explicação ao Copilot
    document.getElementById("btnAskAiExplain").addEventListener("click", async () => {
        const amount = parseFloat(amountInput.value) || 50000;
        const iban = document.getElementById("ibanInput").value.trim() || "PT50 0035 0000 0000 0000 0000 0";
        const beneficiary = document.getElementById("beneficiaryName").value.trim() || "Beneficiário na Europa";

        addCopilotMessage("user", `Por favor, explica-me os custos e o câmbio para enviar ${formatMoney(amount, "AOA")} para ${beneficiary}.`);

        try {
            const res = await fetch(`${API_BASE}/api/ai/explain-transfer`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    source_amount: amount,
                    source_currency: "AOA",
                    dest_amount: amount * 0.000952 * 0.985,
                    dest_currency: "EUR",
                    fx_rate: 0.000952,
                    fee: amount * 0.015,
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

    // Submissão do Envio para IBAN
    document.getElementById("formTransferIban").addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!state.accountAoa) return;

        const iban = document.getElementById("ibanInput").value.trim();
        const beneficiary = document.getElementById("beneficiaryName").value.trim();
        const amount = parseFloat(document.getElementById("ibanSendAmount").value);
        const idempotencyKey = "tx_iban_" + Date.now();

        try {
            const res = await fetch(`${API_BASE}/api/transfers/iban`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${state.token}`
                },
                body: JSON.stringify({
                    from_account_id: state.accountAoa.id,
                    to_iban: iban,
                    beneficiary_name: beneficiary,
                    amount: amount,
                    dest_currency: "EUR",
                    idempotency_key: idempotencyKey
                })
            });

            const data = await res.json();
            if (res.ok) {
                alert(`Sucesso! Envio internacional de ${formatMoney(amount, "AOA")} para ${beneficiary} processado.`);
                document.getElementById("formTransferIban").reset();
                addCopilotMessage("ai", `🌍 **Transferência Internacional Concluída!**\n- Beneficiário: **${beneficiary}**\n- Destino: **${data.dest_amount_decimal} EUR**\n- Rastreio: Rede SEPA Instant (Sandbox)`);
                await loadUserData();
            } else {
                alert(data.detail || "Erro na transferência para IBAN.");
            }
        } catch (err) {
            alert("Erro de conexão ao processar envio internacional.");
        }
    });
}

// Inicialização do Bankão AI Copilot
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
            addCopilotMessage("ai", data.reply);
        } catch (err) {
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

// Adicionar Mensagem no Chat do Copilot
function addCopilotMessage(sender, text) {
    const chatContainer = document.getElementById("copilotChatMessages");
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${sender}`;

    const avatar = sender === "ai" ? "🤖" : "👤";
    // Formatação básica de markdown para negrito e quebras de linha
    const formatted = text
        .replace(/\n\n/g, "<br><br>")
        .replace(/\n/g, "<br>")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>");

    bubble.innerHTML = `
        <div class="bubble-avatar">${avatar}</div>
        <div class="bubble-content"><p>${formatted}</p></div>
    `;

    chatContainer.appendChild(bubble);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // Guardar no histórico
    state.chatHistory.push({
        role: sender === "ai" ? "assistant" : "user",
        content: text
    });
}
