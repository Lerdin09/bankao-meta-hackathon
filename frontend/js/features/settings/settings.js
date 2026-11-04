/**
 * Definições — funcionais e ligadas ao backend (/api/settings).
 * - Preferências guardadas por utilizador na base de dados e aplicadas em toda a app.
 * - Dados sensíveis (IBAN, nº de conta, NIF/nº do documento, nome, KYC) são SÓ DE LEITURA.
 * - Alterações em preferências ficam pendentes até "Guardar alterações"; ações (palavra-passe, PIN,
 *   sessões, bloquear cartão/conta, pedidos) são imediatas.
 */
const ST_DEFAULTS = {
    biometric: false, twofa: false, n_transfers: true, n_payments: true, n_received: true, n_card: true, n_movements: false,
    n_low_balance: true, n_low_balance_threshold: 50000, n_promos: false, ch_push: true, ch_sms: true, ch_email: false,
    language: "pt", currency: "AOA", date_format: "DD/MM/AAAA", number_format: "1 234,56", theme: "dark", home_page: "view-home",
    hide_balances: true, main_account_id: "", online_payments: true, limit_withdraw: 200000, limit_payments: 1000000, limit_transfers: 2000000,
    ai_enabled: true, ai_voice: true, ai_read_aloud: false, ai_language: "pt", ai_confirm: true, ai_style: "equilibrado",
    ai_perm_balances: true, ai_perm_transactions: true, ai_perm_cards: true, ai_perm_savings: false, ai_perm_investments: false
};
const ST = { settings: Object.assign({}, ST_DEFAULTS, JSON.parse(localStorage.getItem("bankao_settings") || "{}")),
    pending: {}, profile: null, accounts: [], cards: [], hasPin: false, locked: false, sessions: 0, svc: null,
    loaded: false, firstApplied: false, seenTx: null, lowFlag: false };

/* ---------- Helpers globais usados por outros módulos ---------- */
function bkSetting(k) { return ST.settings[k]; }
function bkFormatNumber(n, dec) {
    dec = dec === undefined ? 2 : dec;
    const f = ST.settings.number_format;
    const sepT = f === "1.234,56" ? "." : f === "1,234.56" ? "," : "\u00a0", sepD = f === "1,234.56" ? "." : ",";
    const v = Number(n) || 0, p = Math.abs(v).toFixed(dec).split(".");
    return (v < 0 ? "-" : "") + p[0].replace(/\B(?=(\d{3})+(?!\d))/g, sepT) + (dec ? sepD + p[1] : "");
}
function bkFormatDate(d) {
    if (!(d instanceof Date)) d = new Date(d);
    if (isNaN(d)) return "";
    const dd = String(d.getDate()).padStart(2, "0"), mm = String(d.getMonth() + 1).padStart(2, "0"), y = d.getFullYear();
    const f = ST.settings.date_format;
    return f === "MM/DD/AAAA" ? `${mm}/${dd}/${y}` : f === "AAAA-MM-DD" ? `${y}-${mm}-${dd}` : `${dd}/${mm}/${y}`;
}

/* ---------- Aplicar definições à aplicação ---------- */
function bkApplyTheme() {
    let t = ST.settings.theme;
    if (t === "system") t = matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", t);
    const m = document.querySelector('meta[name="theme-color"]');
    if (m) m.content = t === "light" ? "#F3F5FA" : "#070B14";
}
matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => { if (ST.settings.theme === "system") bkApplyTheme(); });

function setBalancesHidden(hidden) {
    document.body.classList.toggle("balances-hidden", hidden);
    ["btnToggleBalance", "btnToggleDashBalance"].forEach(id => {
        const b = document.getElementById(id);
        if (!b) return;
        b.setAttribute("aria-pressed", String(hidden));
        b.setAttribute("aria-label", hidden ? "Mostrar saldos" : "Ocultar saldos");
        b.title = hidden ? "Mostrar saldos" : "Ocultar saldos";
    });
}

function applySettings(opts) {
    const s = ST.settings;
    localStorage.setItem("bankao_settings", JSON.stringify(s));
    bkApplyTheme();
    document.documentElement.lang = s.language === "en" ? "en" : "pt";
    document.body.classList.toggle("ai-off", !s.ai_enabled);
    document.body.classList.toggle("ai-voice-off", !s.ai_voice);
    // Moeda principal / conta principal
    const main = ST.accounts.find(a => a.id === s.main_account_id);
    const first = !ST.firstApplied && ST.loaded;
    let cur = state.prefCurrency;
    if (first || (opts && opts.curChanged)) cur = (opts && opts.curChanged === "cur") ? s.currency : (main ? main.currency : s.currency);
    if (cur !== state.prefCurrency) {
        state.prefCurrency = cur;
        localStorage.setItem("bankao_pref_currency", cur);
        if (typeof updateDashboardHero === "function") try { updateDashboardHero(); } catch (_) {}
        if (typeof renderHomeTrend === "function") try { renderHomeTrend(); } catch (_) {}
    }
    // Primeira aplicação nesta sessão: saldos ocultos e página inicial
    if (!ST.firstApplied && ST.loaded) {
        ST.firstApplied = true;
        setBalancesHidden(!!s.hide_balances);
        if (s.home_page && s.home_page !== "view-home" && typeof showView === "function") showView(s.home_page);
    } else if (opts && opts.balances) {
        setBalancesHidden(!!s.hide_balances);
    }
    // Reaplicar formatos nos ecrãs
    if (opts && opts.formats && state.accounts && state.accounts.length) {
        try { renderAccounts(); if (state.transactions) renderTransactions(state.transactions); } catch (_) {}
    }
}

async function loadUserSettings() {
    if (!state.token) return;
    try {
        const d = await apiRequest("GET", "/api/settings");
        ST.settings = Object.assign({}, ST_DEFAULTS, d.settings);
        ST.profile = d.profile; ST.accounts = d.accounts || []; ST.hasPin = d.has_pin; ST.locked = d.locked; ST.sessions = d.sessions;
        try { const c = await apiRequest("GET", "/api/cards/"); ST.cards = (c.cards || []).filter(x => x.status !== "cancelled"); } catch (_) { ST.cards = []; }
        ST.svc = true;
        ST.loaded = true;
        applySettings({ formats: true });
        maybePinLock();
        const v = document.getElementById("view-settings");
        if (v && v.classList.contains("active")) renderSettings();
    } catch (e) { ST.svc = false; }
}

