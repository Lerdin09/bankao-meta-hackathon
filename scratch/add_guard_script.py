with open('frontend/partials/layout/scripts.html', 'r', encoding='utf-8') as f:
    text = f.read()

target = '<script src="/static/js/core/confirm-dialog.js"></script>'
replacement = '<script src="/static/js/core/confirm-dialog.js"></script>\n<script src="/static/js/core/mobile-app-guard.js"></script>'

assert target in text
text = text.replace(target, replacement, 1)

with open('frontend/partials/layout/scripts.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("Script added successfully")

