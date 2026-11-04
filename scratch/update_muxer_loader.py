with open('edjair.html', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add mp4-muxer script tag to head if not present
old_head = 'family=Poppins:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,700;1,900&display=swap" rel="stylesheet">'
new_head = old_head + '\n    <script src="https://cdn.jsdelivr.net/npm/mp4-muxer@5/build/mp4-muxer.min.js"></script>'

if old_head in text and 'mp4-muxer.min.js' not in text:
    text = text.replace(old_head, new_head)
    print('Added mp4-muxer script tag to <head>')

# 2. Update Muxer resolution in exportMp4
old_muxer_import = """                    msg.textContent = 'A inicializar codificador de vídeo MP4…';
                    const { Muxer, ArrayBufferTarget } = await import('https://cdn.jsdelivr.net/npm/mp4-muxer@5/+esm');

                    let cfg = null;
                    for (const [s, fps, bitrate] of [
                        [1, 60, 35e6], [1, 60, 22e6], [1, 30, 20e6],
                        [0.667, 60, 16e6], [0.667, 30, 12e6]
                    ]) {"""

new_muxer_import = """                    msg.textContent = 'A inicializar codificador de vídeo MP4…';
                    let Muxer = window.Mp4Muxer?.Muxer;
                    let ArrayBufferTarget = window.Mp4Muxer?.ArrayBufferTarget;
                    if (!Muxer || !ArrayBufferTarget) {
                        try {
                            const mod = await import('https://cdn.jsdelivr.net/npm/mp4-muxer@5/+esm');
                            Muxer = mod.Muxer;
                            ArrayBufferTarget = mod.ArrayBufferTarget;
                        } catch (err) {
                            console.warn('Falha no import dinâmico ESM do mp4-muxer:', err);
                        }
                    }
                    if (!Muxer || !ArrayBufferTarget) {
                        return recLive();
                    }

                    const userScale = parseFloat($('q')?.value || 1);
                    let cfg = null;
                    const candidates = [
                        [userScale, 60, Math.round(32e6 * userScale)],
                        [userScale, 30, Math.round(20e6 * userScale)],
                        [1, 60, 35e6], [1, 30, 20e6],
                        [0.667, 60, 16e6], [0.667, 30, 12e6],
                        [0.5, 30, 8e6]
                    ];
                    const seen = new Set();
                    const profiles = [];
                    for (const c of candidates) {
                        const key = c[0] + '_' + c[1];
                        if (!seen.has(key)) {
                            seen.add(key);
                            profiles.push(c);
                        }
                    }

                    for (const [s, fps, bitrate] of profiles) {"""

if old_muxer_import in text:
    text = text.replace(old_muxer_import, new_muxer_import)
    print('Updated Muxer loader and candidate profiles!')
else:
    print('old_muxer_import not matched!')

with open('edjair.html', 'w', encoding='utf-8', newline='') as f:
    f.write(text)

print('File updated successfully!')