/* ---------- Alertas (notificações reais) ---------- */
function bkNotify(msg, kind) {
    if (!ST.settings.ch_push) return;
    toast(msg, kind || "success");
    try {
        if (document.hidden && "Notification" in window && Notification.permission === "granted") new Notification("BankAO", { body: msg });
    } catch (_) {}
}
function checkAlerts() {
    const s = ST.settings;
    if (!ST.loaded || !state.token) return;
    const txs = state.transactions || [];
    if (ST.seenTx === null) { ST.seenTx = new Set(txs.map(t => t.id)); }
    else {
        txs.filter(t => !ST.seenTx.has(t.id)).reverse().forEach(t => {
            ST.seenTx.add(t.id);
            const credit = t.direction === "from" || t.kind === "deposit";
            const val = t.amount_minor !== undefined ? Math.abs(t.amount_minor) / 100 : (t.amount !== undefined ? Math.abs(t.amount) : null);
            const money = val === null ? "" : " de " + formatMoney(val, t.currency || "AOA");
            if (credit && s.n_received) bkNotify("Dinheiro recebido" + money + (t.name ? " · " + t.name : ""));
            else if (!credit && t.kind === "card" && s.n_card) bkNotify("Compra com cartão" + money);
            else if (!credit && (t.kind === "iban" || t.kind === "internal") && s.n_transfers) bkNotify("Transferência efetuada" + money);
            else if (!credit && s.n_payments) bkNotify("Pagamento efetuado" + money);
            else if (s.n_movements) bkNotify("Novo movimento na conta" + money);
        });
    }
    const aoa = state.accountAoa;
    if (aoa && s.n_low_balance) {
        const low = aoa.balance_decimal < s.n_low_balance_threshold;
        if (low && !ST.lowFlag) bkNotify("Saldo baixo: " + formatMoney(aoa.balance_decimal, "AOA"), "error");
        ST.lowFlag = low;
    }
}

/* ---------- Bloqueio por PIN (ao abrir a app) ---------- */
function maybePinLock() {
    if (!ST.settings.twofa || !ST.hasPin || sessionStorage.getItem("bankao_pin_ok") === "1" || document.getElementById("stPinLock")) return;
    const ov = document.createElement("div");
    ov.id = "stPinLock"; ov.className = "st-ov st-lock";
    ov.innerHTML = '<div class="st-modal"><h3>Introduza o PIN</h3><p>Confirme a sua identidade para continuar.</p>' +
        '<input class="st-in" id="stPinLockIn" type="password" inputmode="numeric" maxlength="6" autocomplete="off" placeholder="PIN"><p class="st-err" id="stPinLockErr"></p>' +
        '<div class="st-mact"><button type="button" class="st-btn" id="stPinLockOut">Terminar sessão</button><button type="button" class="st-btn primary" id="stPinLockOk">Entrar</button></div></div>';
    document.body.appendChild(ov);
    let tries = 0;
    const go = async () => {
        const pin = document.getElementById("stPinLockIn").value;
        try {
            const r = await apiRequest("POST", "/api/settings/pin/verify", { pin });
            if (r.ok) { sessionStorage.setItem("bankao_pin_ok", "1"); ov.remove(); return; }
        } catch (_) {}
        tries++;
        document.getElementById("stPinLockErr").textContent = "PIN incorreto (" + tries + "/5)";
        if (tries >= 5) logout();
    };
    document.getElementById("stPinLockOk").onclick = go;
    document.getElementById("stPinLockIn").addEventListener("keydown", e => { if (e.key === "Enter") go(); });
    document.getElementById("stPinLockOut").onclick = () => logout();
    setTimeout(() => document.getElementById("stPinLockIn").focus(), 50);
}

/* ---------- Modais ---------- */
function stModal(title, body, buttons, onOpen) {
    const ov = document.createElement("div");
    ov.className = "st-ov";
    ov.innerHTML = '<div class="st-modal" role="dialog" aria-modal="true"><h3>' + title + '</h3><div class="st-mbody">' + body + '</div><p class="st-err"></p><div class="st-mact"></div></div>';
    const act = ov.querySelector(".st-mact"), err = ov.querySelector(".st-err");
    const close = () => { ov.remove(); document.removeEventListener("keydown", esc); };
    const esc = e => { if (e.key === "Escape") close(); };
    document.addEventListener("keydown", esc);
    (buttons || [{ label: "Fechar" }]).forEach(b => {
        const el = document.createElement("button");
        el.type = "button"; el.className = "st-btn" + (b.primary ? " primary" : "") + (b.danger ? " danger" : ""); el.textContent = b.label;
        el.onclick = async () => {
            if (!b.run) return close();
            err.textContent = ""; el.disabled = true;
            try { const keep = await b.run(ov); if (keep !== false) close(); }
            catch (e) { err.textContent = e.message || "Erro."; }
            el.disabled = false;
        };
        act.appendChild(el);
    });
    ov.addEventListener("mousedown", e => { if (e.target === ov) close(); });
    document.body.appendChild(ov);
    if (onOpen) onOpen(ov, close);
    const f = ov.querySelector("input,select,textarea"); if (f) setTimeout(() => f.focus(), 40);
    return ov;
}
const stIn = (id, label, type, extra) => '<label class="st-lab">' + label + '<input class="st-in" id="' + id + '" type="' + (type || "text") + '" ' + (extra || "") + '></label>';
const stV = id => document.getElementById(id).value;

