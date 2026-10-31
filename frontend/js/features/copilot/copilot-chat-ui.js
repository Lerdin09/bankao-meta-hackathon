/**
 * Copilot — mensagens
 * Mensagens do chat, cartões de ação e indicador de escrita.
 */

// Adicionar Mensagem no Chat do Copilot (com suporte a Action Cards interativos)
function addCopilotMessage(sender, text, action = null) {
    const chatContainer = document.getElementById("copilotChatMessages");
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${sender}`;

    const avatar = sender === "ai" ? `<svg><use href="#i-spark"/></svg>` : "Eu";
    // Escapar HTML e aplicar markdown básico (negrito, itálico, quebras de linha)
    const formatted = escapeHtml(String(text ?? ""))
        .replace(/\n\n/g, "<br><br>")
        .replace(/\n/g, "<br>")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>");

    bubble.innerHTML = `
        <div class="bubble-avatar">${avatar}</div>
        <div class="bubble-content">
            <p>${formatted}</p>
        </div>
    `;

    // Se houver um Action Card estruturado, renderizar dentro da bolha da IA
    if (action && action.type === "TRANSFER_IBAN") {
        const actionCard = document.createElement("div");
        actionCard.className = "copilot-action-card";
        actionCard.innerHTML = `
            <div class="action-card-header">
                <span class="action-badge">🤖 Operação Pronta</span>
                <span class="country-pill">${action.country_name || action.country_code}</span>
            </div>
            <div class="action-summary-grid">
                <div class="action-grid-row">
                    <span class="act-label">Beneficiário</span>
                    <strong class="act-val">${escapeHtml(action.beneficiary_name)}</strong>
                </div>
                <div class="action-grid-row">
                    <span class="act-label">IBAN de Destino</span>
                    <span class="act-val mono">${escapeHtml(action.to_iban)}</span>
                </div>
                <div class="action-grid-row">
                    <span class="act-label">Quantia</span>
                    <span class="act-val">${formatMoney(action.amount, action.currency)}</span>
                </div>
                <div class="action-grid-row">
                    <span class="act-label">Taxa (2%)</span>
                    <span class="act-val text-warning">${formatMoney(action.fee_amount || (action.amount * 0.02), action.currency)}</span>
                </div>
                <div class="action-grid-row highlight-net">
                    <span class="act-label">Quanto vai (Líquido)</span>
                    <strong class="act-val text-success">${formatMoney(action.net_amount || (action.amount * 0.98), action.currency)}</strong>
                </div>
            </div>
            <div class="action-card-btn-wrap">
                <button type="button" class="btn btn-sm btn-action-confirm">
                    <span>Revisar no Painel & Confirmar</span>
                    <svg><use href="#i-arrow-right"/></svg>
                </button>
            </div>
        `;

        const btnConfirm = actionCard.querySelector(".btn-action-confirm");
        btnConfirm.addEventListener("click", () => {
            applyCopilotAction(action, true);
        });

        bubble.querySelector(".bubble-content").appendChild(actionCard);
    } else if (action && action.type === "REGISTER_EXPENSE") {
        const actionCard = document.createElement("div");
        actionCard.className = "copilot-action-card";
        actionCard.innerHTML = `
            <div class="action-card-header">
                <span class="action-badge">📊 Despesa Registada</span>
                <span class="country-pill">${escapeHtml(action.category || "Gasto")}</span>
            </div>
            <div class="action-summary-grid">
                <div class="action-grid-row">
                    <span class="act-label">Estabelecimento/Nome</span>
                    <strong class="act-val">${escapeHtml(action.name || "Despesa")}</strong>
                </div>
                <div class="action-grid-row">
                    <span class="act-label">Valor do Gasto</span>
                    <strong class="act-val debit" style="color:#FB7185;">−${formatTwoTierMoney(action.amount, action.currency || "AOA")}</strong>
                </div>
            </div>
            <div class="action-card-btn-wrap">
                <button type="button" class="btn btn-sm btn-outline" style="width:100%;margin-top:6px;" onclick="showView('view-expenses')">
                    <span>Ver Gráfico Donut de Despesas →</span>
                </button>
            </div>
        `;
        bubble.querySelector(".bubble-content").appendChild(actionCard);
    }

    chatContainer.appendChild(bubble);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // Guardar no histórico
    state.chatHistory.push({
        role: sender === "ai" ? "assistant" : "user",
        content: text
    });
}
function showTyping() {
    const chatContainer = document.getElementById("copilotChatMessages");
    const el = document.createElement("div");
    el.className = "chat-bubble ai";
    el.innerHTML = `<div class="bubble-avatar"><svg><use href="#i-spark"/></svg></div><div class="bubble-content"><span class="typing"><i></i><i></i><i></i></span></div>`;
    chatContainer.appendChild(el);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return el;
}
