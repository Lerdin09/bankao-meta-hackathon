import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Read original edjair.html to get line 109 (base64 assets)
with open('edjair.html', 'r', encoding='utf-8') as f:
    orig_lines = f.readlines()

# Line 109 (0-indexed 108) contains WA_SRC and VF_SRC
line_assets = orig_lines[108].strip()
assert 'WA_SRC' in line_assets and 'VF_SRC' in line_assets, "Assets line missing!"

print(f"Extracted assets line: length = {len(line_assets)}")

# Now construct the enhanced edjair.html
html_content = '''<!DOCTYPE html>
<html lang="pt-BR">

<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Vídeo Vodafone Portugal — 5G & Fibra</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,700;1,900&display=swap" rel="stylesheet">
    <style>
        * {
            box-sizing: border-box;
            user-select: none;
            -webkit-user-select: none;
        }

        html,
        body {
            margin: 0;
            padding: 0;
            height: 100%;
            background: #090a0d;
            color: #fff;
            font-family: 'Poppins', system-ui, -apple-system, sans-serif;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        #c {
            flex: 1 1 auto;
            min-height: 0;
            max-width: 100vw;
            aspect-ratio: 9/16;
            height: auto;
            background: #000;
            box-shadow: 0 16px 48px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            margin-top: 6px;
        }

        #bar {
            width: 100%;
            max-width: 1080px;
            height: 5px;
            background: rgba(255, 255, 255, 0.12);
            position: relative;
            border-radius: 999px;
            overflow: hidden;
            margin-top: 6px;
        }

        #bar i {
            display: block;
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, #e60000, #ff4d4d);
            box-shadow: 0 0 12px #e60000;
            transition: width 0.05s linear;
        }

        #ui {
            flex: 0 0 auto;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            justify-content: center;
            align-items: center;
            padding: 12px 18px 16px;
            font-size: 14px;
            width: 100%;
            max-width: 900px;
        }

        button,
        select {
            padding: 10px 22px;
            font-size: 14px;
            font-weight: 600;
            font-family: inherit;
            border-radius: 999px;
            border: 1px solid rgba(230, 0, 0, 0.5);
            background: #18191d;
            color: #fff;
            cursor: pointer;
            outline: none;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        button:hover:not(:disabled),
        select:hover:not(:disabled) {
            background: #25262c;
            border-color: #e60000;
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(230, 0, 0, 0.25);
        }

        #play {
            border-color: rgba(255, 255, 255, 0.2);
            background: #202126;
        }

        #play:hover:not(:disabled) {
            border-color: #fff;
            background: #2d2e35;
        }

        #rec {
            background: linear-gradient(135deg, #e60000, #b80000);
            border-color: transparent;
            box-shadow: 0 4px 16px rgba(230, 0, 0, 0.4);
        }

        #rec:hover:not(:disabled) {
            background: linear-gradient(135deg, #ff1a1a, #cc0000);
            box-shadow: 0 6px 22px rgba(230, 0, 0, 0.6);
        }

        button:disabled,
        select:disabled {
            opacity: 0.45;
            cursor: not-allowed;
            transform: none !important;
            box-shadow: none !important;
        }

        #msg {
            width: 100%;
            text-align: center;
            color: rgba(255, 255, 255, 0.7);
            font-size: 13px;
            min-height: 1.3em;
            margin-top: 2px;
            letter-spacing: 0.2px;
        }

        #msg a {
            color: #ff5252;
            text-decoration: underline;
        }
    </style>
</head>

<body>
    <canvas id="c" width="1080" height="1920"></canvas>
    <div id="bar"><i></i></div>
    <div id="ui">
        <button id="play">▶ Assistir Vídeo</button>
        <select id="q">
            <option value="1">1080×1920 (Full HD • Alta Fidelidade)</option>
            <option value="0.667" selected>720×1280 (HD • Equilibrado)</option>
            <option value="0.5">540×960 (Leve • Rápido)</option>
        </select>
        <button id="rec">⬇ Exportar MP4 (Alta Qualidade)</button>
        <div id="msg">“Assistir Vídeo” toca a prévia em tempo real com áudio imersivo. “Exportar MP4” codifica em 60 FPS com efeitos sonoros completos.</div>
    </div>
    <script>
        (() => {
            const WHATSAPP = '';            // ex.: '+351 910 000 000'
''' + f"            {line_assets}\n" + '''            const W = 1080, H = 1920, FPS = 60, DURATION = 40;
            const TL = [0, 3, 9, 15, 19.4, 25.4, 30.8, 36.8, 40];
            const RED = '#e60000', DARK_RED = '#990000', NEON_RED = '#ff2b2b', INK = '#111114', GREY = '#7b7b85', GREEN = '#25d366', BLUE = '#0066cc', GOLD = '#ffb300';
            const FONT = 'Poppins, "Segoe UI", system-ui, sans-serif';

            const canvas = document.getElementById('c');
            const mainCtx = canvas.getContext('2d', { alpha: false });
            let ctx = mainCtx;
            const $ = id => document.getElementById(id);
            const HASF = 'filter' in mainCtx;

            // ---------- Funções Matemáticas e de Interpolação Fluida ----------
            const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
            const lerp = (a, b, t) => a + (b - a) * clamp(t);
            const eo = t => 1 - Math.pow(1 - clamp(t), 3.5);
            const ei = t => Math.pow(clamp(t), 3.5);
            const eio = t => { t = clamp(t); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
            const back = (t, s = 1.6) => { t = clamp(t); return 1 + (s + 1) * Math.pow(t - 1, 3) + s * Math.pow(t - 1, 2); };
            const elastic = t => t <= 0 ? 0 : t >= 1 ? 1 : Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * (2 * Math.PI / 3)) + 1;
            const spring = (t, w = 9, d = 7) => t <= 0 ? 0 : t >= 1 ? 1 : 1 - Math.exp(-d * t) * Math.cos(w * t);

            const mk = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };
            const img = s => { const i = new Image(); i.src = s; return i; };
            const waImg = img(WA_SRC), vfImg = img(VF_SRC);

            // Texturas pré-renderizadas para alta performance
            const fog = mk(300, 300);
            {
                const g = fog.getContext('2d'), r = g.createRadialGradient(150, 150, 0, 150, 150, 150);
                r.addColorStop(0, 'rgba(230,0,0,0.65)');
                r.addColorStop(0.5, 'rgba(230,0,0,0.25)');
                r.addColorStop(1, 'rgba(230,0,0,0)');
                g.fillStyle = r; g.fillRect(0, 0, 300, 300);
            }

            // ---------- Utilitários Gráficos de Alta Definição ----------
            function rr(x, y, w, h, r) {
                ctx.beginPath();
                ctx.moveTo(x + r, y);
                ctx.arcTo(x + w, y, x + w, y + h, r);
                ctx.arcTo(x + w, y + h, x, y + h, r);
                ctx.arcTo(x, y + h, x, y, r);
                ctx.arcTo(x, y, x + w, y, r);
                ctx.closePath();
            }

            function T(s, x, y, size, o = {}) {
                const {
                    c = INK, a = 1, sc = 1, w = 700, al = 'center',
                    maxW = W * 0.88, blur = 0, dy = 0, dx = 0, shadow = false
                } = o;
                if (a <= 0) return;
                ctx.save();
                ctx.globalAlpha *= clamp(a);
                ctx.translate(x + dx, y + dy);
                ctx.scale(sc, sc);
                ctx.font = `${w} ${size}px ${FONT}`;
                const m = ctx.measureText(s).width;
                if (m > maxW) ctx.font = `${w} ${Math.max(12, size * maxW / m)}px ${FONT}`;
                if (blur > 0.4 && HASF) ctx.filter = `blur(${blur}px)`;
                if (shadow) {
                    ctx.shadowColor = 'rgba(0,0,0,0.35)';
                    ctx.shadowBlur = 14;
                    ctx.shadowOffsetY = 4;
                }
                ctx.fillStyle = c;
                ctx.textAlign = al;
                ctx.textBaseline = 'middle';
                ctx.fillText(s, 0, 0);
                ctx.restore();
            }

            function rings(cx, cy, u, col, a = 0.35, n = 3, maxR = 900) {
                ctx.save();
                ctx.strokeStyle = col;
                ctx.lineWidth = 3.5;
                for (let k = 0; k < n; k++) {
                    const p = (u * 0.45 + k / n) % 1;
                    ctx.globalAlpha = Math.max(0, (1 - p) * a);
                    ctx.beginPath();
                    ctx.arc(cx, cy, 60 + p * maxR, 0, Math.PI * 2);
                    ctx.stroke();
                }
                ctx.restore();
            }

            function glowCircle(cx, cy, r, color, blur = 20) {
                ctx.save();
                ctx.shadowColor = color;
                ctx.shadowBlur = blur;
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(cx, cy, r, 0, Math.PI * 2);
                ctx.fill();
                ctx.restore();
            }

            const ic = {
                wifi(r, c, weak = false) {
                    ctx.save();
                    ctx.strokeStyle = c; ctx.fillStyle = c; ctx.lineWidth = r * 0.17; ctx.lineCap = 'round';
                    [1, 0.68, 0.36].forEach((k, i) => {
                        const f = (weak && i < 2) ? 0.25 : 1;
                        ctx.globalAlpha *= f;
                        ctx.beginPath();
                        ctx.arc(0, r * 0.55, r * 1.15 * k, Math.PI * 1.22, Math.PI * 1.78);
                        ctx.stroke();
                        ctx.globalAlpha /= f;
                    });
                    ctx.beginPath(); ctx.arc(0, r * 0.55, r * 0.11, 0, Math.PI * 2); ctx.fill();
                    ctx.restore();
                },
                spin(r, c, u) {
                    ctx.save();
                    ctx.strokeStyle = c; ctx.lineWidth = r * 0.2; ctx.lineCap = 'round';
                    ctx.beginPath(); ctx.arc(0, 0, r * 0.85, u * 7, u * 7 + 4.2); ctx.stroke();
                    ctx.restore();
                },
                bolt(r, c) {
                    ctx.save();
                    ctx.fillStyle = c;
                    ctx.beginPath();
                    ctx.moveTo(r * 0.2, -r);
                    ctx.lineTo(-r * 0.55, r * 0.12);
                    ctx.lineTo(-r * 0.05, r * 0.12);
                    ctx.lineTo(-r * 0.25, r);
                    ctx.lineTo(r * 0.55, -r * 0.2);
                    ctx.lineTo(r * 0.05, -r * 0.2);
                    ctx.closePath();
                    ctx.fill();
                    ctx.restore();
                },
                tv(r, c) {
                    ctx.save();
                    ctx.strokeStyle = c; ctx.lineWidth = r * 0.16; ctx.lineCap = 'round';
                    rr(-r, -r * 0.7, r * 2, r * 1.4, r * 0.25); ctx.stroke();
                    ctx.beginPath(); ctx.moveTo(-r * 0.5, r * 0.98); ctx.lineTo(r * 0.5, r * 0.98); ctx.stroke();
                    ctx.restore();
                },
                check(r, c) {
                    ctx.save();
                    ctx.strokeStyle = c; ctx.lineWidth = r * 0.24; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
                    ctx.beginPath();
                    ctx.moveTo(-r * 0.5, 0);
                    ctx.lineTo(-r * 0.12, r * 0.42);
                    ctx.lineTo(r * 0.55, -r * 0.45);
                    ctx.stroke();
                    ctx.restore();
                }
            };

            function logo(x, y, size, a = 1, rot = 0, scale = 1) {
                if (!vfImg.complete) return;
                ctx.save();
                ctx.globalAlpha *= a;
                ctx.translate(x, y);
                ctx.scale(scale, scale);
                ctx.rotate(rot);
                ctx.drawImage(vfImg, -size / 2, -size / 2, size, size);
                ctx.restore();
            }

            function wa(x, y, size, a = 1) {
                if (!waImg.complete) return;
                ctx.save();
                ctx.globalAlpha *= a;
                ctx.translate(x, y);
                rr(-size / 2, -size / 2, size, size, size * 0.23);
                ctx.clip();
                ctx.drawImage(waImg, -size / 2, -size / 2, size, size);
                ctx.restore();
            }

            // Card com sombra suave pre-renderizada
            const cardC = {};
            function card(x, y, w, h, r = 44, fill = '#ffffff') {
                const k = `${w}x${h}x${r}`;
                let c = cardC[k];
                if (!c) {
                    c = cardC[k] = mk(w + 160, h + 180);
                    const g = c.getContext('2d'), pc = ctx;
                    g.shadowColor = 'rgba(0,0,0,0.12)';
                    g.shadowBlur = 40;
                    g.shadowOffsetY = 16;
                    g.fillStyle = '#fff';
                    ctx = g;
                    rr(80, 70, w, h, r);
                    ctx = pc;
                    g.fill();
                }
                ctx.drawImage(c, x - w / 2 - 80, y - h / 2 - 70);
                if (fill !== '#ffffff') {
                    ctx.save();
                    ctx.fillStyle = fill;
                    rr(x - w / 2, y - h / 2, w, h, r);
                    ctx.fill();
                    ctx.restore();
                }
            }

            const STG = { x: 90, y: 340, w: 900, h: 1120 };
            const bg = c => { ctx.fillStyle = c; ctx.fillRect(0, 0, W, H); };
            const dot = (x, y, r, c) => { ctx.fillStyle = c; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); };

            function words(arr, y, size, u, t0, o = {}) {
                const w = o.w || 800, gap = size * 0.28;
                ctx.font = `${w} ${size}px ${FONT}`;
                const ws = arr.map(a => ctx.measureText(a[0]).width);
                const tot = ws.reduce((a, b) => a + b, 0) + gap * (arr.length - 1);
                const k = Math.min(1, (W * 0.88) / tot);
                let x = W / 2 - tot * k / 2;

                arr.forEach((a, i) => {
                    const q = spring(clamp((u - t0 - i * (o.st || 0.12)) / 0.85));
                    const ex = o.out ? eio((u - o.out) / 0.45) : 0;
                    T(a[0], x, y, size * k, {
                        c: a[1] || INK, w, al: 'left',
                        a: q * (1 - ex),
                        blur: 16 * (1 - q) + 20 * ex,
                        dy: 46 * (1 - q),
                        maxW: 1e5
                    });
                    x += (ws[i] + gap) * k;
                });
            }

            function grid(u, col = 'rgba(255,255,255,0.04)') {
                ctx.save();
                ctx.strokeStyle = col;
                ctx.lineWidth = 2;
                ctx.beginPath();
                const off = (u * 35) % 90;
                for (let x = off; x < W; x += 90) { ctx.moveTo(x, 0); ctx.lineTo(x, H); }
                for (let y = off; y < H; y += 90) { ctx.moveTo(0, y); ctx.lineTo(W, y); }
                ctx.stroke();
                ctx.restore();
            }

            function particles(u, count = 28, col = 'rgba(230,0,0,0.35)') {
                ctx.save();
                for (let i = 0; i < count; i++) {
                    const seed = i * 137.5;
                    const x = ((Math.sin(seed + u * 0.3) * 0.5 + 0.5) * W);
                    const y = ((Math.cos(seed * 1.3 - u * 0.2) * 0.5 + 0.5) * H);
                    const sz = 2 + (Math.sin(u * 3 + seed) * 0.5 + 0.5) * 4;
                    const a = 0.2 + (Math.cos(u * 2 + seed) * 0.5 + 0.5) * 0.5;
                    ctx.fillStyle = col;
                    ctx.globalAlpha = a;
                    ctx.beginPath();
                    ctx.arc(x, y, sz, 0, Math.PI * 2);
                    ctx.fill();
                }
                ctx.restore();
            }

            // Speedometer gauge component
            function drawSpeedGauge(cx, cy, radius, val, maxVal, unit = 'Mbps') {
                ctx.save();
                ctx.translate(cx, cy);
                // Background arc
                ctx.lineWidth = 24;
                ctx.lineCap = 'round';
                ctx.strokeStyle = 'rgba(230,0,0,0.12)';
                ctx.beginPath();
                ctx.arc(0, 0, radius, Math.PI * 0.8, Math.PI * 2.2);
                ctx.stroke();

                // Active arc with glow
                const p = clamp(val / maxVal);
                const endAngle = Math.PI * 0.8 + p * (Math.PI * 1.4);
                ctx.strokeStyle = RED;
                ctx.shadowColor = 'rgba(230,0,0,0.6)';
                ctx.shadowBlur = 18;
                ctx.beginPath();
                ctx.arc(0, 0, radius, Math.PI * 0.8, endAngle);
                ctx.stroke();
                ctx.shadowBlur = 0;

                // Center readouts
                T(Math.round(val).toString(), 0, -10, radius * 0.52, { c: INK, w: 900 });
                T(unit, 0, radius * 0.35, radius * 0.18, { c: RED, w: 800 });
                ctx.restore();
            }

            // ---------- Subcenários Detalhados e Fluidos ----------

            // 1. Fibra e Internet Residencial
            const dLand = (t, lu) => {
                const g = ctx.createLinearGradient(0, 0, 0, 1120);
                g.addColorStop(0, '#fff4f4'); g.addColorStop(1, '#ffdede');
                ctx.fillStyle = g; ctx.fillRect(0, 0, 900, 1120);

                // Sol e colinas
                dot(660, 290 + Math.sin(t * 1.8) * 8, 110, 'rgba(230,0,0,0.85)');
                rings(660, 290, lu, 'rgba(230,0,0,0.3)', 0.4, 3, 300);

                ['#fca5a5', '#ef4444', '#b91c1c'].forEach((c, k) => {
                    ctx.fillStyle = c;
                    ctx.beginPath();
                    ctx.moveTo(0, 1120);
                    for (let x = 0; x <= 900; x += 15) {
                        ctx.lineTo(x, 600 + k * 140 + Math.sin((x + t * (45 + k * 45)) / (160 + k * 40)) * (45 + k * 22));
                    }
                    ctx.lineTo(900, 1120);
                    ctx.fill();
                });

                // Cabo de Fibra Ótica luminoso com pulsos de alta velocidade
                const py = x => 980 + Math.sin(x * 0.012 + t * 1.2) * 28;
                ctx.strokeStyle = INK;
                ctx.lineWidth = 10;
                ctx.beginPath();
                for (let x = 0; x <= 900; x += 12) x ? ctx.lineTo(x, py(x)) : ctx.moveTo(x, py(x));
                ctx.stroke();

                // Fio luminoso interior
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 4;
                ctx.stroke();

                // Fotões de luz acelerando pela fibra
                for (let k = 0; k < 5; k++) {
                    const x = ((lu * 820 + k * 220) % 1100) - 100;
                    glowCircle(x, py(x), 16, '#fff', 24);
                    glowCircle(x, py(x), 8, RED, 14);
                }

                // Casa moderna conectada
                const hx = 220, hy = 480;
                ctx.fillStyle = '#fff';
                rr(hx - 120, hy - 80, 240, 160, 20); ctx.fill();
                ctx.fillStyle = INK;
                ctx.beginPath();
                ctx.moveTo(hx - 140, hy - 70); ctx.lineTo(hx, hy - 160); ctx.lineTo(hx + 140, hy - 70);
                ctx.closePath(); ctx.fill();
                // Janelas iluminadas
                ctx.fillStyle = '#ffcc00';
                rr(hx - 80, hy - 40, 50, 50, 8); ctx.fill();
                rr(hx + 30, hy - 40, 50, 50, 8); ctx.fill();
                // Wi-Fi transmitindo do telhado
                ctx.save(); ctx.translate(hx, hy - 170); ic.wifi(38, RED, false); ctx.restore();
                T('1 Gbps Real', hx, hy + 120, 38, { c: INK, w: 800 });
            };

            const dTiles = (t, lu) => {
                ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, 900, 1120);
                // Grid de Azulejos com transformação dinâmica
                for (let r = 0; r < 7; r++) {
                    for (let c = 0; c < 6; c++) {
                        const x = c * 150, y = r * 160;
                        const d = Math.hypot(x + 75 - 450, y + 80 - 560);
                        const on = d < lu * 950;
                        const p = on ? clamp((lu * 950 - d) / 220) : 0;

                        ctx.fillStyle = on ? '#fff5f5' : '#f0f4f9';
                        rr(x + 6, y + 6, 138, 148, 16); ctx.fill();

                        ctx.save();
                        ctx.beginPath();
                        rr(x + 6, y + 6, 138, 148, 16);
                        ctx.clip();
                        ctx.fillStyle = on ? RED : '#0f3875';

                        // Flor de Azulejo
                        [[0, 0], [150, 0], [0, 160], [150, 160]].forEach(q => {
                            ctx.beginPath();
                            ctx.arc(x + q[0], y + q[1], 56 * (0.8 + p * 0.2), 0, Math.PI * 2);
                            ctx.fill();
                        });
                        ctx.translate(x + 75, y + 80);
                        ctx.rotate(Math.PI / 4 + (on ? p * Math.PI : 0));
                        ctx.fillRect(-24, -24, 48, 48);
                        ctx.restore();
                    }
                }
                // Selo central de estabilidade
                const q = spring((lu - 0.4) / 0.6);
                if (q > 0) {
                    ctx.save(); ctx.translate(450, 560); ctx.scale(q, q);
                    card(0, 0, 520, 180, 40, '#ffffff');
                    dot(-180, 0, 48, RED);
                    ctx.save(); ctx.translate(-180, 0); ic.bolt(26, '#fff'); ctx.restore();
                    T('Fibra 100% Estável', 30, -18, 44, { c: INK, w: 800, al: 'center' });
                    T('Latência mínima em todo o país', 30, 28, 28, { c: GREY, w: 600, al: 'center' });
                    ctx.restore();
                }
            };

            const dWifi = (t, lu) => {
                ctx.fillStyle = '#f8f9fa'; ctx.fillRect(0, 0, 900, 1120);
                // Casa 2D estilizada
                ctx.fillStyle = INK;
                ctx.beginPath();
                ctx.moveTo(50, 380); ctx.lineTo(450, 150); ctx.lineTo(850, 380);
                ctx.closePath(); ctx.fill();
                ctx.fillStyle = '#ffffff';
                rr(90, 370, 720, 590, 36); ctx.fill();

                // Quartos e divisões
                const rooms = [
                    ['Streaming 4K', 130, 410, 'tv'],
                    ['Home Office', 470, 410, 'bolt'],
                    ['Gaming 8ms', 130, 680, 'spin'],
                    ['Smart Home', 470, 680, 'wifi']
                ];

                rooms.forEach((r, idx) => {
                    const d = Math.hypot(r[1] + 140 - 450, r[2] + 120 - 660);
                    const on = lu * 580 > d;
                    const popIn = spring((lu - 0.2 - idx * 0.15) / 0.5);
                    ctx.save();
                    ctx.translate(r[1] + 140, r[2] + 120);
                    ctx.scale(popIn, popIn);
                    ctx.fillStyle = on ? 'rgba(230,0,0,0.08)' : '#f2f2f5';
                    rr(-140, -120, 280, 240, 24); ctx.fill();
                    if (on) {
                        ctx.strokeStyle = RED;
                        ctx.lineWidth = 3;
                        rr(-140, -120, 280, 240, 24); ctx.stroke();
                    }
                    ctx.save(); ctx.translate(0, -32);
                    if (r[3] === 'wifi') ic.wifi(28, on ? RED : GREY);
                    else if (r[3] === 'tv') ic.tv(28, on ? RED : GREY);
                    else if (r[3] === 'bolt') ic.bolt(28, on ? RED : GREY);
                    else ic.spin(28, on ? RED : GREY, t);
                    ctx.restore();
                    T(r[0], 0, 42, 34, { c: on ? INK : GREY, w: 800 });
                    ctx.restore();
                });

                // Router central irradiando ondas Wi-Fi 6
                for (let k = 0; k < 4; k++) {
                    const p = (lu * 1.1 + k / 4) % 1;
                    ctx.strokeStyle = `rgba(230,0,0,${(1 - p) * 0.8})`;
                    ctx.lineWidth = 8;
                    ctx.beginPath();
                    ctx.arc(450, 660, 30 + p * 540, 0, Math.PI * 2);
                    ctx.stroke();
                }
                glowCircle(450, 660, 48, RED, 24);
                ctx.save(); ctx.translate(450, 648); ic.wifi(24, '#fff', false); ctx.restore();

                T('Super Wi-Fi 6 em Toda a Casa', 450, 1020, 46, { c: INK, w: 800 });
            };

            // 2. Rede Móvel 5G
            const PT = [
                [-8.87, 41.87], [-8.15, 42.15], [-6.95, 41.95], [-6.2, 41.55],
                [-6.85, 41.0], [-7.0, 40.0], [-7.3, 39.7], [-7.15, 38.88],
                [-7.45, 38.2], [-7.4, 37.17], [-8.0, 37.0], [-8.99, 37.0],
                [-8.8, 37.9], [-9.5, 38.7], [-9.4, 39.35], [-8.87, 40.15],
                [-8.75, 40.65], [-8.7, 41.15]
            ];
            const mp = p => [340 + (p[0] + 9.6) * 138, 130 + (42.2 - p[1]) * 175];
            const CITY = [
                ['Viana', [-8.83, 41.69]],
                ['Porto', [-8.61, 41.15]],
                ['Coimbra', [-8.41, 40.20]],
                ['Lisboa', [-9.14, 38.72]],
                ['Évora', [-7.91, 38.57]],
                ['Faro', [-7.93, 37.02]]
            ].map(c => [c[0], mp(c[1])]);

            const dMap = (t, lu) => {
                ctx.fillStyle = '#f8fafc'; ctx.fillRect(0, 0, 900, 1120);

                // Silhueta de Portugal
                ctx.beginPath();
                PT.forEach((p, i) => { const q = mp(p); i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]); });
                ctx.closePath();
                ctx.fillStyle = '#ffffff';
                ctx.shadowColor = 'rgba(0,0,0,0.08)'; ctx.shadowBlur = 30;
                ctx.fill();
                ctx.shadowBlur = 0;
                ctx.strokeStyle = '#cbd5e1'; ctx.lineWidth = 5; ctx.stroke();

                // Feixe luminoso conectando cidades
                const P = eio(lu / 1.4);
                ctx.strokeStyle = RED;
                ctx.lineWidth = 10;
                ctx.lineCap = 'round';
                ctx.beginPath();
                CITY.forEach((c, i) => {
                    if (i === 0) ctx.moveTo(c[1][0], c[1][1]);
                    else if (i / (CITY.length - 1) <= P) ctx.lineTo(c[1][0], c[1][1]);
                });
                ctx.stroke();

                // Ondas 5G pulsando nas cidades
                CITY.forEach((c, i) => {
                    const active = (lu * 1.5) > (i * 0.2);
                    if (active) {
                        for (let k = 0; k < 3; k++) {
                            const pr = ((t * 2 + k / 3 + i * 0.15) % 1);
                            ctx.strokeStyle = `rgba(230,0,0,${(1 - pr) * 0.7})`;
                            ctx.lineWidth = 4;
                            ctx.beginPath();
                            ctx.arc(c[1][0], c[1][1], 15 + pr * 70, 0, Math.PI * 2);
                            ctx.stroke();
                        }
                        glowCircle(c[1][0], c[1][1], 16, RED, 14);
                    } else {
                        dot(c[1][0], c[1][1], 10, '#94a3b8');
                    }
                    T(c[0], c[1][0] + (i === 3 ? -35 : 35), c[1][1] - 8, 32, {
                        al: i === 3 ? 'right' : 'left', c: active ? INK : GREY, w: 700
                    });
                });

                // Ilhas (Madeira & Açores)
                [['Madeira', 140, 870], ['Açores', 140, 640]].forEach((isl, i) => {
                    const on = lu > 1.0;
                    if (on) {
                        glowCircle(isl[1], isl[2], 16, RED, 14);
                        for (let k = 0; k < 2; k++) {
                            const pr = ((t * 2 + k / 2 + i * 0.3) % 1);
                            ctx.strokeStyle = `rgba(230,0,0,${(1 - pr) * 0.7})`;
                            ctx.lineWidth = 4;
                            ctx.beginPath();
                            ctx.arc(isl[1], isl[2], 15 + pr * 60, 0, Math.PI * 2);
                            ctx.stroke();
                        }
                    } else {
                        dot(isl[1], isl[2], 10, '#94a3b8');
                    }
                    T(isl[0], isl[1], isl[2] + 48, 34, { c: on ? INK : GREY, w: 700 });
                });

                // Badge de cobertura
                ctx.save();
                ctx.translate(450, 1030);
                card(0, 0, 560, 100, 30, '#ffffff');
                T('Cobertura 5G em mais de 99% do país', 0, 0, 36, { c: INK, w: 800 });
                ctx.restore();
            };

            const dKin = (t, lu) => {
                ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, 900, 1120);
                const curSpeed = clamp(lu / 1.6) * 1280;
                drawSpeedGauge(450, 480, 240, curSpeed, 1400, 'Mbps 5G');

                const wordsArr = ['ULTRARRÁPIDO', 'LATÊNCIA < 10ms', 'ESTABILIDADE MÁXIMA'];
                const step = Math.min(2, Math.floor(lu / 0.65));
                const q = spring((lu - step * 0.65) / 0.45);

                ctx.save();
                ctx.translate(450, 890);
                ctx.scale(q, q);
                card(0, 0, 680, 140, 36, RED);
                T(wordsArr[step], 0, 2, 48, { c: '#fff', w: 900 });
                ctx.restore();
            };

            const dRace = (t, lu) => {
                const p = clamp(lu / 1.8);
                // Lado Esquerdo: Sem 5G / Conexão fraca
                ctx.save();
                ctx.beginPath(); ctx.rect(0, 0, 450, 1120); ctx.clip();
                ctx.fillStyle = '#f1f1f4'; ctx.fillRect(0, 0, 450, 1120);
                T('Redes Convencionais', 225, 170, 38, { c: GREY, w: 700 });

                // Loader irritante de buffering
                ctx.save(); ctx.translate(225, 450);
                ic.spin(60, RED, t);
                T('A carregar...', 0, 110, 32, { c: GREY, w: 600 });
                ctx.restore();

                // Elétrico travado
                ctx.fillStyle = '#9ca3af';
                rr(80 + Math.sin(t * 12) * 4, 760, 240, 130, 24); ctx.fill();
                T('Travado', 225, 960, 44, { c: GREY, w: 800 });
                ctx.restore();

                // Lado Direito: Vodafone 5G ultrarrápido
                ctx.save();
                ctx.beginPath(); ctx.rect(450, 0, 450, 1120); ctx.clip();
                ctx.fillStyle = '#fff5f5'; ctx.fillRect(450, 0, 450, 1120);
                T('Vodafone 5G', 675, 170, 42, { c: RED, w: 900 });

                // Velocidade máxima
                ctx.save(); ctx.translate(675, 450);
                glowCircle(0, 0, 70, RED, 24);
                ctx.save(); ctx.translate(0, -6); ic.bolt(42, '#fff'); ctx.restore();
                T('4K HDR LIVE', 0, 110, 34, { c: GREEN, w: 800 });
                ctx.restore();

                // Elétrico voando suavemente com rastros de luz
                const tramX = 470 + eio(p) * 380;
                ctx.fillStyle = RED;
                rr(tramX - 100, 760, 240, 130, 24); ctx.fill();
                // Faróis
                glowCircle(tramX + 130, 830, 14, '#ffea00', 16);
                T('Fluidez Total', 675, 960, 44, { c: RED, w: 800 });
                ctx.restore();

                // Linha divisória
                ctx.fillStyle = '#e2e8f0';
                ctx.fillRect(448, 0, 4, 1120);
            };

            // 3. TV e Streaming
            const dBurst = (t, lu) => {
                ctx.fillStyle = '#f8fafc'; ctx.fillRect(0, 0, 900, 1120);
                const items = [
                    ['HBO Max', '#5c16c5'], ['Disney+', '#113ccf'],
                    ['Sport TV', '#028940'], ['Netflix', '#e50914'],
                    ['Prime Video', '#00a8e1'], ['Kids', '#ff8c00']
                ];

                items.forEach((it, i) => {
                    const row = Math.floor(i / 2);
                    const col = i % 2;
                    const pop = spring((lu - 0.1 - i * 0.12) / 0.55);
                    const cx = 240 + col * 420;
                    const cy = 260 + row * 220;

                    ctx.save();
                    ctx.translate(cx, cy);
                    ctx.scale(pop, pop);
                    card(0, 0, 360, 170, 32, it[1]);
                    T(it[0], 0, 0, 44, { c: '#fff', w: 800 });
                    ctx.restore();
                });

                // Box de TV Vodafone com barra luminosa
                const q = spring((lu - 1.1) / 0.5);
                ctx.save();
                ctx.translate(450, 950);
                ctx.scale(q, q);
                card(0, 0, 680, 160, 38, INK);
                glowCircle(-250, 0, 14, RED, 18);
                T('170+ Canais • Gravações de 7 Dias', 40, -16, 40, { c: '#fff', w: 800 });
                T('Comando por Voz Inteligente incluído', 40, 30, 28, { c: GREY, w: 600 });
                ctx.restore();
            };

            const dPortal = (t, lu) => {
                ctx.fillStyle = '#0f172a'; ctx.fillRect(0, 0, 900, 1120);
                const step = Math.min(2, Math.floor(lu / 0.73));

                // Moldura de TV com Ambilight reativo
                ctx.save();
                const ambilightCol = step === 0 ? 'rgba(34,197,94,0.45)' : step === 1 ? 'rgba(230,0,0,0.5)' : 'rgba(250,204,21,0.45)';
                ctx.shadowColor = ambilightCol;
                ctx.shadowBlur = 80;
                ctx.fillStyle = '#000';
                rr(80, 200, 740, 520, 32); ctx.fill();
                ctx.restore();

                // Ecrã da TV com conteúdos cinematográficos
                ctx.save();
                rr(96, 216, 708, 488, 24);
                ctx.clip();
                if (step === 0) {
                    // Futebol relvado
                    ctx.fillStyle = '#15803d'; ctx.fillRect(96, 216, 708, 488);
                    ctx.strokeStyle = 'rgba(255,255,255,0.7)'; ctx.lineWidth = 6;
                    ctx.strokeRect(140, 260, 620, 400);
                    glowCircle(450 + Math.sin(t * 4) * 180, 460 + Math.cos(t * 4) * 60, 28, '#fff', 20);
                    T('GOLO!', 450, 460, 96, { c: '#fff', w: 900, shadow: true });
                } else if (step === 1) {
                    // Cinema 4K
                    ctx.fillStyle = '#1e1b4b'; ctx.fillRect(96, 216, 708, 488);
                    glowCircle(450, 420, 90, RED, 40);
                    ctx.save(); ctx.translate(450, 410); ic.tv(40, '#fff'); ctx.restore();
                    T('SÉRIES EM 4K HDR', 450, 560, 48, { c: '#fff', w: 800 });
                } else {
                    // Animação infantil
                    ctx.fillStyle = '#fef08a'; ctx.fillRect(96, 216, 708, 488);
                    for (let s = 0; s < 5; s++) {
                        dot(220 + s * 110, 460 - Math.abs(Math.sin(t * 5 + s)) * 120, 36, [RED, BLUE, GREEN, GOLD, RED][s]);
                    }
                    T('DIVERSÃO EM FAMÍLIA', 450, 320, 44, { c: INK, w: 900 });
                }
                ctx.restore();

                // Suporte da TV
                ctx.fillStyle = '#334155';
                ctx.fillRect(400, 720, 100, 70);
                rr(320, 780, 260, 20, 10); ctx.fill();

                T(['Desporto em Direto Sem Atrasos', 'Cinema e Séries em Casa', 'Conteúdos Seguros para Crianças'][step], 450, 930, 48, { c: '#fff', w: 800 });
            };

            // 4. Vodafone Business e IoT
            const dPort = (t, lu) => {
                ctx.fillStyle = '#f1f5f9'; ctx.fillRect(0, 0, 900, 1120);
                // Oceano e cais
                ctx.fillStyle = '#0284c7'; ctx.fillRect(0, 680, 900, 440);

                // Navio porta-contentores
                ctx.fillStyle = INK;
                rr(80, 620, 540, 110, 20); ctx.fill();
                const colors = [RED, BLUE, GOLD, GREEN, '#8b5cf6'];
                for (let r = 0; r < 3; r++) {
                    for (let c = 0; c < 5; c++) {
                        ctx.fillStyle = colors[(c + r * 2) % 5];
                        ctx.fillRect(110 + c * 95, 540 - r * 65, 85, 55);
                    }
                }

                // Grua automatizada 5G
                ctx.strokeStyle = INK; ctx.lineWidth = 14;
                ctx.beginPath();
                ctx.moveTo(660, 750); ctx.lineTo(660, 240); ctx.lineTo(340, 240);
                ctx.stroke();

                // Cabo e gancho robótico
                const hookY = 320 + Math.sin(t * 2) * 110;
                ctx.lineWidth = 4;
                ctx.beginPath(); ctx.moveTo(380, 240); ctx.lineTo(380, hookY); ctx.stroke();
                ctx.fillStyle = RED; ctx.fillRect(340, hookY, 80, 50);

                // Laser de telemetria IoT
                ctx.strokeStyle = RED;
                ctx.lineWidth = 3;
                ctx.setLineDash([8, 8]);
                ctx.beginPath(); ctx.moveTo(380, hookY + 50); ctx.lineTo(380, 620); ctx.stroke();
                ctx.setLineDash([]);

                glowCircle(660, 240, 22, RED, 14);
                glowCircle(380, hookY, 16, RED, 10);

                T('Logística & Portos Conectados 5G', 450, 1020, 46, { c: '#fff', w: 800 });
            };

            const dFarm = (t, lu) => {
                ctx.fillStyle = '#f7fee7'; ctx.fillRect(0, 0, 900, 1120);

                // Vinhas do Alentejo estilizadas
                ctx.strokeStyle = '#65a30d'; ctx.lineWidth = 8;
                for (let r = 0; r < 8; r++) {
                    ctx.beginPath();
                    for (let y = 80; y <= 660; y += 25) {
                        const x = 180 + r * 85 + Math.sin(y * 0.015 + r) * 20;
                        y === 80 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
                    }
                    ctx.stroke();
                }

                // Sensores IoT no terreno pulsando
                [[280, 220], [450, 360], [620, 500], [380, 580]].forEach((p, i) => {
                    glowCircle(p[0], p[1], 18, RED, 16);
                    for (let k = 0; k < 2; k++) {
                        const pr = ((t * 2 + k / 2 + i * 0.2) % 1);
                        ctx.strokeStyle = `rgba(230,0,0,${(1 - pr) * 0.7})`;
                        ctx.lineWidth = 4;
                        ctx.beginPath();
                        ctx.arc(p[0], p[1], 15 + pr * 50, 0, Math.PI * 2);
                        ctx.stroke();
                    }
                });

                // Dashboard de telemetria agrícola
                ctx.save();
                ctx.translate(450, 890);
                card(0, 0, 720, 220, 36, '#ffffff');
                T('Agricultura Inteligente IoT', 0, -55, 42, { c: INK, w: 800 });
                T('Monitorização em tempo real de humidade e clima', 0, -10, 28, { c: GREY, w: 600 });

                // Gráfico com curva suave
                ctx.strokeStyle = GREEN; ctx.lineWidth = 6; ctx.lineCap = 'round';
                ctx.beginPath();
                ctx.moveTo(-280, 50);
                ctx.bezierCurveTo(-140, 10, -50, 80, 80, 30);
                ctx.bezierCurveTo(150, 10, 220, 60, 280, 25);
                ctx.stroke();
                ctx.restore();
            };

            const dCity = (t, lu) => {
                ctx.fillStyle = '#0f172a'; ctx.fillRect(0, 0, 900, 1120);

                // Ruas iluminadas com sensores de trânsito
                ctx.strokeStyle = '#334155'; ctx.lineWidth = 18;
                [320, 620, 880].forEach(y => {
                    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(900, y); ctx.stroke();
                });
                [240, 520, 760].forEach(x => {
                    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, 1120); ctx.stroke();
                });

                // Veículos elétricos conectados em movimento
                for (let i = 0; i < 6; i++) {
                    const posX = ((t * 180 + i * 160) % 1100) - 100;
                    glowCircle(posX, 320, 12, GREEN, 14);
                    glowCircle(900 - posX, 620, 12, BLUE, 14);
                }

                // Postos de carregamento inteligentes
                [[240, 320], [520, 620], [760, 880]].forEach((p, i) => {
                    glowCircle(p[0], p[1], 24, RED, 20);
                    ctx.save(); ctx.translate(p[0], p[1] - 4); ic.bolt(16, '#fff'); ctx.restore();
                });

                ctx.save();
                ctx.translate(450, 140);
                card(0, 0, 600, 110, 32, '#ffffff');
                T('Cidades & Mobilidade Inteligente', 0, 0, 38, { c: INK, w: 800 });
                ctx.restore();
            };

            // 5. O Meu Vodafone
            const dUI = (t, lu) => {
                ctx.fillStyle = '#f8fafc'; ctx.fillRect(0, 0, 900, 1120);
                const perc = clamp(lu / 1.2) * 0.76;

                // Indicador circular de dados
                ctx.save();
                ctx.translate(450, 360);
                ctx.lineWidth = 38;
                ctx.lineCap = 'round';
                ctx.strokeStyle = '#e2e8f0';
                ctx.beginPath(); ctx.arc(0, 0, 170, 0, Math.PI * 2); ctx.stroke();

                ctx.strokeStyle = RED;
                ctx.shadowColor = 'rgba(230,0,0,0.5)'; ctx.shadowBlur = 24;
                ctx.beginPath();
                ctx.arc(0, 0, 170, -Math.PI / 2, -Math.PI / 2 + perc * Math.PI * 2);
                ctx.stroke();
                ctx.shadowBlur = 0;

                T(Math.round(perc * 100) + ' GB', 0, -12, 84, { c: INK, w: 900 });
                T('Dados Móveis Disponíveis', 0, 52, 28, { c: GREY, w: 600 });
                ctx.restore();

                // Fatura Paga com 1 Toque
                const q = spring((lu - 0.7) / 0.5);
                ctx.save();
                ctx.translate(450, 690);
                ctx.scale(q, q);
                card(0, 0, 680, 140, 36, '#ffffff');
                glowCircle(-250, 0, 36, GREEN, 16);
                ctx.save(); ctx.translate(-250, 0); ic.check(22, '#fff'); ctx.restore();
                T('Fatura de Novembro Liquidada', 30, -16, 40, { c: INK, w: 800 });
                T('MB WAY • Pagamento automático ativo', 30, 28, 28, { c: GREY, w: 600 });
                ctx.restore();

                // Botão de alteração rápida
                const bq = spring((lu - 1.2) / 0.4);
                ctx.save();
                ctx.translate(450, 930);
                ctx.scale(bq, bq);
                card(0, 0, 560, 110, 40, RED);
                T('Gerir Pacote com 1 Clique', 0, 0, 40, { c: '#fff', w: 800 });
                ctx.restore();
            };

            const dGame = (t, lu) => {
                ctx.fillStyle = '#fffbeb'; ctx.fillRect(0, 0, 900, 1120);

                // Caixa de presente Happy Shake
                const shake = lu > 0.4 && lu < 1.2 ? Math.sin(t * 36) * 16 : 0;
                const openP = clamp((lu - 1.1) / 0.4);

                ctx.save();
                ctx.translate(450 + shake, 520);

                // Caixa
                ctx.fillStyle = RED;
                rr(-130, -100, 260, 230, 28); ctx.fill();
                // Fita amarela
                ctx.fillStyle = GOLD;
                ctx.fillRect(-25, -100, 50, 230);
                ctx.fillRect(-130, 0, 260, 40);

                // Tampa voando aberta
                ctx.save();
                ctx.translate(0, -100 - openP * 120);
                ctx.rotate(openP * 0.3);
                ctx.fillStyle = DARK_RED;
                rr(-145, -40, 290, 60, 16); ctx.fill();
                ctx.restore();

                // Confetti explodindo
                if (lu > 1.1) {
                    for (let c = 0; c < 28; c++) {
                        const seed = c * 33.7;
                        const dist = (lu - 1.1) * (260 + (seed % 200));
                        const angle = seed;
                        const cx = Math.cos(angle) * dist;
                        const cy = Math.sin(angle) * dist - 100;
                        dot(cx, cy, 8 + (c % 6), [RED, GOLD, GREEN, BLUE, '#ec4899'][c % 5]);
                    }
                }
                ctx.restore();

                if (lu > 1.0) {
                    const pop = spring((lu - 1.0) / 0.5);
                    ctx.save();
                    ctx.translate(450, 870);
                    ctx.scale(pop, pop);
                    card(0, 0, 660, 150, 38, '#ffffff');
                    T('+10 GB BÓNUS GRÁTIS!', 0, -16, 52, { c: RED, w: 900 });
                    T('Desbloqueado no Happy Shake', 0, 36, 30, { c: GREY, w: 600 });
                    ctx.restore();
                }

                T('Happy Shake na App My Vodafone', 450, 180, 48, { c: INK, w: 800 });
            };

            const dChat = (t, lu) => {
                ctx.fillStyle = '#f1f5f9'; ctx.fillRect(0, 0, 900, 1120);

                // Bolhas de chat estilo WhatsApp/TOBi
                const bub = (txt, x, y, w, me, q) => {
                    ctx.save();
                    ctx.translate(x + w / 2, y + 55);
                    ctx.scale(q, q);
                    card(0, 0, w, 110, 32, me ? '#dcf8c6' : '#ffffff');
                    T(txt, 0, 0, 36, { c: INK, w: 700, maxW: w - 50 });
                    ctx.restore();
                };

                const q1 = spring(lu / 0.4);
                bub('Como ativo o Roaming para a viagem?', 90, 240, 720, 1, q1);

                if (lu > 0.6) {
                    const q2 = spring((lu - 0.6) / 0.4);
                    bub('Já está ativo! Use o seu plano na UE sem custos.', 90, 410, 720, 0, q2);
                }

                // Cartão de satisfação 5 Estrelas
                if (lu > 1.1) {
                    const q3 = spring((lu - 1.1) / 0.5);
                    ctx.save();
                    ctx.translate(450, 760);
                    ctx.scale(q3, q3);
                    card(0, 0, 680, 220, 42, '#ffffff');
                    glowCircle(0, -50, 38, GREEN, 16);
                    ctx.save(); ctx.translate(0, -50); ic.check(24, '#fff'); ctx.restore();
                    T('Pedido Resolvido em Segundos', 0, 16, 44, { c: INK, w: 800 });

                    // 5 Estrelas Douradas
                    for (let s = 0; s < 5; s++) {
                        dot(-120 + s * 60, 68, 16, GOLD);
                    }
                    ctx.restore();
                }

                T('Assistente Inteligente TOBi 24/7', 450, 130, 46, { c: INK, w: 800 });
            };

            // 6. Formatos Curtos & Planos Exclusivos
            const dLogo = (t, lu) => {
                ctx.fillStyle = '#0a0a0c'; ctx.fillRect(0, 0, 900, 1120);
                grid(lu, 'rgba(255,255,255,0.05)');
                rings(450, 520, lu, '#fff', 0.25, 3, 700);

                const sc = spring(lu / 0.7);
                glowCircle(450, 520, 180 * sc, RED, 40);
                logo(450, 520, 280, 1, 0, sc);

                // Ícones orbitando
                [['wifi', 0], ['tv', 1], ['bolt', 2]].forEach((it, i) => {
                    const ang = -Math.PI / 2 + (i * Math.PI * 2 / 3) + lu * 0.6;
                    const ox = 450 + Math.cos(ang) * 310;
                    const oy = 520 + Math.sin(ang) * 310;
                    glowCircle(ox, oy, 46, '#ffffff', 14);
                    glowCircle(ox, oy, 38, RED, 10);
                    ctx.save(); ctx.translate(ox, oy);
                    if (it[0] === 'wifi') ic.wifi(24, '#fff');
                    else if (it[0] === 'tv') ic.tv(24, '#fff');
                    else ic.bolt(24, '#fff');
                    ctx.restore();
                });

                T('Potência & Estabilidade', 450, 970, 54, { c: '#fff', w: 800 });
            };

            const dPlan = (t, lu) => {
                ctx.fillStyle = '#f8fafc'; ctx.fillRect(0, 0, 900, 1120);
                const step = Math.min(2, Math.floor(lu / 0.67));
                const plans = [
                    { name: 'Fibra 500', price: '29,90€', feat: 'Wi-Fi 6 incluído • 500 Mbps' },
                    { name: 'Fibra 1 Gbps + TV', price: '39,90€', feat: '170 Canais • 1 Gbps • HBO Max incluída' },
                    { name: 'Total Infinity 5G', price: '49,90€', feat: 'Tudo Ilimitado em Casa e no Telemóvel' }
                ];
                const cur = plans[step];
                const q = spring((lu - step * 0.67) / 0.45);

                ctx.save();
                ctx.translate(450, 540);
                ctx.scale(q, q);
                card(0, 0, 720, 620, 44, '#ffffff');

                // Destaque superior
                ctx.fillStyle = RED;
                rr(-360, -310, 720, 130, 44); ctx.fill();
                ctx.fillRect(-360, -230, 720, 50);
                T('PACOTE RECOMENDADO', 0, -245, 36, { c: '#fff', w: 800 });

                T(cur.name, 0, -90, 64, { c: INK, w: 900 });
                T(cur.price, 0, 20, 100, { c: RED, w: 900 });
                T('/ mês', 0, 100, 32, { c: GREY, w: 600 });

                T(cur.feat, 0, 180, 36, { c: INK, w: 700, maxW: 640 });

                // Botão de escolha
                card(0, 250, 480, 80, 30, RED);
                T('Aderir Já', 0, 250, 36, { c: '#fff', w: 800 });
                ctx.restore();
            };

            const dSeason = (t, lu) => {
                ctx.fillStyle = '#fff7f2'; ctx.fillRect(0, 0, 900, 1120);
                const step = Math.min(2, Math.floor(lu / 0.67));

                ctx.save();
                ctx.translate(450, 500);

                if (step === 0) {
                    // Natal Vodafone
                    ['#15803d', '#16a34a', '#22c55e'].forEach((c, i) => {
                        ctx.fillStyle = c;
                        ctx.beginPath();
                        ctx.moveTo(0, -260 + i * 110);
                        ctx.lineTo(-180 + i * 20, -60 + i * 110);
                        ctx.lineTo(180 - i * 20, -60 + i * 110);
                        ctx.closePath(); ctx.fill();
                    });
                    glowCircle(0, -280, 32, GOLD, 24);
                    // Presentes
                    dot(-80, 180, 40, RED);
                    dot(80, 180, 40, GOLD);
                } else if (step === 1) {
                    // Santos Populares
                    glowCircle(0, -80, 80, GOLD, 20);
                    // Sardinha estilizada
                    ctx.fillStyle = '#64748b';
                    ctx.beginPath();
                    ctx.ellipse(0, 80, 180, 60, 0, 0, Math.PI * 2);
                    ctx.fill();
                    dot(120, 70, 12, '#fff');
                    dot(124, 70, 6, INK);
                } else {
                    // Verão & Roaming
                    glowCircle(0, -60, 120, GOLD, 36);
                    for (let r = 0; r < 12; r++) {
                        const a = r * Math.PI / 6 + t * 0.5;
                        ctx.strokeStyle = GOLD; ctx.lineWidth = 10;
                        ctx.beginPath();
                        ctx.moveTo(Math.cos(a) * 160, -60 + Math.sin(a) * 160);
                        ctx.lineTo(Math.cos(a) * 220, -60 + Math.sin(a) * 220);
                        ctx.stroke();
                    }
                    T('Roaming Europa Grátis', 0, 160, 48, { c: RED, w: 900 });
                }
                ctx.restore();

                T(['Campanha de Natal: Dobro da Velocidade', 'Santos Populares: Festas Conectadas', 'Verão com Roaming Sem Preocupações'][step], 450, 940, 44, { c: INK, w: 800, maxW: 820 });
            };

            // Cenário 0: Intro
            const s0 = (u, du) => {
                bg('#070709');
                grid(u, 'rgba(255,255,255,0.04)');
                particles(u, 28, 'rgba(230,0,0,0.4)');

                const g = ctx.createRadialGradient(W / 2, H * 0.35, 0, W / 2, H * 0.35, 800);
                g.addColorStop(0, 'rgba(230,0,0,0.45)');
                g.addColorStop(1, 'rgba(230,0,0,0)');
                ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

                rings(W / 2, H * 0.35, u, '#fff', 0.28, 4, 850);

                const pop = spring(u / 0.85);
                glowCircle(W / 2, H * 0.35, 170 * pop, RED, 40);
                logo(W / 2, H * 0.35, 340, 1, (1 - pop) * 0.4, pop);

                words([['VODAFONE', '#fff'], ['PORTUGAL', RED]], H * 0.58, 130, u, 0.4, { w: 900 });
                words([['O Futuro é Fascinante. Ready?', '#fff']], H * 0.67, 60, u, 0.9, { w: 600 });

                // Badge de Inovação
                const bq = spring((u - 1.2) / 0.5);
                if (bq > 0) {
                    ctx.save(); ctx.translate(W / 2, H * 0.77); ctx.scale(bq, bq);
                    card(0, 0, 680, 90, 40, 'rgba(255,255,255,0.1)');
                    T('FIBRA GIGABIT • REDE 5G • VODAFONE TV', 0, 0, 32, { c: '#fff', w: 700 });
                    ctx.restore();
                }
            };

            // Cenário 7: Grande Final & CTA
            const s7 = (u, du) => {
                bg('#070709');
                grid(u, 'rgba(255,255,255,0.04)');
                particles(u, 36, 'rgba(230,0,0,0.5)');

                const g = ctx.createRadialGradient(W / 2, H * 0.34, 0, W / 2, H * 0.34, 900);
                g.addColorStop(0, 'rgba(230,0,0,0.5)');
                g.addColorStop(1, 'rgba(230,0,0,0)');
                ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

                rings(W / 2, H * 0.34, u, '#fff', 0.3, 4, 950);

                const pop = spring(u / 0.85);
                glowCircle(W / 2, H * 0.34, 200 * pop, RED, 50);
                logo(W / 2, H * 0.34, 400, 1, 0, pop);

                words([['Vodafone.', '#fff']], H * 0.56, 130, u, 0.4, { w: 900 });
                words([['Ligados', '#fff'], ['a', '#fff'], ['Portugal.', RED]], H * 0.64, 86, u, 0.8, { w: 800 });

                // Botão de Ação com Brilho Deslizante
                const bq = spring((u - 1.3) / 0.6);
                if (bq > 0) {
                    ctx.save();
                    ctx.translate(W / 2, H * 0.76);
                    ctx.scale(bq, bq);
                    card(0, 0, 620, 130, 65, RED);
                    T('Aderir Agora', 0, 0, 52, { c: '#fff', w: 800 });

                    // Brilho passando
                    ctx.save();
                    rr(-310, -65, 620, 130, 65);
                    ctx.clip();
                    const glintX = -400 + ((u * 1.8) % 3) * 600;
                    const gl = ctx.createLinearGradient(glintX, -65, glintX + 160, 65);
                    gl.addColorStop(0, 'rgba(255,255,255,0)');
                    gl.addColorStop(0.5, 'rgba(255,255,255,0.4)');
                    gl.addColorStop(1, 'rgba(255,255,255,0)');
                    ctx.fillStyle = gl;
                    ctx.fillRect(glintX, -65, 160, 130);
                    ctx.restore();

                    ctx.restore();
                }

                if (WHATSAPP) {
                    wa(W / 2 - 320, H * 0.88, 80, eo((u - 1.7) / 0.4));
                    T(WHATSAPP, W / 2 + 50, H * 0.88, 52, { c: '#fff', w: 700, a: eo((u - 1.7) / 0.4) });
                }
            };

            function mkScene(title, labels, ds, bgc = '#fbfbfe') {
                const n = ds.length;
                return (u, dur) => {
                    bg(bgc);
                    words(title, H * 0.095, 96, u, 0.1, { w: 900 });
                    const bl = dur / n;
                    const i = Math.min(n - 1, Math.floor(u / bl));
                    const lu = u - i * bl;
                    const cy = STG.y + STG.h / 2;
                    const ent = spring(u / 0.85);

                    ctx.save();
                    ctx.translate(W / 2, cy);
                    ctx.scale(ent, ent);
                    ctx.translate(-W / 2, -cy);

                    card(W / 2, cy, STG.w, STG.h, 60);

                    ctx.save();
                    rr(STG.x, STG.y, STG.w, STG.h, 60);
                    ctx.clip();
                    ctx.translate(STG.x, STG.y);

                    if (i > 0 && lu < 0.28) {
                        ctx.globalAlpha = 1 - eo(lu / 0.28);
                        ds[i - 1](u, bl + lu);
                        ctx.globalAlpha = eo(lu / 0.28);
                    }
                    ds[i](u, lu);
                    ctx.restore();
                    ctx.restore();

                    // Rótulo da subcena
                    const q = eo(lu / 0.45);
                    T(labels[i], W / 2, STG.y + STG.h + 95, 62, {
                        w: 800, a: q, blur: 14 * (1 - q), dy: 24 * (1 - q)
                    });

                    // Marcadores de progresso
                    for (let k = 0; k < n; k++) {
                        ctx.fillStyle = k === i ? RED : '#cbd5e1';
                        const pw = k === i ? 48 : 18;
                        rr(W / 2 + (k - (n - 1) / 2) * 65 - pw / 2, STG.y + STG.h + 175, pw, 18, 9);
                        ctx.fill();
                    }
                };
            }

            const scenes = [
                s0,
                mkScene([['Fibra', INK], ['em', INK], ['Casa', RED]], ['Velocidade Máxima', 'Rede de Última Geração', 'Super Wi-Fi 6 Total'], [dLand, dTiles, dWifi]),
                mkScene([['Rede', INK], ['Móvel', INK], ['5G', RED]], ['Sinal de Norte a Sul', 'Latência Mínima', 'Comparação em Tempo Real'], [dMap, dKin, dRace]),
                mkScene([['Vodafone', RED], ['TV', INK], ['&', INK], ['Streaming', INK]], ['Os Melhores Canais', 'Experiência de Sala'], [dBurst, dPortal]),
                mkScene([['Vodafone', RED], ['Business', INK], ['&', INK], ['IoT', INK]], ['Portos & Logística', 'Agricultura de Precisão', 'Cidades Inteligentes'], [dPort, dFarm, dCity]),
                mkScene([['App', INK], ['My', INK], ['Vodafone', RED]], ['Painel & Faturas', 'Bónus Happy Shake', 'Suporte TOBi 24/7'], [dUI, dGame, dChat]),
                mkScene([['Planos', INK], ['Exclusivos', RED]], ['Tecnologia de Ponta', 'Pacotes à Medida', 'Campanhas Especiais'], [dLogo, dPlan, dSeason]),
                s7
            ];

            const IMPACTS = TL.slice(1, -1).map((t, i, a) => [t + 0.1, i === a.length - 1 ? 26 : 14]);

            function render(t) {
                ctx = mainCtx;
                ctx.setTransform(canvas.width / W, 0, 0, canvas.height / H, 0, 0);
                ctx.globalAlpha = 1;

                // Micro-tremor de impacto nas transições
                let ox = 0, oy = 0;
                IMPACTS.forEach(([ti, a]) => {
                    const d = t - ti;
                    if (d > 0 && d < 0.8) {
                        const e = Math.exp(-d * 6.5);
                        ox += Math.sin(d * 80) * a * e;
                        oy += Math.cos(d * 90) * a * e;
                    }
                });

                const N = scenes.length;
                for (let i = 0; i < N; i++) {
                    if (t >= TL[i] && (t < TL[i + 1] || i === N - 1)) {
                        const lu = t - TL[i];
                        const du = TL[i + 1] - TL[i];
                        const z = 1 + 0.02 * (lu / du);

                        ctx.save();
                        ctx.translate(W / 2 + ox, H / 2 + oy + 8 * Math.sin(t * 1.1));
                        ctx.scale(z, z);
                        ctx.translate(-W / 2, -H / 2);
                        scenes[i](lu, du);
                        ctx.restore();
                    }
                }

                // Onda vermelha de transição entre cenas
                for (let i = 1; i < N; i++) {
                    const d = t - TL[i];
                    if (d > -0.25 && d < 0.45) {
                        const l = W * (1 - eo((d + 0.25) / 0.25));
                        const r = W * (1 - eio(d / 0.45));
                        const b = 160 * Math.sin(Math.PI * clamp((d + 0.25) / 0.7));
                        if (r > l) {
                            ctx.beginPath();
                            ctx.moveTo(l, 0);
                            ctx.quadraticCurveTo(l - b, H / 2, l, H);
                            ctx.lineTo(r, H);
                            ctx.lineTo(r, 0);
                            ctx.closePath();
                            ctx.fillStyle = RED;
                            ctx.fill();

                            ctx.strokeStyle = '#fff';
                            ctx.lineWidth = 6;
                            ctx.beginPath();
                            ctx.moveTo(l, 0);
                            ctx.quadraticCurveTo(l - b, H / 2, l, H);
                            ctx.stroke();
                        }
                    }
                }
            }

            // ---------- Efeitos Sonoros Imersivos e Trilha Sonora Studio-Quality ----------
            function buildAudio(ac, out, t0) {
                const master = ac.createGain();
                master.gain.setValueAtTime(0.9, t0);
                master.gain.setValueAtTime(0.9, t0 + DURATION - 1.2);
                master.gain.linearRampToValueAtTime(0, t0 + DURATION);

                const comp = ac.createDynamicsCompressor();
                comp.threshold.value = -14;
                comp.ratio.value = 4;
                comp.attack.value = 0.005;
                comp.release.value = 0.15;
                master.connect(comp).connect(out);

                // Reverb de estúdio com decaimento suave
                const revLen = ac.sampleRate * 2.5;
                const ir = ac.createBuffer(2, revLen, ac.sampleRate);
                for (let c = 0; c < 2; c++) {
                    const x = ir.getChannelData(c);
                    for (let i = 0; i < revLen; i++) {
                        x[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / revLen, 3.2);
                    }
                }
                const rv = ac.createConvolver();
                rv.buffer = ir;
                const rg = ac.createGain();
                rg.gain.value = 0.45;
                rv.connect(rg).connect(master);

                const mus = ac.createGain();
                mus.gain.value = 0.85;
                mus.connect(master);

                const bus = (p0, p1, du, t, wet = 0.15) => {
                    const p = ac.createStereoPanner ? ac.createStereoPanner() : ac.createGain();
                    if (p.pan) {
                        p.pan.setValueAtTime(p0, t);
                        if (p1 !== p0) p.pan.linearRampToValueAtTime(p1, t + du);
                    }
                    p.connect(master);
                    if (wet) {
                        const w = ac.createGain();
                        w.gain.value = wet;
                        p.connect(w).connect(rv);
                    }
                    return p;
                };

                // Buffer de ruído branco de alta resolução
                const nb = ac.createBuffer(1, ac.sampleRate * 2, ac.sampleRate);
                const nd = nb.getChannelData(0);
                for (let i = 0; i < nd.length; i++) nd[i] = Math.random() * 2 - 1;

                const noise = (t, du, type, f0, f1, vol, q = 1, p0 = 0, p1 = 0, wet = 0.15) => {
                    const s = ac.createBufferSource();
                    s.buffer = nb; s.loop = true;
                    const f = ac.createBiquadFilter();
                    f.type = type; f.Q.value = q;
                    f.frequency.setValueAtTime(f0, t);
                    f.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t + du);

                    const g = ac.createGain();
                    g.gain.setValueAtTime(0, t);
                    g.gain.linearRampToValueAtTime(vol, t + du * 0.4);
                    g.gain.exponentialRampToValueAtTime(0.001, t + du);

                    s.connect(f).connect(g).connect(bus(p0, p1, du, t, wet));
                    s.start(t); s.stop(t + du + 0.05);
                };

                const tone = (t, du, type, f0, f1, vol, p = 0, wet = 0.2) => {
                    const o = ac.createOscillator();
                    const g = ac.createGain();
                    o.type = type;
                    o.frequency.setValueAtTime(f0, t);
                    if (f1 !== f0) o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t + du * 0.7);

                    g.gain.setValueAtTime(0, t);
                    g.gain.linearRampToValueAtTime(vol, t + 0.008);
                    g.gain.exponentialRampToValueAtTime(0.001, t + du);

                    o.connect(g).connect(bus(p, p, du, t, wet));
                    o.start(t); o.stop(t + du + 0.05);
                };

                // Foley e Efeitos de Impacto
                const subImpact = (t, vol = 0.9) => {
                    tone(t, 1.4, 'sine', 130, 32, vol, 0, 0.25);
                    noise(t, 0.35, 'lowpass', 1200, 60, 0.45, 1, 0, 0, 0.3);
                };

                const whoosh = (t, du = 0.5, d = 1) => {
                    noise(t, du, 'bandpass', 240, 5600, 0.35, 1.3, -0.8 * d, 0.8 * d, 0.2);
                    tone(t, du, 'sine', 280, 1100, 0.06, 0, 0.2);
                };

                const riser = (t, du = 0.8) => {
                    noise(t, du, 'highpass', 350, 9500, 0.28, 1, -0.4, 0.4, 0.3);
                    tone(t, du, 'sine', 120, 1250, 0.14, 0, 0.35);
                };

                const pop = (t, k = 0, p = 0) => {
                    tone(t, 0.12, 'sine', 480 + k * 80, 1200 + k * 160, 0.22, p, 0.25);
                    tone(t + 0.01, 0.07, 'sine', 2500 + k * 220, 2500 + k * 220, 0.04, p, 0.35);
                };

                const click = t => {
                    noise(t, 0.025, 'highpass', 4000, 4000, 0.35, 1, 0, 0, 0.1);
                    tone(t, 0.05, 'sine', 2100, 900, 0.18, 0, 0.1);
                };

                const bell = (t, f, v = 0.15, p = 0) => {
                    tone(t, 1.8, 'sine', f, f, v, p, 0.55);
                    tone(t, 1.1, 'sine', f * 2.75, f * 2.75, v * 0.3, p, 0.55);
                };

                const chime = (t, notes = [523.25, 659.25, 783.99, 1046.5]) => {
                    notes.forEach((f, i) => bell(t + i * 0.075, f, 0.14, (i / (notes.length - 1) - 0.5) * 0.8));
                };

                const sparkle = (t, n = 8) => {
                    for (let i = 0; i < n; i++) {
                        tone(t + i * 0.045, 0.25, 'sine', 2200 + Math.random() * 3000, 2200 + Math.random() * 3000, 0.04, Math.random() * 1.6 - 0.8, 0.5);
                    }
                };

                const success = t => {
                    bell(t, 523.25, 0.15, -0.2);
                    bell(t + 0.08, 659.25, 0.15, 0);
                    bell(t + 0.16, 783.99, 0.18, 0.2);
                };

                // Trilha Musical Eletrónica Corporativa (BPM 118)
                const BPM = 118;
                const beat = 60 / BPM;
                const chords = [
                    [155.56, 196.00, 233.08, 293.66], // Eb maj7
                    [146.83, 174.61, 233.08, 293.66], // Bb / D
                    [130.81, 155.56, 196.00, 233.08], // Cm7
                    [116.54, 155.56, 196.00, 261.63]  // Ab add9
                ];
                const bassNotes = [77.78, 73.42, 65.41, 58.27]; // Eb, D, C, Ab

                // Pads atmosféricos contínuos
                chords.forEach((chord, cIdx) => {
                    chord.forEach((freq, fIdx) => {
                        const o = ac.createOscillator();
                        const g = ac.createGain();
                        o.type = 'sine';
                        o.frequency.value = freq * 2;

                        g.gain.setValueAtTime(0, t0);
                        g.gain.linearRampToValueAtTime(0.035, t0 + 2.0);
                        o.connect(g).connect(mus);
                        o.start(t0); o.stop(t0 + DURATION);
                    });
                });

                // Beat rítmico (Kick, Snare, Hi-hat, Bass, Plucks)
                for (let i = 0; i * beat < DURATION; i++) {
                    const t = t0 + i * beat;
                    if (t - t0 < TL[1] - 0.2) continue; // Começa na cena 1

                    const barIdx = Math.floor(i / 4) % 4;

                    // Kick nos tempos 1 e 3
                    if (i % 2 === 0) {
                        tone(t, 0.28, 'sine', 150, 38, 0.42, 0, 0);
                        noise(t, 0.02, 'lowpass', 800, 100, 0.15, 1, 0, 0, 0);
                    }

                    // Snare/Clap nos tempos 2 e 4
                    if (i % 4 === 2) {
                        noise(t, 0.15, 'bandpass', 1800, 1200, 0.22, 1.2, 0, 0, 0.25);
                        tone(t, 0.08, 'triangle', 220, 110, 0.18, 0, 0.15);
                    }

                    // Hi-hats em semicolcheias (16th notes)
                    for (let h = 0; h < 4; h++) {
                        const ht = t + h * (beat / 4);
                        const vol = h === 0 ? 0.08 : 0.04;
                        noise(ht, 0.03, 'highpass', 8500, 8500, vol, 1, 0.2 * (h % 2 ? 1 : -1), 0, 0.05);
                    }

                    // Linha de Baixo 808
                    tone(t, 0.38, 'sine', bassNotes[barIdx], bassNotes[barIdx] * 0.98, 0.32, 0, 0);

                    // Pluck Melódico Arpejado
                    const melNotes = [311.13, 349.23, 392.00, 466.16, 523.25, 622.25];
                    const note = melNotes[(i * 3 + (barIdx * 2)) % melNotes.length];
                    tone(t + beat / 2, 0.35, 'triangle', note, note, 0.09, Math.sin(i) * 0.6, 0.4);
                }

                // Sincronização dos Efeitos Sonoros com a Linha do Tempo
                const A = (i, x = 0) => t0 + TL[i] + x;

                // Transições principais entre cenas (Risers & Whooshes)
                for (let i = 1; i < 8; i++) {
                    riser(A(i, -0.75), 0.7);
                    whoosh(A(i, -0.2), 0.5, i % 2 ? 1 : -1);
                    subImpact(A(i, 0.05), 0.85);
                }

                // Cena 0: Intro
                subImpact(A(0, 0.1), 0.95);
                chime(A(0, 0.2), [523.25, 783.99, 1046.5]);
                sparkle(A(0, 1.2), 8);

                // Cena 1: Fibra em Casa
                [0.5, 1.1, 1.6].forEach((x, k) => bell(A(1, x), 1568, 0.1, k - 1));
                sparkle(A(1, 2.2), 6);
                pop(A(1, 3.5), 1);
                bell(A(1, 4.2), 1046.5, 0.12);

                // Cena 2: 5G Costa a Costa
                riser(A(2, 0.2), 1.2);
                [0.1, 0.6, 1.1, 1.6].forEach((x, k) => bell(A(2, x), 880 + k * 140, 0.12, -0.6 + k * 0.3));
                whoosh(A(2, 2.4), 0.6, 1);
                [2.8, 3.4, 4.0].forEach(x => click(A(2, x)));

                // Cena 3: TV e Streaming
                [0.2, 0.35, 0.5, 0.65, 0.8].forEach((x, k) => pop(A(3, x), k));
                chime(A(3, 1.4), [783.99, 987.77, 1318.5]);
                subImpact(A(3, 2.3), 0.75);

                // Cena 4: Business e IoT
                [0.4, 1.1, 1.8].forEach(x => { click(A(4, x)); tone(A(4, x), 0.2, 'sine', 110, 65, 0.35); });
                [2.4, 3.0, 3.6].forEach((x, k) => bell(A(4, x), 1400 + k * 120, 0.09, k % 2 ? 0.4 : -0.4));

                // Cena 5: O Meu Vodafone
                bell(A(5, 0.5), 1046.5, 0.12);
                success(A(5, 1.0)); // Fatura paga
                chime(A(5, 2.2), [783.99, 1046.5, 1318.5]); // Happy shake
                sparkle(A(5, 2.5), 10);
                pop(A(5, 3.8), 2); // Chat TOBi

                // Cena 6: Planos e Épocas
                subImpact(A(6, 0.1), 0.8);
                [0.7, 1.3, 1.9].forEach((x, k) => pop(A(6, x), k + 1));
                sparkle(A(6, 2.8), 8);

                // Cena 7: Final & CTA
                subImpact(A(7, 0.05), 1.0);
                chime(A(7, 0.15), [523.25, 659.25, 783.99, 1046.5, 1318.5]);
                sparkle(A(7, 0.8), 12);
                click(A(7, 1.4)); // Botão Aderir
            }

            // ---------- Controlador de Reprodução e Gravação ----------
            let raf = 0;
            const bar = document.querySelector('#bar i');
            const msg = $('msg');
            const setBusy = b => { $('play').disabled = $('rec').disabled = $('q').disabled = b; };
            const setRes = () => {
                const s = parseFloat($('q').value);
                canvas.width = Math.round(W * s);
                canvas.height = Math.round(H * s);
                render(2.0);
            };

            $('q').addEventListener('change', setRes);
            waImg.onload = vfImg.onload = () => render(2.0);

            function run(ac, t0, onEnd) {
                const step = () => {
                    const t = ac.currentTime - t0;
                    if (t >= DURATION) {
                        render(DURATION);
                        bar.style.width = '100%';
                        onEnd();
                        return;
                    }
                    render(Math.max(0, t));
                    bar.style.width = (t / DURATION * 100) + '%';
                    raf = requestAnimationFrame(step);
                };
                raf = requestAnimationFrame(step);
            }

            $('play').addEventListener('click', async () => {
                setBusy(true);
                msg.textContent = 'A reproduzir com áudio de alta definição…';
                const ac = new AudioContext();
                await ac.resume();
                const t0 = ac.currentTime + 0.12;
                buildAudio(ac, ac.destination, t0);
                run(ac, t0, () => {
                    ac.close();
                    setBusy(false);
                    msg.textContent = 'Reprodução concluída.';
                });
            });

            const pickMime = () => [
                'video/mp4;codecs=avc1.640028,mp4a.40.2',
                'video/mp4;codecs=avc1,mp4a.40.2',
                'video/mp4',
                'video/webm;codecs=vp9,opus',
                'video/webm;codecs=vp8,opus',
                'video/webm'
            ].find(m => window.MediaRecorder && MediaRecorder.isTypeSupported(m)) || '';

            async function recLive() {
                if (!window.MediaRecorder) {
                    alert('Este navegador não suporta gravação direta.');
                    return;
                }
                const mime = pickMime(), ext = mime.startsWith('video/mp4') ? 'mp4' : 'webm';
                setBusy(true);
                msg.textContent = `A gravar em ${ext.toUpperCase()}… Não mude de separador.`;
                const ac = new AudioContext();
                await ac.resume();
                const dest = ac.createMediaStreamDestination();
                const stream = new MediaStream([
                    ...canvas.captureStream(FPS).getVideoTracks(),
                    ...dest.stream.getAudioTracks()
                ]);
                const rec = new MediaRecorder(stream, {
                    mimeType: mime || undefined,
                    videoBitsPerSecond: canvas.width >= 1080 ? 25e6 : 15e6,
                    audioBitsPerSecond: 256e3
                });
                const chunks = [];
                rec.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
                rec.onstop = () => {
                    const blob = new Blob(chunks, { type: mime ? mime.split(';')[0] : 'video/webm' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url; a.download = `vodafone_portugal.${ext}`;
                    document.body.appendChild(a); a.click(); a.remove();
                    msg.innerHTML = `Vídeo pronto (${(blob.size / 1048576).toFixed(1)} MB). <a href="${url}" download="vodafone_portugal.${ext}">Clique aqui se o download não iniciou</a>.`;
                    setTimeout(() => URL.revokeObjectURL(url), 600000);
                    ac.close();
                    setBusy(false);
                };
                const t0 = ac.currentTime + 0.35;
                buildAudio(ac, dest, t0);
                rec.start(1000);
                run(ac, t0, () => setTimeout(() => rec.stop(), 300));
            }

            async function exportMp4() {
                if (!window.VideoEncoder || !window.AudioEncoder || !window.OfflineAudioContext) {
                    return recLive();
                }
                setBusy(true);
                let fail = null;
                try {
                    msg.textContent = 'A inicializar codificador de vídeo MP4…';
                    const { Muxer, ArrayBufferTarget } = await import('https://cdn.jsdelivr.net/npm/mp4-muxer@5/+esm');

                    let cfg = null;
                    for (const [s, fps, bitrate] of [
                        [1, 60, 35e6], [1, 60, 22e6], [1, 30, 20e6],
                        [0.667, 60, 16e6], [0.667, 30, 12e6]
                    ]) {
                        const width = Math.round(W * s / 2) * 2;
                        const height = Math.round(H * s / 2) * 2;
                        const codec = 'avc1.64002A';
                        if ((await VideoEncoder.isConfigSupported({
                            codec, width, height, bitrate, framerate: fps, latencyMode: 'quality'
                        })).supported) {
                            cfg = { codec, width, height, bitrate, fps };
                            break;
                        }
                    }
                    if (!cfg) throw new Error('O navegador não suporta codificação H.264.');

                    const SR = 48000;
                    msg.textContent = 'A renderizar áudio e efeitos sonoros com qualidade de estúdio…';
                    const oc = new OfflineAudioContext(2, SR * DURATION, SR);
                    buildAudio(oc, oc.destination, 0);
                    const ab = await oc.startRendering();

                    let acodec = 'mp4a.40.2';
                    if (!(await AudioEncoder.isConfigSupported({ codec: acodec, sampleRate: SR, numberOfChannels: 2, bitrate: 256e3 })).supported) {
                        acodec = 'opus';
                    }

                    const target = new ArrayBufferTarget();
                    const muxer = new Muxer({
                        target,
                        video: { codec: 'avc', width: cfg.width, height: cfg.height, frameRate: cfg.fps },
                        audio: { codec: acodec === 'opus' ? 'opus' : 'aac', sampleRate: SR, numberOfChannels: 2 },
                        fastStart: 'in-memory',
                        firstTimestampBehavior: 'offset'
                    });

                    const aenc = new AudioEncoder({
                        output: (c, m) => muxer.addAudioChunk(c, m),
                        error: e => { fail = e; }
                    });
                    aenc.configure({ codec: acodec, sampleRate: SR, numberOfChannels: 2, bitrate: 256e3 });

                    const L = ab.getChannelData(0);
                    const R = ab.getChannelData(1);
                    const N = ab.length;
                    for (let o = 0; o < N; o += 24000) {
                        const n = Math.min(24000, N - o);
                        const d = new Float32Array(n * 2);
                        d.set(L.subarray(o, o + n), 0);
                        d.set(R.subarray(o, o + n), n);
                        aenc.encode(new AudioData({
                            format: 'f32-planar', sampleRate: SR,
                            numberOfFrames: n, numberOfChannels: 2,
                            timestamp: Math.round(o / SR * 1e6), data: d
                        }));
                    }
                    await aenc.flush();

                    const venc = new VideoEncoder({
                        output: (c, m) => muxer.addVideoChunk(c, m),
                        error: e => { fail = e; }
                    });
                    venc.configure({
                        codec: cfg.codec, width: cfg.width, height: cfg.height,
                        bitrate: cfg.bitrate, framerate: cfg.fps, latencyMode: 'quality'
                    });

                    canvas.width = cfg.width;
                    canvas.height = cfg.height;
                    const total = Math.round(DURATION * cfg.fps);
                    const us = 1e6 / cfg.fps;

                    for (let i = 0; i < total; i++) {
                        if (fail) throw fail;
                        render(i / cfg.fps);
                        const fr = new VideoFrame(canvas, { timestamp: Math.round(i * us), duration: Math.round(us) });
                        venc.encode(fr, { keyFrame: i % (cfg.fps * 2) === 0 });
                        fr.close();

                        if (i % 4 === 0) {
                            bar.style.width = (i / total * 100) + '%';
                            msg.textContent = `A renderizar quadro ${i}/${total} (${cfg.width}×${cfg.height}, ${cfg.fps} fps)…`;
                            await new Promise(r => setTimeout(r));
                        }
                        while (venc.encodeQueueSize > 6) await new Promise(r => setTimeout(r, 5));
                    }
                    await venc.flush();
                    if (fail) throw fail;
                    muxer.finalize();

                    const blob = new Blob([target.buffer], { type: 'video/mp4' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url; a.download = 'vodafone_portugal_5g_fibra.mp4';
                    document.body.appendChild(a); a.click(); a.remove();
                    msg.innerHTML = `Vídeo MP4 gerado com sucesso! (${(blob.size / 1048576).toFixed(1)} MB). <a href="${url}" download="vodafone_portugal_5g_fibra.mp4">Clique aqui para descarregar</a>.`;
                    bar.style.width = '100%';
                } catch (e) {
                    console.error(e);
                    msg.textContent = 'Erro ao exportar: ' + (e && e.message ? e.message : e);
                }
                setRes();
                setBusy(false);
            }

            $('rec').onclick = exportMp4;
            setRes();
        })();
    </script>
</body>

</html>
'''

with open('edjair.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"Successfully updated edjair.html! New size: {len(html_content)} bytes.")
