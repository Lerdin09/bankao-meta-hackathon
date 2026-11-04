import subprocess, os, re

chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
html = '''<!DOCTYPE html><html><body><div id="res">LOADING</div><script>
(async () => {
    try {
        const mod = await import('https://cdn.jsdelivr.net/npm/@audio/encode-aac@1.2.1/aac-encode.js');
        const aac = mod.default;
        const enc = await aac({ sampleRate: 48000, channels: 2, bitrate: 192 });
        const pcm = new Float32Array(48000 * 2);
        for (let i = 0; i < pcm.length; i++) pcm[i] = Math.sin(i * 0.05);
        const out1 = await enc.encode(pcm);
        const out2 = await enc.flush();
        document.getElementById('res').innerText = 'OK: out1=' + out1.length + ', out2=' + out2.length;
    } catch(e) {
        document.getElementById('res').innerText = 'ERR: ' + e.message;
    }
})();
</script></body></html>'''

with open('test_aac_chrome.html', 'w', encoding='utf-8') as f:
    f.write(html)

res = subprocess.run([chrome, '--headless=new', 'file:///' + os.path.abspath('test_aac_chrome.html'), '--dump-dom'], capture_output=True, text=True, timeout=12)
m = re.search(r'<div id="res">([^<]+)</div>', res.stdout)
print('Result in Chrome:', m.group(1) if m else 'None')

