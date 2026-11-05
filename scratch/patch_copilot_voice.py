with open('frontend/js/features/copilot/copilot-voice.js', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update initCopilotVoice
old_init = """  window.initCopilotVoice = function () {
    const hasSR = "webkitSpeechRecognition" in window || "SpeechRecognition" in window;
    if (!hasSR) {
      console.warn("[Voice] Web Speech Recognition não disponível neste navegador.");
      return;
    }

    _buildOverlay();
    _buildFloatingTrigger();
    _buildMicButton();
    _initRecognition();
    _initVoiceVoices();

    // Iniciar escuta passiva se o browser permitir ou após o primeiro toque do utilizador
    _startPassiveListening();
    setInterval(() => { if (isListening && !recActive) _ensureRecognition(); }, 2500);
    document.addEventListener("click", _unlockAudioOnFirstGesture, { once: true });
    document.addEventListener("touchstart", _unlockAudioOnFirstGesture, { once: true });
  };"""

new_init = """  window.initCopilotVoice = function () {
    const hasSR = "webkitSpeechRecognition" in window || "SpeechRecognition" in window;

    _buildOverlay();
    _buildFloatingTrigger();
    _buildMicButton();
    _initVoiceVoices();

    if (hasSR) {
      _initRecognition();
      _startPassiveListening();
      setInterval(() => { if (isListening && !recActive) _ensureRecognition(); }, 2500);
    } else {
      console.log("[Voice] Modo de voz inicializado com suporte a ações rápidas e síntese de áudio.");
    }

    document.addEventListener("click", _unlockAudioOnFirstGesture, { once: true });
    document.addEventListener("touchstart", _unlockAudioOnFirstGesture, { once: true });
  };"""

content = content.replace(old_init.replace('\n', '\r\n'), new_init.replace('\n', '\r\n'))
content = content.replace(old_init, new_init)

# 2. Update floatingBtn class to not hide when unauthenticated
content = content.replace('floatingBtn.className = "voice-floating-trigger hide-unauthenticated";', 'floatingBtn.className = "voice-floating-trigger";')

# 3. Update _startAudioVisualizer with safe check
old_vis = """  async function _startAudioVisualizer() {
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      micSource = audioCtx.createMediaStreamSource(micStream);
      micSource.connect(analyser);
      _drawWave();
    } catch (_) {
      // Se o microfone direto no AudioContext falhar (ex: restrição mobile), roda simulação fluida
      _drawWave();
    }
  }"""

new_vis = """  async function _startAudioVisualizer() {
    try {
      if (navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === "function") {
        micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        micSource = audioCtx.createMediaStreamSource(micStream);
        micSource.connect(analyser);
      }
      _drawWave();
    } catch (_) {
      _drawWave();
    }
  }"""

content = content.replace(old_vis.replace('\n', '\r\n'), new_vis.replace('\n', '\r\n'))
content = content.replace(old_vis, new_vis)

with open('frontend/js/features/copilot/copilot-voice.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("copilot-voice.js successfully patched!")

