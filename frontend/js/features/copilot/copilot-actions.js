/**
 * Copilot — ações
 * Executa a ação preparada pelo Copilot (abre painéis, preenche campos, destaca a confirmação).
 */

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
