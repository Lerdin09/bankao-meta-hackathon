import subprocess, os

chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
html = '''<!DOCTYPE html><html><body><script>
(async () => {
    try {
        const DURATION = 36.0;
        const SR = 48000;
        const TL = [0, 4.5, 9.0, 13.5, 18.0, 22.5, 27.0, 31.5];
        const clamp = (v, min = 0, max = 1) => Math.min(max, Math.max(min, v));
        const oc = new OfflineAudioContext(2, SR * 5, SR); // test 5 sec render

        // insert buildAudio definition
'''

# Let's extract buildAudio from edjair.html
with open('edjair.html', 'r', encoding='utf-8') as f:
    code = f.read()

s_idx = code.find('function buildAudio(ac, out, t0)')
e_idx = code.find('// ---------- Controlador de Reprodução', s_idx)
build_audio_code = code[s_idx:e_idx]

html += build_audio_code + '''
        buildAudio(oc, oc.destination, 0);
        const ab = await oc.startRendering();
        console.error('OFFLINE_RENDER_SUCCESS: channels=' + ab.numberOfChannels + ', len=' + ab.length);
    } catch(e) {
        console.error('OFFLINE_RENDER_FAIL: ' + e.name + ' - ' + e.message + '\\n' + e.stack);
    } finally {
        window.close();
    }
})();
</script></body></html>'''

with open('scratch/test_offline_audio.html', 'w', encoding='utf-8') as f:
    f.write(html)

res = subprocess.run([chrome, '--headless=new', '--enable-logging=stderr', 'file:///' + os.path.abspath('scratch/test_offline_audio.html')], capture_output=True, text=True, timeout=10)
for l in res.stderr.splitlines():
    if 'OFFLINE_RENDER' in l:
        print(l)

