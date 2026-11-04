/**
 * Arranque da aplicação
 * Regista o DOMContentLoaded: inicializa os módulos, restaura a sessão e faz polling dos saldos.
 */

// Inicialização da Aplicação
document.addEventListener("DOMContentLoaded", async () => {
    initTabs();
    initDepositMethodToggle();
    initInternalTransfer();
    initIbanValidation();
    initFxQuoteCalculator();
    initContacts();
    initTransferConfirmModalEvents();
    initCopilot();
    if (typeof initCopilotVoice === "function") initCopilotVoice();
    initShell();
    initChartMobileScrollLock();
    initInvestments();
    initCards();
    initSettings();

    // Taxas de câmbio vêm da base de dados
    await loadFxRates();

    // Se já tiver sessão guardada válida, carregar dados; senão mostrar estado visitante
    if (state.token && state.user) {
        updateTopbarUser(state.user);
        await loadUserData();
        // Redirecionar para KYC se pendente
        if (state.user.kyc_status === 'pendente') {
            setTimeout(() => openKYCModal(), 800);
        }
    } else {
        updateTopbarUser(null);
    }

    // A frase "Bom dia / Boa tarde / Boa noite" acompanha a hora sem recarregar a página
    setInterval(() => updateHomeGreeting(), 60000);

    // Polling suave a cada 15s para atualizar saldos e extrato (só se logado)
    setInterval(() => { if (state.token) loadUserData(); }, 15000);
});

/**
 * Fixa o ecrã no mobile exclusivamente em gráficos de linha enquanto o utilizador
 * desliza horizontalmente para ver dados.
 * O gráfico donut mantém o scroll natural da página intacto.
 * Se o dedo subir um pouco (>14px), pára os detalhes e liberta o scroll (deve clicar de novo).
 */
function initChartMobileScrollLock() {
    let locked = false;
    let cancelled = false;
    let startY = 0;

    function lock() {
        if (!locked) {
            locked = true;
            document.documentElement.classList.add("chart-touch-locked");
            document.body.classList.add("chart-touch-locked");
        }
    }

    function unlock() {
        if (locked) {
            locked = false;
            document.documentElement.classList.remove("chart-touch-locked");
            document.body.classList.remove("chart-touch-locked");
        }
    }

    // Excluir expressamente o donut e aplicar apenas a gráficos de linha
    const isLineChartTarget = el => {
        if (!el || typeof el.closest !== "function") return false;
        if (el.closest("#homeDonut, .nb-donut-wrap, .xp-donut-wrap, .nb-expenses-row")) return false;
        return !!el.closest("#ccHit, #fcFullOverlay, #fcOverlay, .bc-nav");
    };

    document.addEventListener("touchstart", ev => {
        if (!ev.touches || !ev.touches.length) return;
        if (isLineChartTarget(ev.target)) {
            cancelled = false;
            startY = ev.touches[0].clientY;
            lock();
        } else {
            unlock();
        }
    }, { passive: true });

    document.addEventListener("touchmove", ev => {
        if (!ev.touches || !ev.touches.length) return;
        if (!locked) return;
        if (cancelled) return;

        const cy = ev.touches[0].clientY;
        const deltaUp = startY - cy; // Positivo quando o dedo sobe

        // Se o dedo subir um pouco (>14px), pára os detalhes e liberta o scroll
        if (deltaUp > 14 || Math.abs(cy - startY) > 22) {
            cancelled = true;
            unlock();
            if (typeof window.clearChartHoverDetails === "function") {
                window.clearChartHoverDetails();
            }
            if (typeof window.clearForecastHoverDetails === "function") {
                window.clearForecastHoverDetails();
            }
            if (typeof window.clearWidgetHoverDetails === "function") {
                window.clearWidgetHoverDetails();
            }
            return;
        }

        // Movimento horizontal a ler dados na linha: fixa a página
        if (isLineChartTarget(ev.target) && ev.cancelable) {
            ev.preventDefault();
        }
    }, { passive: false });

    window.addEventListener("touchend", () => { cancelled = false; unlock(); }, { passive: true });
    window.addEventListener("touchcancel", () => { cancelled = false; unlock(); }, { passive: true });
    window.addEventListener("pointerup", () => { cancelled = false; unlock(); }, { passive: true });
    window.addEventListener("pointercancel", () => { cancelled = false; unlock(); }, { passive: true });
}


