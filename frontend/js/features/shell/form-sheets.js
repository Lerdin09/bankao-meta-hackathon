/**
 * Formulários em modal (mobile) — ao focar um campo, centra-o na área visível
 * para o teclado nunca o tapar.
 */
document.addEventListener("focusin", (e) => {
    const el = e.target;
    if (!el || !el.matches || !el.matches("input, select, textarea")) return;
    if (!el.closest(".form-modal .confirm-modal-body")) return;
    setTimeout(() => {
        try { el.scrollIntoView({ block: "center", behavior: "smooth" }); } catch (_) { /* ignore */ }
    }, 300);
});
