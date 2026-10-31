/**
 * Operações — confirmação de transferência
 * Modal com o resumo antes de executar uma transferência.
 */

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
