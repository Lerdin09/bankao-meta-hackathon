/**
 * Copilot — ações
 * Pré-preenche o formulário certo com o que a IA preparou (abre painéis, preenche campos, destaca a confirmação).
 * NUNCA conclui nada: o último passo (Confirmar / Criar / Registar) é sempre do utilizador.
 */

// Marca visualmente o formulário e o botão final que o utilizador tem de carregar
function highlightPreparedForm(form, submitBtn) {
    if (form) {
        form.classList.remove("form-highlight-pulse");
        void form.offsetWidth;
        form.classList.add("form-highlight-pulse");
    }
    if (submitBtn) {
        submitBtn.classList.add("btn-highlight-pulse");
        setTimeout(() => submitBtn.classList.remove("btn-highlight-pulse"), 6000);
        setTimeout(() => submitBtn.scrollIntoView({ behavior: "smooth", block: "center" }), 350);
    }
}

// Escreve num campo e dispara os eventos para que a validação/cálculos reajam
function setFieldValue(el, value, events = ["input"]) {
    if (!el) return;
    el.value = value ?? "";
    events.forEach(ev => el.dispatchEvent(new Event(ev, { bubbles: true })));
}

// Executar Ação Preparada pelo Copilot
function applyCopilotAction(action, autoSwitch = true) {
    if (!action) return;
    const canNavigate = autoSwitch && window.showView && window.showTab;

    if (action.type === "TRANSFER_IBAN") {
        if (canNavigate) {
            window.showTab("tab-transfer-iban");
            window.showView("view-ops");
        }
        setFieldValue(document.getElementById("ibanSendCurrency"), action.currency || "AOA", ["change"]);
        setFieldValue(document.getElementById("ibanInput"), action.to_iban || "");
        setFieldValue(document.getElementById("beneficiaryName"), action.beneficiary_name || "", []);
        setFieldValue(document.getElementById("ibanSendAmount"), action.amount || "");

        const aiText = document.getElementById("aiTransferSummaryText");
        if (aiText) {
            aiText.innerHTML = `<strong>✨ Transferência preparada pelo Copilot:</strong><br>` +
                `• <strong>Beneficiário:</strong> ${escapeHtml(action.beneficiary_name || "por preencher")} (${escapeHtml(action.country_name || action.country_code || "")})<br>` +
                `• <strong>Quantia a debitar:</strong> ${formatMoney(action.amount, action.currency)}<br>` +
                `• <strong>Taxa de serviço (${action.fee_percent}%):</strong> ${formatMoney(action.fee_amount, action.currency)}<br>` +
                `• <strong>Valor líquido a receber:</strong> <span class="text-success" style="font-weight:700;">${formatMoney(action.net_amount, action.currency)}</span>`;
        }
        document.getElementById("aiTransferHelperBox")?.classList.add("action-prefilled-active");
        highlightPreparedForm(document.getElementById("formTransferIban"), document.getElementById("btnSubmitIban"));
        toast(action.beneficiary_name
            ? `✨ Transferência para ${action.beneficiary_name} preparada. Reveja e confirme.`
            : "✨ Transferência preparada. Preencha o nome do beneficiário e confirme.", "success");

    } else if (action.type === "TRANSFER_INTERNAL") {
        if (canNavigate) {
            window.showTab("tab-transfer-internal");
            window.showView("view-ops");
        }
        setFieldValue(document.getElementById("internalSendCurrency"), action.currency || "AOA", ["change"]);
        // O campo aceita e-mail do cliente OU número de conta BankAO
        setFieldValue(document.getElementById("internalDestEmail"), action.to_email || action.to_account_number || "");
        setFieldValue(document.getElementById("internalAmount"), action.amount || "");
        setFieldValue(document.getElementById("internalDesc"),
            action.beneficiary_name ? `Transferência para ${action.beneficiary_name}` : "", []);
        highlightPreparedForm(document.getElementById("formTransferInternal"), document.getElementById("btnSubmitInternal"));
        toast("✨ Transferência entre contas preparada. Reveja e confirme.", "success");

    } else if (action.type === "DEPOSIT_EXPRESS") {
        if (canNavigate) {
            window.showTab("tab-deposit");
            window.showView("view-ops");
        }
        setFieldValue(document.getElementById("expressPhone"), action.phone_number || "", ["input"]);
        setFieldValue(document.getElementById("expressAmount"), action.amount || "");
        highlightPreparedForm(document.getElementById("formDepositExpress"), document.getElementById("btnSubmitExpress"));
        toast("✨ Depósito Express preparado. Reveja e solicite a aprovação.", "success");

    } else if (action.type === "REGISTER_EXPENSE") {
        // Abre o formulário de despesa já preenchido — quem regista é o utilizador
        if (typeof openNewExpenseModal === "function") openNewExpenseModal();
        setFieldValue(document.getElementById("expName"), action.name || "", []);
        setFieldValue(document.getElementById("expAmount"), formatNumberWithDots(action.amount || 0), []);
        if (action.date) setFieldValue(document.getElementById("expDate"), action.date, []);
        setFieldValue(document.getElementById("expNotes"), action.notes || "", []);
        if (typeof selectExpenseFormCategory === "function") selectExpenseFormCategory(action.category || "Outros", "new");
        toast("✨ Despesa preparada. Reveja e toque em Registar.", "success");

    } else if (action.type === "CREATE_SAVINGS_GOAL") {
        // Abre o formulário de meta já preenchido — quem cria é o utilizador
        if (typeof openNewGoalModal === "function") openNewGoalModal();
        setFieldValue(document.getElementById("goalName"), action.name || "", []);
        setFieldValue(document.getElementById("goalTarget"), formatNumberWithDots(action.target || 0), []);
        setFieldValue(document.getElementById("goalMonthly"), formatNumberWithDots(action.monthly || 0), []);
        setFieldValue(document.getElementById("goalInitial"), formatNumberWithDots(action.saved || 0), []);
        setFieldValue(document.getElementById("goalDeadline"), action.deadline || "", []);
        // Ícone: reutiliza o clique do seletor para manter o estado interno coerente
        const iconBtn = document.querySelector(`#goalIconPicker button[data-icon="${action.icon_key || "target"}"]`);
        if (iconBtn) iconBtn.click();
        const daySel = document.getElementById("goalDebitDay");
        if (daySel) {
            daySel.value = action.debit_day ? String(action.debit_day) : "";
            const st = document.getElementById("goalStart");
            if (st && action.start_date) st.value = action.start_date.slice(0, 7);
            syncGoalSchedule("goal", true);
        }
        if (typeof calculateSavingsSimulation === "function") calculateSavingsSimulation();
        toast("✨ Meta preparada. Reveja e toque em Criar meta.", "success");

    } else if (action.type === "OPEN_INVESTMENTS" || action.type === "INVESTMENT_APPLY") {
        if (typeof switchInvestTab === "function") switchInvestTab("portfolio");
        if (canNavigate) {
            window.showView("view-investments");
        }
        if (action.product_id && typeof openApplyModal === "function") {
            setTimeout(() => openApplyModal(action.product_id), 300);
        }
        toast("💼 Painel de Investimentos aberto.", "info");
    }
}
