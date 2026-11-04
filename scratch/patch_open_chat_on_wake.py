"""
Patch: Ao activar a sessão de voz por wake word,
       abre o painel do chat do Copilot (mobile) e faz scroll (desktop).
"""
import re

FILE = "frontend/js/features/copilot/copilot-voice.js"

with open(FILE, "rb") as f:
    raw = f.read()

# Detectar a função _openVoiceSession — procurar pela assinatura
marker_start = b"function _openVoiceSession() {"
marker_end   = b"function _closeVoiceSession() {"

idx_start = raw.find(marker_start)
idx_end   = raw.find(marker_end)

if idx_start == -1 or idx_end == -1:
    raise RuntimeError("Não encontrei _openVoiceSession / _closeVoiceSession no ficheiro!")

old_func = raw[idx_start:idx_end]

new_func = (
    b"function _openVoiceSession() {\r\n"
    b"    isWakeMode = false;\r\n"
    b"    _unlockAudioOnFirstGesture();\r\n"
    b"\r\n"
    b"    // Abrir o chat do Copilot ao activar por voz (wake word)\r\n"
    b"    var isWide = window.matchMedia(\"(min-width: 1024px)\").matches;\r\n"
    b"    if (!isWide && typeof window.openCopilot === \"function\") {\r\n"
    b"      // Mobile/tablet: abre o painel do chat sobre a p\xc3\xa1gina actual\r\n"
    b"      window.openCopilot();\r\n"
    b"    }\r\n"
    b"    // Scroll para o fim das mensagens (desktop e mobile)\r\n"
    b"    setTimeout(function () {\r\n"
    b"      var box = document.getElementById(\"copilotChatMessages\");\r\n"
    b"      if (box) box.scrollTop = box.scrollHeight;\r\n"
    b"    }, 150);\r\n"
    b"\r\n"
    b"    _showOverlay();\r\n"
    b"    _setOrbState(\"listening\");\r\n"
    b"    _setStatus(\"\xc3\x80 ouvir com aten\xc3\xa7\xc3\xa3o\xe2\x80\xa6\");\r\n"
    b"    _resetBuffers();\r\n"
    b"    _startAudioVisualizer();\r\n"
    b"\r\n"
    b"    if (micBtn) micBtn.classList.add(\"mic-active\");\r\n"
    b"    if (floatingBtn) floatingBtn.classList.add(\"v-float-active\");\r\n"
    b"\r\n"
    b"    awaitingReply = false;\r\n"
    b"    editing = false;\r\n"
    b"    _applyEditUi(false);\r\n"
    b"    window.copilotSpeak(\"\xc3\x93l\xc3\xa1! Como posso ajudar hoje?\", _resumeListening);\r\n"
    b"  }\r\n"
    b"\r\n"
    b"  "  # indentation before next function
)

new_raw = raw[:idx_start] + new_func + raw[idx_end:]

with open(FILE, "wb") as f:
    f.write(new_raw)

print("Patch aplicado com sucesso!")
print(f"  Função antiga: {len(old_func)} bytes")
print(f"  Função nova:   {len(new_func)} bytes")
