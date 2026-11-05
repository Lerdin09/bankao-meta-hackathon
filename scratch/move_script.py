with open('frontend/partials/layout/scripts.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('<script src="/static/js/data/countries.js"></script>\r\n', '')
text = text.replace('<script src="/static/js/data/countries.js"></script>\n', '')
target = '<script src="/static/js/core/confirm-dialog.js"></script>'
replacement = '<script src="/static/js/core/confirm-dialog.js"></script>\n<script src="/static/js/data/countries.js"></script>'
if target in text:
    text = text.replace(target, replacement, 1)
    with open('frontend/partials/layout/scripts.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Moved successfully')
else:
    print('Target not found')

