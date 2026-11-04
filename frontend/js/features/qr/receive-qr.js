/**
 * Receber por QR
 * Modal "Receber transferência": nome da conta → QR → chave → IBAN → copiar dados.
 * O QR é gerado localmente (qr-encoder.js): nenhum dado da conta sai do dispositivo.
 */

// =====================================================================
//  QR estilizado (SVG): módulos arredondados, olhos de posição redondos e logótipo ao centro
// =====================================================================
function buildBankAoQrSvg(payload) {
    const qr = QrEncoder.encode(payload, "M");          // nível M tolera o logótipo ao centro
    const n = qr.size, quiet = 4, total = n + quiet * 2;

    // Zona do logótipo (ímpar, ~17% do lado → ~3% da área, bem dentro da tolerância de M)
    let logo = Math.round(n * 0.17); if (logo % 2 === 0) logo++;
    const l0 = Math.floor((n - logo) / 2), l1 = l0 + logo;
    const inLogo = (x, y) => x >= l0 - 1 && x <= l1 && y >= l0 - 1 && y <= l1;
    const inFinder = (x, y) => (x < 7 && y < 7) || (x >= n - 7 && y < 7) || (x < 7 && y >= n - 7);

    const r = 0.3, w = +(1 - 2 * r).toFixed(2);
    let d = "";
    for (let y = 0; y < n; y++) {
        for (let x = 0; x < n; x++) {
            if (!qr.modules[y][x] || inFinder(x, y) || inLogo(x, y)) continue;
            const px = x + quiet, py = y + quiet;
            d += `M${px + r},${py}h${w}a${r},${r} 0 0 1 ${r},${r}v${w}a${r},${r} 0 0 1 -${r},${r}h-${w}a${r},${r} 0 0 1 -${r},-${r}v-${w}a${r},${r} 0 0 1 ${r},-${r}z`;
        }
    }

    const finder = (ox, oy) => {
        const x = ox + quiet, y = oy + quiet;
        return `<rect x="${x}" y="${y}" width="7" height="7" rx="0.5" fill="url(#qrInk)"/>` +
               `<rect x="${x + 1}" y="${y + 1}" width="5" height="5" rx="0.25" fill="#fff"/>` +
               `<rect x="${x + 2}" y="${y + 2}" width="3" height="3" rx="0.35" fill="#1D4ED8"/>`;
    };

    const bx = l0 + quiet - 0.5, bs = logo + 1;           // caixa branca do logótipo
    const ix = bx + 0.55, is = bs - 1.1;                  // miolo escuro
    const badge =
        `<rect x="${bx}" y="${bx}" width="${bs}" height="${bs}" rx="${bs * 0.28}" fill="#fff"/>` +
        `<rect x="${ix}" y="${ix}" width="${is}" height="${is}" rx="${is * 0.26}" fill="url(#qrBadge)"/>` +
        `<text x="${total / 2}" y="${total / 2}" text-anchor="middle" dominant-baseline="central" font-family="'Plus Jakarta Sans',system-ui,sans-serif" font-weight="900" font-size="${is * 0.62}" fill="#fff">B</text>`;

    return `<svg viewBox="0 0 ${total} ${total}" xmlns="http://www.w3.org/2000/svg" shape-rendering="geometricPrecision">` +
        `<defs>` +
        `<linearGradient id="qrInk" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="${total}" y2="${total}"><stop offset="0" stop-color="#0B1530"/><stop offset="1" stop-color="#1B2670"/></linearGradient>` +
        `<linearGradient id="qrBadge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#38BDF8"/><stop offset="1" stop-color="#4F46E5"/></linearGradient>` +
        `</defs>` +
        `<rect width="${total}" height="${total}" fill="#fff"/>` +
        `<path d="${d}" fill="url(#qrInk)"/>` +
        finder(0, 0) + finder(n - 7, 0) + finder(0, n - 7) +
        badge + `</svg>`;
}

