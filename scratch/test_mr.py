import subprocess, os, base64, re

chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
html = '''<!DOCTYPE html><html><body><script>
(async () => {
    const cv = document.createElement('canvas'); cv.width = 64; cv.height = 64;
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
        ctx.fillRect(0, 0, 64, 64);
    }, 33);
    
    rec.start(100);
    await new Promise(r => setTimeout(r, 1200));
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
})();
</script></body></html>'''

with open('test_mr_file.html', 'w', encoding='utf-8') as f:
    f.write(html)

res = subprocess.run([chrome, '--headless=new', '--virtual-time-budget=3000', '--dump-dom', 'file:///' + os.path.abspath('test_mr_file.html')], capture_output=True, text=True, timeout=10)
m = re.search(r'<div id="data">([A-Za-z0-9+/=]+)</div>', res.stdout)
if m:
    data = base64.b64decode(m.group(1))
    print('MP4 created! Size:', len(data))
    print('Has mp4a (AAC):', b'mp4a' in data)
    print('Has opus:', b'Opus' in data or b'opus' in data)
    print('Has avc1:', b'avc1' in data)
else:
    print('No data found in DOM.')

