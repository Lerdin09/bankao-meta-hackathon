/**
 * Copilot — inicialização
 * Liga o chat ao endpoint de IA e ao histórico.
 */

// Inicialização do BankAO AI Copilot
function initCopilot() {
    const inputForm = document.getElementById("copilotInputForm");
    const userInput = document.getElementById("copilotUserInput");

    inputForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (!message) return;

        addCopilotMessage("user", message);
        userInput.value = "";

        // Enviar para o backend com Meta Model API
        const typing = showTyping();
        try {
            const res = await fetch(`${API_BASE}/api/ai/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: message,
                    history: state.chatHistory
                })
            });
            const data = await res.json();
            typing.remove();
            
            // Exibir resposta da IA com o card de ação se houver
            addCopilotMessage("ai", data.reply, data.action);

            // Se a IA gerou uma ação de transferência/depósito, pré-preencher o painel imediatamente
            if (data.action) {
                applyCopilotAction(data.action, true);
            }
        } catch (err) {
            typing.remove();
            addCopilotMessage("ai", "Desculpe, ocorreu uma instabilidade ao conectar ao modelo da Meta.");
        }
    });

    // Botões de Perguntas Rápidas
    document.querySelectorAll(".quick-prompt-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const prompt = btn.getAttribute("data-prompt");
            userInput.value = prompt;
            inputForm.dispatchEvent(new Event("submit"));
        });
    });
}
