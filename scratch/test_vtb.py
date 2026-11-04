import subprocess, os, re, base64

chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
res = subprocess.run([chrome, '--headless=new', '--virtual-time-budget=4000', 'file:///' + os.path.abspath('test_mr_real.html'), '--dump-dom'], capture_output=True, text=True, timeout=10)
m = re.search(r'<div id="data">([A-Za-z0-9+/=]+)</div>', res.stdout)
if m:
    data = base64.b64decode(m.group(1))
    print('SUCCESS! MP4 Size:', len(data))
    print('Has mp4a (AAC):', b'mp4a' in data)
    print('Has avc1 (H.264):', b'avc1' in data)
else:
    err = re.search(r'<div id="err">([^<]+)</div>', res.stdout)
    print('Err:', err.group(1) if err else 'None', 'stdout snippet:', res.stdout[:200])

