import subprocess, os, re

chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
html = '''<!DOCTYPE html><html><body><div id="res">LOADING</div><script>
(async () => {
    try {
        const SR = 48000;
        const oc = new OfflineAudioContext(2, SR * 2, SR);
        const osc = oc.createOscillator();
        osc.frequency.value = 440;
        osc.connect(oc.destination);
        osc.start(0);
        const ab = await oc.startRendering();
        
        let chunksCount = 0;
        let lastErr = null;
        const aenc = new AudioEncoder({
            output: (chunk, meta) => { chunksCount++; },
            error: e => { lastErr = e.message; }
        });
        
        aenc.configure({ codec: 'opus', sampleRate: SR, numberOfChannels: 2, bitrate: 128000 });
        
        const L = ab.getChannelData(0), R = ab.getChannelData(1), N = ab.length;
        for (let o = 0; o < N; o += 24000) {
            const n = Math.min(24000, N - o);
            const d = new Float32Array(n * 2);
            d.set(L.subarray(o, o + n), 0);
            d.set(R.subarray(o, o + n), n);
            aenc.encode(new AudioData({
                format: 'f32-planar',
                sampleRate: SR,
                numberOfFrames: n,
                numberOfChannels: 2,
                timestamp: Math.round(o / SR * 1e6),
                data: d
            }));
        }
        await aenc.flush();
        document.getElementById('res').innerText = 'CHUNKS: ' + chunksCount + ', ERR: ' + lastErr;
    } catch(e) {
        document.getElementById('res').innerText = 'EXCEPTION: ' + e.message;
    }
})();
</script></body></html>'''

with open('test_aenc.html', 'w', encoding='utf-8') as f:
    f.write(html)

res = subprocess.run([chrome, '--headless=new', 'file:///' + os.path.abspath('test_aenc.html'), '--dump-dom'], capture_output=True, text=True, timeout=10)
m = re.search(r'<div id="res">([^<]+)</div>', res.stdout)
print('AudioEncoder result:', m.group(1) if m else 'None')

