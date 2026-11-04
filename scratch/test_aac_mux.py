import subprocess, os, re

chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
html = '''<!DOCTYPE html><html><body><div id="res"></div><script>
(async () => {
    try {
        const { Muxer, ArrayBufferTarget } = await import('https://cdn.jsdelivr.net/npm/mp4-muxer@5/+esm');
        const SR = 48000;
        const target = new ArrayBufferTarget();
        const muxer = new Muxer({
            target,
            video: { codec: 'avc', width: 320, height: 240, frameRate: 30 },
            audio: { codec: 'aac', sampleRate: SR, numberOfChannels: 2 },
            fastStart: 'in-memory'
        });
        
        let chunkCount = 0;
        let lastErr = null;
        const aenc = new AudioEncoder({
            output: (c, m) => { chunkCount++; muxer.addAudioChunk(c, m); },
            error: e => { lastErr = e.message; }
        });
        
        await aenc.configure({ codec: 'mp4a.40.2', sampleRate: SR, numberOfChannels: 2, bitrate: 192000 });
        
        // Feed 1 second of audio
        const n = 48000;
        const d = new Float32Array(n * 2);
        for (let i = 0; i < n; i++) {
            d[i] = Math.sin(2 * Math.PI * 440 * i / SR);
            d[n + i] = Math.sin(2 * Math.PI * 440 * i / SR);
        }
        
        aenc.encode(new AudioData({
            format: 'f32-planar',
            sampleRate: SR,
            numberOfFrames: n,
            numberOfChannels: 2,
            timestamp: 0,
            data: d
        }));
        await aenc.flush();
        
        // Feed 1 video frame
        const cv = document.createElement('canvas'); cv.width = 320; cv.height = 240;
        const ctx = cv.getContext('2d'); ctx.fillStyle = 'red'; ctx.fillRect(0,0,320,240);
        
        const venc = new VideoEncoder({
            output: (c, m) => { muxer.addVideoChunk(c, m); },
            error: e => { lastErr = e.message; }
        });
        venc.configure({ codec: 'avc1.64001F', width: 320, height: 240, bitrate: 1e6, framerate: 30 });
        const vf = new VideoFrame(cv, { timestamp: 0, duration: 1e6 / 30 });
        venc.encode(vf, { keyFrame: true });
        vf.close();
        await venc.flush();
        
        muxer.finalize();
        const size = target.buffer.byteLength;
        
        // Check if 'mp4a' box is in buffer
        const bytes = new Uint8Array(target.buffer);
        let hasMp4a = false;
        for (let i = 0; i < bytes.length - 4; i++) {
            if (bytes[i] === 109 && bytes[i+1] === 112 && bytes[i+2] === 52 && bytes[i+3] === 97) { // 'mp4a'
                hasMp4a = true; break;
            }
        }
        
        document.getElementById('res').innerText = JSON.stringify({
            success: true,
            chunkCount,
            size,
            hasMp4a,
            error: lastErr
        });
    } catch(e) {
        document.getElementById('res').innerText = JSON.stringify({ error: e.message });
    }
})();
</script></body></html>'''

with open('test_aac_mux.html', 'w', encoding='utf-8') as f:
    f.write(html)

res = subprocess.run([chrome, '--headless=new', 'file:///' + os.path.abspath('test_aac_mux.html'), '--dump-dom'], capture_output=True, text=True, timeout=12)
m = re.search(r'<div id="res">([^<]*)</div>', res.stdout)
print('AAC Muxing Test Result:', m.group(1) if m else 'None')