function renderReceiveQr(dataString) {
    const container = document.getElementById("qrCanvasContainer");
    if (!container) return;
    try {
        container.innerHTML = buildBankAoQrSvg(dataString);
    } catch (err) {
        console.error("QR:", err);
        container.innerHTML = '<p style="padding:24px;text-align:center;color:#475569;font-size:.85rem">Não foi possível gerar o código QR. Use a chave ou o IBAN abaixo.</p>';
    }
}

// =====================================================================
//  Abrir / fechar
// =====================================================================
function openReceiveQrModal() {
    const m = document.getElementById("modalReceiveQr");
    if (!m) return;

    const user = state.user || {};
    const name = user.nome || user.email?.split("@")[0] || "Cliente BankAO";
    const email = user.email || "cliente@bankao.ao";
    const aoaAcc = state.accountAoa || (state.accounts && state.accounts.find(a => a.currency === "AOA")) || null;
    const iban = aoaAcc ? groupDigits(aoaAcc.iban_virtual) : "AO06 0055 0000 0000 0000 0000 0";

    const setText = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    setText("qrModalUserName", name);
    setText("qrModalUserEmail", email);
    setText("qrModalUserIban", iban);
    setText("qrModalUserStatus", user.kyc_status === "verificado" ? "Conta Verificada BankAO" : "Conta Ativa BankAO");

    window.__qrAcc = { email, name, iban: aoaAcc ? aoaAcc.iban_virtual : "", account: aoaAcc ? aoaAcc.account_number : "" };
    const amtEl = document.getElementById("qrAmountInput");
    if (amtEl) amtEl.value = "";
    refreshReceiveQr();

    // repõe o estado dos botões de copiar
    m.querySelectorAll(".copied").forEach(el => el.classList.remove("copied"));
    const card = m.querySelector(".qr-modal-card");
    if (card) card.scrollTop = 0;

    m.style.display = "flex";
    setTimeout(() => m.classList.add("active"), 10);
    document.addEventListener("keydown", qrEscClose);
}
window.openReceiveQrModal = openReceiveQrModal;

function closeReceiveQrModal() {
    const m = document.getElementById("modalReceiveQr");
    document.removeEventListener("keydown", qrEscClose);
    if (m) {
        m.classList.remove("active");
        setTimeout(() => { m.style.display = "none"; }, 250);
    }
}
window.closeReceiveQrModal = closeReceiveQrModal;

function qrEscClose(e) { if (e.key === "Escape") closeReceiveQrModal(); }

// =====================================================================
//  Copiar (chave, IBAN, ou os dois)
// =====================================================================
async function qrCopyText(text) {
    try {
        if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(text); return true; }
    } catch (e) { /* tenta o método antigo */ }
    try {   // alternativa para páginas sem HTTPS / navegadores antigos
        const ta = document.createElement("textarea");
        ta.value = text; ta.setAttribute("readonly", "");
        ta.style.cssText = "position:fixed;top:0;left:0;opacity:0;pointer-events:none";
        document.body.appendChild(ta); ta.select(); ta.setSelectionRange(0, text.length);
        const ok = document.execCommand("copy");
        ta.remove();
        return ok;
    } catch (e) { return false; }
}

function qrFlash(btn) {
    if (!btn) return;
    btn.classList.add("copied");
    clearTimeout(btn._qrTimer);
    btn._qrTimer = setTimeout(() => btn.classList.remove("copied"), 1800);
}

async function copyQrAccountEmail() {
    const email = document.getElementById("qrModalUserEmail")?.textContent.trim();
    if (!email || email === "carregando...") return;
    if (await qrCopyText(email)) { qrFlash(document.getElementById("btnCopyQrEmail")); toast("Chave copiada: " + email, "success"); }
    else toast("Não foi possível copiar. Selecione e copie manualmente.", "error");
}
window.copyQrAccountEmail = copyQrAccountEmail;

async function copyQrAccountIban() {
    const iban = document.getElementById("qrModalUserIban")?.textContent.trim();
    if (!iban || iban === "carregando...") return;
    if (await qrCopyText(iban)) { qrFlash(document.getElementById("btnCopyQrIban")); toast("IBAN copiado: " + iban, "success"); }
    else toast("Não foi possível copiar. Selecione e copie manualmente.", "error");
}
window.copyQrAccountIban = copyQrAccountIban;

