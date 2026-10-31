/**
 * Diálogo de confirmação reutilizável (substitui o confirm() do browser).
 * Uso: const ok = await confirmDialog({ title, message, details:[{label,value}], note, confirmText, tone });
 */
window.confirmDialog = function (opts = {}) {
    const {
        title = "Tem a certeza?", message = "", details = [], note = "",
        confirmText = "Confirmar", cancelText = "Cancelar", tone = "danger", icon = "#i-trash"
    } = opts;
    const esc = (v) => (typeof escapeHtml === "function" ? escapeHtml(String(v)) : String(v));

    return new Promise((resolve) => {
        const prevFocus = document.activeElement;
        const root = document.createElement("div");
        root.className = "cd-overlay";
        root.innerHTML = `
            <div class="cd-card" role="alertdialog" aria-modal="true" aria-labelledby="cdTitle" data-tone="${tone}">
                <div class="cd-icon"><svg><use href="${icon}"/></svg></div>
                <h3 id="cdTitle">${esc(title)}</h3>
                ${message ? `<p class="cd-msg">${esc(message)}</p>` : ""}
                ${details.length ? `<dl class="cd-details">${details.map(d => `<div><dt>${esc(d.label)}</dt><dd>${esc(d.value)}</dd></div>`).join("")}</dl>` : ""}
                ${note ? `<p class="cd-note">${esc(note)}</p>` : ""}
                <div class="cd-actions">
                    <button type="button" class="cd-btn" data-act="cancel">${esc(cancelText)}</button>
                    <button type="button" class="cd-btn cd-confirm" data-act="ok">${esc(confirmText)}</button>
                </div>
            </div>`;
        document.body.appendChild(root);
        document.body.classList.add("cd-open");

        const btns = root.querySelectorAll(".cd-btn");
        const finish = (val) => {
            document.removeEventListener("keydown", onKey, true);
            root.classList.add("is-closing");
            setTimeout(() => {
                root.remove();
                if (!document.querySelector(".cd-overlay")) document.body.classList.remove("cd-open");
                if (prevFocus && prevFocus.focus) { try { prevFocus.focus({ preventScroll: true }); } catch (_) { /* ignore */ } }
                resolve(val);
            }, 160);
        };
        const onKey = (e) => {
            if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); finish(false); }
            else if (e.key === "Tab") {
                e.preventDefault();
                const i = [...btns].indexOf(document.activeElement);
                btns[(i + (e.shiftKey ? -1 : 1) + btns.length) % btns.length].focus();
            }
        };
        document.addEventListener("keydown", onKey, true);
        root.addEventListener("click", (e) => {
            if (e.target === root) return finish(false);
            const b = e.target.closest(".cd-btn");
            if (b) finish(b.dataset.act === "ok");
        });
        btns[0].focus({ preventScroll: true }); // foco no "Cancelar": o gesto seguro
    });
};