/* ---------- Definição das categorias ---------- */
const OPT = {
    lang: [["pt", "Português"], ["en", "English"]],
    cur: [["AOA", "AOA (Kwanza)"], ["EUR", "EUR (Euro)"], ["USD", "USD (Dólar)"]],
    date: [["DD/MM/AAAA", "DD/MM/AAAA"], ["MM/DD/AAAA", "MM/DD/AAAA"], ["AAAA-MM-DD", "AAAA-MM-DD"]],
    num: [["1 234,56", "1 234,56"], ["1.234,56", "1.234,56"], ["1,234.56", "1,234.56"]],
    theme: [["dark", "Escuro"], ["light", "Claro"], ["system", "Automático (sistema)"]],
    home: [["view-home", "Início"], ["view-accounts", "Contas"], ["view-payments", "Pagamentos"], ["view-savings", "Poupança"], ["view-expenses", "Despesas"], ["view-statement", "Extrato"]],
    style: [["curto", "Curtas e diretas"], ["equilibrado", "Equilibradas"], ["detalhado", "Detalhadas"]]
};
const kz = n => bkFormatNumber(n, 0) + " Kz";
const mask = (s, keep) => s ? "•".repeat(Math.max(0, s.length - keep)) + s.slice(-keep) : "—";
const acctOpts = () => ST.accounts.map(a => [a.id, a.currency + " •••• " + String(a.account_number).slice(-4)]);

