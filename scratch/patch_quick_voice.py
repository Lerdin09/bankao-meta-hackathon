with open('frontend/js/features/copilot/copilot-voice.js', 'r', encoding='utf-8') as f:
    content = f.read()

target = 'window.copilotSpeak("Ólá! Como posso ajudar hoje?", _resumeListening);'
replacement = """window.copilotSpeak("Ólá! Como posso ajudar hoje?", _resumeListening);

    // Se o reconhecimento nativo não estiver ativo (ex: mobile HTTP), mostra atalhos de voz imediatos
    if (!recognition) {
      _setStatus("Assistente de voz ativo (Toque para falar ou perguntar):");
      if (transcriptEl) {
        transcriptEl.innerHTML = `
          <div style="font-size:13px;color:var(--text-2);margin-bottom:8px;">Escolha uma pergunta por voz ou escreva no chat:</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:center;">
            <button type="button" class="chip-btn green" style="cursor:pointer;" onclick="window._copilotSendQuickVoice('Qual é o meu saldo atual?')">💰 Ver saldo</button>
            <button type="button" class="chip-btn" style="cursor:pointer;" onclick="window._copilotSendQuickVoice('Quero fazer uma transferência')">💸 Transferir</button>
            <button type="button" class="chip-btn" style="cursor:pointer;" onclick="window._copilotSendQuickVoice('Quais são as taxas de câmbio actuais?')">💱 Câmbio</button>
            <button type="button" class="chip-btn" style="cursor:pointer;" onclick="window._copilotSendQuickVoice('Como depositar com Multicaixa Express?')">⚡ Depósito MCX</button>
          </div>
        `;
      }
    }"""

content = content.replace(target, replacement)

# Add window._copilotSendQuickVoice helper
export_target = 'window._copilotVoiceCloseSession = _closeVoiceSession;'
export_rep = """window._copilotVoiceCloseSession = _closeVoiceSession;
  window._copilotSendQuickVoice = function (text) {
    if (text) _sendVoiceMessage(text);
  };"""

content = content.replace(export_target, export_rep)

with open('frontend/js/features/copilot/copilot-voice.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("Quick voice support added!")

