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

    // Envio programático sem interferir com o texto digitado pelo utilizador no input
    window.sendCopilotQuery = async function (msgText) {
        const message = String(msgText || "").trim();
        if (!message || busy) return false;
        busy = true;

        addCopilotMessage("user", message);

        const typing = showTyping();
        try {
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
                    history: (state.chatHistory || []).slice(-17, -1),
                    pending: state.copilotPending || null,
                    context: {
                        current_view: document.querySelector(".view.active")?.id || null
                    }
                })
            });
            if (!res.ok) throw new Error("HTTP " + res.status);
            const data = await res.json();
            typing.remove();

            state.copilotPending = data.pending || null;

            addCopilotMessage("ai", data.reply, data.action, data.chart, true, data.reasoning, data.provider);
            const voiceOn = typeof window.copilotVoiceActive === "function" && window.copilotVoiceActive();
            if (!voiceOn && typeof bkSetting === "function" && bkSetting("ai_read_aloud") && typeof window.copilotSpeak === "function") window.copilotSpeak(data.reply);
            document.dispatchEvent(new CustomEvent("copilot:reply", { detail: { ok: true, reply: data.reply } }));

            if (data.action && ["EXPENSE_REGISTERED", "EXPENSE_DELETED"].includes(data.action.type)) {
                refreshExpensesFromCopilot();
            }

            if (data.action) {
                if (wide.matches || ["OPEN_INVESTMENTS", "CREATE_SAVINGS_GOAL", "INVESTMENT_APPLY"].includes(data.action.type)) {
                    applyCopilotAction(data.action, true);
                }
            }
            return true;
        } catch (err) {
            typing.remove();
            console.error("Copilot error:", err);
            document.dispatchEvent(new CustomEvent("copilot:reply", { detail: { ok: false, reply: "" } }));
            addCopilotMessage("ai", "Não consegui contactar o assistente agora. O seu pedido não foi processado.", null, null, false);
            return false;
        } finally {
            busy = false;
        }
    };

    inputForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (!message || busy) return;
        userInput.value = "";
        userInput.style.height = "auto";
        await window.sendCopilotQuery(message);
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