function stCats() {
    const p = ST.profile || {};
    const cardRows = ST.cards.length
        ? ST.cards.map(c => ({ t: "cardblock", i: "i-lock", n: "Bloquear cartão " + (c.network || "").toUpperCase() + " •••• " + c.last_four, card: c }))
        : [{ t: "ro", i: "i-card", n: "Cartões", val: "Sem cartões", nolock: 1 }];
    return [
        { id: "perfil", icon: "i-user", c: "#E6B85C", n: "Perfil e dados pessoais", d: "Dados, BI e verificação KYC", rows: [
            { g: "Dados pessoais" },
            { t: "ro", i: "i-user", n: "Nome", val: p.nome || "—", note: "Conforme o documento" },
            { t: "act", i: "i-user", n: "Fotografia de perfil", s: "Guardada neste dispositivo", act: "photo" },
            { t: "act", i: "i-phone", n: "Número de telefone", val: mask(p.telefone, 3), act: "edit", f: "telefone" },
            { t: "act", i: "i-mail", n: "E-mail", val: p.email || "—", act: "edit", f: "email" },
            { t: "act", i: "i-pin", n: "Endereço", val: p.morada || "Não definido", act: "edit", f: "morada" },
            { g: "Identificação (só leitura)" },
            { t: "ro", i: "i-id", n: p.doc_tipo === "passaporte" ? "Passaporte" : "Bilhete de Identidade / NIF", val: p.doc_numero_masked || "—" },
            { t: "ro", i: "i-verified", n: "Estado da verificação KYC", val: p.kyc_status === "verificado" ? "Verificado" : (p.kyc_status || "Pendente"), cls: p.kyc_status === "verificado" ? "ok" : "", nolock: 1 },
            { t: "act", i: "i-edit", n: "Pedir alteração de dados sensíveis", s: "IBAN, nº de conta e NIF só mudam por pedido ao banco", act: "datareq" }] },
        { id: "seguranca", icon: "i-shield", c: "#34D399", n: "Segurança e privacidade", d: "Acesso, PIN e dispositivos", rows: [
            { g: "Acesso" },
            { t: "act", i: "i-key", n: "Alterar palavra-passe", act: "password" },
            { t: "toggle", i: "i-fingerprint", n: "Autenticação biométrica", s: "Impressão digital ou rosto (se o dispositivo suportar)", key: "biometric" },
            { t: "act", i: "i-lock", n: "PIN de acesso", s: ST.hasPin ? "Alterar o PIN" : "Definir PIN (4 a 6 dígitos)", act: "pin" },
            { t: "toggle", i: "i-shield", n: "Pedir PIN ao abrir a app", s: "Proteção extra ao iniciar sessão", key: "twofa" },
            { g: "Sessões e privacidade" },
            { t: "act", i: "i-device", n: "Dispositivos com sessão iniciada", val: ST.sessions + (ST.sessions === 1 ? " dispositivo" : " dispositivos"), act: "sessions" },
            { t: "act", i: "i-clock", n: "Histórico de acessos", act: "history" },
            { t: "act", i: "i-eye", n: "Gerir permissões e privacidade", act: "perms" },
            { g: "Zona de risco" },
            { t: "act", i: "i-ban", n: ST.locked ? "Desbloquear a conta" : "Bloquear temporariamente a conta", s: ST.locked ? "A conta está bloqueada: nenhum movimento é permitido" : "Suspende todos os movimentos", act: "lock", danger: 1 }] },
        { id: "notificacoes", icon: "i-bell", c: "#F59E0B", n: "Notificações", d: "Alertas e canais", rows: [
            { g: "Alertas" },
            { t: "toggle", i: "i-swap", n: "Transferências", key: "n_transfers" }, { t: "toggle", i: "i-receipt", n: "Pagamentos efetuados", key: "n_payments" },
            { t: "toggle", i: "i-down", n: "Dinheiro recebido", key: "n_received" }, { t: "toggle", i: "i-card", n: "Compras com cartão", key: "n_card" },
            { t: "toggle", i: "i-activity", n: "Movimentos da conta", key: "n_movements" },
            { t: "toggle", i: "i-alert", n: "Alerta de saldo baixo", s: "Abaixo de " + kz(bk("n_low_balance_threshold")), key: "n_low_balance" },
            { t: "num", i: "i-alert", n: "Limite do alerta de saldo", key: "n_low_balance_threshold", unit: "Kz" },
            { t: "toggle", i: "i-bolt", n: "Promoções e novidades", key: "n_promos" },
            { g: "Canais" },
            { t: "toggle", i: "i-bell", n: "Push (na app e no navegador)", key: "ch_push" },
            { t: "toggle", i: "i-phone", n: "SMS", s: "Preferência registada", key: "ch_sms" }, { t: "toggle", i: "i-mail", n: "E-mail", s: "Preferência registada", key: "ch_email" }] },
        { id: "preferencias", icon: "i-sliders", c: "#A78BFA", n: "Preferências", d: "Idioma, moeda e aparência", rows: [
            { g: "Regional" },
            { t: "select", i: "i-globe", n: "Idioma", key: "language", opts: OPT.lang }, { t: "select", i: "i-wallet", n: "Moeda principal", key: "currency", opts: OPT.cur },
            { t: "select", i: "i-calendar", n: "Formato de data", key: "date_format", opts: OPT.date }, { t: "select", i: "i-hash", n: "Formato numérico", key: "number_format", opts: OPT.num },
            { g: "Aparência e início" },
            { t: "select", i: "i-moon", n: "Tema", key: "theme", opts: OPT.theme }, { t: "select", i: "i-home", n: "Página inicial preferida", key: "home_page", opts: OPT.home },
            { t: "toggle", i: "i-eye-off", n: "Ocultar saldos por padrão", key: "hide_balances" }] },
        { id: "contas-cartoes", icon: "i-card", c: "#6C9BFF", n: "Contas e cartões", d: "Contas, limites e bloqueios", rows: [
            { g: "Contas" },
            { t: "act", i: "i-wallet", n: "Contas bancárias (IBAN e nº de conta)", val: ST.accounts.length + " contas", act: "accounts" },
            { t: "select", i: "i-award", n: "Conta principal", key: "main_account_id", opts: acctOpts },
            { g: "Cartões" },
            { t: "act", i: "i-card", n: "Gerir cartões associados", val: ST.cards.length + (ST.cards.length === 1 ? " cartão" : " cartões"), act: "cards" },
            ...cardRows,
            { t: "toggle", i: "i-globe", n: "Pagamentos online (todos os cartões)", key: "online_payments" },
            { g: "Limites diários" },
            { t: "num", i: "i-down", n: "Levantamentos", key: "limit_withdraw", unit: "Kz" }, { t: "num", i: "i-receipt", n: "Pagamentos", key: "limit_payments", unit: "Kz" },
            { t: "num", i: "i-swap", n: "Transferências (aplicado em todas as transferências)", key: "limit_transfers", unit: "Kz" }] },
        { id: "copilot", icon: "i-spark", c: "#E6B85C", n: "Copilot IA", d: "Voz e comportamento", rows: [
            { g: "Assistente" },
            { t: "toggle", i: "i-spark", n: "Assistente IA", s: "Ativar ou desativar o Copilot", key: "ai_enabled" },
            { t: "toggle", i: "i-mic", n: "Interação por voz", key: "ai_voice" }, { t: "toggle", i: "i-volume", n: "Ler respostas em voz alta", key: "ai_read_aloud" },
            { t: "select", i: "i-globe", n: "Idioma do assistente", key: "ai_language", opts: OPT.lang },
            { t: "ro", i: "i-check", n: "Confirmar antes de executar operações", val: "Sempre ativo", nolock: 1, note: "Transferências e pagamentos exigem sempre a sua confirmação" },
            { g: "Dados e personalização" },
            { t: "act", i: "i-list", n: "Histórico de conversas", val: (state.chatHistory || []).length + " mensagens", act: "aihist" },
            { t: "select", i: "i-edit", n: "Personalização das respostas", key: "ai_style", opts: OPT.style },
            { t: "act", i: "i-shield", n: "Acesso aos dados financeiros", val: ["balances", "transactions", "cards", "savings", "investments"].filter(k => bk("ai_perm_" + k)).length + " de 5 permissões ativas", act: "perms" }] },
        { id: "ajuda", icon: "i-help", c: "#22D3EE", n: "Ajuda e suporte", d: "Obter assistência", rows: [
            { g: "Apoio" },
            { t: "act", i: "i-book", n: "Centro de ajuda", act: "doc:help" }, { t: "act", i: "i-help", n: "Perguntas frequentes", act: "doc:faq" },
            { t: "act", i: "i-headset", n: "Contactar suporte", act: "support:suporte" }, { t: "act", i: "i-alert", n: "Reportar um problema", act: "support:problema" },
            { t: "act", i: "i-shield", n: "Comunicar fraude", s: "Contacto urgente", act: "support:fraude", danger: 1 },
            { g: "Legal" },
            { t: "act", i: "i-file", n: "Termos e condições", act: "doc:terms" }, { t: "act", i: "i-lock", n: "Política de privacidade", act: "doc:privacy" }] },
        { id: "sobre", icon: "i-info", c: "#818CF8", n: "Sobre e conta", d: "Informações e versão", out: 1, rows: [
            { g: "A aplicação" },
            { t: "ro", i: "i-info", n: "Versão da aplicação", val: "1.0.0", nolock: 1 }, { t: "act", i: "i-building", n: "Informações do banco", act: "doc:bank" },
            { t: "ro", i: "i-activity", n: "Estado dos serviços", val: ST.svc === false ? "Indisponível" : "Operacional", cls: ST.svc === false ? "" : "ok", nolock: 1 },
            { t: "act", i: "i-file", n: "Termos legais", act: "doc:terms" },
            { g: "Conta" },
            { t: "act", i: "i-trash", n: "Solicitar encerramento da conta", s: "Pedido sujeito a confirmação", act: "close", danger: 1 }] }
    ];
}

/* valor atual (pendente ou guardado) */
function bk(key) { return key in ST.pending ? ST.pending[key] : ST.settings[key]; }
const stIcon = id => '<svg><use href="#' + id + '"/></svg>';
const optLabel = (r) => { const o = typeof r.opts === "function" ? r.opts() : r.opts; const f = o.find(x => x[0] === bk(r.key)); return f ? f[1] : (r.key === "main_account_id" ? "Automática" : "—"); };

