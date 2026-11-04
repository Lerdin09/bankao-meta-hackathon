import subprocess, os, re, base64

chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
html = '''<!DOCTYPE html><html><body><div id="res">INIT</div><script>
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

        const aenc = new AudioEncoder({
            output: (c, m) => muxer.addAudioChunk(c, m),
            error: e => console.error('AENC_ERR', e)
        });
        aenc.configure({ codec: 'mp4a.40.2', sampleRate: SR, numberOfChannels: 2, bitrate: 192000 });

        // 1 second of 440Hz sine wave (multiple of 1024: 48 * 1024 = 49152 samples)
        const N = 49152;
        const d = new Float32Array(N * 2);
        for (let i = 0; i < N; i++) {
            d[i] = Math.sin(2 * Math.PI * 440 * i / SR) * 0.3;
            d[N + i] = Math.sin(2 * Math.PI * 440 * i / SR) * 0.3;
        }

        aenc.encode(new AudioData({
            format: 'f32-planar', sampleRate: SR,
            numberOfFrames: N, numberOfChannels: 2,
            timestamp: 0, data: d
        }));
        await aenc.flush();

        const cv = document.createElement('canvas'); cv.width = 320; cv.height = 240;
        const ctx = cv.getContext('2d');
        ctx.fillStyle = '#e60000'; ctx.fillRect(0, 0, 320, 240);

        const venc = new VideoEncoder({
            output: (c, m) => muxer.addVideoChunk(c, m),
            error: e => console.error('VENC_ERR', e)
        });
        venc.configure({ codec: 'avc1.64001F', width: 320, height: 240, bitrate: 1e6, framerate: 30 });

        for (let i = 0; i < 30; i++) {
            const vf = new VideoFrame(cv, { timestamp: Math.round(i * 1e6 / 30), duration: Math.round(1e6 / 30) });
            venc.encode(vf, { keyFrame: i === 0 });
            vf.close();
        }
        await venc.flush();

        muxer.finalize();
        const bytes = new Uint8Array(target.buffer);
        let hasMp4a = false;
        for (let i = 0; i < bytes.length - 4; i++) {
            if (bytes[i] === 109 && bytes[i+1] === 112 && bytes[i+2] === 52 && bytes[i+3] === 97) {
                hasMp4a = true; break;
            }
        }
        document.getElementById('res').innerText = 'OK size=' + bytes.length + ' mp4a=' + hasMp4a;
    } catch(e) {
        document.getElementById('res').innerText = 'ERR: ' + e.message;
    }
})();
</script></body></html>'''

with open('scratch/test_pipeline.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('File written. Testing with chrome...')

