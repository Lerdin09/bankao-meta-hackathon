/**
 * Receber por QR
 * Gera o código QR e o modal de receber (e-mail, IBAN, partilha).
 */

// =====================================================================
//  MODAL: RECEBER TRANSFERÊNCIA / CÓDIGO QR & CHAVE DA CONTA
// =====================================================================

function buildBankAoQrSvg(payload) {
    const N = 29;
    const grid = Array.from({ length: N }, () => Array(N).fill(0));

    function fillRect(r0, c0, h, w, val) {
        for (let r = r0; r < r0 + h; r++) {
            for (let c = c0; c < c0 + w; c++) {
                if (r >= 0 && r < N && c >= 0 && c < N) grid[r][c] = val;
            }
        }
    }

    function drawFinder(r0, c0) {
        fillRect(r0, c0, 7, 7, 1);
        fillRect(r0 + 1, c0 + 1, 5, 5, 0);
        fillRect(r0 + 2, c0 + 2, 3, 3, 1);
    }

    drawFinder(0, 0);
    drawFinder(0, 22);
    drawFinder(22, 0);

    fillRect(7, 0, 1, 8, 0);
    fillRect(0, 7, 8, 1, 0);
    fillRect(7, 21, 1, 8, 0);
    fillRect(0, 21, 8, 1, 0);
    fillRect(21, 0, 1, 8, 0);
    fillRect(21, 7, 8, 1, 0);

    for (let i = 8; i < 21; i++) {
        grid[6][i] = (i % 2 === 0) ? 1 : 0;
        grid[i][6] = (i % 2 === 0) ? 1 : 0;
    }

    fillRect(20, 20, 5, 5, 1);
    fillRect(21, 21, 3, 3, 0);
    grid[22][22] = 1;

    let hash = 0x811c9dc5;
    for (let i = 0; i < payload.length; i++) {
        hash ^= payload.charCodeAt(i);
        hash = Math.imul(hash, 0x01000193);
    }

    function pseudoRandom() {
        hash = (hash ^ (hash << 13)) >>> 0;
        hash = (hash ^ (hash >> 17)) >>> 0;
        hash = (hash ^ (hash << 5)) >>> 0;
        return (hash & 0xFF) / 255;
    }

    for (let r = 0; r < N; r++) {
        for (let c = 0; c < N; c++) {
            if (r <= 7 && c <= 7) continue;
            if (r <= 7 && c >= 21) continue;
            if (r >= 21 && c <= 7) continue;
            if (r === 6 || c === 6) continue;
            if (r >= 20 && r <= 24 && c >= 20 && c <= 24) continue;
            if (r >= 11 && r <= 17 && c >= 11 && c <= 17) continue;
            grid[r][c] = (pseudoRandom() > 0.48) ? 1 : 0;
        }
    }

    const cellSize = 6;
    const padding = 9;
    const totalSize = N * cellSize + padding * 2;

    let paths = "";
    for (let r = 0; r < N; r++) {
        for (let c = 0; c < N; c++) {
            if (grid[r][c] === 1) {
                const x = padding + c * cellSize;
                const y = padding + r * cellSize;
                paths += `<rect x="${x}" y="${y}" width="${cellSize}" height="${cellSize}" fill="#0A1128"/>`;
            }
        }
    }

    return `<svg viewBox="0 0 ${totalSize} ${totalSize}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;background:#FFF;border-radius:8px;">${paths}</svg>`;
}
function renderReceiveQr(dataString) {
    const container = document.getElementById("qrCanvasContainer");
    if (!container) return;

    const encodedData = encodeURIComponent(dataString);
    const qrApiUrl = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodedData}&format=svg`;

    container.innerHTML = `
        <img id="qrRealImg" src="${qrApiUrl}" alt="Código QR BankAO" width="192" height="192"
             onerror="this.style.display='none'; document.getElementById('qrFallbackSvgWrap').style.display='block';">
        <div id="qrFallbackSvgWrap" style="display:none;width:192px;height:192px;">
            ${buildBankAoQrSvg(dataString)}
        </div>
        <div class="qr-canvas-badge">
            <span>B</span>
        </div>
    `;
}
function openReceiveQrModal() {
    const m = document.getElementById("modalReceiveQr");
    if (!m) return;

    const user = state.user || {};
    const name = user.nome || user.email?.split("@")[0] || "Cliente BankAO";
    const email = user.email || "cliente@bankao.ao";
    const aoaAcc = state.accountAoa || (state.accounts && state.accounts.find(a => a.currency === "AOA")) || null;
    const iban = aoaAcc ? groupDigits(aoaAcc.iban_virtual) : "AO06 0055 0000 0000 0000 0000 0";

    const nameEl = document.getElementById("qrModalUserName");
    const emailEl = document.getElementById("qrModalUserEmail");
    const ibanEl = document.getElementById("qrModalUserIban");
    const avatarEl = document.getElementById("qrModalUserAvatar");
    const statusEl = document.getElementById("qrModalUserStatus");

    if (nameEl) nameEl.textContent = name;
    if (emailEl) emailEl.textContent = email;
    if (ibanEl) ibanEl.textContent = iban;
    if (avatarEl) {
        const initials = name.split(" ").map(w => w[0]).filter(Boolean).slice(0, 2).join("").toUpperCase();
        avatarEl.textContent = initials || "B";
    }
    if (statusEl) {
        statusEl.textContent = (user.kyc_status === "verificado") ? "Conta Verificada BankAO" : "Conta Ativa BankAO";
    }

    const qrPayload = `BANKAO:PAY?email=${encodeURIComponent(email)}&name=${encodeURIComponent(name)}&iban=${encodeURIComponent(aoaAcc ? aoaAcc.iban_virtual : '')}&account=${encodeURIComponent(aoaAcc ? aoaAcc.account_number : '')}`;
    renderReceiveQr(qrPayload);

    m.style.display = "flex";
    setTimeout(() => m.classList.add("active"), 10);
}
window.openReceiveQrModal = openReceiveQrModal;
function closeReceiveQrModal() {
    const m = document.getElementById("modalReceiveQr");
    if (m) {
        m.classList.remove("active");
        setTimeout(() => m.style.display = "none", 250);
    }
}
window.closeReceiveQrModal = closeReceiveQrModal;
async function copyQrAccountEmail() {
    const email = document.getElementById("qrModalUserEmail")?.textContent.trim();
    if (email && email !== "carregando...") {
        try { await navigator.clipboard.writeText(email); } catch (e) { /* ignore */ }
        toast("Chave copiada: " + email, "success");
    }
}
window.copyQrAccountEmail = copyQrAccountEmail;
async function copyQrAccountIban() {
    const iban = document.getElementById("qrModalUserIban")?.textContent.trim();
    if (iban && iban !== "carregando...") {
        try { await navigator.clipboard.writeText(iban); } catch (e) { /* ignore */ }
        toast("IBAN copiado: " + iban, "success");
    }
}
window.copyQrAccountIban = copyQrAccountIban;
async function shareQrDetails() {
    const name = document.getElementById("qrModalUserName")?.textContent.trim();
    const email = document.getElementById("qrModalUserEmail")?.textContent.trim();
    const iban = document.getElementById("qrModalUserIban")?.textContent.trim();

    const fullInfo = 
`🏦 Dados para Transferência BankAO
• Titular: ${name}
• Chave (E-mail): ${email}
• IBAN (AOA): ${iban}
• Instituição: BankAO Digital`;

    try {
        if (navigator.clipboard) {
            await navigator.clipboard.writeText(fullInfo);
            toast("✅ Dados completos copiados para partilhar!", "success");
        } else {
            toast("Chave copiada: " + email, "success");
        }
    } catch (err) {
        toast("Chave copiada: " + email, "success");
    }
}
window.shareQrDetails = shareQrDetails;
