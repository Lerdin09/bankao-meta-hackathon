/**
 * BankAO — Gestor de Aplicação Móvel & PWA (Atalho no Ecrã)
 * Obriga utilizadores mobile a instalar o atalho para usar como app nativa,
 * e ativa permissões de Notificações e Microfone para o Copilot.
 * Reclama permissões em cada sessão até estarem concedidas.
 */

(function () {
    let deferredPrompt = null;

    // ── Service Worker ──────────────────────────────────────────────────────
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/sw.js').catch(() => {});
        });
    }

    // ── Capturar evento de instalação Android/Chrome ────────────────────────
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        const btn = document.getElementById('btnPwaInstall');
        if (btn) btn.style.display = 'flex';
    });

    window.addEventListener('appinstalled', () => {
        deferredPrompt = null;
        localStorage.setItem('bankao_app_installed', '1');
        dismissMobileAppGuard(true);
        if (typeof toast === 'function') {
            toast('🎉 Aplicação BankAO instalada com sucesso no ecrã!', 'success');
        }
    });

    // ── Helpers de estado de permissão ──────────────────────────────────────
    function isNotifGranted() {
        if (!('Notification' in window)) return true; // iOS Safari — sem API, ignorar
        return Notification.permission === 'granted';
    }

    function isMicGranted() {
        // Rastreado em localStorage porque getUserMedia é assíncrono
        return localStorage.getItem('bankao_mic_granted') === '1';
    }

    function areAllPermsGranted() {
        return isNotifGranted() && isMicGranted();
    }

    function isStandaloneMode() {
        return (window.navigator.standalone === true) ||
               window.matchMedia('(display-mode: standalone)').matches ||
               window.matchMedia('(display-mode: fullscreen)').matches;
    }

    function isMobileDevice() {
        return /Android|iPhone|iPad|iPod|Opera Mini|IEMobile|WPDesktop/i.test(navigator.userAgent) ||
               (window.innerWidth <= 768 && ('ontouchstart' in window || navigator.maxTouchPoints > 0));
    }

    // ── Pedido de Permissões ────────────────────────────────────────────────
    window.requestAppPermissions = async function () {
        const btn = document.getElementById('btnRequestMobilePerms');
        const txt = document.getElementById('txtPermBtn');
        if (btn) btn.disabled = true;
        if (txt) txt.textContent = 'A solicitar permissões ao navegador...';

        let notifOk = isNotifGranted();
        let micOk   = isMicGranted();

        // 1. Notificações
        if (!notifOk) {
            try {
                if ('Notification' in window) {
                    const res = await Notification.requestPermission();
                    notifOk = (res === 'granted');
                } else {
                    notifOk = true; // plataforma não suporta → não bloquear
                }
            } catch (_) {}
        }

        // 2. Microfone
        if (!micOk) {
            try {
                if (navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function') {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    micOk = true;
                    stream.getTracks().forEach(t => t.stop());
                } else {
                    // HTTP ou dispositivo sem API → não pode ser verificado, aceitar
                    micOk = true;
                }
            } catch (_) {
                // Utilizador negou → micOk permanece false
            }
        }

        // Persistir estado
        if (micOk)   localStorage.setItem('bankao_mic_granted', '1');
        if (notifOk) localStorage.setItem('bankao_notif_granted', '1');

        // Atualizar botão
        if (btn) btn.disabled = false;
        if (notifOk && micOk) {
            if (btn)  btn.classList.add('ok');
            if (txt)  txt.textContent = '✅ Microfone e Notificações Ativados!';
            if (typeof toast === 'function') {
                toast('Permissões de áudio e notificações configuradas!', 'success');
            }
            // Se já está em standalone E permissões OK → fechar modal automaticamente
            if (isStandaloneMode()) {
                setTimeout(() => dismissMobileAppGuard(true), 900);
                return;
            }
            // Rerender para esconder a etapa 1
            setTimeout(renderMobileGuard, 400);
        } else {
            if (btn) btn.classList.remove('ok');
            const failMsg = [];
            if (!notifOk) failMsg.push('notificações');
            if (!micOk)   failMsg.push('microfone');
            if (txt) txt.textContent = '⚠️ Não foi possível ativar: ' + failMsg.join(' e ');
            if (typeof toast === 'function') {
                toast('Permissão negada. Active nas Definições do Navegador → Permissões do site.', 'warning');
            }
        }
    };

    // ── Instalar PWA no Android ─────────────────────────────────────────────
    window.triggerPwaInstall = async function () {
        if (!deferredPrompt) {
            alert('Toque no menu (⋮) do navegador e selecione "Adicionar ao ecrã inicial" ou "Instalar aplicação".');
            return;
        }
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        if (outcome === 'accepted') {
            deferredPrompt = null;
            dismissMobileAppGuard(true);
        }
    };

    // ── Fechar modal ────────────────────────────────────────────────────────
    // force=true → apaga estado (permissões concedidas / app instalada)
    // force=false → apenas sessão (utilizador clicou "Continuar mesmo assim")
    window.dismissMobileAppGuard = function (force) {
        const modal = document.getElementById('modalMobileAppPrompt');
        if (modal) modal.style.display = 'none';
        try {
            if (force) {
                localStorage.setItem('bankao_guard_dismissed', '1');
            } else {
                // Só ignora nesta sessão — volta na próxima
                sessionStorage.setItem('bankao_pwa_dismissed', '1');
            }
        } catch (_) {}
    };

    // ── Lógica de renderização do modal ─────────────────────────────────────
    function renderMobileGuard() {
        const modal = document.getElementById('modalMobileAppPrompt');
        if (!modal) return;

        const standalone     = isStandaloneMode();
        const permsGranted   = areAllPermsGranted();
        const notifDenied    = 'Notification' in window && Notification.permission === 'denied';

        const stepPerms   = document.getElementById('mobStepPermissions');
        const stepInstall = document.getElementById('mobStepInstall');
        const badge       = document.getElementById('mobAppBadge');
        const title       = document.getElementById('mobAppTitle');

        // Mostrar/esconder etapas conforme o que ainda falta
        if (stepPerms)   stepPerms.style.display   = permsGranted  ? 'none' : 'flex';
        if (stepInstall) stepInstall.style.display  = standalone    ? 'none' : 'flex';

        // Ajustar badge/título se só faltar permissões (já em standalone)
        if (standalone && !permsGranted) {
            if (badge && badge.querySelector('span:last-child'))
                badge.querySelector('span:last-child').textContent = 'Permissões Necessárias';
            if (title) title.textContent = 'Ative as Permissões do BankAO';
        }

        // Se notificação bloqueada pelo utilizador → instruir a ir às Definições
        if (notifDenied) {
            const btn = document.getElementById('btnRequestMobilePerms');
            const txt = document.getElementById('txtPermBtn');
            if (btn) {
                btn.disabled = false; // deixar clicar para mostrar o toast de ajuda
                btn.classList.remove('ok');
            }
            if (txt) txt.textContent = '⚙️ Ativar nas Definições do Navegador';
            const permNote = document.getElementById('mobPermDeniedNote');
            if (permNote) permNote.style.display = 'block';
        }

        // Guia iOS vs Android para a etapa de instalação
        const isIos = /iPhone|iPad|iPod/i.test(navigator.userAgent);
        const guideIos     = document.getElementById('mobGuideIos');
        const guideAndroid = document.getElementById('mobGuideAndroid');
        if (guideIos)     guideIos.style.display     = (isIos && !standalone) ? 'block' : 'none';
        if (guideAndroid) guideAndroid.style.display  = (!isIos && !standalone) ? 'block' : 'none';

        modal.style.display = 'flex';
    }

    // ── Verificação principal ───────────────────────────────────────────────
    function checkMobileAppGuard() {
        if (!isMobileDevice()) return;

        const standalone   = isStandaloneMode();
        const permsGranted = areAllPermsGranted();

        // Nada a fazer se tudo OK
        if (standalone && permsGranted) return;

        // Se utilizador clicou "Continuar mesmo assim" nesta sessão → respeitar (1 sessão apenas)
        if (sessionStorage.getItem('bankao_pwa_dismissed') === '1') {
            // Mas se as permissões foram concedidas entretanto, já não precisamos do modal
            if (permsGranted) return;
            // Caso contrário, apenas não forçar de novo nesta sessão — deixa correr
            return;
        }

        // localStorage dismissal completo (force) — verificar se ainda falta algo
        if (localStorage.getItem('bankao_guard_dismissed') === '1') {
            // Se já estava dismissed mas voltou a perder permissões (raro), mostrar de novo
            if (permsGranted) return;
        }

        renderMobileGuard();
    }

    // ── Rever no regresso de outras abas / Definições ──────────────────────
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            // Dar tempo ao navegador de atualizar o estado de permissões
            setTimeout(checkMobileAppGuard, 600);
        }
    });

    // ── Inicialização ───────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(checkMobileAppGuard, 800);
    });
})();