// "Copiar dados (chave e IBAN)": um texto pronto a colar numa mensagem
async function shareQrDetails() {
    const name = document.getElementById("qrModalUserName")?.textContent.trim();
    const email = document.getElementById("qrModalUserEmail")?.textContent.trim();
    const iban = document.getElementById("qrModalUserIban")?.textContent.trim();
    if (!email || email === "carregando...") return;

    const fullInfo =
`Dados para transferência BankAO
Titular: ${name}
Chave (e-mail): ${email}
IBAN (AOA): ${iban}`;

    if (await qrCopyText(fullInfo)) {
        qrFlash(document.getElementById("btnCopyQrAll"));
        qrFlash(document.getElementById("btnCopyQrEmail"));
        qrFlash(document.getElementById("btnCopyQrIban"));
        toast("Dados copiados para partilhar", "success");
    } else {
        toast("Não foi possível copiar. Selecione e copie manualmente.", "error");
    }
}
window.shareQrDetails = shareQrDetails;

// O QR leva os dados da conta (e, se indicado, o valor): quem o ler já recebe tudo preenchido
function buildReceivePayload() {
    const a = window.__qrAcc || {};
    let p = `BANKAO:PAY?email=${encodeURIComponent(a.email || "")}&name=${encodeURIComponent(a.name || "")}` +
            `&iban=${encodeURIComponent(a.iban || "")}&account=${encodeURIComponent(a.account || "")}`;
    const raw = (document.getElementById("qrAmountInput")?.value || "").replace(/\s/g, "");
    const amount = Number(raw.replace(/\.(?=\d{3}\b)/g, "").replace(",", "."));
    if (amount > 0) p += `&amount=${amount}&currency=AOA`;
    return p;
}
function refreshReceiveQr() { renderReceiveQr(buildReceivePayload()); }
window.refreshReceiveQr = refreshReceiveQr;

// Descarregar o QR como imagem PNG (com nome e IBAN por baixo)
async function downloadReceiveQr() {
    const svg = document.querySelector("#qrCanvasContainer svg");
    if (!svg) return toast("O QR ainda não está pronto.", "error");
    try {
        const clone = svg.cloneNode(true);
        clone.setAttribute("width", "1000"); clone.setAttribute("height", "1000");
        const img = new Image();
        await new Promise((ok, fail) => {
            img.onload = ok; img.onerror = fail;
            img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(clone));
        });
        const a = window.__qrAcc || {}, pad = 60, S = 1000;
        const cv = document.createElement("canvas");
        cv.width = S + pad * 2; cv.height = S + pad * 2 + 170;
        const c = cv.getContext("2d");
        c.fillStyle = "#fff"; c.fillRect(0, 0, cv.width, cv.height);
        c.drawImage(img, pad, pad, S, S);
        c.textAlign = "center"; c.fillStyle = "#0B1530";
        c.font = "700 46px system-ui, sans-serif"; c.fillText(a.name || "Cliente BankAO", cv.width / 2, S + pad * 2 + 20);
        c.fillStyle = "#475569"; c.font = "500 32px ui-monospace, monospace"; c.fillText(groupDigits(a.iban || ""), cv.width / 2, S + pad * 2 + 72);
        c.font = "600 26px system-ui, sans-serif"; c.fillText("Leia com a app BankAO para transferir", cv.width / 2, S + pad * 2 + 122);
        cv.toBlob(blob => {
            const link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.download = "QR-BankAO-" + (a.name || "conta").toLowerCase().replace(/[^a-z0-9]+/g, "-") + ".png";
            document.body.appendChild(link); link.click(); link.remove();
            setTimeout(() => URL.revokeObjectURL(link.href), 4000);
            toast("QR descarregado.", "success");
        }, "image/png");
    } catch (err) {
        console.error(err);
        toast("Não foi possível descarregar o QR.", "error");
    }
}
window.downloadReceiveQr = downloadReceiveQr;
