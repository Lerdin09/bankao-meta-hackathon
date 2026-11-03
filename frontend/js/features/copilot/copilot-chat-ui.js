/**
 * Copilot v2 — Mensagens & Gráficos Inline
 * Renderiza mensagens, cartões de ação e gráficos interativos na conversa.
 */

// ── Adicionar Mensagem ─────────────────────────────────────────────────────

function addCopilotMessage(sender, text, action = null, chart = null, remember = true) {
    const chatContainer = document.getElementById("copilotChatMessages");
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${sender}`;

    const avatar = sender === "ai"
        ? `<svg><use href="#i-spark"/></svg>`
        : `<span>${(state.user?.nome || "EU").slice(0,2).toUpperCase()}</span>`;

    // Renderizar Markdown básico + tabelas simples
    const formatted = renderCopilotMarkdown(text || "");

    const timeStr = new Date().toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" });
    const isAi = sender === "ai";
    const headerLabel = isAi
        ? `<div class="bubble-header-label">
               <span class="sender-name">BankAO Copilot</span>
               <span class="sender-badge">IA v2</span>
               <span class="bubble-time">${timeStr}</span>
           </div>`
        : `<div class="bubble-header-label">
               <span class="sender-name">Você</span>
               <span class="bubble-time">${timeStr}</span>
           </div>`;

    bubble.innerHTML = `
        <div class="bubble-avatar">${avatar}</div>
        <div class="bubble-content">
            ${headerLabel}
            <div class="bubble-text">${formatted}</div>
        </div>
    `;

    const contentEl = bubble.querySelector(".bubble-content");

    // Gráfico inline
    if (chart && typeof buildCopilotChart === "function") {
        const chartEl = buildCopilotChart(chart);
        if (chartEl) {
            chartEl.classList.add("bubble-chart");
            contentEl.appendChild(chartEl);
        }
    }

    // Action Card (transferência preparada, despesa, poupança...)
    if (action && action.type) {
        const card = buildActionCard(action);
        if (card) contentEl.appendChild(card);
    }

    chatContainer.appendChild(bubble);

    // Scroll suave para a nova mensagem
    requestAnimationFrame(() => {
        bubble.scrollIntoView({ behavior: "smooth", block: "end" });
    });

    // Guardar no histórico (mensagens de erro técnico não entram: confundiam o assistente)
    if (remember) {
        if (!state.chatHistory) state.chatHistory = [];
        state.chatHistory.push({
            role: sender === "ai" ? "assistant" : "user",
            content: text
        });
        // Limitar histórico a 20 mensagens
        if (state.chatHistory.length > 20) state.chatHistory = state.chatHistory.slice(-20);
    }
    return bubble;
}

// ── Markdown renderer ──────────────────────────────────────────────────────

function renderCopilotMarkdown(text) {
    return escapeHtml(String(text ?? ""))
        // Títulos
        .replace(/^#{3} (.+)$/gm, "<h5 class='bubble-h'>$1</h5>")
        .replace(/^#{1,2} (.+)$/gm, "<h4 class='bubble-h'>$1</h4>")
        // Negrito e itálico
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/`([^`]+)`/g, "<code class='mono'>$1</code>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>")
        // Listas com bullet •
        .replace(/^[•\-] (.+)$/gm, "<div class='bubble-li'>$1</div>")
        // Separador
        .replace(/^═+$/gm, "<hr class='bubble-hr'>")
        // Quebras de linha
        .replace(/\n\n/g, "<br><br>")
        .replace(/\n/g, "<br>")
        // Wrapping final
        .replace(/^(.+)$/, "<p>$1</p>");
}

// ── Action Cards ───────────────────────────────────────────────────────────

function buildActionCard(action) {
    const row = (label, value, cls = "") =>
        `<div class="action-grid-row ${cls}"><span class="act-label">${label}</span>${value}</div>`;
    const money = (v, c) => formatMoney(v, c || "AOA");
    let badge, pill = "", rows = "", btnLabel;

    if (action.type === "TRANSFER_IBAN") {
        badge = `<svg><use href="#i-spark"/></svg> Transferência por IBAN`;
        pill = escapeHtml(action.country_name || action.country_code || "");
        rows = row("Beneficiário", `<strong class="act-val">${escapeHtml(action.beneficiary_name || "— preencher no formulário")}</strong>`) +
            row("IBAN de destino", `<span class="act-val mono">${escapeHtml(action.to_iban)}</span>`) +
            row("Quantia", `<span class="act-val">${money(action.amount, action.currency)}</span>`) +
            row(`Taxa (${action.fee_percent}%)`, `<span class="act-val text-warning">${money(action.fee_amount, action.currency)}</span>`) +
            row("Quanto vai (líquido)", `<strong class="act-val text-success">${money(action.net_amount, action.currency)}</strong>`, "highlight-net");
        btnLabel = "Rever e confirmar";

    } else if (action.type === "TRANSFER_INTERNAL") {
        badge = `<svg><use href="#i-spark"/></svg> Transferência entre contas`;
        pill = "BankAO";
        rows = (action.beneficiary_name ? row("Beneficiário", `<strong class="act-val">${escapeHtml(action.beneficiary_name)}</strong>`) : "") +
            row(action.to_email ? "E-mail do cliente" : "Nº da conta", `<span class="act-val mono">${escapeHtml(action.to_email || action.to_account_number)}</span>`) +
            row("Quantia", `<span class="act-val">${money(action.amount, action.currency)}</span>`) +
            row(`Taxa (${action.fee_percent}%)`, `<span class="act-val text-warning">${money(action.fee_amount, action.currency)}</span>`) +
            row("Quanto vai (líquido)", `<strong class="act-val text-success">${money(action.net_amount, action.currency)}</strong>`, "highlight-net");
        btnLabel = "Rever e confirmar";

    } else if (action.type === "DEPOSIT_EXPRESS") {
        badge = `<svg><use href="#i-bolt"/></svg> Depósito Express`;
        rows = row("Telemóvel", `<span class="act-val mono">${escapeHtml(action.phone_number)}</span>`) +
            row("Quantia", `<strong class="act-val">${money(action.amount, "AOA")}</strong>`);
        btnLabel = "Rever e confirmar";

    } else if (action.type === "REGISTER_EXPENSE") {
        badge = `<svg><use href="#i-pie"/></svg> Despesa preparada`;
        pill = escapeHtml(action.category || "Gasto");
        rows = row("Nome", `<strong class="act-val">${escapeHtml(action.name || "Despesa")}</strong>`) +
            row("Valor", `<strong class="act-val debit">−${money(action.amount, "AOA")}</strong>`) +
            row("Categoria", `<span class="act-val">${escapeHtml(action.category || "Outros")}</span>`) +
            row("Data", `<span class="act-val">${escapeHtml(action.date || "")}</span>`);
        btnLabel = "Rever e registar";

    } else if (action.type === "CREATE_SAVINGS_GOAL") {
        badge = `<svg><use href="#i-target"/></svg> Meta de Poupança`;
        pill = escapeHtml(action.deadline_label || "");
        rows = row("Objetivo", `<strong class="act-val">${escapeHtml(action.name)}</strong>`) +
            row("Valor da meta", `<strong class="act-val">${money(action.target, "AOA")}</strong>`) +
            row("Prazo", `<span class="act-val">${escapeHtml(action.deadline_label || "")} (${action.months} meses)</span>`) +
            row("Depósito mensal", `<span class="act-val text-success">${money(action.monthly, "AOA")}</span>`) +
            (action.debit_day ? row("Débito automático", `<span class="act-val">dia ${action.debit_day}</span>`) : "") +
            (action.saved ? row("Saldo inicial", `<span class="act-val">${money(action.saved, "AOA")}</span>`) : "");
        btnLabel = "Rever e criar meta";

    } else if (action.type === "OPEN_INVESTMENTS") {
        badge = `<svg><use href="#i-trending"/></svg> Painel de Investimentos`;
        pill = escapeHtml(action.title || "Investimentos BankAO");
        rows = row("Módulo", `<strong class="act-val">Carteira & Catálogo BODIVA</strong>`) +
            row("Taxas", `<span class="act-val text-success">Até 18,5% ao ano</span>`) +
            row("Acesso", `<span class="act-val">Subscrições e acompanhamento</span>`);
        btnLabel = "Abrir Painel de Investimentos";

    } else {
        return null;
    }

    const card = document.createElement("div");
    card.className = "copilot-action-card";
    card.innerHTML = `
        <div class="action-card-header">
            <span class="action-badge">${badge}</span>
            ${pill ? `<span class="country-pill">${pill}</span>` : ""}
        </div>
        <div class="action-summary-grid">${rows}</div>
        <div class="action-card-btn-wrap">
            <button type="button" class="btn btn-sm btn-action-confirm">
                <span>${btnLabel}</span><svg><use href="#i-arrow-right"/></svg>
            </button>
        </div>
        <p class="action-card-note">Nada é concluído sem a sua confirmação.</p>
    `;
    card.querySelector(".btn-action-confirm").addEventListener("click", () => applyCopilotAction(action, true));
    return card;
}

// ── Typing indicator ──────────────────────────────────────────────────────

function showTyping() {
    const chatContainer = document.getElementById("copilotChatMessages");
    const el = document.createElement("div");
    el.className = "chat-bubble ai typing-bubble";
    el.innerHTML = `
        <div class="bubble-avatar"><svg><use href="#i-spark"/></svg></div>
        <div class="bubble-content">
            <span class="typing"><i></i><i></i><i></i></span>
            <span class="typing-label">A analisar os seus dados…</span>
        </div>
    `;
    chatContainer.appendChild(el);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return el;
}

// ── Reiniciar conversa ─────────────────────────────────────────────────────

function resetCopilotConversation() {
    state.chatHistory = [];
    state.copilotPending = null;
    const chatContainer = document.getElementById("copilotChatMessages");
    if (!chatContainer) return;

    // Dicas rápidas contextuais
    const quickPrompts = [
        { label: "📊 Despesas deste mês", prompt: "Mostra-me as minhas despesas deste mês em gráfico" },
        { label: "📈 Evolução 4 meses", prompt: "Mostra a evolução das minhas despesas nos últimos 4 meses" },
        { label: "💰 Balanço geral", prompt: "Qual é o meu balanço financeiro geral?" },
        { label: "💡 Dicas de poupança", prompt: "Dá-me dicas personalizadas de poupança" },
        { label: "🔮 Previsão saldo", prompt: "Qual é a previsão do meu saldo para os próximos 6 meses?" },
        { label: "🎯 Nova meta", prompt: "Quero criar uma meta de poupança" },
    ];

    chatContainer.innerHTML = `
        <div class="chat-bubble ai">
            <div class="bubble-avatar"><svg><use href="#i-spark"/></svg></div>
            <div class="bubble-content">
                <div class="bubble-header-label">
                    <span class="sender-name">BankAO Copilot</span>
                    <span class="sender-badge">IA v2</span>
                </div>
                <p class="greeting-lead">Olá! Sou o seu <strong>assistente financeiro inteligente</strong>.</p>
                <p class="greeting-desc">Tenho acesso aos seus dados reais — saldos, despesas, poupanças e investimentos. Posso gerar gráficos interativos, analisar hábitos e dar-lhe dicas personalizadas.</p>
                <div class="copilot-quick-prompts">
                    ${quickPrompts.map(q => `
                        <button type="button" class="quick-prompt-btn" data-prompt="${escapeHtml(q.prompt)}">
                            ${q.label}
                        </button>
                    `).join("")}
                </div>
                <div class="copilot-capability-tags">
                    <span class="cap-tag"><svg><use href="#i-pie"/></svg> Gráficos Interativos</span>
                    <span class="cap-tag"><svg><use href="#i-target"/></svg> Metas & Poupança</span>
                    <span class="cap-tag"><svg><use href="#i-trending"/></svg> Investimentos</span>
                    <span class="cap-tag"><svg><use href="#i-swap"/></svg> Transferências</span>
                    <span class="cap-tag"><svg><use href="#i-spark"/></svg> Memória & Análise</span>
                </div>
            </div>
        </div>
    `;

    // Re-ligar os botões rápidos
    chatContainer.querySelectorAll(".quick-prompt-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const prompt = btn.getAttribute("data-prompt");
            const input = document.getElementById("copilotUserInput");
            if (input) input.value = prompt;
            document.getElementById("copilotInputForm")?.dispatchEvent(new Event("submit", { cancelable: true }));
        });
    });

    const input = document.getElementById("copilotUserInput");
    if (input) input.focus();
}
