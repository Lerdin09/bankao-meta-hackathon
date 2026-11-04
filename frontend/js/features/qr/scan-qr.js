/**
 * Transferir por QR
 * Lê o QR (câmara, imagem ou código colado), mostra os dados da conta que vêm DENTRO do QR e,
 * com o valor, deixa só o pagamento: "Pagar" abre a confirmação da transferência.
 * Leitura: BarcodeDetector (se o navegador tiver) → leitor local qr-decoder.js (funciona em qualquer
 * navegador, sem internet) → jsQR (cdnjs, só como último recurso para fotos difíceis).
 */
(function () {
    let stream = null, rafId = 0, scanning = false;

    // ---- interpretar o conteúdo lido ----
    function parseQr(text) {
        text = String(text || "").trim();
        if (/^BANKAO:PAY\?/i.test(text)) {
            const q = new URLSearchParams(text.replace(/^BANKAO:PAY\?/i, ""));
            const g = (...k) => { for (const x of k) { const v = q.get(x); if (v) return v; } return ""; };
            const amount = Number(g("v", "amount"));
            const d = { email: g("e", "email"), name: g("n", "name"), iban: g("i", "iban").replace(/\s/g, ""),
                        account: g("a", "account"), amount: amount > 0 ? amount : 0, currency: (g("c", "currency") || "AOA").toUpperCase() };
            return (d.email || d.account || d.iban) ? d : null;
        }
        const iban = text.replace(/\s/g, "").toUpperCase();
        if (/^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$/.test(iban)) return { iban, email: "", name: "", account: "", amount: 0, currency: "AOA" };
        if (/^\S+@\S+\.\S+$/.test(text)) return { email: text, name: "", iban: "", account: "", amount: 0, currency: "AOA" };
        return null;
    }
    const curLabel = (c) => ({ AOA: "Kz", USD: "$", EUR: "€" }[c] || c);
    const money = (n, c) => Number(n).toLocaleString("pt-PT", { maximumFractionDigits: 2 }) + " " + curLabel(c || "AOA");
    const esc = (s) => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const groupAcc = (s) => String(s).replace(/\s/g, "").replace(/(\d{4})(?=\d)/g, "$1 ");
    const groupIban = (s) => String(s).replace(/\s/g, "").replace(/(.{4})/g, "$1 ").trim();

    // ---- preencher o formulário e avançar para a confirmação ----
    function setField(id, v) {
        const el = document.getElementById(id); if (!el) return;
        el.value = v; el.dispatchEvent(new Event("input", { bubbles: true })); el.dispatchEvent(new Event("change", { bubbles: true }));
    }
    function fillTransfer(d) {
        const internal = d.email || d.account;
        if (window.showView) window.showView("view-ops");
        if (window.showTab) window.showTab(internal ? "tab-transfer-internal" : "tab-transfer-iban");
        // O valor do QR vem na moeda do QR (AOA por omissão): acertar a moeda ANTES do valor.
        const cur = ["AOA", "USD", "EUR"].includes(d.currency) ? d.currency : "AOA";
        if (internal) {
            setField("internalDestEmail", d.email || d.account);
            if (d.amount) { setField("internalSendCurrency", cur); setField("internalAmount", d.amount); }
            if (d.name) setField("internalDesc", "Transferência para " + d.name);
        } else {
            setField("ibanInput", d.iban);
            if (d.name) setField("beneficiaryName", d.name);
            if (d.amount) { setField("ibanSendCurrency", cur); setField("ibanSendAmount", d.amount); }
        }
        return internal ? "formTransferInternal" : "formTransferIban";
    }
    const sleep = (ms) => new Promise(r => setTimeout(r, ms));
    async function payNow(d) {
        const formId = fillTransfer(d);
        if (formId === "formTransferInternal") {            // espera pela verificação do destinatário (nome do titular)
            for (let i = 0; i < 20; i++) {
                await sleep(150);
                const t = document.getElementById("recipientLookupStatus")?.textContent || "";
                if (!/procurar/i.test(t) && i > 2) break;
            }
        } else await sleep(200);
        const form = document.getElementById(formId);
        if (!form) return;
        if (form.requestSubmit) form.requestSubmit(); else form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
    }

    // ---- ecrã com os dados lidos do QR + Pagar ----
    async function lookupHolder(d) {
        try {
            if (typeof API_BASE === "undefined" || typeof state === "undefined" || !(d.email || d.account)) return null;
            const qs = d.email ? `email=${encodeURIComponent(d.email)}` : `account=${encodeURIComponent(d.account)}`;
            const res = await fetch(`${API_BASE}/api/users/lookup?${qs}`, { headers: state.token ? { Authorization: `Bearer ${state.token}` } : {} });
            if (!res.ok) return null;
            const j = await res.json();
            return j.found ? { name: j.nome } : { name: "" };
        } catch (_) { return null; }
    }

    function showResult(d) {
        closeResult();
        const mine = typeof state !== "undefined" && state.user && d.email && state.user.email &&
                     d.email.toLowerCase() === String(state.user.email).toLowerCase();
        const isInternal = !!(d.email || d.account);
        const o = document.createElement("div");
        o.className = "qrs-overlay"; o.id = "qrsResult";
        const initial = (d.name || d.email || d.iban || "B").trim().charAt(0).toUpperCase();
        o.innerHTML = `<div class="qrs-sheet" role="dialog" aria-modal="true" aria-labelledby="qrsTitle">
            <div class="qrs-who">
              <span class="qrs-avatar" aria-hidden="true">${esc(initial)}</span>
              <div class="qrs-who-t">
                <small>Vai pagar a</small>
                <strong id="qrsName">${esc(d.name || (isInternal ? "Cliente BankAO" : "Beneficiário"))}</strong>
                <span class="qrs-verify" id="qrsVerify">${isInternal ? "A verificar conta…" : "Transferência por IBAN"}</span>
              </div>
            </div>
            <div class="qrs-data">
              ${d.email ? `<div><span>Chave</span><b>${esc(d.email)}</b></div>` : ""}
              ${d.account ? `<div><span>Nº de conta</span><b class="mono">${esc(groupAcc(d.account))}</b></div>` : ""}
              ${d.iban ? `<div><span>IBAN</span><b class="mono">${esc(groupIban(d.iban))}</b></div>` : ""}
            </div>
            ${d.amount
                ? `<div class="qrs-amount fixed"><span>Valor a pagar</span><strong>${money(d.amount, d.currency)}</strong></div>`
                : `<label class="qrs-amount"><span>Valor a pagar</span>
                     <div class="qrs-amount-in"><input type="text" id="qrsAmount" inputmode="decimal" placeholder="0" autocomplete="off"><em>${curLabel(d.currency)}</em></div></label>`}
            ${mine ? `<p class="qrs-warn">Este QR é da sua própria conta.</p>` : ""}
            <div class="qrs-actions"><button class="btn btn-ghost" type="button" id="qrsCancel">Cancelar</button>
            <button class="btn btn-primary" type="button" id="qrsGo"${mine ? " disabled" : ""}>Pagar</button></div></div>`;
        document.body.appendChild(o);
        o.addEventListener("click", (e) => { if (e.target === o) closeResult(); });
        o.querySelector("#qrsCancel").onclick = closeResult;
        const amtIn = o.querySelector("#qrsAmount");
        if (amtIn) setTimeout(() => amtIn.focus(), 60);
        const go = async () => {
            let amount = d.amount;
            if (!amount) {
                const raw = (amtIn?.value || "").replace(/\s/g, "");
                amount = Number(raw.includes(",") ? raw.replace(/\./g, "").replace(",", ".") : raw);
                if (!(amount > 0)) { toast("Indique o valor a pagar.", "error"); amtIn?.focus(); return; }
            }
            closeResult();
            await payNow({ ...d, amount });
        };
        o.querySelector("#qrsGo").onclick = go;
        amtIn?.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); go(); } });

        if (isInternal) lookupHolder(d).then((h) => {
            const v = document.getElementById("qrsVerify"); if (!v) return;
            if (h && h.name) {
                document.getElementById("qrsName").textContent = h.name;
                v.textContent = "✓ Cliente BankAO verificado"; v.className = "qrs-verify ok";
            } else if (h) { v.textContent = "Conta não encontrada no BankAO"; v.className = "qrs-verify bad"; }
            else { v.textContent = "Dados lidos do QR"; }
        });
    }
    function closeResult() { document.getElementById("qrsResult")?.remove(); }

    function handleText(text) {
        const d = parseQr(text);
        if (!d) return toast("Este QR não é de uma conta BankAO nem de um IBAN.", "error");
        showResult(d);
    }

    // ---- leitores ----
    function nativeDetector() {
        if (!("BarcodeDetector" in window)) return null;
        try { return new BarcodeDetector({ formats: ["qr_code"] }); } catch (_) { return null; }
    }
    let jsQrPromise = null;
    function loadJsQr() {
        if (window.jsQR) return Promise.resolve(window.jsQR);
        if (!jsQrPromise) jsQrPromise = new Promise((ok, fail) => {
            const sc = document.createElement("script");
            sc.src = "https://cdnjs.cloudflare.com/ajax/libs/jsQR/1.4.0/jsQR.min.js";
            sc.onload = () => window.jsQR ? ok(window.jsQR) : fail(); sc.onerror = () => { jsQrPromise = null; fail(); };
            document.head.appendChild(sc);
        });
        return jsQrPromise;
    }
    const cv = document.createElement("canvas");
    const cx = cv.getContext("2d", { willReadFrequently: true });
    function pixels(src, maxSide) {
        const w = src.videoWidth || src.naturalWidth || src.width, h = src.videoHeight || src.naturalHeight || src.height;
        if (!w || !h) return null;
        const k = Math.min(1, maxSide / Math.max(w, h));
        cv.width = Math.max(1, Math.round(w * k)); cv.height = Math.max(1, Math.round(h * k));
        cx.fillStyle = "#fff"; cx.fillRect(0, 0, cv.width, cv.height);
        cx.drawImage(src, 0, 0, cv.width, cv.height);
        return cx.getImageData(0, 0, cv.width, cv.height);
    }
    // sizes: tamanhos máximos a tentar (maior = mais detalhe, menor = mais rápido / menos ruído)
    async function readQr(src, { sizes = [1400, 800, 500], useJsQr = false } = {}) {
        const det = nativeDetector();
        if (det) { try { const r = await det.detect(src); if (r.length) return r[0].rawValue; } catch (_) {} }
        for (const s of sizes) {
            const im = pixels(src, s); if (!im) return "";
            try { const t = QrDecoder.decodeRGBA(im.data, im.width, im.height); if (t) return t; } catch (_) {}
        }
        if (useJsQr) {
            try {
                const jsQR = await loadJsQr(), im = pixels(src, 1000);
                const r = im && jsQR(im.data, im.width, im.height, { inversionAttempts: "attemptBoth" });
                if (r && r.data) return r.data;
            } catch (_) {}
        }
        return "";
    }

    // ---- câmara ----
    window.openQrScanner = async function () {
        if (!navigator.mediaDevices?.getUserMedia) return toast("A câmara não está disponível neste navegador (precisa de HTTPS).", "error");
        closeQrScanner();
        const o = document.createElement("div");
        o.className = "qrs-overlay qrs-cam"; o.id = "qrsCam";
        o.innerHTML = `<div class="qrs-camwrap"><video playsinline muted autoplay></video><div class="qrs-frame"></div>
            <p>Aponte a câmara ao QR da pessoa</p><button type="button" class="btn btn-ghost" id="qrsClose">Fechar</button></div>`;
        document.body.appendChild(o);
        o.querySelector("#qrsClose").onclick = closeQrScanner;
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
        } catch (_) {
            closeQrScanner();
            return toast("Sem permissão para usar a câmara. Pode carregar uma imagem do QR.", "error");
        }
        const v = o.querySelector("video"); v.srcObject = stream; await v.play().catch(() => {});
        scanning = true;
        let last = 0, busy = false, n = 0;
        const loop = async (t) => {
            if (!scanning) return;
            if (!busy && t - last > 220 && v.readyState >= 2) {
                last = t; busy = true; n++;
                try {
                    const txt = await readQr(v, { sizes: [720], useJsQr: n % 4 === 0 });   // jsQR de vez em quando, para fotos difíceis
                    if (scanning && txt && parseQr(txt)) { busy = false; closeQrScanner(); return handleText(txt); }
                } catch (_) {}
                busy = false;
            }
            rafId = requestAnimationFrame(loop);
        };
        rafId = requestAnimationFrame(loop);
    };
    function closeQrScanner() {
        scanning = false; cancelAnimationFrame(rafId);
        if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
        document.getElementById("qrsCam")?.remove();
    }
    window.closeQrScanner = closeQrScanner;

    // ---- imagem ----
    async function loadImage(file) {
        if (window.createImageBitmap) { try { return await createImageBitmap(file); } catch (_) {} }
        return await new Promise((ok, fail) => {
            const url = URL.createObjectURL(file), img = new Image();
            img.onload = () => { ok(img); setTimeout(() => URL.revokeObjectURL(url), 2000); };
            img.onerror = () => { URL.revokeObjectURL(url); fail(); };
            img.src = url;
        });
    }
    window.scanQrFromFile = async function (input) {
        const f = input.files && input.files[0]; input.value = "";
        if (!f) return;
        toast("A ler o QR…", "info");
        try {
            const img = await loadImage(f);
            const txt = await readQr(img, { useJsQr: true });
            if (!txt) return toast("Não encontrei nenhum QR nesta imagem. Use uma imagem nítida, com o QR inteiro visível.", "error");
            handleText(txt);
        } catch (_) { toast("Não consegui abrir a imagem.", "error"); }
    };

    // ---- código colado ----
    window.openQrPasteBox = function () {
        const b = document.getElementById("qrPasteBox"); if (b) { b.style.display = ""; document.getElementById("qrPasteInput")?.focus(); }
    };
    window.submitQrPaste = function () {
        const v = document.getElementById("qrPasteInput")?.value || "";
        if (!v.trim()) return toast("Cole o código do QR.", "error");
        handleText(v);
    };
})();
