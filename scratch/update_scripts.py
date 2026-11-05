import re

with open('frontend/partials/layout/scripts.html', 'r', encoding='utf-8') as f:
    content = f.read()

target = '<script src="/static/js/core/config.js"></script>'
replacement = '<script src="/static/js/data/countries.js"></script>\n<script src="/static/js/core/config.js"></script>'

if target in content:
    content = content.replace(target, replacement, 1)
    with open('frontend/partials/layout/scripts.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success updating scripts.html")
else:
    print("Target not found")
