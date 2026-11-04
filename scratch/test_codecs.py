import subprocess, os, re

chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
html = '''<!DOCTYPE html><html><body><div id="res"></div><script>
(async () => {
    const list = [
        'mp4a.40.2', 'mp4a.40.02', 'mp4a.40.5', 'mp4a.40.29', 'mp4a.67', 'aac',
        'audio/aac', 'audio/mp4', 'mp4a', 'flac', 'pcm', 'pcm-f32', 'alac'
    ];
    let supp = [];
    for (let c of list) {
        try {
            let r = await AudioEncoder.isConfigSupported({ codec: c, sampleRate: 48000, numberOfChannels: 2 });
            if (r.supported) supp.push(c);
        } catch(e) {}
    }
    document.getElementById('res').innerText = JSON.stringify(supp);
})();
</script></body></html>'''

with open('test_codecs.html', 'w', encoding='utf-8') as f:
    f.write(html)

res = subprocess.run([chrome, '--headless=new', 'file:///' + os.path.abspath('test_codecs.html'), '--dump-dom'], capture_output=True, text=True, timeout=10)
m = re.search(r'<div id="res">([^<]*)</div>', res.stdout)
print('Supported audio codecs in WebCodecs:', m.group(1) if m else 'None')