function stRow(r, idx) {
    if (r.g) return '</div><div class="st-group">' + r.g + '</div><div class="st-card">';
    const ch = r.key && r.key in ST.pending ? " changed" : "";
    const txt = '<span class="st-rt"><b>' + r.n + '</b>' + (r.s || r.note ? '<small>' + (r.s || r.note) + '</small>' : '') + '</span>';
    const ico = '<span class="st-ri">' + stIcon(r.i) + '</span>';
    if (r.t === "toggle") { const on = !!bk(r.key); return '<div class="st-row' + ch + '">' + ico + txt + '<button type="button" class="st-sw' + (on ? " on" : "") + '" data-key="' + r.key + '" role="switch" aria-checked="' + on + '" aria-label="' + r.n + '"></button></div>'; }
    if (r.t === "cardblock") { const on = r.card.status === "blocked"; return '<div class="st-row">' + ico + txt + '<button type="button" class="st-sw' + (on ? " on" : "") + '" data-card="' + r.card.id + '" role="switch" aria-checked="' + on + '"></button></div>'; }
    if (r.t === "ro") return '<div class="st-row ro">' + ico + txt + '<span class="st-val ' + (r.cls || "") + '">' + r.val + '</span>' + (r.nolock ? "" : '<span class="st-lockic" title="Não editável">' + stIcon("i-lock") + '</span>') + '</div>';
    const val = r.t === "select" ? '<span class="st-val">' + optLabel(r) + '</span>' : r.t === "num" ? '<span class="st-val">' + kz(bk(r.key)).replace(" Kz", " " + r.unit) + '</span>' : (r.val ? '<span class="st-val ' + (r.cls || "") + '">' + r.val + '</span>' : "");
    return '<button type="button" class="st-row' + (r.danger ? " danger" : "") + ch + '" data-r="' + idx + '">' + ico + txt + val + '<span class="st-go">' + stIcon("i-chevron-right") + '</span></button>';
}

function renderSettings() {
    const nav = document.getElementById("stNav"); if (!nav) return;
    const cats = stCats(), cur = nav.dataset.cur || cats[0].id;
    nav.innerHTML = cats.map(c => '<button type="button" class="st-navbtn' + (c.id === cur ? " on" : "") + '" data-cat="' + c.id + '" style="--c:' + c.c + '"><span class="st-ico">' + stIcon(c.icon) +
        '</span><span class="st-t"><b>' + c.n + '</b><small>' + c.d + '</small></span><span class="st-go">' + stIcon("i-chevron-right") + '</span></button>').join("");
    const p = ST.profile || state.user;
    const nm = (p && (p.nome || p.full_name)) || "";
    if (nm) {
        document.getElementById("stName").textContent = nm;
        const av = document.getElementById("stAvatar"), img = state.user && localStorage.getItem("bankao_avatar_" + state.user.id);
        if (img) { av.style.backgroundImage = "url(" + img + ")"; av.textContent = ""; }
        else { av.style.backgroundImage = ""; av.textContent = nm.split(" ").map(s => s[0]).slice(0, 2).join("").toUpperCase(); }
    }
    const pl = document.getElementById("stPlan");
    if (pl) pl.textContent = ST.locked ? "Conta bloqueada" : "Conta ativa";
    const kc = document.querySelector(".st-kyc");
    if (kc && ST.profile) kc.style.display = ST.profile.kyc_status === "verificado" ? "" : "none";
    openSettingsCat(cur);
}

function openSettingsCat(id) {
    const cats = stCats(), c = cats.find(x => x.id === id) || cats[0];
    const nav = document.getElementById("stNav"), panel = document.getElementById("stPanel");
    nav.dataset.cur = c.id;
    nav.querySelectorAll(".st-navbtn").forEach(b => b.classList.toggle("on", b.dataset.cat === c.id));
    panel.style.setProperty("--c", c.c);
    const dirty = Object.keys(ST.pending).length > 0;
    panel.innerHTML = '<div class="st-phead"><span class="st-ico" style="color:' + c.c + '">' + stIcon(c.icon) + '</span><div><h2>' + c.n + '</h2><p>' + c.d + '</p></div></div>' +
        c.rows.map(stRow).join("").replace("</div>", "") + '</div>' +
        (c.out ? '<button type="button" class="st-logout" id="stLogout">' + stIcon("i-logout") + 'Terminar sessão</button>'
            : '<div class="st-save"><button type="button" class="st-btn primary" id="stSave"' + (dirty ? "" : " disabled") + '>Guardar alterações</button><button type="button" class="st-btn" id="stCancel"' + (dirty ? "" : " disabled") + '>Cancelar</button></div>');
    panel._rows = c.rows;
    document.getElementById("stCatTitle").textContent = c.n;
}
const stRefresh = () => openSettingsCat(document.getElementById("stNav").dataset.cur);

/* ---------- Guardar / cancelar ---------- */
async function saveSettings() {
    const patch = Object.assign({}, ST.pending);
    if (!Object.keys(patch).length) return;
    if (patch.biometric === true) {
        let ok = false;
        try { ok = !!(window.PublicKeyCredential && await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()); } catch (_) {}
        if (!ok) { delete patch.biometric; delete ST.pending.biometric; toast("A biometria não está disponível neste dispositivo.", "error"); }
    }
    if (patch.twofa === true && !ST.hasPin) { delete patch.twofa; delete ST.pending.twofa; toast("Defina primeiro um PIN de acesso.", "error"); }
    if (!Object.keys(patch).length) { stRefresh(); return; }
    try {
        const d = await apiRequest("PUT", "/api/settings", { values: patch });
        const prev = ST.settings;
        ST.settings = Object.assign({}, ST_DEFAULTS, d.settings);
        ST.pending = {};
        if ("online_payments" in patch) await Promise.all(ST.cards.map(c => apiRequest("PATCH", "/api/cards/" + c.id + "/settings", { online_payments: !!patch.online_payments }).catch(() => null)));
        if (patch.ch_push && "Notification" in window && Notification.permission === "default") { try { Notification.requestPermission(); } catch (_) {} }
        applySettings({ formats: true, balances: "hide_balances" in patch, curChanged: "main_account_id" in patch ? "main" : ("currency" in patch ? "cur" : false) });
        if (patch.home_page && patch.home_page !== prev.home_page) toast("Página inicial atualizada.", "success");
        toast("Definições guardadas com sucesso.", "success");
        stRefresh();
    } catch (e) { toast(e.message, "error"); }
}
function cancelSettings() { ST.pending = {}; applySettings({ balances: true, formats: true }); stRefresh(); }

