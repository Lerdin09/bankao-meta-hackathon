/**
 * BankAO Copilot — Sistema de Voz Inteligente (Siri / GPT Style)
 * ================================================================
 * • Acessível em QUALQUER página (Mobile e Desktop) via Floating Trigger e Chat
 * • Wake words contínuas: "Hi bank copilot" / "E aí copiloto do banco" / "Olá copiloto"
 * • Transcrição inteligente em tempo real com normalização de e-mails ditados
 * • Voz calma, serena e natural em Português com detecção das melhores vozes neurais
 * • Silence timer estendido (3.5s) com opção de envio imediato
 * • Resposta ultra-rápida sem atrasos
 */

(function () {
  "use strict";

  // ─── Constantes & Configurações ──────────────────────────────────────────────
  const WAKE_WORDS = [
    "hi bank copilot",
    "hey bank copilot",
    "e aí copiloto do banco",
    "ei copiloto do banco",
    "copiloto do banco",
    "olá copiloto",
    "olá copilot",
    "hey copilot",
    "hi copilot",
    "oi copiloto",
    "copilot",
  ];

  const TTS_LANG = "pt-PT";
  const TTS_RATE = 0.93;       // Ritmo calmo, sereno e natural
  const TTS_PITCH = 1.0;
  const SILENCE_TIMEOUT = 3500; // 3.5 segundos: tempo confortável para respirar e pensar

  // ─── Estado interno ──────────────────────────────────────────────────────────
  let recognition = null;
  let isListening = false;
  let isWakeMode = true;        // true = vigília passiva; false = sessão de diálogo aberta
  let currentUtterance = null;
  let animFrame = null;
  let audioCtx = null;
  let analyser = null;
  let micSource = null;
  let micStream = null;
  let canvas = null;
  let canvasCtx = null;
  let voiceOverlay = null;
  let transcriptEl = null;
  let statusEl = null;
  let floatingBtn = null;
  let micBtn = null;
  let silenceTimer = null;
  let lastFinalTranscript = "";

  // ─── Inicialização Pública ────────────────────────────────────────────────────
  window.initCopilotVoice = function () {
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
    document.addEventListener("click", _unlockAudioOnFirstGesture, { once: true });
    document.addEventListener("touchstart", _unlockAudioOnFirstGesture, { once: true });
  };

  // Garante que o AudioContext e o sintetizador são ativados no primeiro toque (essencial para Mobile)
  function _unlockAudioOnFirstGesture() {
    try {
      if (window.speechSynthesis) {
        window.speechSynthesis.resume();
      }
      if (audioCtx && audioCtx.state === "suspended") {
        audioCtx.resume();
      }
    } catch (_) {}
  }

  // ─── Normalização Inteligente de Fala (E-mails e Contas) ──────────────────────
  function normalizeSpokenEmail(raw) {
    if (!raw) return "";
    let s = String(raw).trim();

    // 1. "arroba" / "at" -> "@"
    s = s.replace(/\s*(?:arroba|\barrobas?\b|@)\s*/gi, "@");

    // 2. "ponto" / "dot" entre palavras -> "."
    s = s.replace(/(\w+)\s+(?:ponto|dot|\.)\s+(\w+)/gi, "$1.$2");

    // 3. Remover espaços ao redor de @ e .
    s = s.replace(/\s*@\s*/g, "@");
    s = s.replace(/\s*\.\s*/g, ".");

    // 4. Junção de nomes compostos antes do @: "ana ferreira@" -> "ana.ferreira@"
    s = s.replace(/([A-Za-z0-9_-]+)\s+([A-Za-z0-9_-]+)@/g, "$1.$2@");

    // 5. Casos comuns ditados em Angola e internacionalmente:
    // "bankao ao" -> "bankao.ao" | "bankao com" -> "bankao.com"
    s = s.replace(/@bankao(?:\s+ao|\.ao)?\b/gi, "@bankao.ao");
    s = s.replace(/@bankao\b(?!\.)/gi, "@bankao.ao");
    s = s.replace(/@gmail(?:\s+com|\.com)?\b/gi, "@gmail.com");
    s = s.replace(/@hotmail(?:\s+com|\.com)?\b/gi, "@hotmail.com");

    return s;
  }

  // ─── Síntese de Voz (TTS) Calma e Natural ─────────────────────────────────────
  let _cachedVoices = [];
  function _initVoiceVoices() {
    if (!("speechSynthesis" in window)) return;
    _cachedVoices = window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => {
      _cachedVoices = window.speechSynthesis.getVoices();
    };
  }

  function _getBestCalmVoice() {
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
  }

  window.copilotSpeak = function (text, onEnd) {
    if (!("speechSynthesis" in window)) {
      if (typeof onEnd === "function") onEnd();
      return;
    }
    window.speechSynthesis.cancel();
    const clean = _stripMarkdown(text);
    if (!clean.trim()) {
      if (typeof onEnd === "function") onEnd();
      return;
    }

    const utter = new SpeechSynthesisUtterance(clean);
    utter.lang = TTS_LANG;
    utter.rate = TTS_RATE;
    utter.pitch = TTS_PITCH;
    utter.volume = 1;

    const calmVoice = _getBestCalmVoice();
    if (calmVoice) utter.voice = calmVoice;

    utter.onstart = () => {
      _setOrbState("speaking");
      _setStatus("BankAO Copilot a falar…");
    };

    utter.onend = () => {
      _setOrbState(isListening && !isWakeMode ? "listening" : "idle");
      _setStatus("A ouvir com atenção…");
      if (typeof onEnd === "function") onEnd();
    };

    utter.onerror = () => {
      _setOrbState("idle");
      if (typeof onEnd === "function") onEnd();
    };

    currentUtterance = utter;
    window.speechSynthesis.speak(utter);
  };

  // ─── Floating Action Button (Visível em QUALQUER Página) ───────────────────────
  function _buildFloatingTrigger() {
    if (document.getElementById("voiceFloatingTrigger")) return;

    floatingBtn = document.createElement("button");
    floatingBtn.type = "button";
    floatingBtn.id = "voiceFloatingTrigger";
    floatingBtn.className = "voice-floating-trigger";
    floatingBtn.setAttribute("aria-label", "Abrir Copilot por Voz (Siri / GPT)");
    floatingBtn.title = "Falar com o BankAO Copilot";
    floatingBtn.innerHTML = `
      <div class="v-float-pulse"></div>
      <div class="v-float-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          <line x1="12" y1="19" x2="12" y2="23"/>
          <line x1="8" y1="23" x2="16" y2="23"/>
        </svg>
      </div>
      <span class="v-float-label">Voz IA</span>
    `;

    floatingBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      _openVoiceSession();
    });

    document.body.appendChild(floatingBtn);
  }

  // ─── Construir Overlay Holográfico Siri / GPT Voice ────────────────────────────
  function _buildOverlay() {
    if (document.getElementById("voiceOverlay")) return;

    voiceOverlay = document.createElement("div");
    voiceOverlay.id = "voiceOverlay";
    voiceOverlay.className = "voice-overlay hidden";
    voiceOverlay.innerHTML = `
      <div class="voice-backdrop-blur"></div>
      
      <div class="voice-header-bar">
        <div class="voice-badge-pill">
          <span class="v-pulse-indicator"></span>
          <span>Copilot Inteligência por Voz</span>
        </div>
        <button type="button" class="voice-close-btn" id="voiceCloseBtn" aria-label="Fechar Voz">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <div class="voice-orb-container" id="voiceOrbContainer" title="Toque no orbe para enviar agora">
        <canvas id="voiceCanvas" width="280" height="280"></canvas>
        <div class="voice-orb-inner">
          <div class="voice-orb-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="23"/>
              <line x1="8" y1="23" x2="16" y2="23"/>
            </svg>
          </div>
        </div>
      </div>

      <div class="voice-status" id="voiceStatus">A ouvir com atenção…</div>

      <div class="voice-transcript-wrapper">
        <div class="voice-transcript" id="voiceTranscript"></div>
      </div>

      <div class="voice-action-controls">
        <button type="button" class="voice-send-now-btn" id="voiceSendNowBtn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
          <span>Enviar Agora</span>
        </button>
      </div>

      <div class="voice-footer-hint">
        <span>Fale naturalmente com calma · Pausa de 3.5s envia automaticamente</span>
      </div>
    `;

    document.body.appendChild(voiceOverlay);

    canvas = document.getElementById("voiceCanvas");
    canvasCtx = canvas.getContext("2d");
    transcriptEl = document.getElementById("voiceTranscript");
    statusEl = document.getElementById("voiceStatus");

    document.getElementById("voiceCloseBtn").addEventListener("click", _closeVoiceSession);
    document.getElementById("voiceOrbContainer").addEventListener("click", () => {
      if (lastFinalTranscript.trim()) {
        _sendVoiceMessage(lastFinalTranscript.trim());
      }
    });
    document.getElementById("voiceSendNowBtn").addEventListener("click", () => {
      const text = (transcriptEl ? transcriptEl.textContent : "") || lastFinalTranscript;
      if (text.trim()) {
        _sendVoiceMessage(text.trim());
      }
    });
  }

  // ─── Botão de Microfone no Formulário do Chat ─────────────────────────────────
  function _buildMicButton() {
    micBtn = document.getElementById("btnCopilotMic");
    const container = document.querySelector(".copilot-input-container");

    if (!micBtn && container) {
      micBtn = document.createElement("button");
      micBtn.type = "button";
      micBtn.id = "btnCopilotMic";
      micBtn.className = "btn-mic-copilot";
      micBtn.setAttribute("aria-label", "Ativar assistente de voz");
      micBtn.title = "Falar com o Copilot (Siri / GPT)";
      micBtn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          <line x1="12" y1="19" x2="12" y2="23"/>
          <line x1="8" y1="23" x2="16" y2="23"/>
        </svg>
      `;
      const sendBtn = container.querySelector(".btn-send-copilot");
      container.insertBefore(micBtn, sendBtn);
    }

    if (micBtn) {
      micBtn.onclick = () => {
        if (isListening && !isWakeMode) {
          _closeVoiceSession();
        } else {
          _openVoiceSession();
        }
      };
    }
  }

  // ─── Speech Recognition Engine ────────────────────────────────────────────────
  function _initRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    try {
      recognition = new SR();
    } catch (e) {
      console.warn("[Voice] Não foi possível instanciar SpeechRecognition:", e);
      return;
    }

    recognition.lang = TTS_LANG;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      let interim = "";
      let final = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) final += t;
        else interim += t;
      }

      // Normalizar e-mails e termos falados em tempo real
      const currentRaw = (final || interim).trim();
      const normalized = normalizeSpokenEmail(currentRaw);

      if (transcriptEl && normalized) {
        transcriptEl.textContent = normalized;
      }

      if (isWakeMode) {
        // Detecção de Wake Word contínua em qualquer página
        const lower = currentRaw.toLowerCase();
        if (WAKE_WORDS.some(w => lower.includes(w))) {
          _openVoiceSession();
        }
      } else {
        // Sessão de conversa ativa: enquanto o utilizador fala, renova o timer
        _clearSilenceTimer();
        lastFinalTranscript = normalized;
        _setStatus("A ouvir com atenção…");
        _setOrbState("listening");

        if (final.trim()) {
          // Iniciar timer de 3.5s de silêncio para dar tempo confortável de falar
          _resetSilenceTimer(normalized);
        }
      }
    };

    recognition.onerror = (e) => {
      if (e.error === "no-speech" || e.error === "aborted") return;
      console.warn("[Voice] Reconhecimento evento de erro:", e.error);
    };

    recognition.onend = () => {
      // Reiniciar continuamente a escuta passiva se estiver ativa
      if (isListening) {
        try {
          recognition.start();
        } catch (_) {}
      }
    };
  }

  function _startPassiveListening() {
    isListening = true;
    isWakeMode = true;
    try {
      recognition.start();
    } catch (_) {}
  }

  // ─── Gestão da Sessão de Voz Ativa ───────────────────────────────────────────
  function _openVoiceSession() {
    isWakeMode = false;
    _unlockAudioOnFirstGesture();
    _showOverlay();
    _setOrbState("listening");
    _setStatus("A ouvir com atenção…");
    if (transcriptEl) transcriptEl.textContent = "";
    lastFinalTranscript = "";
    _startAudioVisualizer();

    if (micBtn) micBtn.classList.add("mic-active");
    if (floatingBtn) floatingBtn.classList.add("v-float-active");

    // Saudação serena inicial
    window.speechSynthesis.cancel();
    const greet = new SpeechSynthesisUtterance("Olá! Como posso ajudar hoje?");
    greet.lang = TTS_LANG;
    greet.rate = TTS_RATE;
    greet.pitch = TTS_PITCH;
    const calmVoice = _getBestCalmVoice();
    if (calmVoice) greet.voice = calmVoice;

    greet.onend = () => {
      _setOrbState("listening");
      _setStatus("A ouvir com atenção…");
      try {
        if (recognition) recognition.start();
      } catch (_) {}
    };

    _setOrbState("speaking");
    window.speechSynthesis.speak(greet);
  }

  function _closeVoiceSession() {
    isWakeMode = true;
    _hideOverlay();
    _stopAudioVisualizer();
    _clearSilenceTimer();
    lastFinalTranscript = "";
    if (micBtn) micBtn.classList.remove("mic-active");
    if (floatingBtn) floatingBtn.classList.remove("v-float-active");
    window.speechSynthesis.cancel();
  }

  function _resetSilenceTimer(transcript) {
    _clearSilenceTimer();
    silenceTimer = setTimeout(() => {
      if (!isWakeMode && transcript.trim()) {
        _sendVoiceMessage(transcript.trim());
      }
    }, SILENCE_TIMEOUT);
  }

  function _clearSilenceTimer() {
    if (silenceTimer) {
      clearTimeout(silenceTimer);
      silenceTimer = null;
    }
  }

  // ─── Envio da Mensagem Falada ────────────────────────────────────────────────
  async function _sendVoiceMessage(text) {
    if (!text || !text.trim()) return;
    _clearSilenceTimer();

    // Normalização final de e-mails
    const processedText = normalizeSpokenEmail(text);

    _setStatus("A processar com rapidez…");
    _setOrbState("thinking");
    if (transcriptEl) transcriptEl.textContent = "«" + processedText + "»";

    // Enviar para o chat do Copilot (preenche o input e aciona o submit do copilot.js)
    const input = document.getElementById("copilotUserInput");
    const form  = document.getElementById("copilotInputForm");
    if (input && form) {
      input.value = processedText;
      form.dispatchEvent(new Event("submit", { cancelable: true }));
    }

    _hookNextAIMessage();
  }

  // ─── Hook na Resposta da IA para Leitura por Voz ─────────────────────────────
  let _ttsHooked = false;
  function _hookNextAIMessage() {
    if (_ttsHooked) return;
    _ttsHooked = true;

    const originalAdd = window.addCopilotMessage;
    window.addCopilotMessage = function (sender, text, action, chart, remember) {
      const bubble = originalAdd.apply(this, arguments);
      if (sender === "ai" && !isWakeMode) {
        _setStatus("BankAO Copilot a responder…");
        window.copilotSpeak(text, () => {
          _setStatus("A ouvir com atenção…");
          _setOrbState("listening");
          if (transcriptEl) transcriptEl.textContent = "";
        });
        window.addCopilotMessage = originalAdd;
        _ttsHooked = false;
      }
      return bubble;
    };
  }

  // ─── Mostrar e Esconder Overlay ──────────────────────────────────────────────
  function _showOverlay() {
    if (!voiceOverlay) return;
    voiceOverlay.classList.remove("hidden");
    requestAnimationFrame(() => voiceOverlay.classList.add("visible"));
  }

  function _hideOverlay() {
    if (!voiceOverlay) return;
    voiceOverlay.classList.remove("visible");
    setTimeout(() => voiceOverlay.classList.add("hidden"), 300);
  }

  function _setOrbState(state) {
    if (!voiceOverlay) return;
    voiceOverlay.dataset.state = state;
  }

  function _setStatus(msg) {
    if (statusEl) statusEl.textContent = msg;
  }

  // ─── Visualizador Dinâmico Siri / GPT no Canvas ──────────────────────────────
  async function _startAudioVisualizer() {
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
  }

  function _stopAudioVisualizer() {
    if (animFrame) {
      cancelAnimationFrame(animFrame);
      animFrame = null;
    }
    if (micSource) {
      micSource.disconnect();
      micSource = null;
    }
    if (micStream) {
      micStream.getTracks().forEach(t => t.stop());
      micStream = null;
    }
    if (audioCtx) {
      audioCtx.close().catch(() => {});
      audioCtx = null;
    }
    analyser = null;
    if (canvasCtx && canvas) {
      canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }

  function _drawWave() {
    if (!canvas || !canvasCtx) return;
    const W = canvas.width;
    const H = canvas.height;
    const cx = W / 2;
    const cy = H / 2;
    const now = performance.now() / 1000;

    canvasCtx.clearRect(0, 0, W, H);

    let amplitude = 0;
    if (analyser) {
      const data = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(data);
      amplitude = data.reduce((a, b) => a + b, 0) / data.length / 128;
    } else {
      amplitude = 0.25 + 0.18 * Math.sin(now * 2.2);
    }

    const state = voiceOverlay?.dataset.state || "idle";
    const colors = _getStateColors(state);

    // Ondas exteriores concêntricas (Siri Glow)
    const rings = state === "idle" ? 2 : 4;
    for (let r = rings; r >= 1; r--) {
      const phase = now * (0.8 + r * 0.25);
      const pulse = 0.5 + 0.5 * Math.sin(phase);
      const baseRadius = 65 + r * 22;
      const radius = baseRadius + amplitude * 32 * pulse;
      const alpha = (0.22 - r * 0.04) * (0.4 + amplitude * 0.6);

      const grad = canvasCtx.createRadialGradient(cx, cy, radius * 0.4, cx, cy, radius);
      grad.addColorStop(0, colors.ring.replace("1)", `${alpha * 1.6})`));
      grad.addColorStop(1, colors.ring.replace("1)", "0)"));

      canvasCtx.beginPath();
      canvasCtx.arc(cx, cy, radius, 0, Math.PI * 2);
      canvasCtx.fillStyle = grad;
      canvasCtx.fill();
    }

    // Esfera central holográfica
    const mainR = 52 + amplitude * 16;
    const mainGrad = canvasCtx.createRadialGradient(cx - 10, cy - 10, 6, cx, cy, mainR);
    mainGrad.addColorStop(0, colors.center0);
    mainGrad.addColorStop(0.5, colors.center1);
    mainGrad.addColorStop(1, colors.center2);

    canvasCtx.beginPath();
    canvasCtx.arc(cx, cy, mainR, 0, Math.PI * 2);
    canvasCtx.fillStyle = mainGrad;
    canvasCtx.shadowBlur = 36;
    canvasCtx.shadowColor = colors.shadow;
    canvasCtx.fill();
    canvasCtx.shadowBlur = 0;

    // Barras de onda internas estilo ChatGPT Voice
    if (state !== "idle") {
      const bars = 26;
      const barW = 3.5;
      const gap = 4.5;
      const totalW = bars * (barW + gap) - gap;
      const startX = cx - totalW / 2;

      for (let i = 0; i < bars; i++) {
        const t = now * 3.2 + i * 0.32;
        const h = state === "thinking"
          ? 8 + 14 * Math.abs(Math.sin(t))
          : 5 + (22 + amplitude * 34) * Math.abs(Math.sin(t));
        const x = startX + i * (barW + gap);
        const y = cy - h / 2;

        const barAlpha = 0.6 + 0.4 * Math.abs(Math.sin(t * 0.8));
        canvasCtx.fillStyle = `rgba(255,255,255,${barAlpha})`;
        canvasCtx.beginPath();
        canvasCtx.roundRect(x, y, barW, h, barW / 2);
        canvasCtx.fill();
      }
    }

    animFrame = requestAnimationFrame(_drawWave);
  }

  function _getStateColors(state) {
    switch (state) {
      case "listening":
        return {
          center0: "#67E8F9", center1: "#38BDF8", center2: "#6366F1",
          shadow: "#38BDF8", ring: "rgba(56,189,248,1)"
        };
      case "speaking":
        return {
          center0: "#E9D5FF", center1: "#A855F7", center2: "#6366F1",
          shadow: "#A855F7", ring: "rgba(168,85,247,1)"
        };
      case "thinking":
        return {
          center0: "#FEF08A", center1: "#F59E0B", center2: "#D97706",
          shadow: "#F59E0B", ring: "rgba(245,158,11,1)"
        };
      default:
        return {
          center0: "#CBD5E1", center1: "#64748B", center2: "#334155",
          shadow: "#64748B", ring: "rgba(100,116,139,1)"
        };
    }
  }

  function _stripMarkdown(text) {
    return String(text || "")
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/\*(.*?)\*/g, "$1")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/^#{1,3}\s+/gm, "")
      .replace(/^[•\-]\s+/gm, "")
      .replace(/\n+/g, ". ")
      .replace(/[═─]+/g, "")
      .replace(/https?:\/\/\S+/g, "")
      .trim();
  }

  // ─── Exportação ───────────────────────────────────────────────────────────────
  window._copilotVoiceOpenSession = _openVoiceSession;
  window._copilotVoiceCloseSession = _closeVoiceSession;

})();
