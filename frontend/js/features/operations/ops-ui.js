/**
 * Operações — interface
 * • Valores rápidos (chips) do depósito
 * • Resumo do depósito em tempo real
 * • Acessibilidade dos separadores (aria-selected + setas do teclado)
 * Não altera a lógica de envio — só a camada visual.
 */
(function () {
    const section = document.querySelector(".operations-section");
    if (!section) return;

    // ---------- Valor rápido + resumo ----------
    function fmt(value) {
        const n = parseFloat(value);
        if (!isFinite(n)) return "—";
        return (typeof formatMoney === "function")
            ? formatMoney(n, "AOA")
            : n.toLocaleString("pt-PT", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " Kz";
    }
    function refreshAmount(inputId) {
        const input = document.getElementById(inputId);
        if (!input) return;
        section.querySelectorAll(`[data-mirror="${inputId}"]`).forEach(el => { el.textContent = fmt(input.value); });
        const current = parseFloat(input.value);
        section.querySelectorAll(`.op-chip[data-target="${inputId}"]`).forEach(chip => {
            chip.classList.toggle("active", parseFloat(chip.dataset.amount) === current);
        });
    }
    section.querySelectorAll(".op-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            const input = document.getElementById(chip.dataset.target);
            if (!input) return;
            input.value = chip.dataset.amount;
            input.dispatchEvent(new Event("input", { bubbles: true }));
        });
    });
    ["expressAmount", "refAmount"].forEach(id => {
        const input = document.getElementById(id);
        if (!input) return;
        input.addEventListener("input", () => refreshAmount(id));
        refreshAmount(id);
    });

    // ---------- Separadores: ARIA + teclado ----------
    const tabs = Array.from(section.querySelectorAll(".tab-btn"));
    function syncAria() {
        tabs.forEach(t => t.setAttribute("aria-selected", String(t.classList.contains("active"))));
    }
    const tabsNav = section.querySelector(".tabs-nav");
    if (tabsNav) new MutationObserver(syncAria).observe(tabsNav, { attributes: true, attributeFilter: ["class"], subtree: true });
    syncAria();
    tabsNav && tabsNav.addEventListener("keydown", (e) => {
        if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
        const i = tabs.indexOf(document.activeElement);
        if (i < 0) return;
        const n = (i + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
        tabs[n].focus(); tabs[n].click(); e.preventDefault();
    });
})();
