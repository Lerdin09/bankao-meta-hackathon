/**
 * Operações — transferência entre contas
 * Transferência por e-mail do cliente (taxa 1%).
 */

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
            const rate = fxRateLabel(sendCurr, "AOA");
            routeRate.textContent = rate ? `${rate} · Instantâneo entre Contas` : "Rede Instantânea BankAO Angola";
        }
    }

    if (amountInput) {
        amountInput.addEventListener("input", updateInternalRealtime);
    }
    if (sendCurrSelect) {
        sendCurrSelect.addEventListener("change", updateInternalRealtime);
    }

    // Destino: e-mail do cliente OU número de conta BankAO (8–14 dígitos)
    const parseDest = (raw) => {
        const v = (raw || "").trim();
        if (v.includes("@")) return { kind: "email", value: v.toLowerCase() };
        const digits = v.replace(/[\s.-]/g, "");
        if (/^\d{8,14}$/.test(digits)) return { kind: "account", value: digits };
        return { kind: "invalid", value: v };
    };

    // Busca e validação do destinatário em tempo real
    if (emailInput) {
        emailInput.addEventListener("input", (e) => {
            clearTimeout(lookupTimer);
            const dest = parseDest(e.target.value);
            const tooShort = dest.kind === "invalid" || (dest.kind === "email" && dest.value.length < 5);
            if (tooShort) {
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
                    const qs = dest.kind === "email" ? `email=${encodeURIComponent(dest.value)}` : `account=${encodeURIComponent(dest.value)}`;
                    const res = await fetch(`${API_BASE}/api/users/lookup?${qs}`, {
                        headers: state.token ? { "Authorization": `Bearer ${state.token}` } : {}
                    });
                    if (res.ok) {
                        const data = await res.json();
                        if (data.found) {
                            verifiedInternalRecipient = { name: data.nome, email: data.email || null };
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
                    console.error("Erro na busca de destinatário:", err);
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

            const dest = parseDest(emailInput ? emailInput.value : "");
            const email = dest.value;
            const amount = parseFloat(amountInput ? amountInput.value : 0) || 0;
            const desc = (descInput ? descInput.value.trim() : "") || "Transferência de conta BankAO";

            if (dest.kind === "invalid") {
                toast("Indique o e-mail do cliente ou o número da conta BankAO.");
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

            const recipientName = verifiedInternalRecipient ? verifiedInternalRecipient.name : (dest.kind === "email" ? email.split("@")[0] : `Conta ${email}`);
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
                rateNote: sendCurr !== "AOA" && fxRateLabel(sendCurr, "AOA") ? `${fxRateLabel(sendCurr, "AOA")} · Transferência instantânea entre contas BankAO` : "Transferência instantânea entre contas BankAO",
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
                            ...(dest.kind === "email" ? { to_email: email } : { to_account_number: email }),
                            amount: amount,
                            description: desc,
                            idempotency_key: idempotencyKey
                        })
                    });
                    const data = await res.json();
                    if (res.ok) {
                        // 1) apagar os dados do formulário
                        form.reset();
                        verifiedInternalRecipient = null;
                        updateInternalRealtime();
                        if (liveNameBox) liveNameBox.style.display = "none";
                        if (statusBadge) {
                            statusBadge.textContent = "Verificar";
                            statusBadge.className = "iban-status-badge";
                        }
                        // 2) mostrar que foi enviada
                        showTransferSuccess({
                            recipientName,
                            recipientDest: email,
                            amountText: formatTwoTierMoney(amount, sendCurr),
                            arriveText: formatTwoTierMoney(arrive, sendCurr),
                            lead: `A transferência para ${recipientName} foi enviada.`
                        });
                        toast("Transferência enviada");
                        addCopilotMessage("ai", `⚡ **Transferência de Conta Concluída!**\n- Beneficiário: **${recipientName}** (${email})\n- Quantia enviada: **${formatTwoTierMoney(amount, sendCurr)}**\n- Taxa BankAO (1%): **${formatTwoTierMoney(fee, sendCurr)}**\n- Quantia creditada: **${formatTwoTierMoney(arrive, sendCurr)}**`);
                        if (typeof copilotOpDone === "function") copilotOpDone("transfer_internal", { speech: `Concluído. A transferência de ${formatTwoTierMoney(amount, sendCurr)} para ${recipientName} foi executada com sucesso.` });
                        await loadUserData();
                    } else {
                        toast(data.detail || "Falha na transferência.");
                    }
                }
            });
        });
    }

    updateInternalRealtime();
}
