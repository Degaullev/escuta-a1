/**
 * Escuta A1 — iOS Safari Compatible Audio & Fallback Timeline Engine
 * - Unlocks Web Audio & HTMLAudioElement on first user gesture
 * - Supports CBR 128kbps MP3 with timestamp margin tolerance
 * - Seamless fallback to Virtual Timeline + Web Speech API (pt-BR) when MP3 is absent
 * - Decouples <video muted loop playsinline> from <audio> playbackRate
 * - Integrates navigator.mediaSession for lock-screen controls
 */
(function (global) {
  "use strict";

  const TIMESTAMP_MARGIN_SEC = 0.08;

  class AudioPlayer {
    constructor(options = {}) {
      this.onTimeUpdate = options.onTimeUpdate || (() => {});
      this.onLineChange = options.onLineChange || (() => {});
      this.onSceneChange = options.onSceneChange || (() => {});
      this.onPlayStateChange = options.onPlayStateChange || (() => {});
      this.onComplete = options.onComplete || (() => {});
      this.onLoopIncrement = options.onLoopIncrement || (() => {});
      this.onModeDetected = options.onModeDetected || (() => {});

      this.audioCtx = null;
      this.unlocked = false;

      this.audioEl = new Audio();
      this.audioEl.preload = "auto";
      this.audioEl.setAttribute("playsinline", "");
      this.audioEl.setAttribute("webkit-playsinline", "");

      // Dedicated element for playing individual neural vocabulary chunk MP3s
      this.chunkAudioEl = new Audio();
      this.chunkAudioEl.preload = "auto";
      this.chunkAudioEl.setAttribute("playsinline", "");
      this.chunkAudioEl.setAttribute("webkit-playsinline", "");

      this.lesson = null;
      this.mode = "fallback"; // "mp3" | "fallback"
      this.isPlaying = false;
      this.playbackRate = options.initialRate || 0.85;
      this.currentTime = 0;
      this.duration = 0;

      this.activeLine = null;
      this.activeScene = null;
      this.lastSpokenLineId = null;

      // Segment stop bound (for single-sentence / A-B playback)
      this.segmentEnd = null;
      this.segmentResolve = null;
      this._segmentSeeking = false;
      this._segmentToken = 0;

      // Step 5 repeat options
      this.loopEnabled = false;
      this.jaGuideEnabled = false;
      this.jaGuideSpeaking = false;
      this.guidedLineIds = new Set();
      this.loopCount = 1;

      // Virtual clock state
      this._rafId = null;
      this._lastFrameTs = 0;

      // Cached Web Speech voices
      this._voices = [];
      this._bindAudioEvents();
      this._setupFirstGestureUnlock();
      this._initSpeechVoices();
    }

    _setupFirstGestureUnlock() {
      const unlock = () => {
        if (this.unlocked) return;
        this.unlocked = true;

        try {
          const AudioContextClass = global.AudioContext || global.webkitAudioContext;
          if (AudioContextClass) {
            if (!this.audioCtx) {
              this.audioCtx = new AudioContextClass();
            }
            if (this.audioCtx.state === "suspended") {
              this.audioCtx.resume();
            }
            // Play 1-sample silent buffer to unlock iOS Safari audio hardware
            const buffer = this.audioCtx.createBuffer(1, 1, 22050);
            const source = this.audioCtx.createBufferSource();
            source.buffer = buffer;
            source.connect(this.audioCtx.destination);
            source.start(0);
          }
        } catch (err) {
          console.warn("[AudioPlayer] WebAudio unlock warning:", err);
        }

        try {
          if ("speechSynthesis" in global) {
            const silentUtter = new SpeechSynthesisUtterance("");
            silentUtter.volume = 0;
            global.speechSynthesis.speak(silentUtter);
          }
        } catch (_) {
          // Ignore speechSynthesis unlock issues
        }

        ["touchstart", "pointerdown", "click"].forEach((ev) =>
          document.removeEventListener(ev, unlock, true)
        );
      };

      ["touchstart", "pointerdown", "click"].forEach((ev) =>
        document.addEventListener(ev, unlock, { capture: true, passive: true })
      );
    }

    _initSpeechVoices() {
      if (!("speechSynthesis" in global)) return;
      const loadVoices = () => {
        this._voices = global.speechSynthesis.getVoices() || [];
      };
      loadVoices();
      if (typeof global.speechSynthesis.onvoiceschanged !== "undefined") {
        global.speechSynthesis.onvoiceschanged = loadVoices;
      }
    }

    _pickVoice(langPrefix, genderHint) {
      if (!this._voices || !this._voices.length) {
        if ("speechSynthesis" in global) {
          this._voices = global.speechSynthesis.getVoices() || [];
        }
      }
      const lowerPrefix = langPrefix.toLowerCase();
      const exactPtBr = this._voices.filter((v) =>
        v.lang.toLowerCase().replace("_", "-").startsWith(lowerPrefix)
      );
      const pool = exactPtBr.length
        ? exactPtBr
        : this._voices.filter((v) =>
            v.lang.toLowerCase().startsWith(lowerPrefix.split("-")[0])
          );
      if (!pool.length) return null;

      if (genderHint === "female") {
        const fem = pool.find((v) =>
          /luciana|fernanda|maria|francisca|vitória|vitoria|female|ana/i.test(v.name)
        );
        if (fem) return fem;
      } else if (genderHint === "male") {
        const mal = pool.find((v) =>
          /felipe|daniel|ricardo|antonio|male|pedro/i.test(v.name)
        );
        if (mal) return mal;
      }
      return pool[0];
    }

    _bindAudioEvents() {
      this.audioEl.addEventListener("timeupdate", () => {
        if (this.mode !== "mp3") return;
        this.currentTime = this.audioEl.currentTime;
        this._syncTimelineState();
      });

      this.audioEl.addEventListener("ended", () => {
        if (this.mode !== "mp3") return;
        this._handleTrackEnded();
      });
    }

    async loadLesson(lesson) {
      this.stop();
      this.lesson = lesson;
      this.currentTime = 0;
      this.duration = Number(lesson.duration) || 60;
      this.activeLine = null;
      this.activeScene = (lesson.scenes && lesson.scenes[0]) || null;
      this.lastSpokenLineId = null;
      this.guidedLineIds.clear();
      this.loopCount = 1;

      const hasMp3 = await this._probeAudioUrl(lesson.audioUrl);
      if (hasMp3) {
        this.mode = "mp3";
        this.audioEl.src = lesson.audioUrl;
        this.audioEl.playbackRate = this.playbackRate;
        await new Promise((resolve) => {
          const onLoaded = () => {
            if (isFinite(this.audioEl.duration) && this.audioEl.duration > 0) {
              this.duration = this.audioEl.duration;
            }
            cleanup();
            resolve();
          };
          const onErr = () => {
            this.mode = "fallback";
            cleanup();
            resolve();
          };
          const cleanup = () => {
            this.audioEl.removeEventListener("loadedmetadata", onLoaded);
            this.audioEl.removeEventListener("error", onErr);
          };
          this.audioEl.addEventListener("loadedmetadata", onLoaded);
          this.audioEl.addEventListener("error", onErr);
          this.audioEl.load();
        });
      } else {
        this.mode = "fallback";
      }

      this.onModeDetected(this.mode);
      this._setupMediaSession();
      this._syncTimelineState(true);
    }

    async _probeAudioUrl(url) {
      if (!url || global.location.protocol === "file:") return false;
      try {
        const res = await fetch(url, { method: "HEAD", cache: "no-cache" });
        if (!res.ok) return false;
        const ctype = (res.headers.get("content-type") || "").toLowerCase();
        if (ctype.includes("text/html")) return false;
        return true;
      } catch (_) {
        return false;
      }
    }

    setPlaybackRate(rate) {
      this.playbackRate = Number(rate) || 1.0;
      if (this.mode === "mp3") {
        this.audioEl.playbackRate = this.playbackRate;
      }
      // Note: <video> element in UI is intentionally untouched so background video never stutters
    }

    setRepeatOptions({ loop = false, jaGuide = false } = {}) {
      this.loopEnabled = Boolean(loop);
      this.jaGuideEnabled = Boolean(jaGuide);
      this.guidedLineIds.clear();
    }

    play() {
      if (!this.lesson) return;
      this.segmentEnd = null;
      if (this.currentTime >= this.duration - 0.1) {
        this.seek(0);
        this.guidedLineIds.clear();
      }
      this.isPlaying = true;
      this.onPlayStateChange(true);

      if (this.mode === "mp3") {
        this.audioEl.playbackRate = this.playbackRate;
        this.audioEl.play().catch((err) => {
          console.warn("[AudioPlayer] MP3 play blocked, switching to fallback:", err);
          this.mode = "fallback";
          this.onModeDetected("fallback");
          this._startVirtualClock();
        });
        this._startMp3Poll();
      } else {
        this._startVirtualClock();
        // Immediately trigger speech if starting inside a line
        const line = this._findLineAt(this.currentTime);
        if (line && this.lastSpokenLineId !== line.id) {
          this._triggerLineFallbackSpeech(line);
        }
      }
      this._updateMediaSessionState("playing");
    }

    pause() {
      this.isPlaying = false;
      this.jaGuideSpeaking = false;
      this.onPlayStateChange(false);

      if (this.mode === "mp3") {
        this.audioEl.pause();
      }
      this._stopClock();
      this._cancelSpeech();
      if (this.segmentResolve) {
        const r = this.segmentResolve;
        this.segmentResolve = null;
        r();
      }
      this._updateMediaSessionState("paused");
    }

    togglePlay() {
      if (this.isPlaying) {
        this.pause();
      } else {
        this.play();
      }
    }

    stop() {
      this.pause();
      this.currentTime = 0;
      this.lastSpokenLineId = null;
      if (this.mode === "mp3") {
        try {
          this.audioEl.currentTime = 0;
        } catch (_) {}
      }
    }

    seek(timeSec, autoPlay = false) {
      if (!this.lesson) return;
      const clamped = Math.max(0, Math.min(this.duration, Number(timeSec) || 0));
      this.currentTime = clamped;
      this.lastSpokenLineId = null;
      this.segmentEnd = null;

      if (this.mode === "mp3") {
        try {
          this.audioEl.currentTime = clamped;
        } catch (_) {}
      } else {
        this._cancelSpeech();
      }

      this._syncTimelineState(true);

      if (autoPlay) {
        if (!this.isPlaying) {
          this.play();
        } else if (this.mode === "fallback") {
          const line = this._findLineAt(clamped);
          if (line) this._triggerLineFallbackSpeech(line);
        }
      }
    }

    seekLineByOffset(delta) {
      if (!this.lesson || !this.lesson.lines || !this.lesson.lines.length) return;
      const lines = this.lesson.lines;
      const currentIdx = this.activeLine
        ? lines.findIndex((l) => l.id === this.activeLine.id)
        : 0;
      const targetIdx = Math.max(0, Math.min(lines.length - 1, currentIdx + delta));
      this.seek(lines[targetIdx].start, this.isPlaying);
    }

    /**
     * Plays a single sentence or phrase and returns a Promise when done.
     * Used in Step 2 popup, Step 3 chunks, Step 4 listening quiz & A/B compare.
     */
    playLineOrText({ line = null, textPt = "", speaker = "Ana" } = {}) {
      // Cancel any ongoing timeline or previous segment cleanly
      const token = ++this._segmentToken;
      if (this.isPlaying) {
        this.pause();
      }
      this._cancelSpeech();

      if (this.mode === "mp3" && line && typeof line.start === "number") {
        return new Promise((resolve) => {
          const targetStart = Math.max(0, Number(line.start) || 0);
          const targetEnd = Math.min(
            this.duration || Number(line.end) + 0.1,
            (Number(line.end) || targetStart + 3) + 0.08
          );

          this.segmentResolve = resolve;
          this.segmentEnd = targetEnd;
          this._segmentSeeking = true;
          this.audioEl.playbackRate = this.playbackRate;

          const finishError = () => {
            if (token !== this._segmentToken) return;
            this._segmentSeeking = false;
            this.isPlaying = false;
            this.segmentEnd = null;
            this.onPlayStateChange(false);
            if (this.segmentResolve) {
              const r = this.segmentResolve;
              this.segmentResolve = null;
              r();
            }
          };

          const startPlaybackAfterSeek = () => {
            if (token !== this._segmentToken) return;
            this._segmentSeeking = false;
            this.currentTime = this.audioEl.currentTime;
            this.isPlaying = true;
            this.onPlayStateChange(true);
            this.audioEl.play().then(() => {
              if (token !== this._segmentToken) return;
              this._startMp3Poll();
            }).catch(finishError);
          };

          const performSeek = () => {
            if (token !== this._segmentToken) return;
            // If already right at targetStart, play immediately
            if (Math.abs(this.audioEl.currentTime - targetStart) < 0.04) {
              startPlaybackAfterSeek();
              return;
            }
            const onSeeked = () => {
              this.audioEl.removeEventListener("seeked", onSeeked);
              clearTimeout(seekFallbackTimer);
              startPlaybackAfterSeek();
            };
            const seekFallbackTimer = setTimeout(() => {
              this.audioEl.removeEventListener("seeked", onSeeked);
              startPlaybackAfterSeek();
            }, 600);
            this.audioEl.addEventListener("seeked", onSeeked, { once: true });
            try {
              this.audioEl.currentTime = targetStart;
            } catch (_) {
              onSeeked();
            }
          };

          if (this.audioEl.readyState >= 1) {
            performSeek();
          } else {
            this.audioEl.addEventListener("loadedmetadata", performSeek, { once: true });
            this.audioEl.load();
          }
        });
      }

      const content = textPt || (line ? line.pt : "");
      return this.speakUtterance(content, "pt-BR", speaker);
    }

    /**
     * Plays a pre-generated neural MP3 chunk (for vocabulary popup, Step 3 chunks, SRS cards),
     * falling back to Web Speech API only when no chunk MP3 URL is available.
     */
    playVocabChunk(item, speaker = "Ana") {
      if (this.isPlaying) {
        this.pause();
      }
      this._cancelSpeech();
      const audioUrl =
        (item && item.audioUrl) ||
        (item && item.lessonId && item.vocabId
          ? `lessons/${item.lessonId}/media/chunks/${item.vocabId}.mp3`
          : null);

      if (!audioUrl || global.location.protocol === "file:") {
        return this.speakUtterance((item && item.chunkPt) || "", "pt-BR", speaker);
      }

      return new Promise((resolve) => {
        this.chunkAudioEl.pause();
        this.chunkAudioEl.src = audioUrl;
        this.chunkAudioEl.playbackRate = this.playbackRate;
        const done = () => {
          this.chunkAudioEl.onended = null;
          this.chunkAudioEl.onerror = null;
          resolve();
        };
        this.chunkAudioEl.onended = done;
        this.chunkAudioEl.onerror = () => {
          this.speakUtterance((item && item.chunkPt) || "", "pt-BR", speaker).then(
            resolve
          );
        };
        this.chunkAudioEl.play().catch(() => {
          this.speakUtterance((item && item.chunkPt) || "", "pt-BR", speaker).then(
            resolve
          );
        });
      });
    }

    speakUtterance(text, lang = "pt-BR", speaker = "Ana") {
      return new Promise((resolve) => {
        if (!text || !("speechSynthesis" in global)) {
          setTimeout(resolve, 650);
          return;
        }
        try {
          global.speechSynthesis.cancel();
          const utter = new SpeechSynthesisUtterance(text);
          utter.lang = lang;
          const gender = speaker === "Pedro" ? "male" : "female";
          const voice = this._pickVoice(lang, gender);
          if (voice) utter.voice = voice;

          if (lang.startsWith("pt")) {
            utter.rate = Math.max(0.65, Math.min(1.1, this.playbackRate * 0.95));
            utter.pitch = speaker === "Pedro" ? 0.92 : 1.06;
          } else {
            utter.rate = 1.05;
          }

          let settled = false;
          const finish = () => {
            if (settled) return;
            settled = true;
            clearTimeout(safetyTimer);
            resolve();
          };
          // Safety timeout in case headless or mobile browser drops onend
          const estMs = Math.max(1200, text.length * 95);
          const safetyTimer = setTimeout(finish, estMs);

          utter.onend = finish;
          utter.onerror = finish;
          global.speechSynthesis.speak(utter);
        } catch (_) {
          setTimeout(resolve, 600);
        }
      });
    }

    _cancelSpeech() {
      try {
        if ("speechSynthesis" in global) {
          global.speechSynthesis.cancel();
        }
      } catch (_) {}
    }

    _startMp3Poll() {
      this._stopClock();
      const tick = () => {
        if (!this.isPlaying || this.mode !== "mp3") return;
        if (this._segmentSeeking || this.audioEl.seeking) {
          this._rafId = requestAnimationFrame(tick);
          return;
        }
        this.currentTime = this.audioEl.currentTime;
        if (this.segmentEnd !== null && this.currentTime >= this.segmentEnd) {
          this.audioEl.pause();
          this.isPlaying = false;
          this.segmentEnd = null;
          this.onPlayStateChange(false);
          if (this.segmentResolve) {
            const r = this.segmentResolve;
            this.segmentResolve = null;
            r();
          }
          return;
        }
        this._syncTimelineState();
        this._rafId = requestAnimationFrame(tick);
      };
      this._rafId = requestAnimationFrame(tick);
    }

    _startVirtualClock() {
      this._stopClock();
      this._lastFrameTs = performance.now();

      const tick = (now) => {
        if (!this.isPlaying || this.mode !== "fallback") return;
        const dtSec = Math.min(0.1, (now - this._lastFrameTs) / 1000);
        this._lastFrameTs = now;

        if (!this.jaGuideSpeaking) {
          this.currentTime += dtSec * this.playbackRate;
        }

        if (this.currentTime >= this.duration) {
          this.currentTime = this.duration;
          this._syncTimelineState();
          this._handleTrackEnded();
          return;
        }

        this._syncTimelineState();
        this._rafId = requestAnimationFrame(tick);
      };
      this._rafId = requestAnimationFrame(tick);
    }

    _stopClock() {
      if (this._rafId) {
        cancelAnimationFrame(this._rafId);
        this._rafId = null;
      }
    }

    _findLineAt(t) {
      if (!this.lesson || !this.lesson.lines) return null;
      return (
        this.lesson.lines.find(
          (l) =>
            t >= l.start - TIMESTAMP_MARGIN_SEC &&
            t <= l.end + TIMESTAMP_MARGIN_SEC
        ) || null
      );
    }

    _findSceneAt(t) {
      if (!this.lesson || !this.lesson.scenes) return null;
      for (let i = this.lesson.scenes.length - 1; i >= 0; i--) {
        const sc = this.lesson.scenes[i];
        if (t >= sc.startTime - TIMESTAMP_MARGIN_SEC) {
          return sc;
        }
      }
      return this.lesson.scenes[0] || null;
    }

    _syncTimelineState(forceNotify = false) {
      const t = this.currentTime;
      const line = this._findLineAt(t);
      const scene = this._findSceneAt(t);

      if (forceNotify || (scene && (!this.activeScene || scene.id !== this.activeScene.id))) {
        this.activeScene = scene;
        this.onSceneChange(scene);
      }

      const prevLineId = this.activeLine ? this.activeLine.id : null;
      const nextLineId = line ? line.id : null;

      if (forceNotify || prevLineId !== nextLineId) {
        this.activeLine = line;
        this.onLineChange(line);

        if (this.isPlaying && line && this.segmentEnd === null) {
          if (this.jaGuideEnabled && !this.guidedLineIds.has(line.id)) {
            this.guidedLineIds.add(line.id);
            this._runJapaneseGuideBeforeLine(line);
          } else if (this.mode === "fallback" && this.lastSpokenLineId !== line.id) {
            this._triggerLineFallbackSpeech(line);
          }
        }
      }

      this.onTimeUpdate(this.currentTime, this.duration);
    }

    async _runJapaneseGuideBeforeLine(line) {
      const guideText = line.jaGuide || line.ja;
      if (!guideText) return;

      this.jaGuideSpeaking = true;
      if (this.mode === "mp3") {
        this.audioEl.pause();
      }
      if (line.jaGuideAudioUrl && global.location.protocol !== "file:") {
        await this.playVocabChunk({ audioUrl: line.jaGuideAudioUrl, chunkPt: "" });
      } else {
        await this.speakUtterance(guideText, "ja-JP", "Ana");
      }
      this.jaGuideSpeaking = false;

      if (!this.isPlaying) return;
      if (this.mode === "mp3") {
        this.audioEl.currentTime = line.start;
        this.audioEl.play().catch(() => {});
      } else {
        this.currentTime = line.start;
        this._triggerLineFallbackSpeech(line);
      }
    }

    _triggerLineFallbackSpeech(line) {
      this.lastSpokenLineId = line.id;
      this.speakUtterance(line.pt, "pt-BR", line.speaker);
    }

    _handleTrackEnded() {
      if (this.loopEnabled) {
        this.loopCount += 1;
        this.guidedLineIds.clear();
        this.lastSpokenLineId = null;
        this.onLoopIncrement(this.loopCount);
        this.seek(0, true);
        return;
      }
      this.isPlaying = false;
      this._stopClock();
      this.onPlayStateChange(false);
      this.onComplete();
      this._updateMediaSessionState("paused");
    }

    _setupMediaSession() {
      if (!("mediaSession" in navigator) || !this.lesson) return;
      try {
        navigator.mediaSession.metadata = new MediaMetadata({
          title: this.lesson.titleJa || this.lesson.title,
          artist: "Ana & Pedro — Escuta A1",
          album: "Escuta A1 (pt-BR Listening)",
        });
        navigator.mediaSession.setActionHandler("play", () => this.play());
        navigator.mediaSession.setActionHandler("pause", () => this.pause());
        navigator.mediaSession.setActionHandler("previoustrack", () =>
          this.seekLineByOffset(-1)
        );
        navigator.mediaSession.setActionHandler("nexttrack", () =>
          this.seekLineByOffset(1)
        );
        navigator.mediaSession.setActionHandler("seekbackward", () =>
          this.seek(this.currentTime - 5, this.isPlaying)
        );
        navigator.mediaSession.setActionHandler("seekforward", () =>
          this.seek(this.currentTime + 5, this.isPlaying)
        );
      } catch (err) {
        console.warn("[AudioPlayer] MediaSession setup warning:", err);
      }
    }

    _updateMediaSessionState(state) {
      if ("mediaSession" in navigator) {
        try {
          navigator.mediaSession.playbackState = state;
        } catch (_) {}
      }
    }
  }

  global.Escuta = global.Escuta || {};
  global.Escuta.AudioPlayer = AudioPlayer;
})(window);
