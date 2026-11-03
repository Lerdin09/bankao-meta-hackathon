/**
 * Shell da aplicação
 * Navegação entre vistas, menu móvel, saldos ocultos e copiar IBAN.
 */

// Navegação entre vistas, atalhos, saldos ocultos, copiar IBAN
function initShell() {
    const wide = window.matchMedia("(min-width: 1024px)");

    // Páginas abertas a partir de outra: o menu continua a marcar a página de origem
    const PARENT_VIEW = { "view-card-chart": "view-home" };

    // ---------- Copilot no telemóvel/tablet: página sobreposta que se fecha no X ----------
    let copilotHistoryPushed = false;

    // Acompanha a área realmente visível (o teclado encolhe-a) para o campo de escrita nunca ficar tapado
    function syncCopilotViewport() {
        const vv = window.visualViewport;
        const root = document.documentElement.style;
        if (!vv || !document.body.classList.contains("copilot-open")) return;
        root.setProperty("--vvh", Math.round(vv.height) + "px");
        root.setProperty("--vv-top", Math.round(vv.offsetTop) + "px");
        const kbd = window.innerHeight - vv.height > 120;
        document.body.classList.toggle("copilot-kbd", kbd);
        const box = document.getElementById("copilotChatMessages");
        if (box) box.scrollTop = box.scrollHeight;
    }

    function openCopilot() {
        const v = document.getElementById("view-copilot");
        if (!v || document.body.classList.contains("copilot-open")) return;
        if (window.closeMobileMenu) window.closeMobileMenu();
        document.body.classList.add("copilot-open");
        v.classList.add("active");
        syncCopilotViewport();
        const box = document.getElementById("copilotChatMessages");
        if (box) box.scrollTop = box.scrollHeight;
        try { history.pushState({ copilot: true }, ""); copilotHistoryPushed = true; } catch (_) { /* ignorar */ }
    }

    function closeCopilot(fromPopState) {
        if (!document.body.classList.contains("copilot-open")) return;
        const v = document.getElementById("view-copilot");
        if (v) {
            v.classList.remove("active");
            if (v.contains(document.activeElement)) document.activeElement.blur();   // fecha o teclado
        }
        document.body.classList.remove("copilot-open", "copilot-kbd");
        document.documentElement.style.removeProperty("--vvh");
        document.documentElement.style.removeProperty("--vv-top");
        if (!fromPopState && copilotHistoryPushed && history.state && history.state.copilot) {
            try { history.back(); } catch (_) { /* ignorar */ }
        }
        copilotHistoryPushed = false;
    }
    window.openCopilot = openCopilot;
    window.closeCopilot = closeCopilot;

    if (window.visualViewport) {
        window.visualViewport.addEventListener("resize", syncCopilotViewport);
        window.visualViewport.addEventListener("scroll", syncCopilotViewport);
    }
    window.addEventListener("popstate", () => closeCopilot(true));      // botão "voltar" do telemóvel
    document.addEventListener("keydown", e => { if (e.key === "Escape") closeCopilot(); });
    wide.addEventListener("change", () => { if (wide.matches) closeCopilot(); });

    function showView(id) {
        if (id === "view-copilot") {
            if (wide.matches) {
                // No ecrã largo (desktop >= 1024px) o Copilot está sempre visível na parede direita
                const input = document.getElementById("copilotUserInput");
                if (input) input.focus();
                const box = document.getElementById("copilotChatMessages");
                if (box) box.scrollTop = box.scrollHeight;
            } else {
                openCopilot();   // por cima da página atual, sem a trocar
            }
            return;
        }
        // Ir para outra página fecha o Copilot sobreposto
        closeCopilot();
        document.querySelectorAll(".view").forEach(v => {
            if (v.id === "view-copilot") return;
            v.classList.toggle("active", v.id === id);
        });
        const navId = PARENT_VIEW[id] || id;
        document.querySelectorAll("[data-view]").forEach(b => b.classList.toggle("active", b.dataset.view === navId));
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
        if (id === "view-card-chart") renderCardChart();
        if (id === "view-investments") loadInvestmentsData();
        if (id === "view-cards") loadCardsData();
        if (id === "view-statement") {
            initStatementDateRange();
            refreshStatement();
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
    document.querySelectorAll("[data-goto]").forEach(el => {
        const go = () => {
            if (el.dataset.gotoTab) showTab(el.dataset.gotoTab);
            showView(el.dataset.goto);
        };
        el.addEventListener("click", go);
        // Elementos que não são <button>/<a> (ex.: linhas de contas) também funcionam com o teclado
        if (!/^(BUTTON|A)$/.test(el.tagName)) {
            if (!el.hasAttribute("tabindex")) el.tabIndex = 0;
            if (!el.hasAttribute("role")) el.setAttribute("role", "button");
            el.addEventListener("keydown", ev => {
                if (ev.target !== el) return;
                if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); go(); }
            });
        }
    });
    document.getElementById("btnToggleCopilot").addEventListener("click", () => showView("view-copilot"));

    // Ocultar / mostrar saldos — SEMPRE começa oculto por padrão
    // (bal-no-anim evita que a troca valor→máscara se anime ao abrir a app)
    document.body.classList.add("bal-no-anim", "balances-hidden");
    requestAnimationFrame(() => requestAnimationFrame(() => document.body.classList.remove("bal-no-anim")));
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
            if (typeof renderHomeTrend === "function") renderHomeTrend();
        });
    });

    // Copiar chave da conta (e-mail)
    const btnCopyKey = document.getElementById("btnCopyDashEmail");
    if (btnCopyKey) {
        btnCopyKey.addEventListener("click", async () => {
            const email = document.getElementById("dashAccountEmail")?.textContent.trim();
            if (!email || email === "carregando...") return;
            const ok = await qrCopyText(email);   // com alternativa para páginas sem HTTPS
            if (ok) {
                btnCopyKey.classList.add("copied");
                clearTimeout(btnCopyKey._copiedTimer);
                btnCopyKey._copiedTimer = setTimeout(() => btnCopyKey.classList.remove("copied"), 1500);
                toast("Chave da conta copiada: " + email, "success");
            } else {
                toast("Não foi possível copiar. Selecione a chave e copie manualmente.", "error");
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
