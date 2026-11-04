/**
 * Transferir por QR
 * Lê o QR (câmara, imagem ou código colado), interpreta os dados da conta e preenche a transferência.
 * Leitura por câmara/imagem usa o BarcodeDetector do navegador (Chrome/Edge/Android); em navegadores sem
 * esse suporte fica o código colado. Nada sai do dispositivo.
 */
(function () {
    let stream = null, rafId = 0, scanning = false;

    // ---- interpretar o conteúdo lido ----
    function parseQr(text) {
        text = String(text || "").trim();
        if (/^BANKAO:PAY\?/i.test(text)) {
            const q = new URLSearchParams(text.replace(/^BANKAO:PAY\?/i, ""));
            const amount = Number(q.get("amount"));
            const d = { email: q.get("email") || "", name: q.get("name") || "", iban: (q.get("iban") || "").replace(/\s/g, ""),
                        account: q.get("account") || "", amount: amount > 0 ? amount : 0, currency: q.get("currency") || "AOA" };
            return (d.email || d.account || d.iban) ? d : null;
        }
        const iban = text.replace(/\s/g, "").toUpperCase();
        if (/^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$/.test(iban)) return { iban, email: "", name: "", account: "", amount: 0, currency: "AOA" };
        if (/^\S+@\S+\.\S+$/.test(text)) return { email: text, name: "", iban: "", account: "", amount: 0, currency: "AOA" };
        return null;
    }
    const money = (n) => Number(n).toLocaleString("pt-PT") + " Kz";
    const esc = (s) => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

    // ---- aplicar na transferência ----
    function setField(id, v) {
        const el = document.getElementById(id); if (!el) return;
        el.value = v; el.dispatchEvent(new Event("input", { bubbles: true })); el.dispatchEvent(new Event("change", { bubbles: true }));
    }
    function applyScanned(d) {
        const internal = d.email || d.account;
        if (window.showView) window.showView("view-ops");
        if (window.showTab) window.showTab(internal ? "tab-transfer-internal" : "tab-transfer-iban");
        // O valor do QR vem na moeda do QR (AOA por omissão): acertar a moeda ANTES de preencher o valor,
        // senão 5000 Kz passavam a 5000 USD.
        const cur = ["AOA", "USD", "EUR"].includes(String(d.currency).toUpperCase()) ? String(d.currency).toUpperCase() : "AOA";
        if (internal) {
            setField("internalDestEmail", d.email || d.account);
            if (d.amount) { setField("internalSendCurrency", cur); setField("internalAmount", d.amount); }
            if (d.name) setField("internalDesc", "Transferência para " + d.name);
            document.getElementById("internalAmount")?.focus();
        } else {
            setField("ibanInput", d.iban);
            if (d.name) setField("beneficiaryName", d.name);
            if (d.amount) { setField("ibanSendCurrency", cur); setField("ibanSendAmount", d.amount); }
        }
        toast(d.amount ? "Dados e valor preenchidos. Confirme a transferência." : "Dados da conta preenchidos. Indique o valor e confirme.", "success");
    }

    // ---- cartão de confirmação depois de ler ----
    function showResult(d) {
        closeResult();
        const o = document.createElement("div");
        o.className = "qrs-overlay"; o.id = "qrsResult";
        o.innerHTML = `<div class="qrs-sheet"><h3>QR lido ✓</h3>
            <div class="qrs-data">
              ${d.name ? `<div><span>Titular</span><b>${esc(d.name)}</b></div>` : ""}
              ${d.email ? `<div><span>Chave</span><b>${esc(d.email)}</b></div>` : ""}
              ${d.iban ? `<div><span>IBAN</span><b class="mono">${esc(d.iban)}</b></div>` : ""}
              ${d.account && !d.iban ? `<div><span>Conta</span><b class="mono">${esc(d.account)}</b></div>` : ""}
              ${d.amount ? `<div><span>Valor pedido</span><b>${money(d.amount)}</b></div>` : ""}
            </div>
            <div class="qrs-actions"><button class="btn btn-ghost" type="button" id="qrsCancel">Cancelar</button>
            <button class="btn btn-primary" type="button" id="qrsGo">Transferir</button></div></div>`;
        document.body.appendChild(o);
        o.querySelector("#qrsCancel").onclick = closeResult;
        o.querySelector("#qrsGo").onclick = () => { closeResult(); applyScanned(d); };
    }
    function closeResult() { document.getElementById("qrsResult")?.remove(); }

    function handleText(text) {
        const d = parseQr(text);
        if (!d) return toast("Este QR não é de uma conta BankAO nem de um IBAN.", "error");
        showResult(d);
    }

    // ---- câmara ----
    function detector() {
        if (!("BarcodeDetector" in window)) return null;
        try { return new BarcodeDetector({ formats: ["qr_code"] }); } catch (_) { return null; }
    }
    window.openQrScanner = async function () {
        if (!navigator.mediaDevices?.getUserMedia) return toast("A câmara não está disponível neste navegador (precisa de HTTPS).", "error");
        const det = detector();
        if (!det) { toast("Este navegador não lê QR pela câmara. Carregue uma imagem ou cole o código.", "info"); return openQrPasteBox(); }
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
        let last = 0;
        const loop = async (t) => {
            if (!scanning) return;
            if (t - last > 180 && v.readyState >= 2) {
                last = t;
                try { const r = await det.detect(v); if (r.length && parseQr(r[0].rawValue)) { closeQrScanner(); return handleText(r[0].rawValue); } } catch (_) {}
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
    window.scanQrFromFile = async function (input) {
        const f = input.files && input.files[0]; input.value = "";
        if (!f) return;
        const det = detector();
        if (!det) { toast("Este navegador não lê QR de imagens. Cole o código.", "info"); return openQrPasteBox(); }
        try {
            const bmp = await createImageBitmap(f);
            const r = await det.detect(bmp);
            if (!r.length) return toast("Não encontrei nenhum QR nesta imagem.", "error");
            handleText(r[0].rawValue);
        } catch (_) { toast("Não consegui ler a imagem.", "error"); }
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
