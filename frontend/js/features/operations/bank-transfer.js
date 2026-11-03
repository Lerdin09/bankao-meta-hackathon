/**
 * Operações — transferência bancária e câmbio
 * Transferência por IBAN (taxa 2,5%) com cotação de câmbio dinâmica.
 */

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
            const rate = fxRateLabel(sendCurr, destCurr);
            const net = destCurr === "EUR" ? "Rede Bancária SEPA" : "Rede Bancária";
            routeRate.textContent = rate
                ? `${rate} · Taxa: 2,5% · ${net}`
                : `Taxa Bancária: 2,5% · Rede Internacional / SEPA`;
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
            const fxLabel = fxRateLabel(sendCurr, destCurr);
            const rateNote = fxLabel
                ? `${fxLabel} · Taxa: 2,5% · Rede Bancária`
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
                        // 1) apagar os dados do formulário
                        form.reset();
                        updateIbanRealtime();
                        const vBadge = document.getElementById("ibanValidationStatus");
                        if (vBadge) { vBadge.textContent = "Aguardando"; vBadge.className = "iban-status-badge"; }
                        const vHint = document.getElementById("ibanFeedbackText");
                        if (vHint) vHint.textContent = "Validado com algoritmo Mod 97 (ISO 7064).";
                        // 2) mostrar que foi enviada
                        showTransferSuccess({
                            recipientName: beneficiary,
                            recipientDest: iban,
                            amountText: formatTwoTierMoney(amount, sendCurr),
                            arriveText: `${data.dest_amount_decimal} ${destCurr}`,
                            lead: `O envio bancário para ${beneficiary} foi enviado.`
                        });
                        toast("Transferência enviada");
                        addCopilotMessage("ai", `🌍 **Transferência Bancária Concluída!**\n- Titular: **${beneficiary}**\n- IBAN: \`${iban}\`\n- Quantia enviada: **${formatTwoTierMoney(amount, sendCurr)}**\n- Taxa bancária (2.5%): **${formatTwoTierMoney(fee, sendCurr)}**\n- Creditado ao destino: **${data.dest_amount_decimal} ${destCurr}**`);
                        await loadUserData();
                    } else {
                        toast(data.detail || "Erro na transferência para IBAN.");
                    }
                }
            });
        });
    }
}
