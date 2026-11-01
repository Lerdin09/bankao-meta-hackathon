/**
 * Autenticação
 * Login, registo, logout e atualização do utilizador na barra superior.
 */

// =====================================================================
//  AUTENTICAÇÃO — Login / Registo / Logout
// =====================================================================

function openAuthModal() {
    const m = document.getElementById('modalAuth');
    m.style.display = 'flex';
    setTimeout(() => m.classList.add('active'), 10);
}
function closeAuthModal() {
    const m = document.getElementById('modalAuth');
    m.classList.remove('active');
    setTimeout(() => m.style.display = 'none', 300);
}
function switchAuthTab(tab) {
    const isLogin = tab === 'login';
    document.getElementById('tabLogin').classList.toggle('active', isLogin);
    document.getElementById('tabRegister').classList.toggle('active', !isLogin);
    document.getElementById('formLogin').style.display = isLogin ? '' : 'none';
    document.getElementById('formRegister').style.display = isLogin ? 'none' : '';
    document.getElementById('loginError').classList.remove('show');
    document.getElementById('registerError').classList.remove('show');
}
function togglePasswordVis(inputId, btn) {
    const inp = document.getElementById(inputId);
    const isNowText = inp.type === 'password';
    inp.type = isNowText ? 'text' : 'password';
    btn.querySelector('.ic-eye').style.display = isNowText ? 'none' : '';
    btn.querySelector('.ic-eye-off').style.display = isNowText ? '' : 'none';
}
async function handleLogin(e) {
    e.preventDefault();
    const errEl = document.getElementById('loginError');
    errEl.classList.remove('show');
    const btn = document.getElementById('btnLoginSubmit');
    btn.disabled = true;
    btn.querySelector('span').textContent = 'A autenticar...';

    try {
        const res = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: document.getElementById('loginEmail').value.trim(),
                password: document.getElementById('loginPassword').value
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Erro ao iniciar sessão.');

        await onAuthSuccess(data);
        closeAuthModal();
    } catch (err) {
        errEl.textContent = err.message;
        errEl.classList.add('show');
    } finally {
        btn.disabled = false;
        btn.querySelector('span').textContent = 'Entrar na minha carteira';
    }
}
async function handleRegister(e) {
    e.preventDefault();
    const errEl = document.getElementById('registerError');
    errEl.classList.remove('show');

    const password = document.getElementById('regPassword').value;
    const confirm  = document.getElementById('regConfirmPassword').value;
    if (password !== confirm) {
        errEl.textContent = 'As palavras-passe não coincidem.';
        errEl.classList.add('show');
        return;
    }
    if (!document.getElementById('regTerms').checked) {
        errEl.textContent = 'Deve aceitar os Termos e Condições.';
        errEl.classList.add('show');
        return;
    }

    const btn = document.getElementById('btnRegisterSubmit');
    btn.disabled = true;
    btn.querySelector('span').textContent = 'A criar conta...';

    try {
        const res = await fetch(`${API_BASE}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: document.getElementById('regEmail').value.trim(),
                telefone: document.getElementById('regPhone').value.trim(),
                password,
                confirm_password: confirm,
                terms_accepted: true
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Erro ao criar conta.');

        await onAuthSuccess(data);
        closeAuthModal();
        // Abre KYC logo após registo
        setTimeout(() => openKYCModal(), 400);
    } catch (err) {
        errEl.textContent = err.message;
        errEl.classList.add('show');
    } finally {
        btn.disabled = false;
        btn.querySelector('span').textContent = 'Criar conta BankAO';
    }
}
async function onAuthSuccess(data) {
    state.token = data.access_token;
    state.user  = data.user;
    localStorage.setItem('bankao_token', state.token);
    localStorage.setItem('bankao_user', JSON.stringify(state.user));
    updateTopbarUser(state.user);
    await loadUserData();
    toast('Sessão iniciada com sucesso! Bem-vindo ao BankAO.', 'success');
}
function logout() {
    state.token = null;
    state.user  = null;
    state.accounts = [];
    state.accountAoa = null;
    state.accountEur = null;
    localStorage.removeItem('bankao_token');
    localStorage.removeItem('bankao_user');
    updateTopbarUser(null);
    toast('Sessão terminada. Até breve!', 'info');
}
function updateTopbarUser(user) {
    const nameEl   = document.getElementById('userNameDisplay');
    const avatarEl = document.getElementById('userAvatar');
    const badgeEl  = document.getElementById('userKycBadge');
    const btnEl    = document.getElementById('btnAuthAction');

    const sideNameEl   = document.getElementById('sidebarUserNameDisplay');
    const sideAvatarEl = document.getElementById('sidebarUserAvatar');
    const sideBadgeEl  = document.getElementById('sidebarUserKycBadge');

    const mobNameEl   = document.getElementById('mobileDrawerUserName');
    const mobAvatarEl = document.getElementById('mobileDrawerAvatar');
    const mobKycEl    = document.getElementById('mobileDrawerKyc');

    if (!user) {
        // Modo visitante: marcar body para esconder elementos desnecessários
        document.body.classList.add('unauthenticated');
        updateHomeGreeting(null);
        if (nameEl)  nameEl.textContent   = 'Visitante';
        if (avatarEl) avatarEl.textContent = '?';
        if (badgeEl) {
            badgeEl.textContent = '';
            badgeEl.className   = 'kyc-badge';
        }
        if (sideNameEl)   sideNameEl.textContent   = 'Visitante';
        if (sideAvatarEl) sideAvatarEl.textContent = '?';
        if (sideBadgeEl)  sideBadgeEl.textContent  = 'Não autenticado';

        if (mobNameEl)   mobNameEl.textContent   = 'Visitante';
        if (mobAvatarEl) mobAvatarEl.textContent = '?';
        if (mobKycEl)    mobKycEl.textContent    = 'Não autenticado';

        if (btnEl) {
            btnEl.textContent = 'Entrar';
            btnEl.className   = 'btn-auth-action';
            btnEl.onclick     = openAuthModal;
        }
        return;
    }

    // Utilizador autenticado: remover modo visitante
    document.body.classList.remove('unauthenticated');

    const name = user.nome || user.primeiro_nome || 'Utilizador';
    const initials = name.split(' ').filter(Boolean).map(n => n[0]).join('').substring(0, 2).toUpperCase();

    if (nameEl)  nameEl.textContent  = name;
    if (avatarEl) avatarEl.textContent = initials;

    if (sideNameEl)   sideNameEl.textContent   = name;
    if (sideAvatarEl) sideAvatarEl.textContent = initials;

    if (mobNameEl)   mobNameEl.textContent   = name;
    if (mobAvatarEl) mobAvatarEl.textContent = initials;

    // Saudação (nome + frase conforme a hora)
    updateHomeGreeting(user);

    // Badge KYC
    const isVerif = user.kyc_status === 'verificado';
    if (badgeEl) {
        badgeEl.textContent = isVerif ? 'KYC Verificado' : 'KYC Pendente';
        badgeEl.className   = isVerif ? 'kyc-badge verified' : 'kyc-badge pendente';
    }
    if (sideBadgeEl) {
        sideBadgeEl.textContent = isVerif ? 'Cliente Premium' : 'KYC Pendente';
    }
    if (mobKycEl) {
        mobKycEl.textContent = isVerif ? 'Cliente Premium (Verificado)' : 'KYC Pendente';
    }

    // Botão Sair
    if (btnEl) {
        btnEl.textContent = 'Sair';
        btnEl.className   = 'btn-auth-action logout-mode';
        btnEl.onclick     = logout;
    }

    updateDashboardHero();
}
