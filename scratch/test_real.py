import subprocess, os, re, base64

chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
html = '''<!DOCTYPE html><html><body><script>
(async () => {
    try {
        const cv = document.createElement('canvas'); cv.width = 120; cv.height = 120;
        const ctx = cv.getContext('2d');
        const ac = new AudioContext();
        await ac.resume();
        const dest = ac.createMediaStreamDestination();
        const osc = ac.createOscillator();
        osc.frequency.value = 440;
        osc.connect(dest);
        osc.start();

        const stream = new MediaStream([
            ...cv.captureStream(30).getVideoTracks(),
            ...dest.stream.getAudioTracks()
        ]);
        
        let mime = 'video/mp4;codecs=avc1,mp4a.40.2';
        if (!MediaRecorder.isTypeSupported(mime)) mime = 'video/mp4';
        
        const rec = new MediaRecorder(stream, { mimeType: mime });
        const chunks = [];
        rec.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
        
        let frames = 0;
        const iv = setInterval(() => {
            ctx.fillStyle = (frames++ % 2) ? '#f00' : '#00f';
            ctx.fillRect(0, 0, 120, 120);
        }, 33);
        
        rec.start(100);
        await new Promise(r => setTimeout(r, 1500));
        clearInterval(iv);
        rec.stop();
        await new Promise(r => rec.onstop = r);
        
        const blob = new Blob(chunks, { type: mime });
        const buf = await blob.arrayBuffer();
        let bin = '';
        const bytes = new Uint8Array(buf);
        for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
        const b64 = btoa(bin);
        
        const d = document.createElement('div');
        d.id = 'data';
        d.innerText = b64;
        document.body.appendChild(d);
    } catch(err) {
        const d = document.createElement('div');
        d.id = 'err';
        d.innerText = err.message;
        document.body.appendChild(d);
    }
})();
</script></body></html>'''

with open('test_mr_real.html', 'w', encoding='utf-8') as f:
    f.write(html)

res = subprocess.run([chrome, '--headless=new', 'file:///' + os.path.abspath('test_mr_real.html'), '--dump-dom'], capture_output=True, text=True, timeout=10)
m = re.search(r'<div id="data">([A-Za-z0-9+/=]+)</div>', res.stdout)
if m:
    data = base64.b64decode(m.group(1))
    print('SUCCESS! MP4 Size:', len(data))
    print('Has mp4a (AAC):', b'mp4a' in data)
    print('Has avc1 (H.264):', b'avc1' in data)
    print('Has opus:', b'Opus' in data or b'opus' in data)
else:
    err = re.search(r'<div id="err">([^<]+)</div>', res.stdout)
    print('Failed. Error:', err.group(1) if err else 'None', 'Output len:', len(res.stdout))

