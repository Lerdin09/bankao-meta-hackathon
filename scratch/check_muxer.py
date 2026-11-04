import urllib.request, re

url = 'https://cdn.jsdelivr.net/npm/mp4-muxer@5/build/mp4-muxer.mjs'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as resp:
    text = resp.read().decode('utf-8')

matches = re.findall(r'audio\.codec\s*===?\s*[\'"](\w+)[\'"]', text)
print('Audio codecs:', set(matches))

