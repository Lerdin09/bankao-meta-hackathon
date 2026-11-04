with open('frontend/js/features/copilot/copilot-voice.js', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

# Substituir selecao de voz
old_selection = '''  function _getBestCalmVoice() {
    if (!_cachedVoices.length && window.speechSynthesis) {
      _cachedVoices = window.speechSynthesis.getVoices();
    }
    // Preferência por vozes neurais / calmas em português
    const preferredNames = ["Google português", "Luciana", "Joana", "Francisca", "Raquel", "Maria", "Yelda", "Helena"];
    for (const name of preferredNames) {
      const match = _cachedVoices.find(v => v.lang.startsWith("pt") && v.name.includes(name));
      if (match) return match;
    }
    // Fallback: qualquer voz pt-PT ou pt-BR
    return _cachedVoices.find(v => v.lang === "pt-PT") ||
           _cachedVoices.find(v => v.lang.startsWith("pt")) ||
           null;
  }'''

new_selection = '''  function _getBestCalmVoice() {
    if (!_cachedVoices.length && window.speechSynthesis) {
      _cachedVoices = window.speechSynthesis.getVoices();
    }
    // Prioridade para vozes neurais de alta definicao (Microsoft Natural, Google Neural, Apple Siri)
    const priorityNames = [
      "Microsoft Duarte Online (Natural) - Portuguese (Portugal)",
      "Microsoft Raquel Online (Natural) - Portuguese (Portugal)",
      "Microsoft Antonio Online (Natural) - Portuguese (Brazil)",
      "Microsoft Francisca Online (Natural) - Portuguese (Brazil)",
      "Google português do Brasil",
      "Google português",
      "Luciana",
      "Joana",
      "Francisca",
      "Duarte",
      "Helena"
    ];
    for (const name of priorityNames) {
      const match = _cachedVoices.find(v => v.name.toLowerCase().includes(name.toLowerCase()));
      if (match) return match;
    }
    // Fallback suave com prioridade a pt-PT e pt-BR
    return _cachedVoices.find(v => v.lang === "pt-PT") ||
           _cachedVoices.find(v => v.lang === "pt-BR") ||
           _cachedVoices.find(v => v.lang && v.lang.startsWith("pt")) ||
           null;
  }'''

text = text.replace(old_selection.replace('\r\n', '\n'), new_selection.replace('\r\n', '\n'))

# Ajuste do TTS_RATE para fala mais natural e clara
text = text.replace('const TTS_RATE = 0.93;', 'const TTS_RATE = 0.98;')

with open('frontend/js/features/copilot/copilot-voice.js', 'w', encoding='utf-8') as f:
    f.write(text)

print('Vozes atualizadas com sucesso!')

