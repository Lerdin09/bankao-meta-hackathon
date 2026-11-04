/* Origem Copilot: quando o formulário foi preparado pelo Copilot, ao concluir a operação
   (meta, investimento, transferência, depósito, despesa…) o chat mostra que foi feita e,
   se estava em modo voz, o Copilot diz em voz alta que a execução foi concluída. */
const copilotOrigin = {};
function markCopilotOrigin(kind) {
    copilotOrigin[kind] = { t: Date.now(), voice: !!(window.copilotVoiceActive && window.copilotVoiceActive()) };
}
// opts: { chat: texto para o chat, speech: frase falada, direct: true se o próprio Copilot executou (sem formulário) }
function copilotOpDone(kind, opts) {
    opts = opts || {};
    const o = copilotOrigin[kind];
    delete copilotOrigin[kind];
    const fromCopilot = !!opts.direct || (!!o && Date.now() - o.t < 30 * 60 * 1000);
    if (!fromCopilot) return;                               // operação feita à mão, não pelo Copilot
    if (opts.chat && typeof addCopilotMessage === "function" && document.getElementById("copilotChatMessages")) {
        addCopilotMessage("ai", opts.chat);
    }
    const voiceOn = (window.copilotVoiceActive && window.copilotVoiceActive()) || (o && o.voice);
    if (opts.speech && voiceOn && typeof window.copilotSpeakDone === "function") window.copilotSpeakDone(opts.speech);
}
function copilotAnnounceDone(kind, text, speech) { copilotOpDone(kind, { chat: text, speech }); }

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

// Abre o formulário de subscrição já preenchido; o cliente é quem confirma
async function openInvestmentFromCopilot(action) {
    try {
        if (typeof INV !== "undefined" && !INV.catalog.length && typeof loadInvestmentsData === "function") {
            await loadInvestmentsData();
        }
        // Sem produto escolhido: só abre o catálogo para ele escolher
        if (!action.product_id) {
            if (typeof switchInvestTab === "function") switchInvestTab("catalog");
            toast("Escolha o produto no catálogo e toque em Subscrever.", "info");
            return;
        }
        if (typeof switchInvestTab === "function") switchInvestTab("portfolio");
        if (typeof INV === "undefined" || !INV.catalog.some(p => p.id === action.product_id)) {
            toast("Este produto já não está disponível no catálogo.", "error");
            return;
        }
        markCopilotOrigin("investment");
        openApplyModal(action.product_id);
        if (action.amount) setFieldValue(document.getElementById("mivAppAmountInput"), action.amount, ["input"]);
        setFieldValue(document.getElementById("mivAppNotesInput"), action.notes || "", []);
        highlightPreparedForm(document.querySelector("#modalInvestApply form"), document.getElementById("mivAppSubmitBtn"));
        toast("✨ Subscrição preparada. Reveja e toque em Confirmar.", "success");
    } catch (err) {
        toast("Não consegui abrir o formulário de investimento.", "error");
    }
}

// O Copilot registou ou removeu uma despesa na base de dados: recarrega os dados e redesenha a página de Despesas
async function refreshExpensesFromCopilot() {
    try {
        if (typeof loadFinanceData === "function") await loadFinanceData();
        if (typeof renderExpensesView === "function") renderExpensesView();
    } catch (err) {
        console.error("Não consegui atualizar as despesas:", err);
    }
}

// Executar Ação Preparada pelo Copilot
function applyCopilotAction(action, autoSwitch = true) {
    if (!action) return;
    const canNavigate = autoSwitch && window.showView && window.showTab;

    if (action.type === "TRANSFER_IBAN") {
        markCopilotOrigin("transfer_iban");
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
        markCopilotOrigin("transfer_internal");
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
        markCopilotOrigin("deposit");
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
        markCopilotOrigin("expense");
        if (typeof openNewExpenseModal === "function") openNewExpenseModal();
        setFieldValue(document.getElementById("expName"), action.name || "", []);
        setFieldValue(document.getElementById("expAmount"), formatNumberWithDots(action.amount || 0), []);
        if (action.date) setFieldValue(document.getElementById("expDate"), action.date, []);
        setFieldValue(document.getElementById("expNotes"), action.notes || "", []);
        if (typeof selectExpenseFormCategory === "function") selectExpenseFormCategory(action.category || "Outros", "new");
        toast("✨ Despesa preparada. Reveja e toque em Registar.", "success");

    } else if (action.type === "CREATE_SAVINGS_GOAL") {
        // Abre o formulário de meta já preenchido — quem cria é o utilizador
        markCopilotOrigin("goal");
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

    } else if (action.type === "INVESTMENT_APPLY") {
        if (canNavigate) window.showView("view-investments");
        openInvestmentFromCopilot(action);

    } else if (action.type === "OPEN_INVESTMENTS") {
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
