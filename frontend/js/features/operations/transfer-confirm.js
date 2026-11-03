/**
 * Operações — confirmação de transferência
 * Modal com o resumo antes de executar uma transferência.
 */

// ==========================================================================
// Modal de Confirmação Resumo de Transferência
// ==========================================================================
let pendingTransferExecution = null;
let transferInFlight = false;
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

    // Volta sempre ao ecrã de confirmação (e não ao de "enviada" da vez anterior)
    const box = modal.querySelector(".confirm-transfer-modal");
    if (box) box.classList.remove("is-done");

    modal.style.display = "flex";
    modal.classList.add("active");
}
function closeTransferConfirmModal(force) {
    // Enquanto o envio está a decorrer não se fecha (evita duplicar ou perder o resultado)
    if (transferInFlight && force !== true) return;
    const modal = document.getElementById("modalTransferConfirm");
    if (modal) {
        modal.style.display = "none";
        modal.classList.remove("active");
        const box = modal.querySelector(".confirm-transfer-modal");
        if (box) box.classList.remove("is-done");
    }
    pendingTransferExecution = null;
}

/**
 * Mostra no próprio modal que a transferência foi enviada.
 * Chamado depois de o formulário já ter sido limpo.
 */
function showTransferSuccess({ recipientName, recipientDest, amountText, arriveText, title, lead }) {
    const modal = document.getElementById("modalTransferConfirm");
    if (!modal) return;
    const box = modal.querySelector(".confirm-transfer-modal");
    const set = (id, v) => { const n = document.getElementById(id); if (n) n.textContent = v; };
    set("csTitle", title || "Transferência enviada");
    set("csLead", lead || "A sua transferência foi enviada com sucesso.");
    set("csAmount", amountText || "—");
    set("csTo", recipientName || "—");
    set("csDest", recipientDest || "—");
    set("csArrive", arriveText || "—");
    set("csWhen", new Date().toLocaleString("pt-PT", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }));
    if (box) box.classList.add("is-done");
    modal.style.display = "flex";
    modal.classList.add("active");
    const done = document.getElementById("btnTransferDone");
    if (done) setTimeout(() => done.focus(), 50);
}
window.showTransferSuccess = showTransferSuccess;
// Inicializar botões do modal de confirmação
function initTransferConfirmModalEvents() {
    const btnClose = document.getElementById("btnCloseConfirmTransfer");
    const btnCancel = document.getElementById("btnCancelTransferConfirm");
    const btnExecute = document.getElementById("btnExecuteTransferConfirm");
    const btnDone = document.getElementById("btnTransferDone");

    if (btnDone) btnDone.addEventListener("click", () => closeTransferConfirmModal(true));
    if (btnClose) btnClose.addEventListener("click", () => closeTransferConfirmModal());
    if (btnCancel) btnCancel.addEventListener("click", () => closeTransferConfirmModal());
    document.addEventListener("keydown", e => {
        const m = document.getElementById("modalTransferConfirm");
        if (e.key === "Escape" && m && m.classList.contains("active")) closeTransferConfirmModal();
    });

    if (btnExecute) {
        btnExecute.addEventListener("click", async () => {
            if (transferInFlight) return;
            if (typeof pendingTransferExecution === "function") {
                transferInFlight = true;
                btnExecute.closest(".confirm-transfer-modal")?.classList.add("is-busy");
                const originalHtml = btnExecute.innerHTML;
                btnExecute.disabled = true;
                btnExecute.innerHTML = `<span>A processar...</span>`;
                try {
                    await pendingTransferExecution();
                } catch (err) {
                    console.error("Erro ao executar transferência:", err);
                    toast("Falha na execução da transferência.");
                } finally {
                    transferInFlight = false;
                    btnExecute.closest(".confirm-transfer-modal")?.classList.remove("is-busy");
                    btnExecute.disabled = false;
                    btnExecute.innerHTML = originalHtml;
                }
            }
        });
    }
}