/* ---------- Ações ---------- */
const DOCS = {
    help: ["Centro de ajuda", "<p><b>Transferências:</b> Operações → escolha conta, destino e montante. <b>Depósitos:</b> Multicaixa Express ou Referência. <b>Cartões:</b> bloqueie/desbloqueie em Definições → Contas e cartões.</p><p>Precisa de falar connosco? Use «Contactar suporte».</p>"],
    faq: ["Perguntas frequentes", "<p><b>Posso alterar o meu IBAN ou NIF?</b> Não. São dados sensíveis e só mudam por pedido ao banco.</p><p><b>O que acontece se bloquear a conta?</b> Todos os movimentos ficam suspensos até desbloquear.</p><p><b>Como mudo os limites diários?</b> Definições → Contas e cartões → Limites diários.</p>"],
    terms: ["Termos e condições", "<p>A utilização do BankAO está sujeita aos termos aceites no registo. Esta é uma aplicação de demonstração (sandbox): os valores e documentos são fictícios.</p>"],
    privacy: ["Política de privacidade", "<p>Os seus dados pessoais são usados apenas para operar a conta, cumprir obrigações KYC e melhorar a experiência. Os dados sensíveis aparecem sempre mascarados e nunca são partilhados com terceiros.</p>"],
    bank: ["Informações do banco", "<p><b>BankAO</b> — carteira digital para Angola e o mundo.<br>Ambiente: sandbox de demonstração.<br>Contas em AOA, EUR e USD.</p>"]
};

async function stAction(r) {
    const a = r.act || "";
    if (r.t === "select") return stPick(r);
    if (r.t === "num") return stNum(r);
    if (a === "edit") return stEdit(r.f, r.n);
    if (a === "photo") return stPhoto();
    if (a === "datareq") return stSupport("suporte", "Pedido de alteração de dados sensíveis", "Indique que dado pretende alterar e o motivo.");
    if (a === "password") return stPassword();
    if (a === "pin") return stPin();
    if (a === "sessions") return stSessions();
    if (a === "history") return stHistory();
    if (a === "perms") return stPerms();
    if (a === "lock") return stLock();
    if (a === "accounts") return stAccounts();
    if (a === "cards") { showView("view-cards"); return; }
    if (a === "aihist") return stAiHist();
    if (a === "close") return stClose();
    if (a.startsWith("doc:")) { const d = DOCS[a.slice(4)]; return stModal(d[0], d[1]); }
    if (a.startsWith("support:")) {
        const k = a.slice(8);
        return stSupport(k, { suporte: "Contactar suporte", problema: "Reportar um problema", fraude: "Comunicar fraude" }[k], k === "fraude" ? "Descreva a situação suspeita. Se perdeu dinheiro, bloqueie a conta em Segurança." : "Descreva o assunto.");
    }
}

