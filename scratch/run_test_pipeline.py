import subprocess, os, re, time

chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
html_path = os.path.abspath('scratch/test_pipeline.html')

res = subprocess.run([
    chrome,
    '--headless=new',
    '--enable-logging=stderr',
    '--v=1',
    'file:///' + html_path,
    '--dump-dom'
], capture_output=True, text=True, timeout=10)

m = re.search(r'<div id="res">(.*?)</div>', res.stdout)
if m:
    print('Result:', m.group(1))
else:
    print('Could not find res div. stdout snippet:', res.stdout[:300])

