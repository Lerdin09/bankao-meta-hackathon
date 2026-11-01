/**
 * Navegação inferior — vidro líquido
 * • Toque num item: vai para a página.
 * • Manter o dedo e deslizar: a lente segue o dedo (com mola) e ao soltar abre o item escolhido.
 * A lente é movida por uma mola física (overshoot + esticar com a velocidade), sem bibliotecas.
 */
(function () {
    const nav = document.getElementById("bottomNav");
    const track = document.getElementById("bnTrack");
    const lens = document.getElementById("bnLens");
    if (!nav || !track || !lens) return;

    const items = Array.from(track.querySelectorAll(".nav-item"));
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    nav.classList.add("bn-js");

    // Estado da mola (px) — x: posição da lente, s: escala de "pressão"
    const spring = { x: 0, vx: 0, tx: 0, s: 1, vs: 0, ts: 1 };
    let raf = 0, last = 0;
    let dragging = false, pointerId = null, hotIndex = -1, startX = 0, moved = false;
    let lensW = 0;

    const activeIndex = () => items.findIndex(i => i.classList.contains("active"));
    const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

    function metrics() {
        const first = items[0];
        if (!first || !first.offsetWidth) return false;
        lensW = Math.round(first.offsetWidth - 4);
        lens.style.setProperty("--lw", lensW + "px");
        return true;
    }
    const centerOf = (i) => items[i].offsetLeft + items[i].offsetWidth / 2;
    const xForCenter = (c) => c - lensW / 2;

    function render() {
        // esticar na direção do movimento, com compressão vertical leve (efeito líquido)
        const stretch = Math.min(Math.abs(spring.vx) / 4200, 0.12);
        const sx = (1 + stretch) * spring.s;
        const sy = (1 - stretch * 0.2) * spring.s;
        lens.style.setProperty("--lx", spring.x.toFixed(2) + "px");
        lens.style.setProperty("--sx", sx.toFixed(4));
        lens.style.setProperty("--sy", sy.toFixed(4));
    }

    function tick(now) {
        const dt = Math.min((now - last) / 1000, 0.032) || 0.016;
        last = now;
        // Mola amortecida: ligeiramente sub-amortecida para dar o "salto" final
        const k = 380, c = 34;
        const ax = -k * (spring.x - spring.tx) - c * spring.vx;
        spring.vx += ax * dt; spring.x += spring.vx * dt;
        const ks = 420, cs = 26;
        const as = -ks * (spring.s - spring.ts) - cs * spring.vs;
        spring.vs += as * dt; spring.s += spring.vs * dt;
        render();
        const settled = Math.abs(spring.x - spring.tx) < 0.15 && Math.abs(spring.vx) < 2 &&
                        Math.abs(spring.s - spring.ts) < 0.002 && Math.abs(spring.vs) < 0.05;
        if (settled) {
            spring.x = spring.tx; spring.vx = 0; spring.s = spring.ts; spring.vs = 0;
            render(); raf = 0; return;
        }
        raf = requestAnimationFrame(tick);
    }
    function kick() { if (!raf) { last = performance.now(); raf = requestAnimationFrame(tick); } }

    function goTo(x, scale, instant) {
        spring.tx = x; spring.ts = scale;
        if (instant || reduceMotion.matches) {
            spring.x = x; spring.vx = 0; spring.s = scale; spring.vs = 0; render();
        } else kick();
    }

    // Coloca a lente sobre o item ativo da página (se não houver, esconde-a)
    function syncToActive(instant) {
        if (dragging) return;
        if (!metrics()) return;
        const i = activeIndex();
        lens.classList.toggle("ready", i >= 0);
        if (i < 0) return;
        goTo(xForCenter(centerOf(i)), 1, instant || !lens.dataset.placed);
        lens.dataset.placed = "1";
    }

    function indexAt(clientX) {
        const rect = track.getBoundingClientRect();
        const x = clientX - rect.left;
        let best = 0, bestD = Infinity;
        items.forEach((it, i) => {
            const d = Math.abs(x - centerOf(i));
            if (d < bestD) { bestD = d; best = i; }
        });
        return best;
    }
    function setHot(i) {
        if (i === hotIndex) return;
        hotIndex = i;
        items.forEach((it, idx) => it.classList.toggle("hot", idx === i));
        if (i >= 0 && navigator.vibrate) { try { navigator.vibrate(6); } catch (_) { /* ignore */ } }
    }

    // ---------- Gestos ----------
    track.addEventListener("pointerdown", (e) => {
        if (e.button !== undefined && e.button > 0) return;
        if (!metrics()) return;
        dragging = true; moved = false; pointerId = e.pointerId; startX = e.clientX;
        try { track.setPointerCapture(pointerId); } catch (_) { /* ignore */ }
        nav.classList.add("pressing");
        lens.classList.add("ready");
        const i = indexAt(e.clientX);
        setHot(i);
        // A lente "salta" para o dedo e cresce ao toque
        const rect = track.getBoundingClientRect();
        goTo(clamp(e.clientX - rect.left - lensW / 2, xForCenter(centerOf(0)) - 6, xForCenter(centerOf(items.length - 1)) + 6), 1.08);
    });

    track.addEventListener("pointermove", (e) => {
        if (!dragging || e.pointerId !== pointerId) return;
        if (Math.abs(e.clientX - startX) > 4) moved = true;
        const rect = track.getBoundingClientRect();
        const minX = xForCenter(centerOf(0)) - 6;
        const maxX = xForCenter(centerOf(items.length - 1)) + 6;
        goTo(clamp(e.clientX - rect.left - lensW / 2, minX, maxX), 1.08);
        setHot(indexAt(e.clientX));
    });

    function finish(e, cancelled) {
        if (!dragging || (e && e.pointerId !== pointerId)) return;
        dragging = false;
        nav.classList.remove("pressing");
        try { track.releasePointerCapture(pointerId); } catch (_) { /* ignore */ }
        const chosen = cancelled ? -1 : hotIndex;
        setHot(-1);
        if (chosen < 0) { syncToActive(false); return; }
        const item = items[chosen];
        const isMore = item.classList.contains("nav-more-btn");
        if (isMore) {
            // "Mais" abre o menu; a lente volta ao item da página atual
            goTo(xForCenter(centerOf(chosen)), 1);
            item.click();
            setTimeout(() => syncToActive(false), 280);
        } else {
            goTo(xForCenter(centerOf(chosen)), 1);
            item.click(); // dispara o showView do shell.js; o observer abaixo confirma a posição
        }
    }
    // Depois de um gesto na barra, engole o clique nativo que o browser dispara a seguir: o item
    // já foi aberto no pointerup e o clique poderia cair no que acabou de aparecer (ex.: o menu "Mais").
    let swallowUntil = 0;
    document.addEventListener("click", (e) => {
        if (e.isTrusted && performance.now() < swallowUntil) { e.stopImmediatePropagation(); e.preventDefault(); }
    }, true);
    track.addEventListener("pointerup", (e) => {
        if (dragging && e.pointerId === pointerId) swallowUntil = performance.now() + 450;
        finish(e, false);
    });
    track.addEventListener("pointercancel", (e) => finish(e, true));
    track.addEventListener("lostpointercapture", (e) => { if (dragging) finish(e, true); });

    // O toque nativo já foi tratado no pointerup — bloqueia o clique duplicado.
    // Cliques programáticos (isTrusted=false) e de teclado (detail=0) passam.
    track.addEventListener("click", (e) => {
        if (e.isTrusted && e.detail > 0) { e.stopImmediatePropagation(); e.preventDefault(); }
    }, true);
    track.addEventListener("contextmenu", (e) => e.preventDefault());

    // Teclado: setas movem o foco entre itens
    track.addEventListener("keydown", (e) => {
        if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
        const i = items.indexOf(document.activeElement);
        if (i < 0) return;
        const n = (i + (e.key === "ArrowRight" ? 1 : -1) + items.length) % items.length;
        items[n].focus(); e.preventDefault();
    });

    // Mantém a lente alinhada quando a página muda por outras vias (menu lateral, atalhos, etc.)
    new MutationObserver(() => syncToActive(false)).observe(track, { attributes: true, attributeFilter: ["class"], subtree: true });
    if ("ResizeObserver" in window) new ResizeObserver(() => syncToActive(true)).observe(track);
    window.addEventListener("resize", () => syncToActive(true));
    window.addEventListener("orientationchange", () => setTimeout(() => syncToActive(true), 200));
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => syncToActive(true));
    syncToActive(true);
})();