function stPick(r) {
    const opts = typeof r.opts === "function" ? r.opts() : r.opts;
    if (!opts.length) return toast("Sem opções disponíveis.", "error");
    const cur = bk(r.key);
    const html = '<div class="st-opts">' + opts.map(o => '<label class="st-opt"><input type="radio" name="stopt" value="' + o[0] + '"' + (o[0] === cur ? " checked" : "") + '><span>' + o[1] + '</span></label>').join("") + '</div>';
    stModal(r.n, html, [{ label: "Cancelar" }, { label: "Aplicar", primary: 1, run: ov => {
        const v = ov.querySelector("input:checked"); if (!v) return;
        if (v.value === ST.settings[r.key]) delete ST.pending[r.key]; else ST.pending[r.key] = v.value;
        if (r.key === "theme") { const old = ST.settings.theme; ST.settings.theme = v.value; bkApplyTheme(); ST.settings.theme = old; }
        stRefresh();
    } }]);
}
function stNum(r) {
    stModal(r.n, '<label class="st-lab">Valor em ' + r.unit + '<input class="st-in js-money" id="stNumIn" type="text" inputmode="numeric" value="' + bkFormatNumber(bk(r.key), 0).replace(/\u00a0/g, ".") + '"></label>', [{ label: "Cancelar" }, { label: "Aplicar", primary: 1, run: () => {
        const v = Math.round(parseCleanNumber(stV("stNumIn")));
        if (!(v >= 0) || v > 1000000000) throw new Error("Valor inválido.");
        if (r.key.startsWith("limit_") && v === 0) throw new Error("O limite deve ser maior que zero.");
        if (v === ST.settings[r.key]) delete ST.pending[r.key]; else ST.pending[r.key] = v;
        stRefresh();
    } }]);
}
function stEdit(f, label) {
    const p = ST.profile || {}, type = f === "email" ? "email" : f === "telefone" ? "tel" : "text";
    stModal("Alterar " + label.toLowerCase(), stIn("stEdIn", label, type, 'value="' + escapeHtml(p[f] || "") + '"') + '<p class="st-hint">Nome, nº do documento, IBAN e nº de conta não podem ser alterados aqui.</p>',
        [{ label: "Cancelar" }, { label: "Guardar", primary: 1, run: async () => {
            const d = await apiRequest("PATCH", "/api/settings/profile", { [f]: stV("stEdIn") });
            ST.profile = d.profile;
            if (state.user) { if (f === "email") state.user.email = d.profile.email; if (f === "telefone") state.user.telefone = d.profile.telefone; localStorage.setItem("bankao_user", JSON.stringify(state.user)); }
            toast("Dados atualizados com sucesso.", "success"); stRefresh();
        } }]);
}
function stPhoto() {
    const inp = document.createElement("input"); inp.type = "file"; inp.accept = "image/*";
    inp.onchange = () => {
        const f = inp.files[0]; if (!f) return;
        const img = new Image();
        img.onload = () => {
            const c = document.createElement("canvas"); c.width = c.height = 160; const x = c.getContext("2d");
            const s = Math.min(img.width, img.height); x.drawImage(img, (img.width - s) / 2, (img.height - s) / 2, s, s, 0, 0, 160, 160);
            localStorage.setItem("bankao_avatar_" + state.user.id, c.toDataURL("image/jpeg", .85));
            toast("Fotografia atualizada com sucesso.", "success"); renderSettings();
        };
        img.src = URL.createObjectURL(f);
    };
    inp.click();
}
function stPassword() {
    stModal("Alterar palavra-passe", stIn("pwC", "Palavra-passe atual", "password", 'autocomplete="current-password"') + stIn("pwN", "Nova palavra-passe", "password", 'autocomplete="new-password"') + stIn("pwR", "Confirmar nova palavra-passe", "password", 'autocomplete="new-password"') + '<p class="st-hint">Mínimo 8 caracteres, com letras e números.</p>',
        [{ label: "Cancelar" }, { label: "Alterar", primary: 1, run: async () => {
            if (stV("pwN") !== stV("pwR")) throw new Error("As palavras-passe não coincidem.");
            await apiRequest("POST", "/api/settings/password", { current_password: stV("pwC"), new_password: stV("pwN") });
            toast("Palavra-passe alterada com sucesso.", "success");
        } }]);
}
function stPin() {
    stModal(ST.hasPin ? "Alterar PIN" : "Definir PIN", (ST.hasPin ? stIn("pnC", "PIN atual", "password", 'inputmode="numeric" maxlength="6"') : "") + stIn("pnN", "Novo PIN (4 a 6 dígitos)", "password", 'inputmode="numeric" maxlength="6"') + stIn("pnR", "Confirmar PIN", "password", 'inputmode="numeric" maxlength="6"'),
        [{ label: "Cancelar" }, { label: "Guardar", primary: 1, run: async () => {
            if (stV("pnN") !== stV("pnR")) throw new Error("Os PIN não coincidem.");
            await apiRequest("POST", "/api/settings/pin", { pin: stV("pnN"), current_pin: ST.hasPin ? stV("pnC") : null });
            ST.hasPin = true; sessionStorage.setItem("bankao_pin_ok", "1");
            toast("PIN guardado com sucesso.", "success"); stRefresh();
        } }]);
}
const uaShort = ua => { ua = ua || ""; const b = /Edg\//.test(ua) ? "Edge" : /Chrome\//.test(ua) ? "Chrome" : /Firefox\//.test(ua) ? "Firefox" : /Safari\//.test(ua) ? "Safari" : "Navegador"; const o = /Android/.test(ua) ? "Android" : /iPhone|iPad/.test(ua) ? "iOS" : /Windows/.test(ua) ? "Windows" : /Mac OS/.test(ua) ? "macOS" : /Linux/.test(ua) ? "Linux" : ""; return b + (o ? " · " + o : ""); };
const stWhen = v => { const d = new Date(String(v).replace(" ", "T") + "Z"); return isNaN(d) ? "" : bkFormatDate(d) + " " + d.toLocaleTimeString("pt-AO", { hour: "2-digit", minute: "2-digit" }); };
async function stSessions() {
    const d = await apiRequest("GET", "/api/settings/sessions");
    const list = d.sessions.map(s => '<div class="st-li"><div><b>' + escapeHtml(uaShort(s.device)) + (s.id === d.current ? ' <em class="st-tag">Este dispositivo</em>' : "") + '</b><small>' + escapeHtml(s.ip || "") + " · " + stWhen(s.last_seen) + '</small></div>' +
        (s.id === d.current ? "" : '<button type="button" class="st-btn danger sm" data-sid="' + s.id + '">Terminar</button>') + '</div>').join("") || "<p>Sem sessões.</p>";
    const ov = stModal("Dispositivos com sessão iniciada", list, [{ label: "Terminar todas as outras", danger: 1, run: async () => { await apiRequest("POST", "/api/settings/sessions/revoke-others"); ST.sessions = 1; toast("Outras sessões terminadas.", "success"); stRefresh(); } }, { label: "Fechar" }]);
    ov.addEventListener("click", async e => {
        const b = e.target.closest("[data-sid]"); if (!b) return;
        await apiRequest("DELETE", "/api/settings/sessions/" + b.dataset.sid); b.closest(".st-li").remove(); ST.sessions = Math.max(1, ST.sessions - 1); toast("Sessão terminada.", "success"); stRefresh();
    });
}
async function stHistory() {
    const d = await apiRequest("GET", "/api/settings/login-history");
    stModal("Histórico de acessos", d.history.map(h => '<div class="st-li"><div><b>' + (h.success ? "Início de sessão" : "Tentativa falhada") + '</b><small>' + escapeHtml(uaShort(h.device)) + " · " + escapeHtml(h.ip || "") + " · " + stWhen(h.created_at) + '</small></div><span class="st-val' + (h.success ? " ok" : "") + '">' + (h.success ? "OK" : "Falhou") + '</span></div>').join("") || "<p>Sem registos.</p>");
}
function stPerms() {
    const P = [["hide_balances", "Ocultar saldos por padrão"], ["ai_perm_balances", "Copilot: ver saldos"], ["ai_perm_transactions", "Copilot: ver movimentos"], ["ai_perm_cards", "Copilot: ver cartões"], ["ai_perm_savings", "Copilot: ver poupanças"], ["ai_perm_investments", "Copilot: ver investimentos"]];
    const html = P.map(p => '<div class="st-row"><span class="st-rt"><b>' + p[1] + '</b></span><button type="button" class="st-sw' + (ST.settings[p[0]] ? " on" : "") + '" data-pk="' + p[0] + '" role="switch"></button></div>').join("");
    const ov = stModal("Permissões e privacidade", html, [{ label: "Cancelar" }, { label: "Guardar", primary: 1, run: async ov => {
        const v = {}; ov.querySelectorAll("[data-pk]").forEach(b => { const on = b.classList.contains("on"); if (on !== !!ST.settings[b.dataset.pk]) v[b.dataset.pk] = on; });
        if (Object.keys(v).length) { const d = await apiRequest("PUT", "/api/settings", { values: v }); ST.settings = Object.assign({}, ST_DEFAULTS, d.settings); applySettings({ balances: "hide_balances" in v }); toast("Permissões guardadas.", "success"); }
        stRefresh();
    } }]);
    ov.addEventListener("click", e => { const b = e.target.closest("[data-pk]"); if (b) b.classList.toggle("on"); });
}
function stLock() {
    const lock = !ST.locked;
    stModal(lock ? "Bloquear a conta" : "Desbloquear a conta", '<p>' + (lock ? "Todos os movimentos (transferências, pagamentos, poupança) ficam suspensos até desbloquear." : "Os movimentos voltam a estar permitidos.") + '</p>' + stIn("lkP", "Palavra-passe", "password"),
        [{ label: "Cancelar" }, { label: lock ? "Bloquear" : "Desbloquear", primary: 1, danger: lock, run: async () => {
            await apiRequest("POST", "/api/settings/account-lock", { lock, password: stV("lkP") });
            ST.locked = lock; toast(lock ? "Conta bloqueada com sucesso." : "Conta desbloqueada com sucesso.", "success");
            if (typeof loadUserData === "function") loadUserData(); renderSettings();
        } }]);
}
function stAccounts() {
    const html = ST.accounts.map(a => '<div class="st-acc"><b>' + a.currency + (a.status !== "active" ? ' <em class="st-tag">' + (a.status === "blocked" ? "Bloqueada" : a.status) + '</em>' : "") + '</b>' +
        '<small>Nº de conta</small><div class="st-copy"><code>' + groupDigits(a.account_number) + '</code><button type="button" class="st-btn sm" data-copy="' + a.account_number + '">Copiar</button></div>' +
        '<small>IBAN</small><div class="st-copy"><code>' + groupDigits(a.iban || "") + '</code><button type="button" class="st-btn sm" data-copy="' + (a.iban || "") + '">Copiar</button></div></div>').join("") + '<p class="st-hint">IBAN e nº de conta são só de leitura e não podem ser alterados.</p>';
    const ov = stModal("Contas bancárias", html);
    ov.addEventListener("click", e => { const b = e.target.closest("[data-copy]"); if (b) { navigator.clipboard && navigator.clipboard.writeText(b.dataset.copy); toast("Copiado com sucesso.", "success"); } });
}
function stAiHist() {
    stModal("Histórico de conversas", "<p>" + (state.chatHistory || []).length + " mensagens guardadas nesta sessão. Pode limpar a conversa com o Copilot.</p>",
        [{ label: "Cancelar" }, { label: "Limpar histórico", danger: 1, run: () => {
            state.chatHistory = []; state.copilotPending = null;
            const box = document.getElementById("copilotChatMessages"); if (box) box.querySelectorAll(".copilot-msg, .msg, .chat-msg, .copilot-bubble").forEach(n => n.remove());
            toast("Histórico limpo com sucesso.", "success"); stRefresh();
        } }]);
}
function stSupport(kind, title, hint) {
    stModal(title, '<p class="st-hint">' + hint + '</p><label class="st-lab">Mensagem<textarea class="st-in" id="spM" rows="4" maxlength="1000"></textarea></label>',
        [{ label: "Cancelar" }, { label: "Enviar", primary: 1, run: async () => {
            const d = await apiRequest("POST", "/api/settings/support", { kind, message: stV("spM") });
            toast("Pedido enviado com sucesso. Ref. " + d.id, "success");
        } }]);
}
function stClose() {
    stModal("Solicitar encerramento da conta", '<p>Pedido sujeito a confirmação do banco. Para continuar escreva <b>ENCERRAR</b>.</p>' + stIn("clT", "Confirmação"),
        [{ label: "Cancelar" }, { label: "Enviar pedido", danger: 1, run: async () => {
            if (stV("clT").trim().toUpperCase() !== "ENCERRAR") throw new Error("Escreva ENCERRAR para confirmar.");
            const d = await apiRequest("POST", "/api/settings/support", { kind: "encerramento", message: "Pedido de encerramento da conta" });
            toast("Pedido enviado com sucesso. Ref. " + d.id, "success");
        } }]);
}

/* ---------- Eventos ---------- */
function initSettings() {
    const v = document.getElementById("view-settings"); if (!v) return;
    renderSettings();
    document.getElementById("stNav").addEventListener("click", e => {
        const b = e.target.closest(".st-navbtn"); if (!b) return;
        v.classList.add("st-detail"); openSettingsCat(b.dataset.cat); window.scrollTo({ top: 0 });
    });
    document.getElementById("stBack").addEventListener("click", () => v.classList.remove("st-detail"));
    document.querySelector(".st-edit")?.addEventListener("click", () => { v.classList.add("st-detail"); openSettingsCat("perfil"); });
    document.getElementById("stPanel").addEventListener("click", async e => {
        const panel = document.getElementById("stPanel");
        if (e.target.closest("#stLogout")) return logout();
        if (e.target.closest("#stSave")) return saveSettings();
        if (e.target.closest("#stCancel")) return cancelSettings();
        const sw = e.target.closest(".st-sw");
        if (sw && sw.dataset.key) {
            const k = sw.dataset.key, nv = !bk(k);
            if (nv === !!ST.settings[k]) delete ST.pending[k]; else ST.pending[k] = nv;
            if (k === "ai_enabled" || k === "ai_voice") { document.body.classList.toggle(k === "ai_enabled" ? "ai-off" : "ai-voice-off", !nv); }
            return stRefresh();
        }
        if (sw && sw.dataset.card) {
            const c = ST.cards.find(x => x.id === sw.dataset.card), block = c.status !== "blocked";
            try {
                await apiRequest("POST", "/api/cards/" + c.id + "/control", { action: block ? "block" : "unblock" });
                c.status = block ? "blocked" : "active"; toast(block ? "Cartão bloqueado com sucesso." : "Cartão desbloqueado com sucesso.", "success"); stRefresh();
                if (typeof loadCardsData === "function") loadCardsData();
            } catch (er) { toast(er.message, "error"); }
            return;
        }
        const row = e.target.closest("[data-r]");
        if (row) { try { await stAction(panel._rows[+row.dataset.r]); } catch (er) { toast(er.message, "error"); } }
    });
}
