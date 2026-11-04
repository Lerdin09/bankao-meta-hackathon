/**
 * Contactos — pessoas (clientes BankAO) e IBANs com quem já movimentei dinheiro.
 *
 * API:  GET /api/contacts            -> { contacts: [...], total }   (histórico + guardados, já ordenados)
 *       POST /api/contacts           -> guarda/atualiza (apelido, favorito)
 *       PATCH /api/contacts/{id}     -> apelido / favorito
 *       DELETE /api/contacts/{id}    -> remove dos guardados (o histórico continua a sugeri-lo)
 * «Enviar» pré-preenche o separador de transferência certo (conta BankAO ou IBAN).
 */
const CT = { items: [], filter: "all", q: "", edit: null, loaded: false, busy: false };

const ctEsc = s => escapeHtml(s == null ? "" : s);
const ctEl = id => document.getElementById(id);

function ctDate(v) {
    if (!v) return "";
    const d = new Date(String(v).includes("T") ? v : String(v).replace(" ", "T") + "Z");
    return isNaN(d) ? "" : (typeof bkFormatDate === "function" ? bkFormatDate(d) : d.toLocaleDateString("pt-AO", { day: "2-digit", month: "short", year: "numeric" }));
}

function ctInitials(name) {
    const parts = String(name || "?").trim().split(/\s+/).filter(Boolean);
    return ((parts[0] || "?")[0] + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

function ctHue(key) {
    let h = 0;
    for (const ch of String(key || "")) h = (h * 31 + ch.charCodeAt(0)) % 360;
    return h;
}

const ctGroupIban = v => String(v || "").replace(/\s+/g, "").replace(/(.{4})/g, "$1 ").trim();
const ctGroupAcc = v => String(v || "").replace(/\D/g, "").replace(/(\d{4})(?=\d)/g, "$1 ");

function ctMatches(c) {
    if (CT.filter === "favorite" && !c.favorite) return false;
    if (CT.filter === "sent" && !c.sent_count) return false;
    if (CT.filter === "received" && !c.received_count) return false;
    if (CT.filter === "internal" && c.kind !== "internal") return false;
    if (CT.filter === "iban" && c.kind !== "iban") return false;
    if (CT.q) {
        const hay = [c.name, c.nickname, c.account_number, c.iban].filter(Boolean).join(" ").toLowerCase();
        const qn = CT.q.toLowerCase();
        if (!hay.includes(qn) && !hay.replace(/\s/g, "").includes(qn.replace(/\s/g, ""))) return false;
    }
    return true;
}

function ctMeta(c) {
    const bits = [];
    if (c.last_direction === "sent" && c.last_sent_amount != null) {
        bits.push(`Último envio: ${formatMoney(c.last_sent_amount, c.last_sent_currency || "AOA")}`);
    } else if (c.last_direction === "received") {
        bits.push("Último movimento: recebeu dele(a)");
    }
    if (c.last_at) bits.push(ctDate(c.last_at));
    const counts = [];
    if (c.sent_count) counts.push(`${c.sent_count} envio${c.sent_count > 1 ? "s" : ""}`);
    if (c.received_count) counts.push(`${c.received_count} recebido${c.received_count > 1 ? "s" : ""}`);
    if (counts.length) bits.push(counts.join(" · "));
    return bits.length ? bits.join(" · ") : "Guardado, sem movimentos ainda";
}

function ctRow(c) {
    const sub = c.kind === "internal"
        ? `Cliente BankAO · conta ${ctEsc(ctGroupAcc(c.account_number))}`
        : `IBAN ${ctEsc(ctGroupIban(c.iban))}`;
    const showName = c.nickname ? `<small>${ctEsc(c.name)}</small>` : "";
    return `
    <article class="ct-card" data-key="${ctEsc(c.key)}">
        <div class="ct-avatar" style="--h:${ctHue(c.key)}" data-act="open" aria-hidden="true">${ctEsc(ctInitials(c.name))}</div>
        <div class="ct-info" data-act="open" role="button" tabindex="0" aria-label="Ver transferências com ${ctEsc(c.display_name)}">
            <strong>${ctEsc(c.display_name)}${showName}</strong>
            <span class="ct-sub ${c.kind === "iban" ? "mono" : ""}">${sub}</span>
            <span class="ct-meta">${ctEsc(ctMeta(c))}</span>
        </div>
        <div class="ct-actions">
            <button type="button" class="ct-icon-btn ct-fav ${c.favorite ? "on" : ""}" data-act="fav" aria-pressed="${c.favorite}" aria-label="${c.favorite ? "Remover dos favoritos" : "Adicionar aos favoritos"}" title="Favorito">
                <svg><use href="#i-heart"/></svg>
            </button>
            <button type="button" class="ct-icon-btn" data-act="edit" aria-label="Editar apelido" title="Editar apelido"><svg><use href="#i-edit"/></svg></button>
            ${c.saved ? `<button type="button" class="ct-icon-btn" data-act="del" aria-label="Remover contacto" title="Remover"><svg><use href="#i-trash"/></svg></button>` : ""}
            <button type="button" class="ct-send" data-act="send"><span>Enviar</span><svg><use href="#i-send"/></svg></button>
        </div>
    </article>`;
}

function renderContacts() {
    const list = ctEl("ctList"), empty = ctEl("ctEmpty");
    if (!list) return;
    const items = CT.items.filter(ctMatches);
    list.innerHTML = items.map(ctRow).join("");
    const none = !items.length;
    if (empty) {
        empty.hidden = !none;
        if (none) {
            const filtering = CT.items.length > 0;
            ctEl("ctEmptyTitle").textContent = filtering ? "Nenhum contacto encontrado" : "Ainda não tem contactos";
            ctEl("ctEmptyText").textContent = filtering
                ? "Experimente outro filtro ou outra pesquisa."
                : "Quando enviar ou receber dinheiro, as pessoas e os IBANs aparecem aqui automaticamente.";
        }
    }
}

async function loadContacts(silent) {
    if (!state.token) return;
    try {
        const d = await apiRequest("GET", "/api/contacts");
        CT.items = d.contacts || [];
        CT.loaded = true;
        renderContacts();
    } catch (err) {
        if (!silent) toast(err.message || "Não foi possível carregar os contactos.", "error");
    }
}

/* ─── Enviar: pré-preenche a transferência certa ────────────────────────── */
function ctFire(el) {
    if (!el) return;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
}

function ctSend(c) {
    if (c.kind === "internal") {
        window.showTab && window.showTab("tab-transfer-internal");
        const dest = ctEl("internalDestEmail");
        if (dest) { dest.value = ctGroupAcc(c.account_number); ctFire(dest); }
        setTimeout(() => ctEl("internalAmount")?.focus(), 60);
    } else {
        window.showTab && window.showTab("tab-transfer-iban");
        const iban = ctEl("ibanInput"), name = ctEl("beneficiaryName");
        if (iban) { iban.value = ctGroupIban(c.iban); ctFire(iban); }
        if (name) { name.value = c.name; ctFire(name); }
        setTimeout(() => ctEl("ibanSendAmount")?.focus(), 60);
    }
    ctEl("view-ops")?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    toast(`Destinatário preenchido: ${c.display_name}. Indique o valor.`, "success");
}

/* ─── Guardar / editar / favorito / remover ─────────────────────────────── */
function ctPayload(c, extra) {
    return { kind: c.kind, account_number: c.account_number || undefined, iban: c.iban || undefined, name: c.name, ...extra };
}

async function ctToggleFav(c) {
    try {
        if (c.saved) await apiRequest("PATCH", `/api/contacts/${c.id}`, { favorite: !c.favorite });
        else await apiRequest("POST", "/api/contacts", ctPayload(c, { favorite: true, nickname: c.nickname || undefined }));
        await loadContacts(true);
    } catch (err) { toast(err.message || "Não foi possível atualizar o favorito.", "error"); }
}

async function ctDelete(c) {
    const ok = await confirmDialog({
        title: "Remover contacto?", message: `${c.display_name} deixa de estar guardado.`,
        note: c.total_count ? "Como já houve movimentos com esta pessoa/IBAN, continuará a aparecer como sugestão." : "",
        confirmText: "Remover"
    });
    if (!ok) return;
    try {
        await apiRequest("DELETE", `/api/contacts/${c.id}`);
        toast("Contacto removido.", "success");
        await loadContacts(true);
    } catch (err) { toast(err.message || "Não foi possível remover.", "error"); }
}

function ctOpenForm(c) {
    CT.edit = c || null;
    const form = ctEl("ctForm");
    if (!form) return;
    const editing = !!c;
    ctEl("ctFormTitle").textContent = editing ? `Editar ${c.name}` : "Novo contacto";
    ctEl("ctKindRow").hidden = editing;
    ctEl("ctAccountGroup").hidden = editing || ctKind() !== "internal";
    ctEl("ctIbanGroup").hidden = editing || ctKind() !== "iban";
    ctEl("ctNameGroup").hidden = editing || ctKind() !== "iban";
    ctEl("ctAccount").value = ""; ctEl("ctIban").value = ""; ctEl("ctName").value = "";
    ctEl("ctNickname").value = editing ? (c.nickname || "") : "";
    ctFormError("");
    form.hidden = false;
    (editing ? ctEl("ctNickname") : (ctKind() === "iban" ? ctEl("ctIban") : ctEl("ctAccount"))).focus();
}

function ctCloseForm() { CT.edit = null; const f = ctEl("ctForm"); if (f) f.hidden = true; ctFormError(""); }
const ctKind = () => document.querySelector('input[name="ctKind"]:checked')?.value || "internal";
function ctFormError(msg) { const e = ctEl("ctFormError"); if (e) { e.textContent = msg; e.hidden = !msg; } }

async function ctSubmit(ev) {
    ev.preventDefault();
    if (CT.busy) return;
    const nickname = ctEl("ctNickname").value.trim();
    const btn = ctEl("ctFormSave");
    CT.busy = true; if (btn) btn.disabled = true;
    ctFormError("");
    try {
        if (CT.edit) {
            if (CT.edit.saved) await apiRequest("PATCH", `/api/contacts/${CT.edit.id}`, { nickname });
            else await apiRequest("POST", "/api/contacts", ctPayload(CT.edit, { nickname: nickname || undefined }));
        } else if (ctKind() === "internal") {
            await apiRequest("POST", "/api/contacts", { kind: "internal", account_number: ctEl("ctAccount").value, nickname: nickname || undefined });
        } else {
            await apiRequest("POST", "/api/contacts", { kind: "iban", iban: ctEl("ctIban").value, name: ctEl("ctName").value.trim(), nickname: nickname || undefined });
        }
        toast("Contacto guardado com sucesso.", "success");
        ctCloseForm();
        await loadContacts(true);
    } catch (err) { ctFormError(err.message || "Não foi possível guardar."); }
    finally { CT.busy = false; if (btn) btn.disabled = false; }
}

/* ─── Inicialização ─────────────────────────────────────────────────────── */
function initContacts() {
    if (!ctEl("tab-contacts")) return;

    document.querySelector('.tab-btn[data-tab="tab-contacts"]')?.addEventListener("click", () => loadContacts());

    ctEl("ctSearch")?.addEventListener("input", e => { CT.q = e.target.value.trim(); renderContacts(); });

    ctEl("ctFilters")?.addEventListener("click", e => {
        const b = e.target.closest(".ct-chip");
        if (!b) return;
        document.querySelectorAll("#ctFilters .ct-chip").forEach(x => x.classList.toggle("active", x === b));
        CT.filter = b.dataset.ct;
        renderContacts();
    });

    ctEl("ctAddBtn")?.addEventListener("click", () => ctOpenForm(null));
    ctEl("ctFormCancel")?.addEventListener("click", ctCloseForm);
    ctEl("ctForm")?.addEventListener("submit", ctSubmit);
    document.querySelectorAll('input[name="ctKind"]').forEach(r => r.addEventListener("change", () => {
        const iban = ctKind() === "iban";
        ctEl("ctAccountGroup").hidden = iban;
        ctEl("ctIbanGroup").hidden = !iban;
        ctEl("ctNameGroup").hidden = !iban;
        ctFormError("");
    }));

    ctEl("ctList")?.addEventListener("keydown", e => {
        if (e.key !== "Enter" && e.key !== " ") return;
        const t = e.target.closest('.ct-info[data-act="open"]');
        if (!t) return;
        e.preventDefault();
        const c = CT.items.find(x => x.key === t.closest(".ct-card")?.dataset.key);
        if (c) ctOpenSheet(c);
    });

    ctEl("ctList")?.addEventListener("click", e => {
        const btn = e.target.closest("[data-act]");
        const card = e.target.closest(".ct-card");
        if (!btn || !card) return;
        const c = CT.items.find(x => x.key === card.dataset.key);
        if (!c) return;
        ({ send: ctSend, fav: ctToggleFav, edit: ctOpenForm, del: ctDelete, open: ctOpenSheet })[btn.dataset.act]?.(c);
    });
}

/* ═══ Ficha do contacto: histórico por páginas com janela deslizante ═══════
 * Carrega 10 de cada vez. No ecrã ficam no máximo CTD_MAX (50) linhas: ao chegar às 60, as 10 primeiras
 * saem do DOM (ficam num espaçador com a mesma altura) e voltam quando se sobe outra vez.
 */
const CTD_PAGE = 10, CTD_MAX = 50, CTD_ROW_H = 86;
let CTD = null;

function ctDateTime(v) {
    if (!v) return "";
    const d = new Date(String(v).includes("T") ? v : String(v).replace(" ", "T") + "Z");
    return isNaN(d) ? "" : d.toLocaleString("pt-AO", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function ctdRow(t, i) {
    const sent = t.direction === "sent";
    return `
    <div class="ctd-row" data-i="${i}">
        <div class="ctd-ic ${sent ? "sent" : "received"}"><svg><use href="#${sent ? "i-up" : "i-down"}"/></svg></div>
        <div class="ctd-main">
            <strong>${sent ? "Enviou para" : "Recebeu de"} ${ctEsc(t.name)}</strong>
            <span>${ctEsc(ctDateTime(t.created_at))} · ${ctEsc(t.method)}</span>
            <span class="ctd-bal">Tinha ${ctEsc(formatMoney(t.balance_before, t.currency))} · Ficou ${ctEsc(formatMoney(t.balance_after, t.currency))}</span>
        </div>
        <div class="ctd-amt ${sent ? "sent" : "received"}">${sent ? "−" : "+"}${ctEsc(formatMoney(t.amount, t.currency))}</div>
    </div>`;
}

function ctOpenSheet(c) {
    ctCloseSheet();
    const prevFocus = document.activeElement;
    const root = document.createElement("div");
    root.className = "ctd-overlay";
    const sub = c.kind === "internal" ? `Cliente BankAO · conta ${ctGroupAcc(c.account_number)}` : `IBAN ${ctGroupIban(c.iban)}`;
    root.innerHTML = `
        <div class="ctd-sheet" role="dialog" aria-modal="true" aria-labelledby="ctdTitle">
            <header class="ctd-head">
                <div class="ct-avatar" style="--h:${ctHue(c.key)}" aria-hidden="true">${ctEsc(ctInitials(c.name))}</div>
                <div class="ctd-who">
                    <h3 id="ctdTitle">${ctEsc(c.display_name)}</h3>
                    ${c.nickname ? `<small>${ctEsc(c.name)}</small>` : ""}
                    <span class="${c.kind === "iban" ? "mono" : ""}">${ctEsc(sub)}</span>
                </div>
                <button type="button" class="ct-icon-btn" id="ctdClose" aria-label="Fechar"><svg><use href="#i-x"/></svg></button>
            </header>
            <div class="ctd-summary">
                <span><b>${c.sent_count}</b> envio${c.sent_count === 1 ? "" : "s"}</span>
                <span><b>${c.received_count}</b> recebido${c.received_count === 1 ? "" : "s"}</span>
                <button type="button" class="ct-send" id="ctdSend"><span>Enviar</span><svg><use href="#i-send"/></svg></button>
            </div>
            <div class="ctd-scroll" id="ctdScroll">
                <div id="ctdTopSpacer"></div>
                <div id="ctdTopSentinel" class="ctd-sentinel"></div>
                <div id="ctdRows"></div>
                <div id="ctdBottomSentinel" class="ctd-sentinel"></div>
                <div id="ctdBottomSpacer"></div>
                <p class="ctd-status" id="ctdStatus" aria-live="polite"></p>
            </div>
        </div>`;
    document.body.appendChild(root);
    document.body.style.overflow = "hidden";

    CTD = { c, root, prevFocus, items: [], total: null, winStart: 0, winEnd: 0, heights: [], busy: false, error: false, io: null };
    const scroll = root.querySelector("#ctdScroll");
    const onKey = e => { if (e.key === "Escape") { e.stopPropagation(); ctCloseSheet(); } };
    CTD.onKey = onKey;
    document.addEventListener("keydown", onKey, true);
    root.addEventListener("click", e => { if (e.target === root) ctCloseSheet(); });
    root.querySelector("#ctdClose").addEventListener("click", ctCloseSheet);
    root.querySelector("#ctdSend").addEventListener("click", () => { const cc = CTD.c; ctCloseSheet(); ctSend(cc); });
    root.querySelector("#ctdStatus").addEventListener("click", e => { if (e.target.closest("[data-retry]")) ctdLoadMore(true); });

    CTD.io = new IntersectionObserver(entries => {
        entries.forEach(en => {
            if (!en.isIntersecting || !CTD) return;
            if (en.target.id === "ctdBottomSentinel") ctdLoadMore();
            else ctdShowEarlier();
        });
    }, { root: scroll, rootMargin: "80px 0px" });

    // Salto grande (arrastar a barra, ir ao topo): se o ecrã cair no espaço das linhas retiradas, reposiciona a janela.
    let raf = 0;
    scroll.addEventListener("scroll", () => {
        if (raf) return;
        raf = requestAnimationFrame(() => { raf = 0; ctdSyncToScroll(); });
    }, { passive: true });

    root.querySelector("#ctdClose").focus();
    ctdLoadMore(true);
}

function ctCloseSheet() {
    if (!CTD) return;
    CTD.io && CTD.io.disconnect();
    document.removeEventListener("keydown", CTD.onKey, true);
    CTD.root.remove();
    document.body.style.overflow = "";
    try { CTD.prevFocus && CTD.prevFocus.focus({ preventScroll: true }); } catch (_) { /* ignore */ }
    CTD = null;
}

/** Descendo: mostra mais 10 (já carregadas ou novas do servidor) e, se passar de 50, larga as mais antigas do topo. */
async function ctdLoadMore(force) {
    const d = CTD;
    if (!d || d.busy) return;
    if (d.error && !force) return;
    const loaded = d.items.length;
    if (d.winEnd >= loaded && d.total !== null && loaded >= d.total) return;   // fim
    d.busy = true; d.error = false; ctdStatus();
    try {
        if (d.winEnd >= loaded) {
            const r = await apiRequest("GET", `/api/contacts/history?key=${encodeURIComponent(d.c.key)}&limit=${CTD_PAGE}&offset=${loaded}`);
            if (CTD !== d) return;
            d.total = r.total;
            d.items.push(...(r.items || []));
        }
        d.winEnd = Math.min(d.items.length, d.winEnd + CTD_PAGE);
        if (d.winEnd - d.winStart > CTD_MAX) d.winStart = d.winEnd - CTD_MAX;
    } catch (err) {
        if (CTD !== d) return;
        d.error = true;
    } finally {
        if (CTD === d) { d.busy = false; ctdRender(); }
    }
}

/** Subindo: volta a mostrar as 10 mais recentes que tinham saído e, se passar de 50, larga as últimas de baixo. */
function ctdShowEarlier() {
    const d = CTD;
    if (!d || d.busy || d.winStart === 0) return;
    d.winStart = Math.max(0, d.winStart - CTD_PAGE);
    if (d.winEnd - d.winStart > CTD_MAX) d.winEnd = d.winStart + CTD_MAX;
    ctdRender();
}

function ctdSyncToScroll() {
    const d = CTD; if (!d || d.busy || !d.items.length) return;
    const scroll = d.root.querySelector("#ctdScroll");
    const st = scroll.scrollTop, vh = scroll.clientHeight;
    const rowsEl = d.root.querySelector("#ctdRows");
    const rowsTop = rowsEl.offsetTop, rowsBottom = rowsTop + rowsEl.offsetHeight;
    if (st + vh > rowsTop && st < rowsBottom) return;           // ainda vê linhas: os sentinelas tratam do resto
    let acc = 0, idx = 0;                                       // índice da linha que está no topo do ecrã
    for (; idx < d.items.length - 1; idx++) {
        const h = d.heights[idx] || CTD_ROW_H;
        if (acc + h > st) break;
        acc += h;
    }
    const start = Math.max(0, Math.floor(idx / CTD_PAGE) * CTD_PAGE - CTD_PAGE);
    d.winStart = start;
    d.winEnd = Math.min(d.items.length, start + CTD_MAX);
    ctdRender();
}

function ctdStatus() {
    const d = CTD; if (!d) return;
    const el = d.root.querySelector("#ctdStatus");
    if (d.error) el.innerHTML = `Não foi possível carregar. <button type="button" class="btn-text" data-retry>Tentar novamente</button>`;
    else if (d.busy) el.textContent = "A carregar…";
    else if (d.total === 0) el.textContent = "Ainda não há transferências com este contacto.";
    else if (d.total !== null && d.winEnd >= d.total) el.textContent = `${d.total} transferência${d.total === 1 ? "" : "s"} no total`;
    else el.textContent = "";
}

function ctdRender() {
    const d = CTD; if (!d) return;
    const q = s => d.root.querySelector(s);
    const rows = q("#ctdRows");
    rows.innerHTML = d.items.slice(d.winStart, d.winEnd).map((t, k) => ctdRow(t, d.winStart + k)).join("");
    rows.querySelectorAll(".ctd-row").forEach(el => { d.heights[+el.dataset.i] = el.getBoundingClientRect().height; });
    const sum = (from, to) => { let h = 0; for (let i = from; i < to; i++) h += d.heights[i] || CTD_ROW_H; return h; };
    q("#ctdTopSpacer").style.height = sum(0, d.winStart) + "px";            // linhas fora do ecrã, em cima
    q("#ctdBottomSpacer").style.height = sum(d.winEnd, d.items.length) + "px"; // carregadas mas fora do ecrã, em baixo
    ctdStatus();
    // voltar a observar: se o sentinela continuar visível, o observador dispara outra vez
    const top = q("#ctdTopSentinel"), bottom = q("#ctdBottomSentinel");
    const more = d.winEnd < d.items.length || d.total === null || d.items.length < d.total;
    bottom.hidden = !more || d.error; top.hidden = d.winStart === 0;
    d.io.unobserve(top); d.io.unobserve(bottom);
    if (!top.hidden) d.io.observe(top);
    if (!bottom.hidden) d.io.observe(bottom);
}
