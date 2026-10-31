/**
 * Operações — validação de IBAN
 * Validação em tempo real (Mod 97).
 */

// ==========================================================================
// Validação de IBAN em Tempo Real (Mod 97)
// ==========================================================================
function initIbanValidation() {
    const ibanInput = document.getElementById("ibanInput");
    const statusBadge = document.getElementById("ibanValidationStatus");
    const feedback = document.getElementById("ibanFeedbackText");
    let timer = null;

    if (!ibanInput) return;

    ibanInput.addEventListener("input", (e) => {
        clearTimeout(timer);
        const value = e.target.value.trim();
        if (value.length < 15) {
            if (statusBadge) {
                statusBadge.textContent = "Aguardando";
                statusBadge.className = "iban-status-badge";
            }
            if (feedback) feedback.textContent = "Validado com algoritmo Mod 97 (ISO 7064).";
            return;
        }

        timer = setTimeout(async () => {
            try {
                const res = await fetch(`${API_BASE}/api/iban/validate?iban=${encodeURIComponent(value)}`);
                const data = await res.json();
                if (data.valid) {
                    if (statusBadge) {
                        statusBadge.textContent = `Válido (${data.country})`;
                        statusBadge.className = "iban-status-badge valid";
                    }
                    if (feedback) feedback.textContent = `✅ IBAN de ${data.country === 'PT' ? 'Portugal (SEPA)' : data.country === 'AO' ? 'Angola' : data.country} verificado pelo algoritmo Mod 97.`;
                } else {
                    if (statusBadge) {
                        statusBadge.textContent = "Inválido";
                        statusBadge.className = "iban-status-badge invalid";
                    }
                    if (feedback) feedback.textContent = `❌ Dígitos de controlo matematicamente incorretos. Verifique o número.`;
                }
            } catch (err) {
                console.error(err);
            }
        }, 300);
    });
}
