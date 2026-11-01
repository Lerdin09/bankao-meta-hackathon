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

    const timeStr = new Date().toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" });
    const isAi = sender === "ai";
    const headerLabel = isAi
        ? `<div class="bubble-header-label"><span class="sender-name">BankAO Copilot</span><span class="sender-badge">Assistente IA</span><span class="bubble-time">${timeStr}</span></div>`
        : `<div class="bubble-header-label"><span class="sender-name">Você</span><span class="bubble-time">${timeStr}</span></div>`;

    bubble.innerHTML = `
        <div class="bubble-avatar">${avatar}</div>
        <div class="bubble-content">
            ${headerLabel}
            <div class="bubble-text"><p>${formatted}</p></div>
        </div>
    `;

    // Se houver um Action Card estruturado, renderizar dentro da bolha da IA
    if (action && action.type === "TRANSFER_IBAN") {
        const actionCard = document.createElement("div");
        actionCard.className = "copilot-action-card";
        actionCard.innerHTML = `
            <div class="action-card-header">
                <span class="action-badge"><svg><use href="#i-spark"/></svg> Operação Pronta</span>
                <span class="country-pill">${escapeHtml(action.country_name || action.country_code || "")}</span>
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
                <span class="action-badge"><svg><use href="#i-pie"/></svg> Despesa Registada</span>
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
    if (!state.chatHistory) state.chatHistory = [];
    state.chatHistory.push({
        role: sender === "ai" ? "assistant" : "user",
        content: text
    });
}

function showTyping() {
    const chatContainer = document.getElementById("copilotChatMessages");
    const el = document.createElement("div");
    el.className = "chat-bubble ai typing-bubble";
    el.innerHTML = `
        <div class="bubble-avatar"><svg><use href="#i-spark"/></svg></div>
        <div class="bubble-content">
            <span class="typing"><i></i><i></i><i></i></span>
        </div>
    `;
    chatContainer.appendChild(el);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return el;
}

// Reiniciar / Limpar conversa do Copilot
function resetCopilotConversation() {
    state.chatHistory = [];
    const chatContainer = document.getElementById("copilotChatMessages");
    if (!chatContainer) return;
    chatContainer.innerHTML = `
        <div class="chat-bubble ai">
            <div class="bubble-avatar"><svg><use href="#i-spark"/></svg></div>
            <div class="bubble-content">
                <div class="bubble-header-label">
                    <span class="sender-name">BankAO Copilot</span>
                    <span class="sender-badge">Assistente IA</span>
                </div>
                <p class="greeting-lead">Olá! Sou o seu <strong>assistente financeiro inteligente</strong>.</p>
                <p class="greeting-desc">Estou pronto para simular envios, analisar despesas, esclarecer câmbio e depósitos Multicaixa Express.</p>
                <div class="copilot-capability-tags">
                    <span class="cap-tag"><svg><use href="#i-swap"/></svg> Câmbio EUR/USD/AOA</span>
                    <span class="cap-tag"><svg><use href="#i-shield"/></svg> Multicaixa Express</span>
                    <span class="cap-tag"><svg><use href="#i-pie"/></svg> Gráfico de Despesas</span>
                    <span class="cap-tag"><svg><use href="#i-target"/></svg> Metas de Poupança</span>
                </div>
            </div>
        </div>
    `;
    const input = document.getElementById("copilotUserInput");
    if (input) input.focus();
}
