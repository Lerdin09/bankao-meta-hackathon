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
    initTransferConfirmModalEvents();
    initCopilot();
    initShell();

    // Limpar sessão de conta demo antiga (se existir) — utilizadores devem criar conta própria
    const savedUser = state.user;
    if (savedUser && savedUser.email === 'lerdin.santos@bankao.ao') {
        // Conta demo removida — limpar sessão
        localStorage.removeItem('bankao_token');
        localStorage.removeItem('bankao_user');
        state.token = null;
        state.user  = null;
    }

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
