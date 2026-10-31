/**
 * Shell da aplicação
 * Navegação entre vistas, menu móvel, saldos ocultos e copiar IBAN.
 */

// Navegação entre vistas, atalhos, saldos ocultos, copiar IBAN
function initShell() {
    const wide = window.matchMedia("(min-width: 1280px)");

    function showView(id) {
        // No ecrã largo o Copilot está sempre visível ao lado
        if (id === "view-copilot" && wide.matches) {
            document.getElementById("copilotUserInput").focus();
            return;
        }
        document.querySelectorAll(".views > .view").forEach(v => v.classList.toggle("active", v.id === id));
        document.querySelectorAll("[data-view]").forEach(b => b.classList.toggle("active", b.dataset.view === id));
        // Scroll para o topo: usa o main-content em desktop (scroll interno), window em mobile
        const mc = document.querySelector(".main-content");
        if (mc && getComputedStyle(mc).overflowY === "auto") {
            mc.scrollTo({ top: 0, behavior: "smooth" });
        } else {
            window.scrollTo({ top: 0, behavior: "smooth" });
        }
        if (id === "view-accounts") renderAccountsView();
        if (id === "view-payments") renderPayments();
        if (id === "view-expenses") renderExpensesView();
        if (id === "view-savings") renderSavingsView();
        if (id === "view-statement") {
            initStatementDateRange();
            refreshStatement();
        }
        if (id === "view-copilot") {
            const box = document.getElementById("copilotChatMessages");
            box.scrollTop = box.scrollHeight;
        }
    }

    // Scroll progressivo contínuo ao descer a página no Extrato
    // Ouve tanto o window (mobile) como o main-content (desktop com scroll interno)
    function onAnyScroll() {
        const stmt = document.getElementById("view-statement");
        if (!stmt || !stmt.classList.contains("active")) return;
        if (typeof statementRenderedCount === "undefined" || statementRenderedCount >= statementFilteredTxs.length) return;
        const mc = document.querySelector(".main-content");
        if (mc && getComputedStyle(mc).overflowY === "auto") {
            if (mc.scrollTop + mc.clientHeight >= mc.scrollHeight - 400) renderStatementBatch();
        } else {
            if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 400) renderStatementBatch();
        }
    }
    window.addEventListener("scroll", onAnyScroll, { passive: true });
    document.querySelector(".main-content")?.addEventListener("scroll", onAnyScroll, { passive: true });

    initExpenseCategoryFilters();

    function showTab(tabId) {
        document.querySelectorAll(".tab-btn").forEach(t => t.classList.toggle("active", t.dataset.tab === tabId));
        document.querySelectorAll(".tab-pane").forEach(p => p.classList.toggle("active", p.id === tabId));
    }

    window.showView = showView;
    window.showTab = showTab;

    window.toggleMobileMenu = function() {
        const overlay = document.getElementById("mobileMenuOverlay");
        if (!overlay) return;
        const isHidden = overlay.style.display === "none" || !overlay.style.display;
        overlay.style.display = isHidden ? "flex" : "none";
        document.body.style.overflow = isHidden ? "hidden" : "";
    };

    window.closeMobileMenu = function() {
        const overlay = document.getElementById("mobileMenuOverlay");
        if (overlay) overlay.style.display = "none";
        document.body.style.overflow = "";
    };

    window.mobileNavTo = function(viewId) {
        window.closeMobileMenu();
        showView(viewId);
    };

    document.querySelectorAll("[data-view]").forEach(btn => btn.addEventListener("click", () => showView(btn.dataset.view)));
    document.querySelectorAll("[data-goto]").forEach(btn => btn.addEventListener("click", () => {
        if (btn.dataset.gotoTab) showTab(btn.dataset.gotoTab);
        showView(btn.dataset.goto);
    }));
    document.getElementById("btnToggleCopilot").addEventListener("click", () => showView("view-copilot"));

    // Ocultar / mostrar saldos — SEMPRE começa oculto por padrão
    document.body.classList.add("balances-hidden");
    const btnEyeTop = document.getElementById("btnToggleBalance");
    const btnEyeDash = document.getElementById("btnToggleDashBalance");
    // Mantém aria-label/aria-pressed e o título coerentes com o estado (o olho anima por CSS)
    function syncEyeButtons() {
        const hidden = document.body.classList.contains("balances-hidden");
        [btnEyeTop, btnEyeDash].forEach(btn => {
            if (!btn) return;
            btn.setAttribute("aria-pressed", String(hidden));
            btn.setAttribute("aria-label", hidden ? "Mostrar saldos" : "Ocultar saldos");
            btn.title = hidden ? "Mostrar saldos" : "Ocultar saldos";
        });
    }
    function toggleBalancesVisibility(ev) {
        document.body.classList.toggle("balances-hidden");
        syncEyeButtons();
        const btn = ev && ev.currentTarget;
        if (btn) {
            btn.classList.remove("eye-btn-pop");
            void btn.offsetWidth; // reinicia a animação
            btn.classList.add("eye-btn-pop");
        }
    }
    if (btnEyeTop) btnEyeTop.addEventListener("click", toggleBalancesVisibility);
    if (btnEyeDash) btnEyeDash.addEventListener("click", toggleBalancesVisibility);
    syncEyeButtons();

    // Seletor de moeda de preferência no Dashboard Hero
    document.querySelectorAll(".dash-curr-tag").forEach(tag => {
        tag.addEventListener("click", () => {
            const curr = tag.getAttribute("data-curr");
            state.prefCurrency = curr;
            localStorage.setItem("bankao_pref_currency", curr);
            updateDashboardHero();
        });
    });

    // Copiar chave da conta (e-mail)
    const btnCopyKey = document.getElementById("btnCopyDashEmail");
    if (btnCopyKey) {
        btnCopyKey.addEventListener("click", async () => {
            const email = document.getElementById("dashAccountEmail")?.textContent.trim();
            if (email && email !== "carregando...") {
                try { await navigator.clipboard.writeText(email); } catch (e) { /* ignore */ }
                toast("Chave da conta copiada: " + email, "success");
            }
        });
    }

    // Copiar conta / IBAN com um toque
    document.querySelectorAll(".copyable").forEach(el => el.addEventListener("click", async () => {
        const text = el.textContent.trim();
        try { await navigator.clipboard.writeText(text); } catch (e) { /* ignorar */ }
        el.classList.add("copied");
        setTimeout(() => el.classList.remove("copied"), 1200);
    }));

    // Fechar modais ao tocar fora
    document.querySelectorAll(".modal-overlay").forEach(m => m.addEventListener("click", e => {
        if (e.target === m && !m.classList.contains('kyc-overlay')) {
            m.classList.remove("active");
            if (m.id === "modalReceiveQr") closeReceiveQrModal();
            else setTimeout(() => { m.style.display = "none"; }, 250);
        }
    }));
}
