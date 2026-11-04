import subprocess, os, re

chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
html = '''<!DOCTYPE html><html><body><div id="res"></div><script>
(async () => {
    const bitrates = [64000, 96000, 128000, 160000, 192000, 256000, 320000];
    let supp = [];
    for (let b of bitrates) {
        try {
            let r = await AudioEncoder.isConfigSupported({ codec: 'mp4a.40.2', sampleRate: 48000, numberOfChannels: 2, bitrate: b });
            if (r.supported) supp.push(b);
        } catch(e) {}
    }
    document.getElementById('res').innerText = JSON.stringify(supp);
})();
</script></body></html>'''

with open('test_bitrates.html', 'w', encoding='utf-8') as f:
    f.write(html)

res = subprocess.run([chrome, '--headless=new', 'file:///' + os.path.abspath('test_bitrates.html'), '--dump-dom'], capture_output=True, text=True, timeout=10)
m = re.search(r'<div id="res">([^<]*)</div>', res.stdout)
print('Supported bitrates for mp4a.40.2:', m.group(1) if m else 'None')

