/**
 * Receber por QR
 * Modal "Receber transferência": nome da conta → QR → chave → IBAN → copiar dados.
 * O QR é gerado localmente (qr-encoder.js): nenhum dado da conta sai do dispositivo.
 */

// =====================================================================
//  QR em SVG — preto sobre branco, módulos quadrados, olhos de posição normais e margem de 4 módulos.
//  Sem logótipo, sem gradientes e sem cantos redondos: é o formato que qualquer câmara ou leitor lê.
// =====================================================================
function buildBankAoQrSvg(payload) {
    const qr = QrEncoder.encode(payload, "M");
    const n = qr.size, quiet = 4, total = n + quiet * 2;
    let d = "";
    for (let y = 0; y < n; y++) {                       // junta módulos seguidos na mesma linha (SVG mais leve)
        let x = 0;
        while (x < n) {
            if (!qr.modules[y][x]) { x++; continue; }
            let x2 = x; while (x2 < n && qr.modules[y][x2]) x2++;
            d += `M${x + quiet},${y + quiet}h${x2 - x}v1h-${x2 - x}z`;
            x = x2;
        }
    }
    return `<svg viewBox="0 0 ${total} ${total}" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges">` +
        `<rect width="${total}" height="${total}" fill="#fff"/><path d="${d}" fill="#000"/></svg>`;
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

// O QR leva os dados da conta (e, se indicado, o valor). Conteúdo curto = menos módulos = leitura mais fácil.
// Chaves: e=e-mail, n=nome, i=IBAN, a=nº de conta, v=valor, c=moeda.
function buildReceivePayload() {
    const a = window.__qrAcc || {};
    const enc = encodeURIComponent;
    const parts = [];
    if (a.email)   parts.push("e=" + enc(a.email));
    if (a.account) parts.push("a=" + enc(String(a.account).replace(/\s/g, "")));
    if (a.iban)    parts.push("i=" + enc(String(a.iban).replace(/\s/g, "")));
    if (a.name)    parts.push("n=" + enc(String(a.name).trim().slice(0, 28)));
    const raw = (document.getElementById("qrAmountInput")?.value || "").replace(/\s/g, "");
    const normalized = raw.includes(",") ? raw.replace(/\./g, "").replace(",", ".") : raw.replace(/\.(?=\d{3}\b)/g, "");
    const amount = Number(normalized);
    if (isFinite(amount) && amount > 0) parts.push("v=" + (Math.round(amount * 100) / 100) + "&c=AOA");
    return "BANKAO:PAY?" + parts.join("&");
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
        const vm = /[?&]v=([\d.]+)/.exec(buildReceivePayload());
        const amountTxt = vm ? Number(vm[1]).toLocaleString("pt-PT", { minimumFractionDigits: 0, maximumFractionDigits: 2 }) + " Kz" : "";
        const extra = amountTxt ? 80 : 0;
        cv.width = S + pad * 2; cv.height = S + pad * 2 + 170 + extra;
        const c = cv.getContext("2d");
        c.fillStyle = "#fff"; c.fillRect(0, 0, cv.width, cv.height);
        c.drawImage(img, pad, pad, S, S);
        c.textAlign = "center"; c.fillStyle = "#0B1530";
        c.font = "700 46px system-ui, sans-serif"; c.fillText(a.name || "Cliente BankAO", cv.width / 2, S + pad * 2 + 20);
        let yy = S + pad * 2 + 20;
        if (amountTxt) { yy += 76; c.fillStyle = "#0B1530"; c.font = "800 62px system-ui, sans-serif"; c.fillText(amountTxt, cv.width / 2, yy); }
        c.fillStyle = "#475569"; c.font = "500 32px ui-monospace, monospace"; c.fillText(groupDigits(a.iban || ""), cv.width / 2, yy + 52);
        c.font = "600 26px system-ui, sans-serif"; c.fillText("Leia com a app BankAO para transferir", cv.width / 2, yy + 102);
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
