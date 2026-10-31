/**
 * Operações — depósito
 * Método de depósito (Referência / Multicaixa Express) e confirmação do pagamento simulado.
 */

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
