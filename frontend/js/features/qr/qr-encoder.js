/**
 * Gerador de código QR (ISO 18004) — local, sem dependências e sem pedidos à rede.
 * Modo byte (UTF-8), versões 1–40, correcção de erros L/M/Q/H, máscara automática.
 * Uso:  const qr = QrEncoder.encode("texto", "M");  qr.size, qr.modules[y][x]
 */
const QrEncoder = (() => {
    const ECC_PER_BLOCK = [
        [-1, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28, 28, 28, 30, 30, 26, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30],
        [-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28],
        [-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30, 28, 30, 30, 30, 30, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30],
        [-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28, 30, 24, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30],
    ];
    const NUM_BLOCKS = [
        [-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8, 8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25],
        [-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49],
        [-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 8, 10, 12, 16, 12, 17, 16, 18, 21, 20, 23, 23, 25, 27, 29, 34, 34, 35, 38, 40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68],
        [-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25, 25, 34, 30, 32, 35, 37, 40, 42, 45, 48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81],
    ];
    const ECL_INDEX = { L: 0, M: 1, Q: 2, H: 3 };
    const ECL_FORMAT = { L: 1, M: 0, Q: 3, H: 2 };

    const bit = (x, i) => ((x >>> i) & 1) !== 0;

    function rawDataModules(ver) {
        let r = (16 * ver + 128) * ver + 64;
        if (ver >= 2) {
            const na = Math.floor(ver / 7) + 2;
            r -= (25 * na - 10) * na - 55;
            if (ver >= 7) r -= 36;
        }
        return r;
    }
    const dataCodewords = (ver, e) => Math.floor(rawDataModules(ver) / 8) - ECC_PER_BLOCK[e][ver] * NUM_BLOCKS[e][ver];

    // ----- Reed-Solomon sobre GF(256) -----
    function gfMul(x, y) {
        let z = 0;
        for (let i = 7; i >= 0; i--) { z = (z << 1) ^ ((z >>> 7) * 0x11D); z ^= ((y >>> i) & 1) * x; }
        return z;
    }
    function rsDivisor(degree) {
        const res = new Array(degree).fill(0); res[degree - 1] = 1;
        let root = 1;
        for (let i = 0; i < degree; i++) {
            for (let j = 0; j < res.length; j++) { res[j] = gfMul(res[j], root); if (j + 1 < res.length) res[j] ^= res[j + 1]; }
            root = gfMul(root, 0x02);
        }
        return res;
    }
    function rsRemainder(data, divisor) {
        const res = divisor.map(() => 0);
        for (const b of data) {
            const factor = b ^ res.shift(); res.push(0);
            divisor.forEach((coef, i) => { res[i] ^= gfMul(coef, factor); });
        }
        return res;
    }

    function interleave(data, ver, e) {
        const nb = NUM_BLOCKS[e][ver], eccLen = ECC_PER_BLOCK[e][ver];
        const raw = Math.floor(rawDataModules(ver) / 8);
        const shortCount = nb - (raw % nb), shortLen = Math.floor(raw / nb);
        const blocks = [], div = rsDivisor(eccLen);
        for (let i = 0, k = 0; i < nb; i++) {
            const dat = data.slice(k, k + shortLen - eccLen + (i < shortCount ? 0 : 1)); k += dat.length;
            const ecc = rsRemainder(dat, div);
            if (i < shortCount) dat.push(0);
            blocks.push(dat.concat(ecc));
        }
        const out = [];
        for (let i = 0; i < blocks[0].length; i++)
            blocks.forEach((blk, j) => { if (i !== shortLen - eccLen || j >= shortCount) out.push(blk[i]); });
        return out;
    }

    function encode(text, eclName = "M") {
        const e = ECL_INDEX[eclName];
        const bytes = Array.from(new TextEncoder().encode(text));
        let ver = 1, used = 0;
        for (; ; ver++) {
            if (ver > 40) throw new RangeError("Texto demasiado longo para um código QR");
            used = 4 + (ver < 10 ? 8 : 16) + bytes.length * 8;
            if (used <= dataCodewords(ver, e) * 8) break;
        }
        // ----- bits de dados -----
        const bits = [];
        const push = (val, len) => { for (let i = len - 1; i >= 0; i--) bits.push((val >>> i) & 1); };
        push(0x4, 4); push(bytes.length, ver < 10 ? 8 : 16); bytes.forEach(b => push(b, 8));
        const cap = dataCodewords(ver, e) * 8;
        push(0, Math.min(4, cap - bits.length));
        push(0, (8 - (bits.length % 8)) % 8);
        for (let pad = 0xEC; bits.length < cap; pad ^= 0xEC ^ 0x11) push(pad, 8);
        const data = new Array(bits.length / 8).fill(0);
        bits.forEach((b, i) => { data[i >>> 3] |= b << (7 - (i & 7)); });
        const codewords = interleave(data, ver, e);

        // ----- matriz -----
        const size = ver * 4 + 17;
        const modules = Array.from({ length: size }, () => new Array(size).fill(false));
        const isFn = Array.from({ length: size }, () => new Array(size).fill(false));
        const setFn = (x, y, dark) => { modules[y][x] = dark; isFn[y][x] = true; };

        function drawFormat(mask) {
            const d = (ECL_FORMAT[eclName] << 3) | mask;
            let rem = d;
            for (let i = 0; i < 10; i++) rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
            const f = ((d << 10) | rem) ^ 0x5412;
            for (let i = 0; i <= 5; i++) setFn(8, i, bit(f, i));
            setFn(8, 7, bit(f, 6)); setFn(8, 8, bit(f, 7)); setFn(7, 8, bit(f, 8));
            for (let i = 9; i < 15; i++) setFn(14 - i, 8, bit(f, i));
            for (let i = 0; i < 8; i++) setFn(size - 1 - i, 8, bit(f, i));
            for (let i = 8; i < 15; i++) setFn(8, size - 15 + i, bit(f, i));
            setFn(8, size - 8, true);
        }
        function drawFinder(cx, cy) {
            for (let dy = -4; dy <= 4; dy++) for (let dx = -4; dx <= 4; dx++) {
                const dist = Math.max(Math.abs(dx), Math.abs(dy)), x = cx + dx, y = cy + dy;
                if (x >= 0 && x < size && y >= 0 && y < size) setFn(x, y, dist !== 2 && dist !== 4);
            }
        }
        function drawAlign(cx, cy) {
            for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++)
                setFn(cx + dx, cy + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
        }
        for (let i = 0; i < size; i++) { setFn(6, i, i % 2 === 0); setFn(i, 6, i % 2 === 0); }
        drawFinder(3, 3); drawFinder(size - 4, 3); drawFinder(3, size - 4);
        if (ver > 1) {
            const na = Math.floor(ver / 7) + 2;
            const step = ver === 32 ? 26 : Math.ceil((ver * 4 + 4) / (na * 2 - 2)) * 2;
            const pos = [6];
            for (let p = size - 7; pos.length < na; p -= step) pos.splice(1, 0, p);
            for (let i = 0; i < na; i++) for (let j = 0; j < na; j++)
                if (!((i === 0 && j === 0) || (i === 0 && j === na - 1) || (i === na - 1 && j === 0))) drawAlign(pos[i], pos[j]);
        }
        drawFormat(0);
        if (ver >= 7) {
            let rem = ver;
            for (let i = 0; i < 12; i++) rem = (rem << 1) ^ ((rem >>> 11) * 0x1F25);
            const v = (ver << 12) | rem;
            for (let i = 0; i < 18; i++) { const a = size - 11 + (i % 3), b = Math.floor(i / 3); setFn(a, b, bit(v, i)); setFn(b, a, bit(v, i)); }
        }
        // codewords em zigue-zague
        let k = 0;
        for (let right = size - 1; right >= 1; right -= 2) {
            if (right === 6) right = 5;
            for (let vert = 0; vert < size; vert++) for (let j = 0; j < 2; j++) {
                const x = right - j, up = ((right + 1) & 2) === 0, y = up ? size - 1 - vert : vert;
                if (!isFn[y][x] && k < codewords.length * 8) { modules[y][x] = bit(codewords[k >>> 3], 7 - (k & 7)); k++; }
            }
        }
        const applyMask = (m) => {
            for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
                let inv;
                switch (m) {
                    case 0: inv = (x + y) % 2 === 0; break;
                    case 1: inv = y % 2 === 0; break;
                    case 2: inv = x % 3 === 0; break;
                    case 3: inv = (x + y) % 3 === 0; break;
                    case 4: inv = (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0; break;
                    case 5: inv = ((x * y) % 2) + ((x * y) % 3) === 0; break;
                    case 6: inv = (((x * y) % 2) + ((x * y) % 3)) % 2 === 0; break;
                    default: inv = (((x + y) % 2) + ((x * y) % 3)) % 2 === 0;
                }
                if (!isFn[y][x] && inv) modules[y][x] = !modules[y][x];
            }
        };
        const penalty = () => {
            let p = 0, dark = 0;
            const line = (get) => {
                for (let a = 0; a < size; a++) {
                    let run = 1;
                    for (let b = 1; b < size; b++) {
                        if (get(a, b) === get(a, b - 1)) { run++; if (run === 5) p += 3; else if (run > 5) p++; } else run = 1;
                    }
                    for (let b = 0; b + 10 < size; b++) { // padrão tipo "finder" 1:1:3:1:1
                        const s = []; for (let t = 0; t < 11; t++) s.push(get(a, b + t) ? 1 : 0);
                        const str = s.join("");
                        if (str === "10111010000" || str === "00001011101") p += 40;
                    }
                }
            };
            line((a, b) => modules[a][b]); line((a, b) => modules[b][a]);
            for (let y = 0; y < size - 1; y++) for (let x = 0; x < size - 1; x++) {
                const c = modules[y][x]; if (c === modules[y][x + 1] && c === modules[y + 1][x] && c === modules[y + 1][x + 1]) p += 3;
            }
            modules.forEach(r => r.forEach(c => { if (c) dark++; }));
            p += Math.floor(Math.abs(dark * 20 - size * size * 10) / (size * size)) * 10;
            return p;
        };
        let best = 0, bestP = Infinity;
        for (let m = 0; m < 8; m++) {
            applyMask(m); drawFormat(m);
            const p = penalty(); if (p < bestP) { best = m; bestP = p; }
            applyMask(m);
        }
        applyMask(best); drawFormat(best);
        return { size, version: ver, modules, isFunction: isFn };
    }
    return { encode };
})();
window.QrEncoder = QrEncoder;
