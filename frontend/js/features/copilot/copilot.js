/**
 * Copilot v2 — inicialização e envio de mensagens
 * Usa /api/ai/chat-v2 com contexto real, memória e gráficos inline.
 */

function initCopilot() {
    const inputForm  = document.getElementById("copilotInputForm");
    const userInput  = document.getElementById("copilotUserInput");
    const wide       = window.matchMedia("(min-width: 1024px)");
    let busy = false;

    if (!inputForm) return;

    // Auto-resize do textarea
    userInput?.addEventListener("input", () => {
        userInput.style.height = "auto";
        userInput.style.height = Math.min(userInput.scrollHeight, 120) + "px";
    });

    inputForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (!message || busy) return;
        busy = true;
        userInput.style.height = "auto";

        addCopilotMessage("user", message);
        userInput.value = "";

        const typing = showTyping();
        try {
            // Usar chat-v2 se o utilizador estiver autenticado
            const endpoint = state.token ? "/api/ai/chat-v2" : "/api/ai/chat";
            const headers = {
                "Content-Type": "application/json",
                ...(state.token ? { "Authorization": `Bearer ${state.token}` } : {})
            };

            const res = await fetch(`${API_BASE}${endpoint}`, {
                method: "POST",
                headers,
                body: JSON.stringify({
                    message,
                    history: (state.chatHistory || []).slice(-17, -1), // sem a mensagem atual (vai à parte)
                    pending: state.copilotPending || null,
                    // Passar contexto do frontend (saldos visíveis, etc.)
                    context: {
                        current_view: document.querySelector(".view.active")?.id || null
                    }
                })
            });
            if (!res.ok) throw new Error("HTTP " + res.status);
            const data = await res.json();
            typing.remove();

            state.copilotPending = data.pending || null;

            // Renderizar resposta (com ou sem gráfico)
            addCopilotMessage("ai", data.reply, data.action, data.chart);
            if (typeof bkSetting === "function" && bkSetting("ai_read_aloud") && typeof window.copilotSpeak === "function") window.copilotSpeak(data.reply);

            // Despesa registada/removida pelo Copilot: já está na base de dados, só falta atualizar o ecrã
            if (data.action && ["EXPENSE_REGISTERED", "EXPENSE_DELETED"].includes(data.action.type)) {
                refreshExpensesFromCopilot();
            }

            // Abrir formulário ou painel correspondente (poupanças, investimentos, operações)
            if (data.action) {
                if (wide.matches || ["OPEN_INVESTMENTS", "CREATE_SAVINGS_GOAL", "INVESTMENT_APPLY"].includes(data.action.type)) {
                    applyCopilotAction(data.action, true);
                }
            }
        } catch (err) {
            typing.remove();
            console.error("Copilot error:", err);
            // Erro honesto + botão para repetir o mesmo pedido (sem entrar no histórico da conversa)
            const errBubble = addCopilotMessage("ai",
                "Não consegui contactar o assistente agora. O seu pedido não foi processado.",
                null, null, false
            );
            const retry = document.createElement("button");
            retry.type = "button";
            retry.className = "btn btn-sm quick-prompt-btn";
            retry.textContent = "Tentar de novo";
            retry.addEventListener("click", () => {
                retry.remove();
                // retira a última mensagem do utilizador do histórico: vai ser reenviada
                if (state.chatHistory?.length && state.chatHistory[state.chatHistory.length - 1].role === "user") {
                    state.chatHistory.pop();
                }
                userInput.value = message;
                inputForm.dispatchEvent(new Event("submit", { cancelable: true }));
            });
            errBubble?.querySelector(".bubble-content")?.appendChild(retry);
        } finally {
            busy = false;
        }
    });

    // Enter envia, Shift+Enter nova linha
    userInput?.addEventListener("keydown", e => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            inputForm.dispatchEvent(new Event("submit", { cancelable: true }));
        }
    });

    // Botões de Perguntas Rápidas
    document.querySelectorAll(".quick-prompt-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const prompt = btn.getAttribute("data-prompt");
            if (userInput) userInput.value = prompt;
            inputForm.dispatchEvent(new Event("submit", { cancelable: true }));
        });
    });

    // Botão de limpar conversa
    document.getElementById("btnCopilotReset")?.addEventListener("click", resetCopilotConversation);
}
