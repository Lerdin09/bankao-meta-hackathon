/**
 * Detalhe de um movimento do extrato
 * Abre ao tocar num movimento (extrato e "recentes" do início): origem/destino,
 * data e hora exatas (com segundos), valores, taxa e valor total.
 * Depende de: statementTxById, parseTxDate (statement.js), formatMoney, escapeHtml, toast.
 */

const TXD_TYPE_LABEL = {
    deposit: "Depósito",
    transfer_iban: "Envio internacional (IBAN)",
    fx_exchange: "Câmbio",
    savings_deposit: "Depósito em poupança",
    savings_refund: "Resgate de poupança",
};
const TXD_STATUS = { completed: ["Concluído", "completed"], failed: ["Falhou", "failed"] };

let txdLastFocus = null;

function txdMask(value) {
    if (!value) return "";
    const v = String(value).replace(/\s+/g, "");
    return v.length <= 10 ? v : `${v.slice(0, 4)} •••• ${v.slice(-4)}`;
}

function txdInitials(name) {
    const parts = String(name || "?").trim().split(/\s+/).filter(Boolean);
    return ((parts[0] || "?")[0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

function txdAvatar(node) {
    if (node.kind === "deposit") {
        return `<svg><use href="#${node.refLabel === "Telemóvel" ? "i-phone" : "i-wallet"}"/></svg>`;
    }
    if (node.kind === "iban") return `<svg><use href="#i-globe"/></svg>`;
    return escapeHtml(txdInitials(node.name));
}

function txdNode(node, role, isTarget) {
    return `
        <div class="txd-node ${isTarget ? "is-target" : ""}">
            <div class="txd-av">${txdAvatar(node)}</div>
            <div class="txd-node-text">
                <span class="txd-node-role">${escapeHtml(role)}</span>
                <span class="txd-node-name">${escapeHtml(node.name || "—")}</span>
                ${node.ref ? `<span class="txd-node-ref">${escapeHtml(node.refLabel ? node.refLabel + " " : "")}${escapeHtml(node.ref)}</span>` : ""}
                ${node.extra ? `<span class="txd-node-ref">${escapeHtml(node.extra)}</span>` : ""}
            </div>
        </div>`;
}

function txdRow(label, valueHtml, cls) {
    return `<div class="txd-row"><span class="txd-lbl">${label}</span><span class="txd-val ${cls || ""}">${valueHtml}</span></div>`;
}

function buildTxDetail(tx) {
    const d = parseTxDate(tx.created_at);
    const valid = !isNaN(d.getTime());
    const isCredit = (tx.amount_minor > 0) || (tx.amount_decimal > 0);
    const cur = tx.currency;
    const total = Math.abs(tx.amount_decimal);
    const cp = tx.counterparty;
    const tr = tx.transfer;

    // ---- Tipo / estado ----
    const kind = tx.type === "transfer_internal"
        ? (isCredit ? "Transferência recebida" : "Transferência enviada")
        : (TXD_TYPE_LABEL[tx.type] || "Movimento");
    const [statusText, statusClass] = TXD_STATUS[tx.status] || ["Pendente", "pending"];
    const icon = tx.type === "transfer_iban" ? "i-globe" : (isCredit ? "i-down" : "i-up");

    // ---- Data e hora exatas ----
    let dateStr = "—", timeStr = "—", tz = "";
    if (valid) {
        dateStr = d.toLocaleDateString("pt-AO", { weekday: "long", day: "2-digit", month: "long", year: "numeric" });
        dateStr = dateStr.charAt(0).toUpperCase() + dateStr.slice(1);
        timeStr = d.toLocaleTimeString("pt-AO", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
        try {
            tz = (new Intl.DateTimeFormat("pt-AO", { timeZoneName: "short" }).formatToParts(d).find(p => p.type === "timeZoneName") || {}).value || "";
        } catch (e) { tz = ""; }
    }

    // ---- Origem → Destino ----
    const me = {
        name: (state.user && (state.user.nome || state.user.name)) || "A sua conta BankAO",
        ref: txdMask(tx.account_iban || tx.account_number),
        refLabel: tx.account_iban ? "IBAN" : "Conta",
    };
    let flowTitle, flowHtml;
    if (cp) {
        const other = { name: cp.name, ref: cp.ref, refLabel: cp.ref_label, extra: cp.extra, kind: cp.kind };
        if (isCredit) {
            flowTitle = "De onde veio o dinheiro";
            flowHtml = txdNode(other, "Origem", false) + txdNode(me, "Destino · a sua conta", true);
        } else {
            flowTitle = "Para onde foi o dinheiro";
            flowHtml = txdNode(me, "Origem · a sua conta", false) + txdNode(other, "Destino", true);
        }
    } else {
        flowTitle = isCredit ? "De onde veio o dinheiro" : "Para onde foi o dinheiro";
        flowHtml = txdNode(me, isCredit ? "Creditado na sua conta" : "Debitado da sua conta", true);
    }

    // ---- Linhas de detalhe ----
    const rows = [];
    rows.push(txdRow("Data", escapeHtml(dateStr)));
    rows.push(txdRow("Hora exata", `<span class="txd-time">${escapeHtml(timeStr)}</span>${tz ? `<small>${escapeHtml(tz)}</small>` : ""}`));

    if (tr && !isCredit) {
        if (tr.fee_decimal > 0) rows.push(txdRow("Taxa", `<span class="txd-val-money">${escapeHtml(formatMoney(tr.fee_decimal, tr.source_currency || cur))}</span>`));
        if (tr.dest_currency && tr.dest_currency !== (tr.source_currency || cur)) {
            rows.push(txdRow("Câmbio aplicado", `1 ${escapeHtml(tr.source_currency || cur)} = ${escapeHtml(Number(tr.fx_rate || 0).toLocaleString("pt-AO", { maximumFractionDigits: 6 }))} ${escapeHtml(tr.dest_currency)}`));
        }
        rows.push(txdRow("O destinatário recebe", `<span class="txd-val-money">${escapeHtml(formatMoney(tr.dest_amount_decimal, tr.dest_currency || cur))}</span>`));
    }

    rows.push(txdRow("Conta", `${escapeHtml(cur)} · ${escapeHtml(txdMask(tx.account_number) || "—")}`, "mono"));
    const shortId = String(tx.transaction_id || "").slice(0, 8).toUpperCase();
    if (tx.transaction_id) {
        rows.push(txdRow("Nº da operação",
            `<button type="button" class="txd-copy" data-copy="${escapeHtml(tx.transaction_id)}" title="Copiar identificador completo">
                <span>#${escapeHtml(shortId)}</span><svg><use href="#i-copy"/></svg>
            </button>`, "mono"));
    }

    return `
        <div class="txd-hero">
            <div class="txd-ic ${isCredit ? "credit" : "debit"}"><svg><use href="#${icon}"/></svg></div>
            <span class="txd-kind">${escapeHtml(kind)}</span>
            <div class="txd-amount ${isCredit ? "credit" : "debit"}" id="txdTitle">${isCredit ? "+" : "−"}${escapeHtml(formatMoney(total, cur))}</div>
            <div class="txd-title">${escapeHtml(tx.description || "Operação no BankAO")}</div>
            <span class="status-tag ${statusClass}">${statusText}</span>
        </div>

        <div class="txd-flow">
            <div class="txd-flow-title">${flowTitle}</div>
            ${flowHtml}
        </div>

        <div class="txd-list">${rows.join("")}</div>

        <div class="txd-total">
            <span class="txd-total-lbl">Valor total<small>${isCredit ? "Creditado na sua conta" : (tr && tr.fee_decimal > 0 ? "Debitado, taxa incluída" : "Debitado da sua conta")}</small></span>
            <span class="txd-total-val txd-val-money">${isCredit ? "+" : "−"}${escapeHtml(formatMoney(total, cur))}</span>
        </div>`;
}

function openTxDetail(id) {
    const tx = statementTxById.get(String(id));
    const overlay = document.getElementById("txDetailOverlay");
    const content = document.getElementById("txdContent");
    if (!tx || !overlay || !content) return;

    txdLastFocus = document.activeElement;
    content.innerHTML = buildTxDetail(tx);
    document.getElementById("txdScroll").scrollTop = 0;

    overlay.setAttribute("aria-hidden", "false");
    document.body.classList.add("txd-lock");
    // dois frames: garante que a transição de entrada é executada
    requestAnimationFrame(() => requestAnimationFrame(() => overlay.classList.add("open")));
    setTimeout(() => { const c = overlay.querySelector(".txd-close"); if (c) c.focus({ preventScroll: true }); }, 60);
}
window.openTxDetail = openTxDetail;

function closeTxDetail() {
    const overlay = document.getElementById("txDetailOverlay");
    if (!overlay || !overlay.classList.contains("open")) return;
    overlay.classList.remove("open");
    overlay.setAttribute("aria-hidden", "true");
    document.body.classList.remove("txd-lock");
    if (txdLastFocus && typeof txdLastFocus.focus === "function") txdLastFocus.focus({ preventScroll: true });
    txdLastFocus = null;
}
window.closeTxDetail = closeTxDetail;

// ---- Abrir ao tocar num movimento (também com teclado) ----
document.addEventListener("click", ev => {
    const copyBtn = ev.target.closest && ev.target.closest(".txd-copy");
    if (copyBtn) {
        const text = copyBtn.dataset.copy || "";
        const done = () => toast("Copiado para a área de transferência.", "success");
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(done, () => {});
        } else {
            const ta = document.createElement("textarea");
            ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
            document.body.appendChild(ta); ta.select();
            try { document.execCommand("copy"); done(); } catch (e) {}
            ta.remove();
        }
        return;
    }
    const item = ev.target.closest && ev.target.closest(".tx-item[data-tx-id]");
    if (item) openTxDetail(item.dataset.txId);
});
document.addEventListener("keydown", ev => {
    if (ev.key === "Escape") { closeTxDetail(); return; }
    if ((ev.key === "Enter" || ev.key === " ") && ev.target.matches && ev.target.matches(".tx-item[data-tx-id]")) {
        ev.preventDefault();
        openTxDetail(ev.target.dataset.txId);
    }
});

// ---- Arrastar para baixo para fechar (telemóvel) ----
(function initTxDetailDrag() {
    const drag = document.getElementById("txdDrag");
    const sheet = document.getElementById("txDetailSheet");
    if (!drag || !sheet) return;
    let startY = 0, dy = 0, startT = 0, active = false;
    const isMobile = () => window.matchMedia("(max-width: 639px)").matches;

    drag.addEventListener("pointerdown", e => {
        if (!isMobile() || e.target.closest(".txd-close, .txd-eye")) return;
        active = true; startY = e.clientY; dy = 0; startT = e.timeStamp;
        sheet.classList.add("dragging");
        drag.setPointerCapture(e.pointerId);
    });
    drag.addEventListener("pointermove", e => {
        if (!active) return;
        dy = Math.max(0, e.clientY - startY);
        sheet.style.transform = `translateY(${dy}px)`;
    });
    function end(e) {
        if (!active) return;
        active = false;
        const velocity = dy / Math.max(1, e.timeStamp - startT); // px/ms
        sheet.classList.remove("dragging");
        sheet.style.transform = "";
        if (dy > 110 || velocity > 0.6) closeTxDetail();
    }
    drag.addEventListener("pointerup", end);
    drag.addEventListener("pointercancel", end);
})();
