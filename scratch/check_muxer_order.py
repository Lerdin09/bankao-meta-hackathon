import urllib.request, re

url = 'https://cdn.jsdelivr.net/npm/mp4-muxer@5/build/mp4-muxer.mjs'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as resp:
    text = resp.read().decode('utf-8')

for m in re.finditer(r'.{0,150}timestamp.{0,150}', text):
    line = m.group(0).strip()
    if 'addAudioChunk' in line or 'addVideoChunk' in line or 'order' in line or 'interleav' in line:
        print('-->', line)

