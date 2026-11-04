/**
 * Leitor de código QR (ISO 18004) — local, sem dependências e sem rede.
 * Recebe pixéis em tons de cinza e devolve o texto do QR (ou "").
 * Faz: binarização (Otsu e adaptativa) → localização dos 3 "olhos" → amostragem da grelha →
 *      leitura do formato e da máscara → Reed-Solomon (corrige módulos errados) → texto.
 * Serve para imagens de QR (descarregadas, capturas de ecrã, fotografias razoavelmente frontais).
 * Depende de QrEncoder (tabelas de blocos), por isso carrega depois de qr-encoder.js.
 */
const QrDecoder = (() => {
    const T = QrEncoder.tables;

    // ---------- GF(256) + Reed-Solomon ----------
    const EXP = new Array(512).fill(0), LOG = new Array(256).fill(0);
    (function () { let x = 1; for (let i = 0; i < 255; i++) { EXP[i] = x; LOG[x] = i; x <<= 1; if (x & 256) x ^= 0x11D; } for (let i = 255; i < 512; i++) EXP[i] = EXP[i - 255]; })();
    const gmul = (a, b) => (a && b ? EXP[LOG[a] + LOG[b]] : 0);
    const gdiv = (a, b) => (a === 0 ? 0 : EXP[(LOG[a] + 255 - LOG[b]) % 255]);
    const gpow = (x, p) => EXP[(((LOG[x] * p) % 255) + 255) % 255];
    const ginv = (x) => EXP[255 - LOG[x]];
    const pAdd = (p, q) => { const r = new Array(Math.max(p.length, q.length)).fill(0); for (let i = 0; i < p.length; i++) r[i + r.length - p.length] = p[i]; for (let i = 0; i < q.length; i++) r[i + r.length - q.length] ^= q[i]; return r; };
    const pScale = (p, x) => p.map(c => gmul(c, x));
    const pMul = (p, q) => { const r = new Array(p.length + q.length - 1).fill(0); for (let j = 0; j < q.length; j++) for (let i = 0; i < p.length; i++) r[i + j] ^= gmul(p[i], q[j]); return r; };
    const pEval = (p, x) => { let y = p[0]; for (let i = 1; i < p.length; i++) y = gmul(y, x) ^ p[i]; return y; };

    // devolve os codewords de dados corrigidos (ou null se não for possível corrigir)
    function rsCorrect(block, nsym) {
        const msg = block.slice();
        const synd = [0]; let bad = false;
        for (let i = 0; i < nsym; i++) { const v = pEval(msg, gpow(2, i)); synd.push(v); if (v) bad = true; }
        if (!bad) return msg.slice(0, msg.length - nsym);
        // localizador de erros (Berlekamp-Massey)
        let errLoc = [1], oldLoc = [1];
        for (let i = 0; i < nsym; i++) {
            const K = i + 1; let delta = synd[K];
            for (let j = 1; j < errLoc.length; j++) delta ^= gmul(errLoc[errLoc.length - 1 - j], synd[K - j]);
            oldLoc = oldLoc.concat([0]);
            if (delta !== 0) {
                if (oldLoc.length > errLoc.length) { const nl = pScale(oldLoc, delta); oldLoc = pScale(errLoc, ginv(delta)); errLoc = nl; }
                errLoc = pAdd(errLoc, pScale(oldLoc, delta));
            }
        }
        while (errLoc.length && errLoc[0] === 0) errLoc.shift();
        const errs = errLoc.length - 1;
        if (errs * 2 > nsym) return null;
        const pos = [], locRev = errLoc.slice().reverse();
        for (let i = 0; i < msg.length; i++) if (pEval(locRev, gpow(2, i)) === 0) pos.push(msg.length - 1 - i);
        if (pos.length !== errs) return null;
        // magnitudes (Forney)
        const coefPos = pos.map(p => msg.length - 1 - p);
        let eLoc = [1];
        coefPos.forEach(c => { eLoc = pMul(eLoc, pAdd([1], [gpow(2, c), 0])); });
        let ev = pMul(synd.slice().reverse(), eLoc);
        ev = ev.slice(-(eLoc.length));            // resto da divisão por x^(len)
        const X = coefPos.map(c => gpow(2, -(255 - c)));
        const E = new Array(msg.length).fill(0);
        for (let i = 0; i < X.length; i++) {
            const Xi = X[i], Xinv = ginv(Xi);
            let prime = 1;
            for (let j = 0; j < X.length; j++) if (j !== i) prime = gmul(prime, 1 ^ gmul(Xinv, X[j]));
            if (prime === 0) return null;
            let y = pEval(ev, Xinv); y = gmul(Xi, y);
            E[pos[i]] = gdiv(y, prime);
        }
        const fixed = pAdd(msg, E);
        for (let i = 0; i < nsym; i++) { if (pEval(fixed, gpow(2, i)) !== 0) return null; }
        return fixed.slice(0, fixed.length - nsym);
    }

    // ---------- Decodificar a matriz de módulos ----------
    const FMT_ECL = { 1: "L", 0: "M", 3: "Q", 2: "H" };
    const ECL_IDX = { L: 0, M: 1, Q: 2, H: 3 };
    const popc = (x) => { let c = 0; while (x) { c += x & 1; x >>>= 1; } return c; };
    function fmtCode(d) { let rem = d; for (let i = 0; i < 10; i++) rem = (rem << 1) ^ ((rem >>> 9) * 0x537); return ((d << 10) | rem) ^ 0x5412; }

    function readFormat(get, size) {
        let a = 0, b = 0;
        for (let i = 0; i <= 5; i++) a |= get(8, i) << i;
        a |= get(8, 7) << 6; a |= get(8, 8) << 7; a |= get(7, 8) << 8;
        for (let i = 9; i < 15; i++) a |= get(14 - i, 8) << i;
        for (let i = 0; i < 8; i++) b |= get(size - 1 - i, 8) << i;
        for (let i = 8; i < 15; i++) b |= get(8, size - 15 + i) << i;
        let best = null, bestD = 99;
        for (let d = 0; d < 32; d++) {
            const c = fmtCode(d), dist = Math.min(popc(c ^ a), popc(c ^ b));
            if (dist < bestD) { bestD = dist; best = d; }
        }
        return bestD <= 3 ? { ecl: FMT_ECL[best >> 3], mask: best & 7 } : null;
    }

    function functionMap(size, ver) {
        const fn = Array.from({ length: size }, () => new Uint8Array(size));
        const rect = (x0, y0, x1, y1) => { for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) if (x >= 0 && y >= 0 && x < size && y < size) fn[y][x] = 1; };
        rect(0, 0, 8, 8); rect(size - 8, 0, size - 1, 8); rect(0, size - 8, 8, size - 1);
        for (let i = 0; i < size; i++) { fn[6][i] = 1; fn[i][6] = 1; }
        if (ver > 1) {
            const na = Math.floor(ver / 7) + 2;
            const step = ver === 32 ? 26 : Math.ceil((ver * 4 + 4) / (na * 2 - 2)) * 2;
            const pos = [6];
            for (let p = size - 7; pos.length < na; p -= step) pos.splice(1, 0, p);
            for (let i = 0; i < na; i++) for (let j = 0; j < na; j++)
                if (!((i === 0 && j === 0) || (i === 0 && j === na - 1) || (i === na - 1 && j === 0))) rect(pos[i] - 2, pos[j] - 2, pos[i] + 2, pos[j] + 2);
        }
        if (ver >= 7) { rect(size - 11, 0, size - 9, 5); rect(0, size - 11, 5, size - 9); }
        return fn;
    }
    const MASKS = [
        (x, y) => (x + y) % 2 === 0, (x, y) => y % 2 === 0, (x, y) => x % 3 === 0, (x, y) => (x + y) % 3 === 0,
        (x, y) => (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0, (x, y) => ((x * y) % 2) + ((x * y) % 3) === 0,
        (x, y) => (((x * y) % 2) + ((x * y) % 3)) % 2 === 0, (x, y) => (((x + y) % 2) + ((x * y) % 3)) % 2 === 0,
    ];

    function parseSegments(bytes, ver) {
        let pos = 0;
        const total = bytes.length * 8;
        const read = (n) => { let v = 0; for (let i = 0; i < n; i++, pos++) { if (pos >= total) return null; v = (v << 1) | ((bytes[pos >> 3] >> (7 - (pos & 7))) & 1); } return v; };
        const ALNUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:";
        let out = [];
        while (pos + 4 <= total) {
            const mode = read(4);
            if (mode === 0 || mode === null) break;
            if (mode === 4) {
                const n = read(ver < 10 ? 8 : 16); if (n === null) return null;
                for (let i = 0; i < n; i++) { const b = read(8); if (b === null) return null; out.push(b); }
            } else if (mode === 2) {
                const n = read(ver < 10 ? 9 : ver < 27 ? 11 : 13); if (n === null) return null;
                let s = "";
                for (let i = 0; i + 1 < n; i += 2) { const v = read(11); if (v === null) return null; s += ALNUM[Math.floor(v / 45)] + ALNUM[v % 45]; }
                if (n % 2) { const v = read(6); if (v === null) return null; s += ALNUM[v]; }
                out.push(...new TextEncoder().encode(s));
            } else if (mode === 1) {
                const n = read(ver < 10 ? 10 : ver < 27 ? 12 : 14); if (n === null) return null;
                let s = "";
                for (let i = 0; i < n; i += 3) { const k = Math.min(3, n - i), v = read(k === 3 ? 10 : k === 2 ? 7 : 4); if (v === null) return null; s += String(v).padStart(k, "0"); }
                out.push(...new TextEncoder().encode(s));
            } else if (mode === 7) {
                const f = read(8); if (f === null) return null; if (f & 0x80) read(8);
            } else return null;
        }
        try { return new TextDecoder("utf-8", { fatal: false }).decode(new Uint8Array(out)); } catch (_) { return null; }
    }

    function decodeMatrix(m, size) {
        if ((size - 17) % 4 !== 0 || size < 21 || size > 177) return null;
        const ver = (size - 17) / 4;
        const get = (x, y) => m[y][x] ? 1 : 0;
        const f = readFormat(get, size); if (!f) return null;
        const e = ECL_IDX[f.ecl], maskFn = MASKS[f.mask];
        const fn = functionMap(size, ver);
        // bits em zigue-zague (igual ao codificador), já sem a máscara
        const raw = Math.floor(T.rawDataModules(ver) / 8);
        const cw = new Array(raw).fill(0); let k = 0;
        for (let right = size - 1; right >= 1; right -= 2) {
            if (right === 6) right = 5;
            for (let vert = 0; vert < size; vert++) for (let j = 0; j < 2; j++) {
                const x = right - j, up = ((right + 1) & 2) === 0, y = up ? size - 1 - vert : vert;
                if (fn[y][x] || k >= raw * 8) continue;
                let bit = get(x, y); if (maskFn(x, y)) bit ^= 1;
                cw[k >>> 3] |= bit << (7 - (k & 7)); k++;
            }
        }
        // desentrelaçar os blocos e corrigir cada um
        const nb = T.NUM_BLOCKS[e][ver], eccLen = T.ECC_PER_BLOCK[e][ver];
        const shortCount = nb - (raw % nb), shortLen = Math.floor(raw / nb);
        const dataLens = []; for (let i = 0; i < nb; i++) dataLens.push(shortLen - eccLen + (i < shortCount ? 0 : 1));
        const blocks = dataLens.map(() => []); let p = 0;
        const maxData = Math.max(...dataLens);
        for (let i = 0; i < maxData; i++) for (let j = 0; j < nb; j++) if (i < dataLens[j]) blocks[j].push(cw[p++]);
        for (let i = 0; i < eccLen; i++) for (let j = 0; j < nb; j++) blocks[j].push(cw[p++]);
        let data = [];
        for (let j = 0; j < nb; j++) { const fixed = rsCorrect(blocks[j], eccLen); if (!fixed) return null; data = data.concat(fixed); }
        return parseSegments(data, ver);
    }

    // ---------- Imagem → grelha ----------
    function otsu(gray) {
        const hist = new Array(256).fill(0); for (let i = 0; i < gray.length; i++) hist[gray[i]]++;
        let sum = 0; for (let i = 0; i < 256; i++) sum += i * hist[i];
        let sumB = 0, wB = 0, best = 0, th = 128; const tot = gray.length;
        for (let t = 0; t < 256; t++) {
            wB += hist[t]; if (!wB) continue; const wF = tot - wB; if (!wF) break;
            sumB += t * hist[t]; const mB = sumB / wB, mF = (sum - sumB) / wF, v = wB * wF * (mB - mF) * (mB - mF);
            if (v > best) { best = v; th = t; }
        }
        return th;
    }
    function binarize(gray, w, h, mode) {
        const bin = new Uint8Array(w * h);
        if (mode === 0) { const th = otsu(gray); for (let i = 0; i < bin.length; i++) bin[i] = gray[i] <= th ? 1 : 0; return bin; }
        const win = Math.max(15, (Math.round(Math.max(w, h) / 8) | 1)), r = win >> 1;
        const I = new Float64Array((w + 1) * (h + 1));
        for (let y = 0; y < h; y++) { let row = 0; for (let x = 0; x < w; x++) { row += gray[y * w + x]; I[(y + 1) * (w + 1) + x + 1] = I[y * (w + 1) + x + 1] + row; } }
        for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
            const x0 = Math.max(0, x - r), x1 = Math.min(w, x + r + 1), y0 = Math.max(0, y - r), y1 = Math.min(h, y + r + 1);
            const s = I[y1 * (w + 1) + x1] - I[y0 * (w + 1) + x1] - I[y1 * (w + 1) + x0] + I[y0 * (w + 1) + x0];
            bin[y * w + x] = gray[y * w + x] < (s / ((x1 - x0) * (y1 - y0))) * 0.9 ? 1 : 0;
        }
        return bin;
    }

    function ratioOk(c) {
        const tot = c[0] + c[1] + c[2] + c[3] + c[4]; if (tot < 7) return 0;
        const ms = tot / 7, tol = ms * 0.65;
        return (Math.abs(c[0] - ms) < tol && Math.abs(c[1] - ms) < tol && Math.abs(c[2] - 3 * ms) < 3 * tol &&
                Math.abs(c[3] - ms) < tol && Math.abs(c[4] - ms) < tol) ? ms : 0;
    }
    // confirma o padrão 1:1:3:1:1 na linha/coluna que passa por (x,y); devolve {center, ms} ou null
    function crossCheck(bin, w, h, x, y, dx, dy) {
        const at = (i) => bin[(y + dy * i) * w + (x + dx * i)];
        const inb = (i) => { const xx = x + dx * i, yy = y + dy * i; return xx >= 0 && yy >= 0 && xx < w && yy < h; };
        const c = [0, 0, 0, 0, 0];
        let i = 0;
        while (inb(i) && at(i)) { c[2]++; i--; } if (!inb(i)) return null;
        while (inb(i) && !at(i)) { c[1]++; i--; } if (!inb(i)) return null;
        while (inb(i) && at(i)) { c[0]++; i--; }
        let j = 1;
        while (inb(j) && at(j)) { c[2]++; j++; } if (!inb(j)) return null;
        while (inb(j) && !at(j)) { c[3]++; j++; } if (!inb(j)) return null;
        while (inb(j) && at(j)) { c[4]++; j++; }
        const ms = ratioOk(c); if (!ms) return null;
        return { center: j - c[4] - c[3] - c[2] / 2, ms };
    }
    function findFinders(bin, w, h) {
        const clusters = [];
        for (let y = 0; y < h; y++) {
            const runs = []; let cur = bin[y * w], len = 0, start = 0;
            for (let x = 0; x < w; x++) {
                if (bin[y * w + x] === cur) len++; else { runs.push([cur, len, start]); cur = bin[y * w + x]; len = 1; start = x; }
            }
            runs.push([cur, len, start]);
            for (let k = 0; k + 4 < runs.length; k++) {
                if (runs[k][0] !== 1) continue;
                const ms = ratioOk([runs[k][1], runs[k + 1][1], runs[k + 2][1], runs[k + 3][1], runs[k + 4][1]]); if (!ms) continue;
                const cx = Math.round(runs[k + 2][2] + runs[k + 2][1] / 2);
                const v = crossCheck(bin, w, h, cx, y, 0, 1); if (!v) continue;
                const cy = Math.round(y + v.center);
                const hz = crossCheck(bin, w, h, cx, cy, 1, 0); if (!hz) continue;
                const fx = cx + hz.center, fy = cy, fms = (ms + v.ms + hz.ms) / 3;
                let c = clusters.find(c => Math.hypot(c.x - fx, c.y - fy) < Math.max(c.ms, fms) * 4);
                if (c) { c.x = (c.x * c.n + fx) / (c.n + 1); c.y = (c.y * c.n + fy) / (c.n + 1); c.ms = (c.ms * c.n + fms) / (c.n + 1); c.n++; }
                else clusters.push({ x: fx, y: fy, ms: fms, n: 1 });
            }
        }
        return clusters.filter(c => c.n >= 2).sort((a, b) => b.n - a.n).slice(0, 9);
    }
    function pickTriples(cl) {
        const out = [];
        for (let i = 0; i < cl.length; i++) for (let j = i + 1; j < cl.length; j++) for (let k = j + 1; k < cl.length; k++) {
            const P = [cl[i], cl[j], cl[k]];
            const d = [Math.hypot(P[1].x - P[2].x, P[1].y - P[2].y), Math.hypot(P[0].x - P[2].x, P[0].y - P[2].y), Math.hypot(P[0].x - P[1].x, P[0].y - P[1].y)];
            const hi = d.indexOf(Math.max(...d)); const a = d[(hi + 1) % 3], b = d[(hi + 2) % 3], c = d[hi];
            const score = Math.abs(a - b) / ((a + b) / 2) + Math.abs(c * c - a * a - b * b) / (c * c) +
                          Math.abs(P[0].ms - P[1].ms) / P[0].ms * 0.5 + Math.abs(P[1].ms - P[2].ms) / P[1].ms * 0.5;
            if (score < 0.5) out.push({ score, tl: P[hi], o: [P[(hi + 1) % 3], P[(hi + 2) % 3]] });
        }
        return out.sort((x, y) => x.score - y.score).slice(0, 4);
    }

    function sampleAndDecode(bin, w, h, tl, tr, bl, ms) {
        const dTR = Math.hypot(tr.x - tl.x, tr.y - tl.y), dBL = Math.hypot(bl.x - tl.x, bl.y - tl.y);
        const est = ((dTR + dBL) / 2) / ms + 7;
        const base = Math.round((est - 17) / 4) * 4 + 17;
        for (const size of [base, base - 4, base + 4]) {
            if (size < 21 || size > 177) continue;
            const span = size - 7;
            const ux = (tr.x - tl.x) / span, uy = (tr.y - tl.y) / span, vx = (bl.x - tl.x) / span, vy = (bl.y - tl.y) / span;
            const m = Array.from({ length: size }, () => new Array(size).fill(false));
            let ok = true;
            for (let y = 0; y < size && ok; y++) for (let x = 0; x < size; x++) {
                const u = x + 0.5 - 3.5, v = y + 0.5 - 3.5;
                let dark = 0;
                for (const [ou, ov] of [[0, 0], [0.2, 0], [-0.2, 0], [0, 0.2], [0, -0.2]]) {
                    const px = Math.round(tl.x + (u + ou) * ux + (v + ov) * vx), py = Math.round(tl.y + (u + ou) * uy + (v + ov) * vy);
                    if (px < 0 || py < 0 || px >= w || py >= h) { ok = false; break; }
                    dark += bin[py * w + px];
                }
                if (!ok) break;
                m[y][x] = dark >= 3;
            }
            if (!ok) continue;
            const t = decodeMatrix(m, size); if (t) return t;
        }
        return null;
    }

    function decodeBin(bin, w, h) {
        const cl = findFinders(bin, w, h); if (cl.length < 3) return null;
        for (const t of pickTriples(cl)) {
            let [a, b] = t.o;
            const cross = (a.x - t.tl.x) * (b.y - t.tl.y) - (a.y - t.tl.y) * (b.x - t.tl.x);
            const tr = cross > 0 ? a : b, bl = cross > 0 ? b : a;
            const r = sampleAndDecode(bin, w, h, t.tl, tr, bl, (t.tl.ms + tr.ms + bl.ms) / 3);
            if (r) return r;
        }
        return null;
    }

    // gray: Uint8Array w*h  →  texto ou ""
    function decode(gray, w, h) {
        for (const mode of [0, 1]) {
            const bin = binarize(gray, w, h, mode);
            let r = decodeBin(bin, w, h); if (r) return r;
            for (let i = 0; i < bin.length; i++) bin[i] ^= 1;        // QR claro sobre fundo escuro
            r = decodeBin(bin, w, h); if (r) return r;
        }
        return "";
    }
    // RGBA (ImageData) → texto ou ""
    function decodeRGBA(rgba, w, h) {
        const gray = new Uint8Array(w * h);
        for (let i = 0, j = 0; i < gray.length; i++, j += 4) gray[i] = (rgba[j] * 77 + rgba[j + 1] * 151 + rgba[j + 2] * 28) >> 8;
        return decode(gray, w, h);
    }
    return { decode, decodeRGBA };
})();
window.QrDecoder = QrDecoder;
