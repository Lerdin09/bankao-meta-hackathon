/**
 * Utilitários de interface
 * escapeHtml e toast.
 */

// Utilitários de interface
function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function toast(message, type) {
    const stack = document.getElementById("toastStack");
    if (!stack) return;
    const kind = type || (/sucesso|enviada|confirmado|copiado/i.test(message) ? "success" : "error");
    const el = document.createElement("div");
    el.className = `toast ${kind}`;
    el.setAttribute("role", "status");
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 260); }, 4200);
}
