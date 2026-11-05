/**
 * Autenticação
 * Login, registo, logout e atualização do utilizador na barra superior.
 */

// =====================================================================
//  AUTENTICAÇÃO — Login / Registo / Logout
// =====================================================================

function populateAuthCountries() {
    const countries = window.BANKAO_COUNTRIES || [];
    const selCode = document.getElementById('regPhoneCode');
    const selNat = document.getElementById('regNationality');
    if (!selCode || !selNat || selCode.options.length > 0) return;

    countries.forEach(c => {
        // Indicativo telefónico: "AO (+244)"
        const optCode = document.createElement('option');
        optCode.value = c.dial;
        optCode.textContent = `${c.code} (${c.dial})`;
        if (c.code === 'AO') optCode.selected = true;
        selCode.appendChild(optCode);

        // Nacionalidade: "Angola"
        const optNat = document.createElement('option');
        optNat.value = c.name;
        optNat.textContent = `${c.name} (${c.code})`;
        if (c.code === 'AO') optNat.selected = true;
        selNat.appendChild(optNat);
    });
}

function openAuthModal(forced = false) {
    populateAuthCountries();
    const m = document.getElementById('modalAuth');
    if (!m) return;
    const isLocked = forced || !state.token;
    if (isLocked) {
        document.body.classList.add('auth-required');
        m.classList.add('auth-locked');
    } else {
        m.classList.remove('auth-locked');
    }
    m.style.display = 'flex';
    setTimeout(() => m.classList.add('active'), 10);
}

function closeAuthModal(force = false) {
    if (!state.token && !force) {
        // Bloqueio rigoroso: utilizador não autenticado tem de permanecer na tela de autenticação
        return;
    }
    const m = document.getElementById('modalAuth');
    if (!m) return;
    m.classList.remove('active', 'auth-locked');
    document.body.classList.remove('auth-required');
    setTimeout(() => {
        if (state.token || force) {
            m.style.display = 'none';
        }
    }, 280);
}

function fillDemoUser(email) {
    switchAuthTab('login');
    const emailEl = document.getElementById('loginEmail');
    const passEl  = document.getElementById('loginPassword');
    if (emailEl) emailEl.value = email;
    if (passEl)  passEl.value  = 'Demo1234!';
    const btn = document.getElementById('btnLoginSubmit');
    if (btn) {
        btn.focus();
        btn.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}
function switchAuthTab(tab) {
    populateAuthCountries();
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
        closeAuthModal(true);
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

    const displayName = (document.getElementById('regDisplayName')?.value || '').trim();
    const dialCode = document.getElementById('regPhoneCode')?.value || '+244';
    const phoneRaw = (document.getElementById('regPhoneNumber')?.value || '').trim().replace(/\D/g, '');
    const email = (document.getElementById('regEmail')?.value || '').trim();
    const nationality = document.getElementById('regNationality')?.value || 'Angola';
    const password = document.getElementById('regPassword').value;
    const confirm  = document.getElementById('regConfirmPassword').value;

    if (!displayName) {
        errEl.textContent = 'Introduza o seu nome de apresentação.';
        errEl.classList.add('show');
        return;
    }
    if (!phoneRaw || phoneRaw.length < 5) {
        errEl.textContent = 'Introduza um número de telefone válido.';
        errEl.classList.add('show');
        return;
    }
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

    const telefone = dialCode + phoneRaw;
    const btn = document.getElementById('btnRegisterSubmit');
    btn.disabled = true;
    btn.querySelector('span').textContent = 'A criar conta...';

    try {
        const res = await fetch(`${API_BASE}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nome: displayName,
                email: email,
                telefone: telefone,
                nacionalidade: nationality,
                password,
                confirm_password: confirm,
                terms_accepted: true
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Erro ao criar conta.');

        await onAuthSuccess(data);
        closeAuthModal(true);
        // Abre KYC logo após registo para capturar e validar o verdadeiro nome legal da conta
        setTimeout(() => {
            if (typeof openKYCModal === 'function') openKYCModal();
        }, 400);
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
    state.accountUsd = null;
    state.transactions = [];
    clearFinanceData();
    localStorage.removeItem('bankao_token');
    localStorage.removeItem('bankao_user');
    // Recarrega para não ficar nenhum dado da sessão anterior no ecrã
    location.reload();
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
            btnEl.style.display = '';
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
    const photoUrl = user.id ? localStorage.getItem('bankao_avatar_' + user.id) : null;

    const applyAvatar = (el) => {
        if (!el) return;
        if (photoUrl) {
            el.style.backgroundImage = `url("${photoUrl}")`;
            el.style.backgroundSize = "cover";
            el.style.backgroundPosition = "center";
            el.textContent = "";
        } else {
            el.style.backgroundImage = "";
            el.textContent = initials;
        }
    };

    if (nameEl)  nameEl.textContent  = name;
    applyAvatar(avatarEl);

    if (sideNameEl)   sideNameEl.textContent   = name;
    applyAvatar(sideAvatarEl);

    if (mobNameEl)   mobNameEl.textContent   = name;
    applyAvatar(mobAvatarEl);

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

    // Com sessão iniciada o botão da barra superior desaparece:
    // "Terminar sessão" fica nas Definições (Sobre e conta).
    if (btnEl) {
        btnEl.style.display = 'none';
        btnEl.onclick       = null;
    }

    updateDashboardHero();
}

document.addEventListener('DOMContentLoaded', populateAuthCountries);
