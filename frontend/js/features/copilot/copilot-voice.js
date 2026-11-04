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
  const TTS_RATE = 0.98;       // Ritmo calmo, sereno e natural
  const TTS_PITCH = 1.0;
  const SILENCE_TIMEOUT = 6000; // só usado se o envio automático estiver ligado (desligado por defeito)

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
  let finalBuffer = "";     // tudo o que já foi reconhecido (acumula a sessão inteira)
  let interimText = "";     // parte ainda provisória da frase em curso
  let ignoreInput = false;  // ignora o microfone enquanto o Copilot fala (evita ouvir-se a si próprio)
  let autoSend = false;
  try { autoSend = localStorage.getItem("copilotVoiceAutoSend") === "1"; } catch (_) {}

  let editing = false;        // a editar o texto à mão
  let awaitingReply = false;  // enviado, à espera da resposta do Copilot
  let userEchoSeen = false;   // o chat aceitou mesmo a mensagem
  let recActive = false;      // o reconhecimento está realmente a correr
  let replyWatchdog = null;
  let speakToken = 0;
  let activeFinish = null;
  let listenersBound = false;

  function _fullText() {
    return normalizeSpokenEmail((finalBuffer + " " + interimText).replace(/\s+/g, " ").trim());
  }
  function _resetBuffers() {
    finalBuffer = ""; interimText = ""; lastFinalTranscript = "";
    _showText("");
  }
  function _showText(text) {
    if (transcriptEl) {
      transcriptEl.textContent = text;
      transcriptEl.scrollTop = transcriptEl.scrollHeight;
    }
    const sendBtn = document.getElementById("voiceSendNowBtn");
    if (sendBtn) sendBtn.disabled = !text.trim();
  }

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
    setInterval(() => { if (isListening && !recActive) _ensureRecognition(); }, 2500);
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
    if (!/arroba|@/i.test(s)) return s; // frase normal: não mexer

    // 1. "arroba" / "at" -> "@"
    s = s.replace(/\s*(?:arroba|\barrobas?\b|@)\s*/gi, "@");

    // 2. "ponto" / "dot" entre palavras -> "."
    s = s.replace(/(\w+)\s+(?:ponto|dot|\.)\s+(\w+)/gi, "$1.$2");

    // 3. Remover espaços ao redor de @ e .
    s = s.replace(/\s*@\s*/g, "@");

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
  }

  function _splitForSpeech(raw) {
    const t = String(raw || "").replace(/[\u{1F300}-\u{1FAFF}\u2600-\u27BF]/gu, "").replace(/\s+/g, " ").trim();
    if (!t) return [];
    const parts = (t.match(/[^.!?…;:]+[.!?…;:]*\s*/g) || [t]).map(x => x.trim()).filter(Boolean);
    const out = [];
    let cur = "";
    for (const part of parts) {
      if (cur && (cur + " " + part).length > 180) { out.push(cur); cur = part; }
      else cur = cur ? cur + " " + part : part;
    }
    if (cur) out.push(cur);
    return out.flatMap(c => c.length > 260 ? (c.match(/.{1,240}(\s|$)/g) || [c]).map(x => x.trim()) : [c]);
  }

  // Interrompe a fala atual (e devolve o controlo a quem estava à espera dela)
  function _stopSpeaking() {
    speakToken++;
    try { if (window.speechSynthesis) window.speechSynthesis.cancel(); } catch (_) {}
    const f = activeFinish;
    activeFinish = null;
    if (f) f();
  }

  window.copilotSpeak = function (text, onEnd) {
    _stopSpeaking();
    const token = ++speakToken;
    let finished = false;
    let watchdog = null;
    const finish = () => {
      if (finished) return;
      finished = true;
      clearTimeout(watchdog);
      if (activeFinish === finish) activeFinish = null;
      ignoreInput = false;
      if (typeof onEnd === "function") onEnd();
    };
    const chunks = ("speechSynthesis" in window) ? _splitForSpeech(_stripMarkdown(text)) : [];
    if (!chunks.length) { finish(); return; }

    activeFinish = finish;
    ignoreInput = true; // não ouvir a própria voz
    _setOrbState("speaking");
    _setStatus("A responder… toque no orbe para interromper");

    // Rede de segurança: alguns telemóveis nunca avisam que a fala terminou
    const total = chunks.reduce((n, c) => n + c.length, 0);
    watchdog = setTimeout(() => {
      if (token !== speakToken) return;
      speakToken++;
      try { window.speechSynthesis.cancel(); } catch (_) {}
      finish();
    }, Math.min(180000, 8000 + total * 90));

    const voice = _getBestCalmVoice();
    let i = 0;
    const next = () => {
      if (finished || token !== speakToken) return;
      if (i >= chunks.length) { finish(); return; }
      const u = new SpeechSynthesisUtterance(chunks[i++]);
      u.lang = TTS_LANG; u.rate = TTS_RATE; u.pitch = TTS_PITCH; u.volume = 1;
      if (voice) u.voice = voice;
      u.onend = next;
      u.onerror = (e) => { if (e && (e.error === "interrupted" || e.error === "canceled")) return; next(); };
      currentUtterance = u; // mantém referência (evita que o navegador a apanhe antes do fim)
      window.speechSynthesis.speak(u);
    };
    setTimeout(next, 40);
  };

  // Modo voz aberto? (usado para anunciar por voz as operações concluídas)
  window.copilotVoiceActive = function () {
    return !!(voiceOverlay && voiceOverlay.classList.contains("visible"));
  };
  window.copilotSpeakDone = function (text) {
    window.copilotSpeak(text, function () { try { _resumeListening(); } catch (_) {} });
  };

  // ─── Floating Action Button (Visível em QUALQUER Página) ───────────────────────
  function _buildFloatingTrigger() {
    if (document.getElementById("voiceFloatingTrigger")) return;

    floatingBtn = document.createElement("button");
    floatingBtn.type = "button";
    floatingBtn.id = "voiceFloatingTrigger";
    floatingBtn.className = "voice-floating-trigger hide-unauthenticated";
    floatingBtn.setAttribute("aria-label", "Falar com o Copilot");
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
      <div class="voice-panel">
        <div class="voice-panel-top">
          <span class="voice-status" id="voiceStatus">A ouvir…</span>
        </div>

        <div class="voice-transcript-wrapper">
          <div class="voice-transcript" id="voiceTranscript" aria-live="polite"></div>
        </div>

        <div class="voice-dock" role="group" aria-label="Controlos de voz">
          <button type="button" class="voice-dock-btn voice-dock-close" id="voiceCloseBtn" aria-label="Fechar voz" title="Fechar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>

          <button type="button" class="voice-dock-btn voice-dock-clear" id="voiceClearBtn" aria-label="Apagar e repetir" title="Apagar e repetir">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
          </button>

          <div class="voice-orb-container" id="voiceOrbContainer" role="button" aria-label="Microfone. Toque para interromper o Copilot">
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

          <button type="button" class="voice-dock-btn voice-dock-send" id="voiceSendNowBtn" aria-label="Enviar" title="Enviar" disabled>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>

          <button type="button" class="voice-dock-btn voice-dock-edit" id="voiceEditBtn" aria-label="Editar no chat" title="Editar no chat do Copilot">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
          </button>
        </div>

        <label class="voice-auto">
          <input type="checkbox" id="voiceAutoSend">
          <span>Enviar sozinho após 6 s de silêncio</span>
        </label>
      </div>
    `;

    document.body.appendChild(voiceOverlay);

    canvas = document.getElementById("voiceCanvas");
    canvasCtx = canvas.getContext("2d");
    transcriptEl = document.getElementById("voiceTranscript");
    statusEl = document.getElementById("voiceStatus");

    const $ = (id) => document.getElementById(id);
    $("voiceCloseBtn").addEventListener("click", _closeVoiceSession);
    $("voiceOrbContainer").addEventListener("click", () => { if (activeFinish) _stopSpeaking(); });
    $("voiceEditBtn").addEventListener("click", _editInChat);
    $("voiceClearBtn").addEventListener("click", _clearAndRepeat);
    $("voiceSendNowBtn").addEventListener("click", () => {
      const text = _currentText();
      if (text) _sendVoiceMessage(text);
    });
    const autoEl = $("voiceAutoSend");
    autoEl.checked = autoSend;
    autoEl.addEventListener("change", () => {
      autoSend = autoEl.checked;
      try { localStorage.setItem("copilotVoiceAutoSend", autoSend ? "1" : "0"); } catch (_) {}
      _clearSilenceTimer();
      if (autoSend && _fullText()) _resetSilenceTimer();
    });

    if (listenersBound) return;
    listenersBound = true;

    // Enter envia · Shift+Enter muda de linha (só com o ecrã de voz aberto) · Esc fecha ou cancela a edição
    document.addEventListener("keydown", (e) => {
      if (!voiceOverlay || !voiceOverlay.classList.contains("visible")) return;
      if (e.key === "Escape") {
        e.preventDefault();
        if (editing) _exitEdit(false); else _closeVoiceSession();
        return;
      }
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        if (e.target && e.target.closest && e.target.closest("button, input, textarea")) return;
        e.preventDefault();
        const text = _currentText();
        if (text) _sendVoiceMessage(text);
      }
    });

    // O chat avisa sempre que há uma mensagem nova: é assim que sabemos que a resposta chegou
    document.addEventListener("copilot:message", (e) => {
      const d = (e && e.detail) || {};
      if (d.sender === "user") { userEchoSeen = true; return; }
      if (d.sender !== "ai" || isWakeMode || !awaitingReply) return;
      awaitingReply = false;
      clearTimeout(replyWatchdog);
      window.copilotSpeak(d.text, _resumeListening);
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

    recognition.onstart = () => { recActive = true; };

    recognition.onresult = (event) => {
      let chunk = "";
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i];
        const t = r[0].transcript;
        chunk += " " + t;
        if (r.isFinal) {
          if (!isWakeMode && !ignoreInput && !editing) {
            finalBuffer = (finalBuffer + " " + t).replace(/\s+/g, " ").trim();
          }
        } else {
          interim += t;
        }
      }

      if (isWakeMode) {
        const lower = chunk.toLowerCase();
        if (WAKE_WORDS.some(w => lower.includes(w))) _openVoiceSession();
        return;
      }
      if (ignoreInput || editing) return;

      interimText = interim.trim();
      const text = _fullText();
      lastFinalTranscript = text;
      _showText(text);
      _setStatus("A ouvir…");
      _setOrbState("listening");

      _clearSilenceTimer();
      if (autoSend && text) _resetSilenceTimer();
    };

    recognition.onerror = (e) => {
      if (e.error === "no-speech" || e.error === "aborted") return;
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        isListening = false;
        _setStatus("Permita o microfone para falar com o Copilot");
        return;
      }
      console.warn("[Voice] Reconhecimento evento de erro:", e.error);
    };

    recognition.onend = () => {
      recActive = false;
      // O navegador termina a escuta de tempos a tempos: reinicia sem perder o que já foi dito
      if (!isListening) return;
      setTimeout(_ensureRecognition, 200);
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

    // Abrir o chat do Copilot ao activar por voz (wake word)
    var isWide = window.matchMedia("(min-width: 1024px)").matches;
    if (!isWide && typeof window.openCopilot === "function") {
      // Mobile/tablet: abre o painel do chat sobre a página actual
      window.openCopilot();
    }
    // Scroll para o fim das mensagens (desktop e mobile)
    setTimeout(function () {
      var box = document.getElementById("copilotChatMessages");
      if (box) box.scrollTop = box.scrollHeight;
    }, 150);

    _showOverlay();
    _setOrbState("listening");
    _setStatus("À ouvir com atenção…");
    _resetBuffers();
    _startAudioVisualizer();

    if (micBtn) micBtn.classList.add("mic-active");
    if (floatingBtn) floatingBtn.classList.add("v-float-active");

    awaitingReply = false;
    editing = false;
    _applyEditUi(false);
    window.copilotSpeak("Ólá! Como posso ajudar hoje?", _resumeListening);
  }

  function _closeVoiceSession() {
    isWakeMode = true;
    _hideOverlay();
    _stopAudioVisualizer();
    _clearSilenceTimer();
    _resetBuffers();
    ignoreInput = false;
    if (micBtn) micBtn.classList.remove("mic-active");
    if (floatingBtn) floatingBtn.classList.remove("v-float-active");
    awaitingReply = false;
    clearTimeout(replyWatchdog);
    if (editing) { editing = false; _applyEditUi(false); }
    _stopSpeaking();
  }

  function _resetSilenceTimer() {
    _clearSilenceTimer();
    silenceTimer = setTimeout(() => {
      const t = _fullText();
      if (!isWakeMode && t) _sendVoiceMessage(t);
    }, SILENCE_TIMEOUT);
  }

  function _clearSilenceTimer() {
    if (silenceTimer) {
      clearTimeout(silenceTimer);
      silenceTimer = null;
    }
  }

  // ─── Voltar a ouvir: um só caminho, usado no fim de cada turno ───────────────
  function _ensureRecognition() {
    if (!recognition || recActive) return;
    try { recognition.start(); } catch (_) {}
  }

  function _restartRecognition() {
    try { recognition.abort(); } catch (_) {}
    setTimeout(_ensureRecognition, 350);
  }

  function _resumeListening() {
    clearTimeout(replyWatchdog);
    awaitingReply = false;
    ignoreInput = false;
    if (isWakeMode || editing) return;
    _resetBuffers();
    _setOrbState("listening");
    _setStatus("A ouvir…");
    _ensureRecognition();
  }

  // ─── Texto atual (ditado ou editado à mão) ───────────────────────────────────
  function _currentText() {
    if (editing) {
      const area = document.getElementById("voiceEditArea");
      return (area ? area.value : "").replace(/\s+/g, " ").trim();
    }
    return _fullText();
  }

  function _applyEditUi(on) {
    const area = document.getElementById("voiceEditArea");
    const label = document.getElementById("voiceEditLabel");
    if (area) area.hidden = !on;
    if (transcriptEl) transcriptEl.hidden = on;
    if (label) label.textContent = on ? "Continuar a falar" : "Editar";
    if (voiceOverlay) voiceOverlay.classList.toggle("is-editing", on);
  }

  function _enterEdit() {
    if (editing || awaitingReply) return;
    _clearSilenceTimer();
    _stopSpeaking();
    editing = true;
    const area = document.getElementById("voiceEditArea");
    const text = _fullText();
    interimText = "";
    finalBuffer = text;
    _applyEditUi(true);
    _setOrbState("idle");
    _setStatus("A editar o texto");
    if (area) {
      area.value = text;
      document.getElementById("voiceSendNowBtn").disabled = !text;
      area.focus();
      area.setSelectionRange(area.value.length, area.value.length);
    }
  }

  function _exitEdit(apply) {
    if (!editing) return;
    const area = document.getElementById("voiceEditArea");
    if (apply && area) finalBuffer = area.value.replace(/\s+/g, " ").trim();
    interimText = "";
    editing = false;
    _applyEditUi(false);
    _showText(finalBuffer);
    _setOrbState("listening");
    _setStatus("A ouvir…");
    _restartRecognition(); // descarta o que ficou a meio e continua a ouvir
  }

  // Lápis: leva o texto para o chat do Copilot (mobile: abre o chat) para corrigir à mão
  function _editInChat() {
    if (awaitingReply) return;
    const text = _currentText();
    _closeVoiceSession();
    const input = document.getElementById("copilotUserInput");
    if (input) {
      input.value = text;
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
    const wide = window.matchMedia("(min-width: 1024px)").matches;
    if (!wide && typeof window.openCopilot === "function") window.openCopilot();
    setTimeout(() => {
      if (!input) return;
      input.focus();
      try { input.setSelectionRange(input.value.length, input.value.length); } catch (_) {}
    }, 80);
  }

  // Apaga tudo e fica pronto a ouvir de novo
  function _clearAndRepeat() {
    if (awaitingReply) return;
    _stopSpeaking();
    if (editing) { editing = false; _applyEditUi(false); }
    const area = document.getElementById("voiceEditArea");
    if (area) area.value = "";
    _clearSilenceTimer();
    ignoreInput = false;
    _resetBuffers();
    _setOrbState("listening");
    _setStatus("A ouvir… pode repetir");
    _restartRecognition();
  }

  // ─── Envio da mensagem ───────────────────────────────────────────────────────
  async function _sendVoiceMessage(text) {
    const processed = normalizeSpokenEmail(String(text || "")).trim();
    if (!processed || awaitingReply) return;
    _clearSilenceTimer();
    _stopSpeaking();
    if (editing) { editing = false; _applyEditUi(false); }

    awaitingReply = true;
    ignoreInput = true;
    finalBuffer = ""; interimText = ""; lastFinalTranscript = "";
    _setStatus("A pensar…");
    _setOrbState("thinking");
    _showText(processed);

    // Enviar diretamente para o assistente sem poluir o textarea de escrita manual
    userEchoSeen = false;
    if (typeof window.sendCopilotQuery === 'function') {
      window.sendCopilotQuery(processed).then(success => {
        if (!success) {
          awaitingReply = false;
          ignoreInput = false;
          finalBuffer = processed;
          _showText(processed);
          _setOrbState('listening');
          _setStatus('O Copilot ainda está a responder. Tente enviar de novo.');
        }
      });
      userEchoSeen = true;
    } else {
      const input = document.getElementById('copilotUserInput');
      const form  = document.getElementById('copilotInputForm');
      if (input && form) {
        input.value = processed;
        form.dispatchEvent(new Event('submit', { cancelable: true }));
      }
    }
    if (!userEchoSeen) {
      // o chat não aceitou (ainda a responder ao pedido anterior): guarda o texto e continua a ouvir
      awaitingReply = false;
      ignoreInput = false;
      finalBuffer = processed;
      _showText(processed);
      _setOrbState("listening");
      _setStatus("O Copilot ainda está a responder. Tente enviar de novo.");
      return;
    }

    // Se a resposta nunca chegar, não ficar preso: volta a ouvir passado um minuto
    clearTimeout(replyWatchdog);
    replyWatchdog = setTimeout(_resumeListening, 60000);
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
