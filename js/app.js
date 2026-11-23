/**
 * Escuta A1 (Gemini Edition) — Main Application Controller
 * Coordinates Home Catalog, 6 SLA Learning Steps, Sticky Player,
 * Symbol Grounding Popups, SM-2 SRS Flashcards, and Local AI Pipeline UI.
 */
(function (global) {
  "use strict";

  const STEP_NAMES = {
    1: "① 字幕なしで聞く（全体推測）",
    2: "② 字幕あり（精聴・記号接地）",
    3: "③ チャンク＆文法予測（気づき）",
    4: "④ 練習（4択＆録音A/B比較）",
    5: "⑤ 反復（耳慣らしループ）",
    6: "⑥ 振り返り（文化・メタ認知）",
  };

  function escapeHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatSec(sec) {
    const s = Math.max(0, Math.floor(Number(sec) || 0));
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return `${m}:${rem < 10 ? "0" : ""}${rem}`;
  }

  function formatBracketHighlight(text) {
    return escapeHtml(text).replace(
      /\[([^\]]+)\]/g,
      '<span class="grammar-highlight">$1</span>'
    );
  }

  /**
   * Built-in rich SVG illustrations so scenes have expressive Brain Soaking visuals
   * even before `scripts/generate_visuals.py` generates WebP/MP4 files.
   */
  function buildFallbackSceneSvg(scene, lessonTitle) {
    const idx = (scene && scene.index) || 1;
    if (idx === 1) {
      // Manaus Scene 1: Encontro das Águas (Black Rio Negro + Sandy Yellow Rio Solimões + Boat)
      return `
      <svg viewBox="0 0 640 260" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="水の出会い">
        <defs>
          <linearGradient id="sky1" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#0284c7"/>
            <stop offset="100%" stop-color="#bae6fd"/>
          </linearGradient>
        </defs>
        <rect width="640" height="115" fill="url(#sky1)"/>
        <circle cx="540" cy="46" r="26" fill="#fde047" opacity="0.92"/>
        <path d="M0 115 Q90 82 190 112 T390 108 T640 115 Z" fill="#065f46"/>
        <!-- Left/Top dark Rio Negro -->
        <path d="M0 115 L640 115 L640 185 Q340 165 0 215 Z" fill="#0f172a"/>
        <!-- Right/Bottom sandy yellow Rio Solimões -->
        <path d="M0 215 Q340 165 640 185 L640 260 L0 260 Z" fill="#ca8a04"/>
        <path d="M0 215 Q340 165 640 185" stroke="#fef08a" stroke-width="3" stroke-dasharray="8 6" fill="none" opacity="0.75"/>
        <!-- Small wooden riverboat with Ana & Pedro -->
        <g transform="translate(215, 132)">
          <polygon points="0,34 150,34 132,54 18,54" fill="#78350f"/>
          <rect x="20" y="30" width="110" height="5" fill="#f59e0b"/>
          <!-- Ana (white shirt) -->
          <circle cx="55" cy="14" r="9" fill="#fed7aa"/>
          <path d="M43 32 Q55 20 67 32 Z" fill="#ffffff"/>
          <!-- Pedro (yellow shirt) -->
          <circle cx="95" cy="13" r="9" fill="#fdba74"/>
          <path d="M83 32 Q95 20 107 32 Z" fill="#ffd54f"/>
        </g>
      </svg>`;
    }
    if (idx === 2) {
      // Manaus Scene 2: Close-up of non-mixing black & yellow water currents
      return `
      <svg viewBox="0 0 640 260" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="混ざらない2つの川">
        <rect width="640" height="260" fill="#0f172a"/>
        <path d="M310 0 C275 75, 355 165, 295 260 L640 260 L640 0 Z" fill="#d97706"/>
        <path d="M310 0 C275 75, 355 165, 295 260" stroke="#fde68a" stroke-width="4" fill="none"/>
        <!-- Gentle waves on Rio Negro (warm & calm) -->
        <path d="M55 78 Q95 70 135 78 T215 78" stroke="#38bdf8" stroke-width="3" fill="none" opacity="0.55"/>
        <path d="M75 165 Q115 157 155 165 T235 165" stroke="#38bdf8" stroke-width="3" fill="none" opacity="0.45"/>
        <!-- Fast arrows/ripples on Rio Solimões (cold, fast, heavy) -->
        <path d="M395 70 L535 70 M515 58 L538 70 L515 82" stroke="#fef08a" stroke-width="4" fill="none" opacity="0.8"/>
        <path d="M420 145 L575 145 M555 133 L578 145 L555 157" stroke="#fef08a" stroke-width="4" fill="none" opacity="0.8"/>
        <path d="M385 212 L525 212 M505 200 L528 212 L505 224" stroke="#fef08a" stroke-width="4" fill="none" opacity="0.8"/>
      </svg>`;
    }
    if (idx === 3) {
      // Manaus Scene 3: Mercado Municipal — Açaí bowls, fried fish, farinha
      return `
      <svg viewBox="0 0 640 260" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="マナウスの市場">
        <rect width="640" height="260" fill="#1e1b4b"/>
        <!-- Market awning -->
        <rect x="0" y="0" width="640" height="46" fill="#059669"/>
        <path d="M0 46 L40 64 L80 46 L120 64 L160 46 L200 64 L240 46 L280 64 L320 46 L360 64 L400 46 L440 64 L480 46 L520 64 L560 46 L600 64 L640 46 Z" fill="#10b981"/>
        <!-- Wooden counter -->
        <rect x="0" y="165" width="640" height="95" fill="#78350f"/>
        <rect x="0" y="160" width="640" height="10" fill="#b45309"/>
        <!-- Dark purple Açaí bowl -->
        <ellipse cx="195" cy="152" rx="52" ry="18" fill="#4c1d95"/>
        <path d="M143 152 Q195 202 247 152 Z" fill="#581c87"/>
        <!-- Golden fried fish plate -->
        <ellipse cx="345" cy="158" rx="62" ry="16" fill="#fef3c7"/>
        <path d="M300 154 Q345 130 382 154 Q345 174 300 154 Z" fill="#d97706"/>
        <polygon points="378,154 398,142 396,166" fill="#b45309"/>
        <!-- Farinha bowl -->
        <ellipse cx="485" cy="154" rx="44" ry="15" fill="#fde68a"/>
        <path d="M441 154 Q485 194 529 154 Z" fill="#92400e"/>
      </svg>`;
    }

    // Generic tropical Brazilian scene fallback
    return `
    <svg viewBox="0 0 640 260" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="genBg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#065f46"/>
          <stop offset="100%" stop-color="#0f172a"/>
        </linearGradient>
      </defs>
      <rect width="640" height="260" fill="url(#genBg)"/>
      <circle cx="520" cy="64" r="38" fill="#ffd54f" opacity="0.25"/>
      <text x="32" y="135" fill="#f8fafc" font-size="22" font-weight="bold">${escapeHtml(
        (scene && (scene.titleJa || scene.title)) || lessonTitle || "Escuta A1"
      )}</text>
    </svg>`;
  }

  class EscutaApp {
    constructor() {
      this.storage = new global.Escuta.SRSStorage();
      this.recorder = new global.Escuta.VoiceRecorder();

      this.catalog = [];
      this.selectedCategory = "all";
      this.currentLesson = null;
      this.vocabMap = new Map();
      this.currentStep = 1;
      this.showJaInStep2 = true;

      // Step 4 state
      this.step4Submode = "quiz"; // "quiz" | "repeat"
      this.repeatLineIndex = 0;
      this.abAutoCompare = true;
      this.abStatusText = "";
      this.quizRevealPt = {};

      // Step 5 state
      this.step5GuideMode = false;

      // SRS Session state
      this.srsQueue = [];
      this.srsCurrentCard = null;
      this.srsFlipped = false;

      // Local AI Server status
      this.localServerAvailable = false;

      this.player = new global.Escuta.AudioPlayer({
        initialRate: this.storage.getPlaybackRate(),
        onTimeUpdate: (cur, dur) => this._handleTimeUpdate(cur, dur),
        onLineChange: (line) => this._handleLineChange(line),
        onSceneChange: (scene) => this._handleSceneChange(scene),
        onPlayStateChange: (playing) => this._handlePlayStateChange(playing),
        onComplete: () => this._handleAudioComplete(),
        onLoopIncrement: (count) => this._handleLoopIncrement(count),
        onModeDetected: (mode) => this._handleAudioModeDetected(mode),
      });
    }

    async init() {
      this._applyTheme(this.storage.getTheme());
      this._bindGlobalUI();
      await this._checkLocalServer();
      const hyd = await this.storage.hydrate(this.localServerAvailable);
      this._applyTheme(this.storage.getTheme());
      this.player.setPlaybackRate(this.storage.getPlaybackRate());
      await this._loadCatalog();
      this.renderHome();
      if (hyd.importedFromHash) {
        this.showToast(`引き継ぎ完了！カード合計 ${hyd.totalCards} 枚を統合しました`);
      } else if (hyd.restoredCount > 0) {
        this.showToast(`バックアップ層から復習カード ${hyd.restoredCount} 枚を自動復元しました`);
      }
    }

    _applyTheme(theme) {
      document.documentElement.setAttribute("data-theme", theme);
      const icon = document.getElementById("themeToggleIcon");
      if (icon) icon.textContent = theme === "dark" ? "☀️" : "🌙";
    }

    _bindGlobalUI() {
      document.getElementById("brandHomeTrigger").addEventListener("click", () => {
        this.navigateHome();
      });

      document.getElementById("backToHomeBtn").addEventListener("click", () => {
        this.navigateHome();
      });

      document.getElementById("themeToggleBtn").addEventListener("click", () => {
        const next = this.storage.getTheme() === "dark" ? "light" : "dark";
        this.storage.setTheme(next);
        this._applyTheme(next);
      });

      document.getElementById("startSrsBtn").addEventListener("click", () => {
        this.openSrsModal();
      });

      document.getElementById("aiCreateOpenBtn").addEventListener("click", () => {
        this.openAiGeneratorModal();
      });

      const apiKeyBtn = document.getElementById("apiKeyOpenBtn");
      if (apiKeyBtn) {
        apiKeyBtn.addEventListener("click", () => {
          this.openApiKeyModal();
        });
      }

      // Sync URL Copy (localhost <-> GitHub Pages / Safari <-> Home Screen PWA)
      const syncBtn = document.getElementById("copySyncUrlBtn");
      if (syncBtn) {
        syncBtn.addEventListener("click", async () => {
          const url = this.storage.buildSyncUrl("https://degaullev.github.io/escuta-a1/");
          try {
            await navigator.clipboard.writeText(url);
            this.showToast("引き継ぎURLをコピーしました！移行先のブラウザで開くと統合されます");
          } catch (_) {
            window.prompt("この引き継ぎURLをコピーして移行先で開いてください:", url);
          }
        });
      }

      // Backup Export / Import
      document.getElementById("exportJsonBtn").addEventListener("click", () => {
        const jsonStr = this.storage.exportJSON();
        const blob = new Blob([jsonStr], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        const dateTag = new Date().toISOString().slice(0, 10);
        a.href = url;
        a.download = `escuta-a1-backup-${dateTag}.json`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        this.showToast("学習履歴JSONを書き出しました");
      });

      const fileInput = document.getElementById("importJsonFileInput");
      document.getElementById("importJsonBtn").addEventListener("click", () => {
        fileInput.value = "";
        fileInput.click();
      });
      fileInput.addEventListener("change", async (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;
        try {
          const text = await file.text();
          const summary = this.storage.importJSON(text);
          this._applyTheme(this.storage.getTheme());
          this.renderHome();
          this.showToast(`復元完了（カード ${summary.cardCount}枚）`);
        } catch (err) {
          this.showToast(`読み込みエラー: ${err.message}`);
        }
      });

      // Step Tabs
      document.getElementById("stepTabsNav").addEventListener("click", (e) => {
        const btn = e.target.closest("[data-step]");
        if (!btn) return;
        this.switchStep(Number(btn.dataset.step));
      });

      // Player Controls
      document.getElementById("playPauseBtn").addEventListener("click", () => {
        this.player.togglePlay();
      });
      document.getElementById("prevLineBtn").addEventListener("click", () => {
        this.player.seekLineByOffset(-1);
      });
      document.getElementById("nextLineBtn").addEventListener("click", () => {
        this.player.seekLineByOffset(1);
      });

      const slider = document.getElementById("timelineSlider");
      slider.addEventListener("input", (e) => {
        this.player.seek(Number(e.target.value), this.player.isPlaying);
      });

      document.querySelectorAll(".speed-btn").forEach((btn) => {
        btn.classList.toggle(
          "active",
          Number(btn.dataset.rate) === this.storage.getPlaybackRate()
        );
        btn.addEventListener("click", () => {
          const rate = Number(btn.dataset.rate);
          this.storage.setPlaybackRate(rate);
          this.player.setPlaybackRate(rate);
          document.querySelectorAll(".speed-btn").forEach((b) => {
            b.classList.toggle("active", Number(b.dataset.rate) === rate);
          });
          this.showToast(`再生速度 ×${rate}`);
        });
      });

      // Close modals on backdrop tap
      ["vocabModalBackdrop", "srsModalBackdrop", "aiModalBackdrop"].forEach((id) => {
        const backdrop = document.getElementById(id);
        backdrop.addEventListener("click", (e) => {
          if (e.target === backdrop) {
            backdrop.classList.add("hidden");
          }
        });
      });
    }

    async _checkLocalServer() {
      if (global.location.protocol === "file:") {
        this.localServerAvailable = false;
        return;
      }
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          this.localServerAvailable = Boolean(data && data.ok);
          this.apiKeyConfigured = Boolean(data && data.apiKeyConfigured);
        }
      } catch (_) {
        this.localServerAvailable = false;
      }
      const apiKeyBtn = document.getElementById("apiKeyOpenBtn");
      const aiCreateBtn = document.getElementById("aiCreateOpenBtn");
      if (!this.localServerAvailable) {
        if (apiKeyBtn) apiKeyBtn.classList.add("hidden");
        if (aiCreateBtn) aiCreateBtn.classList.add("hidden");
      } else {
        const keyLabel = document.getElementById("apiKeyBtnLabel");
        if (keyLabel) {
          keyLabel.textContent = this.apiKeyConfigured ? "🟢 キー登録済" : "🔑 APIキー登録";
        }
      }
      const badge = document.getElementById("serverModeIndicator");
      if (badge) {
        badge.textContent = this.localServerAvailable
          ? "🟢 ローカルAI管理モード"
          : "📱 静的ビューアーモード";
      }
    }

    async _loadCatalog() {
      if (global.ESCUTA_EMBEDDED_DATA && global.ESCUTA_EMBEDDED_DATA.index) {
        this.catalog = global.ESCUTA_EMBEDDED_DATA.index.lessons || [];
        return;
      }
      try {
        const res = await fetch("lessons/index.json", { cache: "no-cache" });
        const json = await res.json();
        this.catalog = json.lessons || [];
      } catch (err) {
        console.error("[EscutaApp] Failed to load lessons/index.json:", err);
        this.catalog = [];
      }
    }

    async _fetchLesson(entry) {
      if (
        global.ESCUTA_EMBEDDED_DATA &&
        global.ESCUTA_EMBEDDED_DATA.lessons &&
        global.ESCUTA_EMBEDDED_DATA.lessons[entry.id]
      ) {
        return global.ESCUTA_EMBEDDED_DATA.lessons[entry.id];
      }
      const res = await fetch(entry.path, { cache: "no-cache" });
      if (!res.ok) throw new Error(`教材の読み込みに失敗しました (${res.status})`);
      return res.json();
    }

    /* ==================== HOME SCREEN ==================== */

    navigateHome() {
      this.player.pause();
      if (this.recorder.isRecording) {
        this.recorder.stopRecording();
      }
      document.querySelector(".app-shell").classList.remove("in-lesson");
      document.getElementById("lessonView").classList.add("hidden");
      document.getElementById("homeView").classList.remove("hidden");
      this.renderHome();
    }

    renderHome() {
      // SRS Hero stats
      const allCards = this.storage.getAllCards();
      const dueCards = this.storage.getDueCards();
      const summaryEl = document.getElementById("srsSummaryText");
      const startBtn = document.getElementById("startSrsBtn");

      if (allCards.length === 0) {
        summaryEl.textContent =
          "まだカードがありません。レッスン内の単語やStep ③から「＋カード追加」してみましょう！";
        startBtn.disabled = false;
        startBtn.innerHTML = "<span>💡 サンプル3語を登録して復習を試す</span>";
      } else if (dueCards.length > 0) {
        summaryEl.textContent = `今日復習タイミングのカード: ${dueCards.length}枚（登録合計 ${allCards.length}枚）`;
        startBtn.disabled = false;
        startBtn.innerHTML = `<span>🎧 今すぐ復習する（${dueCards.length}枚）</span>`;
      } else {
        summaryEl.textContent = `今日の復習はすべて完了！🎉（登録合計 ${allCards.length}枚）`;
        startBtn.disabled = false;
        startBtn.innerHTML = `<span>🔁 前倒しで復習する（全${allCards.length}枚）</span>`;
      }

      // Category filter pills
      const catTitle = document.getElementById("catalogSectionTitle");
      if (catTitle) {
        catTitle.textContent = `📚 マナウス教材一覧（全${this.catalog.length}課）`;
      }

      const filterBar = document.getElementById("categoryFilterBar");
      if (filterBar) {
        const categories = [
          { id: "all", label: `すべて (${this.catalog.length})` },
          { id: "history", label: "🏛 歴史・街歩き" },
          { id: "food", label: "🍽 グルメ・市場" },
          { id: "nature", label: "🌿 自然・川辺" },
          { id: "culture", label: "🎭 文化・暮らし" },
        ];
        filterBar.innerHTML = categories
          .map(
            (c) =>
              `<button type="button" class="cat-pill ${
                this.selectedCategory === c.id ? "active" : ""
              }" data-cat="${c.id}">${escapeHtml(c.label)}</button>`
          )
          .join("");
        filterBar.querySelectorAll("[data-cat]").forEach((btn) => {
          btn.addEventListener("click", () => {
            this.selectedCategory = btn.dataset.cat;
            this.renderHome();
          });
        });
      }

      // Lesson catalog cards
      const listEl = document.getElementById("lessonListContainer");
      if (!this.catalog.length) {
        listEl.innerHTML = `<div class="utility-card">教材が見つかりません。ローカルサーバー経由で開いてください。</div>`;
        return;
      }

      const filteredCatalog =
        this.selectedCategory === "all"
          ? this.catalog
          : this.catalog.filter((x) => x.category === this.selectedCategory);

      listEl.innerHTML = filteredCatalog
        .map((item) => {
          const doneCount = this.storage.getCompletedStepCount(item.id);
          const pct = Math.round((doneCount / 6) * 100);
          const stepChips = [1, 2, 3, 4, 5, 6]
            .map((s) => {
              const done = this.storage.isStepCompleted(item.id, s);
              return `<span class="step-chip ${done ? "done" : ""}">Step ${s}${
                done ? " ✓" : ""
              }</span>`;
            })
            .join("");

          return `
          <button type="button" class="lesson-card" data-lesson-id="${escapeHtml(item.id)}">
            <div class="lesson-card-header">
              <span class="lesson-level-tag">${escapeHtml(item.level || "CEFR A1")}</span>
              <span class="lesson-meta-tag">${escapeHtml(
                item.badge || `${item.sceneCount || 3}場面・${item.lineCount || 12}文`
              )}</span>
            </div>
            <h3 class="lesson-title">${escapeHtml(item.title)}</h3>
            <p class="lesson-title-ja">${escapeHtml(item.titleJa || "")}</p>
            <p class="lesson-desc">${escapeHtml(item.description || "")}</p>
            <div class="progress-bar-track" aria-label="学習進捗 ${pct}%">
              <div class="progress-bar-fill" style="width: ${pct}%;"></div>
            </div>
            <div class="step-check-chips">${stepChips}</div>
          </button>`;
        })
        .join("");

      listEl.querySelectorAll("[data-lesson-id]").forEach((card) => {
        card.addEventListener("click", () => {
          this.openLesson(card.dataset.lessonId);
        });
      });
    }

    /* ==================== LESSON VIEW ==================== */

    async openLesson(lessonId) {
      const entry = this.catalog.find((c) => c.id === lessonId);
      if (!entry) return;

      try {
        const lesson = await this._fetchLesson(entry);
        this.currentLesson = lesson;
        this.vocabMap.clear();
        (lesson.vocabulary || []).forEach((v) => this.vocabMap.set(v.id, v));
        this.repeatLineIndex = 0;
        this.quizRevealPt = {};

        document.querySelector(".app-shell").classList.add("in-lesson");
        document.getElementById("homeView").classList.add("hidden");
        document.getElementById("lessonView").classList.remove("hidden");
        document.getElementById("lessonNavTitle").textContent =
          lesson.titleJa || lesson.title;

        await this.player.loadLesson(lesson);
        const slider = document.getElementById("timelineSlider");
        slider.max = String(this.player.duration);
        slider.value = "0";
        document.getElementById("durationLabel").textContent = formatSec(
          this.player.duration
        );

        const savedStep = this.storage.getLessonState(lesson.id).lastStep || 1;
        this.switchStep(savedStep);
        global.scrollTo({ top: 0, behavior: "instant" });
      } catch (err) {
        this.showToast(err.message);
      }
    }

    switchStep(stepNum) {
      if (!this.currentLesson) return;
      this.currentStep = stepNum;
      this.storage.setLastStep(this.currentLesson.id, stepNum);

      // Configure repeat loop options only for Step 5
      if (stepNum === 5) {
        this.player.setRepeatOptions({
          loop: true,
          jaGuide: this.step5GuideMode,
        });
      } else {
        this.player.setRepeatOptions({ loop: false, jaGuide: false });
      }

      // Sticky player visibility: visible in Steps 1, 2, 5; compact/optional in 3, 4, 6
      const deck = document.getElementById("stickyPlayerDeck");
      if (stepNum === 1 || stepNum === 2 || stepNum === 5) {
        deck.classList.remove("hidden");
      } else {
        this.player.pause();
        deck.classList.add("hidden");
      }

      this._refreshStepTabsUI();
      this._renderSubtitleStage(this.player.activeLine);
      this._renderSceneVisual(this.player.activeScene);
      this.renderStepBody();
    }

    _refreshStepTabsUI() {
      if (!this.currentLesson) return;
      const lessonId = this.currentLesson.id;
      const doneCount = this.storage.getCompletedStepCount(lessonId);
      document.getElementById("lessonStepProgressBadge").textContent = `${doneCount}/6 ✓`;

      document.querySelectorAll("#stepTabsNav .step-tab-btn").forEach((btn) => {
        const s = Number(btn.dataset.step);
        btn.classList.toggle("active", s === this.currentStep);
        btn.classList.toggle("completed", this.storage.isStepCompleted(lessonId, s));
      });
    }

    markCurrentStepDone() {
      if (!this.currentLesson) return;
      const already = this.storage.isStepCompleted(
        this.currentLesson.id,
        this.currentStep
      );
      this.storage.setStepCompleted(this.currentLesson.id, this.currentStep, !already);
      this._refreshStepTabsUI();
      this.renderStepBody();
      this.showToast(
        !already
          ? `Step ${this.currentStep} を完了（✓）にしました！`
          : `Step ${this.currentStep} の完了チェックを解除しました`
      );
    }

    /* ==================== PLAYER CALLBACKS ==================== */

    _handleAudioModeDetected(mode) {
      const badge = document.getElementById("audioModeBadge");
      if (!badge) return;
      badge.textContent =
        mode === "mp3" ? "CBR 128k MP3" : "Web Speech (pt-BR)";
    }

    _handlePlayStateChange(playing) {
      const btn = document.getElementById("playPauseBtn");
      if (btn) btn.textContent = playing ? "⏸" : "▶";
      const step5Btn = document.getElementById("step5BigPlayBtn");
      if (step5Btn) {
        step5Btn.textContent = playing ? "⏸ ループ再生を一時停止" : "▶ バックグラウンド反復を開始";
      }
    }

    _handleTimeUpdate(cur, dur) {
      document.getElementById("currentTimeLabel").textContent = formatSec(cur);
      document.getElementById("durationLabel").textContent = formatSec(dur);
      const slider = document.getElementById("timelineSlider");
      if (document.activeElement !== slider) {
        slider.value = String(cur);
      }
    }

    _handleSceneChange(scene) {
      this._renderSceneVisual(scene);
      if (this.currentStep === 1) {
        document.querySelectorAll(".scene-kw-card").forEach((el) => {
          el.classList.toggle("active-scene", scene && el.dataset.sceneId === scene.id);
        });
      }
    }

    _handleLineChange(line) {
      this._renderSubtitleStage(line);
      if (line && line.image) {
        this._renderSceneVisual(this.player.activeScene, line);
      }

      if (this.currentStep === 2 && line) {
        document.querySelectorAll(".line-card").forEach((el) => {
          const isMatch = el.dataset.lineId === line.id;
          el.classList.toggle("active", isMatch);
          if (isMatch && this.player.isPlaying) {
            this._scrollCardInsideStepBody(el);
          }
        });
      }
    }

    _scrollCardInsideStepBody(cardEl) {
      const scroller = document.getElementById("stepContentBody");
      if (!scroller || !cardEl) return;
      const scrollerRect = scroller.getBoundingClientRect();
      const cardRect = cardEl.getBoundingClientRect();
      const topOffset = cardRect.top - scrollerRect.top + scroller.scrollTop;
      const desiredTop = Math.max(0, topOffset - scroller.clientHeight * 0.18);
      scroller.scrollTo({ top: desiredTop, behavior: "smooth" });
    }

    _handleAudioComplete() {
      if (!this.currentLesson) return;
      if (
        (this.currentStep === 1 || this.currentStep === 2) &&
        !this.storage.isStepCompleted(this.currentLesson.id, this.currentStep)
      ) {
        this.storage.setStepCompleted(this.currentLesson.id, this.currentStep, true);
        this._refreshStepTabsUI();
        this.showToast(`通し再生完了！ Step ${this.currentStep} に ✓ が付きました`);
      }
    }

    _handleLoopIncrement(loopCount) {
      const el = document.getElementById("step5LoopCounter");
      if (el) el.textContent = `現在 ${loopCount} 周目`;
      if (
        this.currentLesson &&
        this.currentStep === 5 &&
        loopCount >= 2 &&
        !this.storage.isStepCompleted(this.currentLesson.id, 5)
      ) {
        this.storage.setStepCompleted(this.currentLesson.id, 5, true);
        this._refreshStepTabsUI();
      }
    }

    /* ==================== VISUAL & SUBTITLE STAGE ==================== */

    _renderSceneVisual(scene, activeLine = null) {
      const mount = document.getElementById("visualMediaMount");
      const label = document.getElementById("sceneOverlayLabel");
      if (!mount || !this.currentLesson) return;

      const activeScene =
        scene || (this.currentLesson.scenes && this.currentLesson.scenes[0]);
      if (label && activeScene) {
        label.textContent = activeScene.titleJa || activeScene.title;
      }

      const lineObj = activeLine || this.player.activeLine;
      const lineImage = lineObj && lineObj.image ? lineObj.image : null;
      const currentKey = lineImage
        ? `line:${lineImage}`
        : activeScene
        ? `scene:${activeScene.id}`
        : "default";
      if (mount.dataset.renderedScene === currentKey) return;
      mount.dataset.renderedScene = currentKey;

      const fallbackSvg = buildFallbackSceneSvg(
        activeScene,
        this.currentLesson.titleJa
      );

      // 0. Per-line still illustration (high-frequency storyboard mode)
      if (lineImage) {
        this._mountImageOrSvg(
          mount,
          Object.assign({}, activeScene, { image: lineImage }),
          fallbackSvg
        );
        return;
      }

      // 1. Separated <video muted loop playsinline> if scene.video is defined
      if (activeScene && activeScene.video) {
        mount.innerHTML = "";
        const video = document.createElement("video");
        video.src = activeScene.video;
        video.muted = true;
        video.loop = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute("muted", "");
        video.setAttribute("loop", "");
        video.setAttribute("playsinline", "");
        video.onerror = () => {
          this._mountImageOrSvg(mount, activeScene, fallbackSvg);
        };
        mount.appendChild(video);
        video.play().catch(() => {});
        return;
      }

      // 2. Consistent character still image -> fallback SVG
      this._mountImageOrSvg(mount, activeScene, fallbackSvg);
    }

    _mountImageOrSvg(mount, scene, fallbackSvg) {
      if (!scene || !scene.image || global.location.protocol === "file:") {
        mount.innerHTML = fallbackSvg;
        return;
      }
      mount.innerHTML = "";
      const img = document.createElement("img");
      img.className = "slide-img";
      img.alt = scene.titleJa || scene.title || "Scene illustration";
      img.src = scene.image;
      img.onerror = () => {
        mount.innerHTML = fallbackSvg;
      };
      mount.appendChild(img);
    }

    _renderSubtitleStage(line) {
      const stage = document.getElementById("subtitleStage");
      if (!stage || !this.currentLesson) return;

      // Step 1: Blind listening mode — never show full transcript text
      if (this.currentStep === 1) {
        const sc = this.player.activeScene;
        const kwText = sc
          ? (sc.keywords || []).map((k) => k.pt).join("  •  ")
          : "";
        stage.innerHTML = `
          <p class="subtitle-blind-hint">
            👂 <strong>字幕なし推測モード</strong> — 声のトーンと場面キーワードに集中<br/>
            <span style="color:#ffd54f;font-weight:700;">${escapeHtml(kwText)}</span>
          </p>`;
        return;
      }

      if (!line) {
        stage.innerHTML = `
          <p class="subtitle-blind-hint">
            ▶ 再生ボタンを押すか、下の文をタップしてスタート
          </p>`;
        return;
      }

      const isPedro = line.speaker === "Pedro";
      const speakerClass = isPedro ? "pedro" : "ana";
      const ptColorClass = isPedro ? "speaker-pedro" : "speaker-ana";

      stage.innerHTML = `
        <div class="subtitle-speaker-row">
          <span class="speaker-badge ${speakerClass}">${escapeHtml(line.speaker)}</span>
          <span class="time-label">#${line.index}</span>
        </div>
        <p class="subtitle-pt ${ptColorClass}">${this._renderTokenizedPt(line)}</p>
        ${
          this.showJaInStep2 || this.currentStep === 5
            ? `<p class="subtitle-ja">${escapeHtml(line.ja)}</p>`
            : ""
        }
      `;

      this._bindVocabTokens(stage);
    }

    _renderTokenizedPt(line) {
      const vocabItems = (line.vocabIds || [])
        .map((id) => this.vocabMap.get(id))
        .filter(Boolean);

      if (!vocabItems.length) return escapeHtml(line.pt);

      // Build token -> vocabId lookup
      const tokenLookup = new Map();
      vocabItems.forEach((v) => {
        (v.matchTokens || [v.surface]).forEach((tok) => {
          tokenLookup.set(tok.toLowerCase(), v.id);
        });
      });

      // Split preserving whitespace & punctuation
      return line.pt
        .split(/(\s+)/)
        .map((part) => {
          if (/^\s+$/.test(part)) return part;
          const match = part.match(/^([¡¿"“(\[]*)([^\s"“”()\[\].,!?;:]+)([.,!?;:"”)\]]*)$/);
          if (!match) return escapeHtml(part);
          const [, lead, word, trail] = match;
          const vId = tokenLookup.get(word.toLowerCase());
          if (!vId) return escapeHtml(part);
          return `${escapeHtml(
            lead
          )}<span class="vocab-token" role="button" tabindex="0" data-vocab-id="${escapeHtml(
            vId
          )}">${escapeHtml(word)}</span>${escapeHtml(trail)}`;
        })
        .join("");
    }

    _bindVocabTokens(rootEl) {
      rootEl.querySelectorAll("[data-vocab-id]").forEach((el) => {
        el.addEventListener("click", (ev) => {
          ev.stopPropagation();
          this.openVocabModal(el.dataset.vocabId);
        });
      });
    }

    /* ==================== STEP CONTENT RENDERERS ==================== */

    renderStepBody() {
      const container = document.getElementById("stepContentBody");
      if (!container || !this.currentLesson) return;

      switch (this.currentStep) {
        case 1:
          this._renderStep1(container);
          break;
        case 2:
          this._renderStep2(container);
          break;
        case 3:
          this._renderStep3(container);
          break;
        case 4:
          this._renderStep4(container);
          break;
        case 5:
          this._renderStep5(container);
          break;
        case 6:
          this._renderStep6(container);
          break;
      }
    }

    _renderStepCompleteButton() {
      const done = this.storage.isStepCompleted(
        this.currentLesson.id,
        this.currentStep
      );
      return `
        <button type="button" class="complete-step-btn" id="toggleStepDoneBtn">
          ${
            done
              ? `✓ ${STEP_NAMES[this.currentStep]} 完了済み（タップで解除）`
              : `このステップを完了（✓）にする`
          }
        </button>
      `;
    }

    _bindStepDoneButton(container) {
      const btn = container.querySelector("#toggleStepDoneBtn");
      if (btn) {
        btn.addEventListener("click", () => this.markCurrentStepDone());
      }
    }

    /* ---------- Step 1: Blind Listening + Keyword Spotting ---------- */
    _renderStep1(container) {
      const lesson = this.currentLesson;
      const scenesHtml = (lesson.scenes || [])
        .map((sc) => {
          const active =
            this.player.activeScene && this.player.activeScene.id === sc.id;
          const kws = (sc.keywords || [])
            .map((kw) => {
              const checked = this.storage.isKeywordChecked(lesson.id, kw.id);
              return `
                <button type="button" class="kw-check-btn ${
                  checked ? "checked" : ""
                }" data-kw-id="${escapeHtml(kw.id)}">
                  <div>
                    <span class="kw-pt">${escapeHtml(kw.pt)}</span>
                    <span class="kw-ja"> — ${escapeHtml(kw.ja)}</span>
                    ${
                      kw.pronunciationHint
                        ? `<span class="kw-hint">💡 ${escapeHtml(
                            kw.pronunciationHint
                          )}</span>`
                        : ""
                    }
                  </div>
                  <span class="kw-mark">${checked ? "✓" : ""}</span>
                </button>`;
            })
            .join("");

          return `
            <div class="scene-kw-card ${active ? "active-scene" : ""}" data-scene-id="${escapeHtml(
            sc.id
          )}">
              <h3 class="scene-kw-title">${escapeHtml(sc.titleJa || sc.title)}</h3>
              <p class="scene-kw-setting">${escapeHtml(sc.setting || "")}</p>
              <div class="kw-grid">${kws}</div>
            </div>`;
        })
        .join("");

      container.innerHTML = `
        <div class="guide-banner">
          🌱 <strong>今は100%分からなくて大丈夫。</strong><br/>
          声のトーンや感情、そして下の「場面キーワード」の音だけを宝探しのように拾ってみましょう！聞き取れた単語はタップしてチェックできます。
        </div>
        ${scenesHtml}
        ${this._renderStepCompleteButton()}
      `;

      container.querySelectorAll("[data-kw-id]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const checked = this.storage.toggleKeyword(
            lesson.id,
            btn.dataset.kwId
          );
          btn.classList.toggle("checked", checked);
          btn.querySelector(".kw-mark").textContent = checked ? "✓" : "";
        });
      });

      this._bindStepDoneButton(container);
    }

    /* ---------- Step 2: Subtitled Listening + Symbol Grounding ---------- */
    _renderStep2(container) {
      const lesson = this.currentLesson;
      const sceneMap = new Map((lesson.scenes || []).map((s) => [s.id, s]));
      let lastSceneId = null;

      const rows = (lesson.lines || [])
        .map((line) => {
          let divider = "";
          if (line.sceneId !== lastSceneId) {
            lastSceneId = line.sceneId;
            const sc = sceneMap.get(line.sceneId);
            if (sc) {
              divider = `<div class="script-scene-divider">📍 ${escapeHtml(
                sc.titleJa || sc.title
              )}</div>`;
            }
          }
          const isActive =
            this.player.activeLine && this.player.activeLine.id === line.id;
          const spClass = line.speaker === "Pedro" ? "pedro" : "ana";

          return `
            ${divider}
            <article class="line-card ${isActive ? "active" : ""}" data-line-id="${escapeHtml(
            line.id
          )}" data-start="${line.start}">
              <div class="line-header">
                <span class="line-speaker-tag ${spClass}">${escapeHtml(
            line.speaker
          )} · ${formatSec(line.start)}</span>
                <span class="line-play-btn">▶ ここから再生</span>
              </div>
              <p class="line-pt">${this._renderTokenizedPt(line)}</p>
              ${
                this.showJaInStep2
                  ? `<p class="line-ja">${escapeHtml(line.ja)}</p>`
                  : ""
              }
            </article>
          `;
        })
        .join("");

      container.innerHTML = `
        <div class="guide-banner">
          🎯 <strong>精聴＆記号接地モード</strong><br/>
          点線付きの<span class="vocab-token" style="cursor:default;">重要語</span>をタップすると、「コアイメージ・文脈の意味・会話チャンク」が開きます。文カードをタップするとその秒数からすぐ再生します。
        </div>
        <div class="script-toolbar">
          <span class="lesson-meta-tag">全 ${lesson.lines.length} 文（Ana＝白 / Pedro＝黄）</span>
          <button type="button" class="pill-btn" id="toggleJaSubBtn">
            ${this.showJaInStep2 ? "日本語訳 ON" : "日本語訳 OFF"}
          </button>
        </div>
        <div class="script-list">${rows}</div>
        ${this._renderStepCompleteButton()}
      `;

      container.querySelector("#toggleJaSubBtn").addEventListener("click", () => {
        this.showJaInStep2 = !this.showJaInStep2;
        this._renderSubtitleStage(this.player.activeLine);
        this._renderStep2(container);
      });

      this._bindVocabTokens(container);

      container.querySelectorAll(".line-card").forEach((card) => {
        card.addEventListener("click", () => {
          const start = Number(card.dataset.start);
          this.player.seek(start, true);
        });
      });

      this._bindStepDoneButton(container);
    }

    /* ---------- Step 3: Chunks + Grammar Pattern Noticing ---------- */
    _renderStep3(container) {
      const lesson = this.currentLesson;
      const lineMap = new Map((lesson.lines || []).map((l) => [l.id, l]));

      const grammarHtml = (lesson.grammarQuizzes || [])
        .map((gq) => {
          const revealed = this.storage.isGrammarRevealed(lesson.id, gq.id);
          const exHtml = (gq.examples || [])
            .map(
              (ex) => `
              <div class="grammar-ex-item">
                <div style="font-weight:800;font-size:0.92rem;">${formatBracketHighlight(
                  ex.pt
                )}</div>
                <div style="font-size:0.78rem;color:var(--text-secondary);">${escapeHtml(
                  ex.ja
                )}</div>
              </div>`
            )
            .join("");

          return `
            <div class="grammar-box" data-grammar-id="${escapeHtml(gq.id)}">
              <h3 class="scene-kw-title">🔍 ${escapeHtml(gq.title)}</h3>
              <p style="font-size:0.83rem;margin:6px 0;">${escapeHtml(gq.prompt)}</p>
              <div class="grammar-examples">${exHtml}</div>
              ${
                gq.hint
                  ? `<p style="font-size:0.78rem;color:var(--text-secondary);margin:6px 0;">💡 ヒント: ${escapeHtml(
                      gq.hint
                    )}</p>`
                  : ""
              }
              <button type="button" class="pill-btn reveal-grammar-btn" data-gid="${escapeHtml(
                gq.id
              )}">
                ${revealed ? "✓ 法則の答え合わせ表示中" : "👀 自分の予測と答え合わせする"}
              </button>
              <div class="grammar-answer ${revealed ? "" : "hidden"}" id="ans-${escapeHtml(
            gq.id
          )}">
                <div style="font-weight:800;margin-bottom:4px;">✨ ${escapeHtml(
                  gq.ruleTitle
                )}</div>
                <div style="white-space:pre-line;">${escapeHtml(gq.explanation)}</div>
              </div>
            </div>
          `;
        })
        .join("");

      const chunksHtml = (lesson.vocabulary || [])
        .map((v) => {
          const inDeck = this.storage.hasCard(lesson.id, v.id);
          return `
            <div class="chunk-card">
              <div class="chunk-top">
                <div>
                  <p class="chunk-phrase">${escapeHtml(v.chunkPt)}</p>
                  <p class="chunk-ja">${escapeHtml(v.chunkJa)}</p>
                </div>
                <div class="chunk-actions">
                  <button type="button" class="icon-btn play-chunk-btn" data-vid="${escapeHtml(
                    v.id
                  )}" aria-label="チャンク再生">🔊</button>
                  <button type="button" class="icon-btn add-card-btn" data-vid="${escapeHtml(
                    v.id
                  )}">
                    ${inDeck ? "✓ 登録済" : "＋ カード"}
                  </button>
                </div>
              </div>
              <div class="chunk-core">🧭 <strong>${escapeHtml(
                v.surface
              )}</strong>: ${escapeHtml(v.coreImage)}</div>
            </div>`;
        })
        .join("");

      container.innerHTML = `
        <div class="guide-banner">
          🧠 <strong>法則予測（Noticing）＆チャンク学習</strong><br/>
          先に3つの文を見比べて「どんな法則があるか」予測してから解説を開くと、丸暗記の数倍深く定着します。
        </div>
        ${grammarHtml}
        <div class="section-header">
          <h3 class="section-title">🗣 そのまま使える会話チャンク（${
            (lesson.vocabulary || []).length
          }表現）</h3>
          <button type="button" class="pill-btn" id="addAllCardsBtn">＋ 一括カード登録</button>
        </div>
        ${chunksHtml}
        ${this._renderStepCompleteButton()}
      `;

      container.querySelectorAll(".reveal-grammar-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          const gid = btn.dataset.gid;
          this.storage.setGrammarRevealed(lesson.id, gid);
          const ans = container.querySelector(`#ans-${gid}`);
          if (ans) ans.classList.remove("hidden");
          btn.textContent = "✓ 法則の答え合わせ表示中";

          // Auto-check Step 3 if all grammar quizzes are revealed
          const allDone = (lesson.grammarQuizzes || []).every((g) =>
            this.storage.isGrammarRevealed(lesson.id, g.id)
          );
          if (allDone && !this.storage.isStepCompleted(lesson.id, 3)) {
            this.storage.setStepCompleted(lesson.id, 3, true);
            this._refreshStepTabsUI();
          }
        });
      });

      container.querySelectorAll(".play-chunk-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          const v = this.vocabMap.get(btn.dataset.vid);
          if (!v) return;
          const line = lineMap.get(v.lineId);
          this.player.playVocabChunk(v, line ? line.speaker : "Ana");
        });
      });

      container.querySelectorAll(".add-card-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          const v = this.vocabMap.get(btn.dataset.vid);
          if (!v) return;
          const res = this.storage.addCard(lesson.id, v);
          btn.textContent = "✓ 登録済";
          this.showToast(
            res.added ? `「${v.surface}」を復習カードに追加しました` : "すでに登録済みです"
          );
        });
      });

      container.querySelector("#addAllCardsBtn").addEventListener("click", () => {
        let added = 0;
        (lesson.vocabulary || []).forEach((v) => {
          if (this.storage.addCard(lesson.id, v).added) added++;
        });
        this._renderStep3(container);
        this.showToast(
          added > 0 ? `${added}枚のカードをまとめて追加しました！` : "すべて登録済みです"
        );
      });

      this._bindStepDoneButton(container);
    }

    /* ---------- Step 4: 4-Choice Listening Quiz & A/B Voice Recorder ---------- */
    _renderStep4(container) {
      const lesson = this.currentLesson;
      const lineMap = new Map((lesson.lines || []).map((l) => [l.id, l]));
      const ls = this.storage.getLessonState(lesson.id);

      const subSwitchHtml = `
        <div class="submode-switch" role="tablist">
          <button type="button" class="submode-btn ${
            this.step4Submode === "quiz" ? "active" : ""
          }" data-submode="quiz">🎧 4択聞き取りクイズ</button>
          <button type="button" class="submode-btn ${
            this.step4Submode === "repeat" ? "active" : ""
          }" data-submode="repeat">🎙 録音A/Bリピート</button>
        </div>
      `;

      let bodyHtml = "";
      if (this.step4Submode === "quiz") {
        bodyHtml = (lesson.listeningQuizzes || [])
          .map((q, idx) => {
            const line = lineMap.get(q.lineId);
            const answered = ls.quizAnswers[q.id];
            const hasAnswered = typeof answered === "number";
            const showPt = hasAnswered || Boolean(this.quizRevealPt[q.id]);

            const optsHtml = (q.options || [])
              .map((opt, oIdx) => {
                let cls = "";
                if (hasAnswered) {
                  if (oIdx === q.correctIndex) cls = "correct";
                  else if (oIdx === answered) cls = "wrong";
                }
                return `
                  <button type="button" class="quiz-option-btn ${cls}" data-qid="${escapeHtml(
                  q.id
                )}" data-oidx="${oIdx}">
                    ${oIdx + 1}. ${escapeHtml(opt)}
                  </button>`;
              })
              .join("");

            return `
              <div class="quiz-card">
                <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
                  <span class="lesson-level-tag">Q${idx + 1}</span>
                  <div style="display:flex;gap:6px;">
                    <button type="button" class="pill-btn quiz-play-btn" data-lid="${escapeHtml(
                      q.lineId
                    )}">🔊 音声を聞く</button>
                    <button type="button" class="icon-btn quiz-hint-btn" data-qid="${escapeHtml(
                      q.id
                    )}">文字ヒント</button>
                  </div>
                </div>
                ${
                  showPt && line
                    ? `<p style="margin:8px 0 4px;font-weight:700;color:var(--sky);">${escapeHtml(
                        line.pt
                      )}</p>`
                    : ""
                }
                <p style="margin:10px 0 4px;font-size:0.86rem;font-weight:700;">${escapeHtml(
                  q.question
                )}</p>
                ${optsHtml}
                ${
                  hasAnswered
                    ? `<div class="grammar-answer" style="margin-top:10px;">
                        ${
                          answered === q.correctIndex ? "⭕ 正解！" : "💡 惜しい！"
                        } ${escapeHtml(q.explanation || "")}
                      </div>`
                    : ""
                }
              </div>`;
          })
          .join("");
      } else {
        // Pronunciation A/B Comparison Repeat UI
        const lines = lesson.lines || [];
        const line = lines[this.repeatLineIndex] || lines[0];
        const hasRec = line && this.recorder.hasRecording(line.id);
        const isRec = this.recorder.isRecording;

        bodyHtml = `
          <div class="guide-banner">
            👄 <strong>生理学的フィードバック（即時A/B聴き比べ）</strong><br/>
            お手本を聞いたあと自分の声で録音すると、<strong>「お手本 → 自分の声」</strong>が連続再生されます。リズム・鼻母音（ão）・リエゾンの違いを耳で比べましょう（※録音はメモリ上のみで保持され保存されません）。
          </div>
          <div class="recorder-card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
              <button type="button" class="icon-btn" id="repPrevBtn">← 前の文</button>
              <span class="lesson-level-tag">文 ${this.repeatLineIndex + 1} / ${
          lines.length
        }（${escapeHtml(line.speaker)}）</span>
              <button type="button" class="icon-btn" id="repNextBtn">次の文 →</button>
            </div>
            <p style="font-size:1.08rem;font-weight:800;margin:8px 0 4px;">${escapeHtml(
              line.pt
            )}</p>
            <p style="font-size:0.84rem;color:var(--text-secondary);margin:0 0 10px;">${escapeHtml(
              line.ja
            )}</p>

            <div class="rec-btn-row">
              <button type="button" class="rec-action-btn" id="repPlayModelBtn">
                <span style="font-size:1.2rem;">🔊</span>
                <span>① お手本</span>
              </button>
              <button type="button" class="rec-action-btn ${
                isRec ? "recording" : ""
              }" id="repRecordBtn">
                <span style="font-size:1.2rem;">${isRec ? "⏹" : "🎙"}</span>
                <span>${isRec ? "録音停止" : "② 録音する"}</span>
              </button>
              <button type="button" class="rec-action-btn ${
                hasRec ? "ab-ready" : ""
              }" id="repCompareBtn" ${hasRec ? "" : "disabled"}>
                <span style="font-size:1.2rem;">🔁</span>
                <span>③ A/B比較</span>
              </button>
            </div>

            <label style="display:flex;align-items:center;gap:8px;margin-top:12px;font-size:0.78rem;color:var(--text-secondary);">
              <input type="checkbox" id="autoCompareToggle" ${
                this.abAutoCompare ? "checked" : ""
              } />
              録音停止後に自動で「お手本 → 自分の声」を連続再生する
            </label>

            <div id="abLiveStatus" style="margin-top:10px;font-size:0.82rem;font-weight:700;color:var(--accent);min-height:22px;">
              ${escapeHtml(this.abStatusText)}
            </div>
          </div>
        `;
      }

      container.innerHTML = `
        ${subSwitchHtml}
        ${bodyHtml}
        ${this._renderStepCompleteButton()}
      `;

      container.querySelectorAll("[data-submode]").forEach((btn) => {
        btn.addEventListener("click", () => {
          this.step4Submode = btn.dataset.submode;
          this._renderStep4(container);
        });
      });

      if (this.step4Submode === "quiz") {
        container.querySelectorAll(".quiz-play-btn").forEach((btn) => {
          btn.addEventListener("click", () => {
            const line = lineMap.get(btn.dataset.lid);
            if (line) this.player.playLineOrText({ line });
          });
        });

        container.querySelectorAll(".quiz-hint-btn").forEach((btn) => {
          btn.addEventListener("click", () => {
            const qid = btn.dataset.qid;
            this.quizRevealPt[qid] = !this.quizRevealPt[qid];
            this._renderStep4(container);
          });
        });

        container.querySelectorAll(".quiz-option-btn").forEach((btn) => {
          btn.addEventListener("click", () => {
            const qid = btn.dataset.qid;
            const oidx = Number(btn.dataset.oidx);
            this.storage.saveQuizAnswer(lesson.id, qid, oidx);

            const allAnswered = (lesson.listeningQuizzes || []).every(
              (q) => typeof ls.quizAnswers[q.id] === "number"
            );
            if (allAnswered && !this.storage.isStepCompleted(lesson.id, 4)) {
              this.storage.setStepCompleted(lesson.id, 4, true);
              this._refreshStepTabsUI();
            }
            this._renderStep4(container);
          });
        });
      } else {
        const lines = lesson.lines || [];
        const line = lines[this.repeatLineIndex] || lines[0];
        const statusEl = container.querySelector("#abLiveStatus");
        const setStatus = (msg) => {
          this.abStatusText = msg;
          if (statusEl) statusEl.textContent = msg;
        };

        container.querySelector("#repPrevBtn").addEventListener("click", () => {
          this.repeatLineIndex =
            (this.repeatLineIndex - 1 + lines.length) % lines.length;
          this.abStatusText = "";
          this._renderStep4(container);
        });
        container.querySelector("#repNextBtn").addEventListener("click", () => {
          this.repeatLineIndex = (this.repeatLineIndex + 1) % lines.length;
          this.abStatusText = "";
          this._renderStep4(container);
        });
        container
          .querySelector("#autoCompareToggle")
          .addEventListener("change", (e) => {
            this.abAutoCompare = e.target.checked;
          });

        container
          .querySelector("#repPlayModelBtn")
          .addEventListener("click", async () => {
            setStatus("🔊 お手本音声を再生中...");
            await this.player.playLineOrText({ line });
            setStatus("お手本再生完了。次はマイクで録音してみましょう！");
          });

        const runAB = async () => {
          try {
            await this.recorder.compareAB(line, this.player, (phase) => {
              if (phase === "model") setStatus("🔊 A: お手本を再生中...");
              else if (phase === "pause") setStatus("⏳ 聴き比べ切り替え...");
              else if (phase === "self") setStatus("🎙 B: あなたの録音を再生中...");
              else setStatus("✨ A/B比較完了！リズムや鼻母音の違いはどうでしたか？");
            });
          } catch (err) {
            this.showToast(err.message);
          }
        };

        container
          .querySelector("#repRecordBtn")
          .addEventListener("click", async () => {
            try {
              if (!this.recorder.isRecording) {
                await this.recorder.startRecording(line.id);
                setStatus("🔴 録音中... ポルトガル語で声に出したら「録音停止」をタップ");
                this._renderStep4(container);
              } else {
                await this.recorder.stopRecording();
                setStatus("録音完了！");
                this._renderStep4(container);
                if (this.abAutoCompare) {
                  await runAB();
                }
              }
            } catch (err) {
              setStatus("");
              this.showToast(`マイク利用不可: ${err.message}`);
            }
          });

        const cmpBtn = container.querySelector("#repCompareBtn");
        if (cmpBtn) {
          cmpBtn.addEventListener("click", runAB);
        }
      }

      this._bindStepDoneButton(container);
    }

    /* ---------- Step 5: Background Ear-Soaking Loop Mode ---------- */
    _renderStep5(container) {
      this.player.setRepeatOptions({
        loop: true,
        jaGuide: this.step5GuideMode,
      });

      container.innerHTML = `
        <div class="guide-banner">
          🔁 <strong>耳慣らしバックグラウンド反復モード（Media Session対応）</strong><br/>
          散歩・通勤・家事の合間に流しっぱなしにして、ポルトガル語の音とリズムに脳を浸しましょう。スマホのロック画面からも再生・一時停止・文送り操作が可能です。
        </div>

        <div class="loop-panel">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span class="scene-kw-title">再生スタイルを選択</span>
            <span class="lesson-level-tag" id="step5LoopCounter">現在 ${
              this.player.loopCount
            } 周目</span>
          </div>

          <button type="button" class="radio-card ${
            !this.step5GuideMode ? "selected" : ""
          }" data-guide-mode="off">
            <div style="font-weight:800;font-size:0.9rem;">🇧🇷 ポルトガル語のみ連続ループ再生</div>
            <div style="font-size:0.78rem;color:var(--text-secondary);margin-top:2px;">
              日本語を挟まず、自然な会話のテンポのまま繰り返し浴びるモード
            </div>
          </button>

          <button type="button" class="radio-card ${
            this.step5GuideMode ? "selected" : ""
          }" data-guide-mode="on">
            <div style="font-weight:800;font-size:0.9rem;">🇯🇵＋🇧🇷 ポーズ中に短い日本語ガイドを挟むモード</div>
            <div style="font-size:0.78rem;color:var(--text-secondary);margin-top:2px;">
              画面を見られない移動中でも意味を思い出しやすいよう、各文の前に短い日本語ガイドを読み上げます
            </div>
          </button>

          <button type="button" class="srs-start-btn" id="step5BigPlayBtn" style="margin-top:16px;">
            ${
              this.player.isPlaying
                ? "⏸ ループ再生を一時停止"
                : "▶ バックグラウンド反復を開始"
            }
          </button>
        </div>
        ${this._renderStepCompleteButton()}
      `;

      container.querySelectorAll("[data-guide-mode]").forEach((card) => {
        card.addEventListener("click", () => {
          this.step5GuideMode = card.dataset.guideMode === "on";
          this.player.setRepeatOptions({
            loop: true,
            jaGuide: this.step5GuideMode,
          });
          this._renderStep5(container);
        });
      });

      container.querySelector("#step5BigPlayBtn").addEventListener("click", () => {
        this.player.togglePlay();
      });

      this._bindStepDoneButton(container);
    }

    /* ---------- Step 6: Cultural Reflection & Meta-Cognitive Notes ---------- */
    _renderStep6(container) {
      const lesson = this.currentLesson;
      const ls = this.storage.getLessonState(lesson.id);

      const questionsHtml = (lesson.reflectionQuestions || [])
        .map((rq, idx) => {
          const picked = ls.reflectionAnswers[rq.id];
          const hasPicked = typeof picked === "number";
          const opts = (rq.options || [])
            .map((opt, oIdx) => {
              let cls = "";
              if (hasPicked) {
                if (oIdx === rq.correctIndex) cls = "correct";
                else if (oIdx === picked) cls = "wrong";
              }
              return `
                <button type="button" class="quiz-option-btn ${cls}" data-rqid="${escapeHtml(
                rq.id
              )}" data-oidx="${oIdx}">
                  ${escapeHtml(opt)}
                </button>`;
            })
            .join("");

          return `
            <div class="quiz-card">
              <span class="lesson-level-tag">理解・文化チェック ${idx + 1}</span>
              <p style="font-size:0.88rem;font-weight:700;margin:8px 0;">${escapeHtml(
                rq.question
              )}</p>
              ${opts}
              ${
                hasPicked
                  ? `<div class="grammar-answer" style="margin-top:10px;">
                      🌴 <strong>背景コラム:</strong> ${escapeHtml(
                        rq.culturalNote || ""
                      )}
                    </div>`
                  : ""
              }
            </div>`;
        })
        .join("");

      const savedStamp = ls.notes && ls.notes.updatedAt
        ? `自動保存済み (${new Date(ls.notes.updatedAt).toLocaleTimeString("ja-JP")})`
        : "入力すると localStorage に自動保存されます";

      container.innerHTML = `
        <div class="guide-banner">
          📝 <strong>振り返り（メタ認知・文化背景の定着）</strong><br/>
          ストーリーの背景を確認し、「今日聞き取れた音」と言語化しておくことで次回の知覚感度が高まります。
        </div>
        ${questionsHtml}

        <div class="quiz-card">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <h3 class="scene-kw-title">📓 学習振り返りメモ</h3>
            <span class="lesson-meta-tag" id="memoSavedStatus">${escapeHtml(
              savedStamp
            )}</span>
          </div>

          <div class="form-field">
            <label for="memoHeardInput">✨ 今日聞き取れるようになった音・フレーズ</label>
            <textarea id="memoHeardInput" class="memo-textarea" placeholder="例: quente が「ケンチ」と聞こえた、a gente toma のつながりが掴めた 等">${escapeHtml(
              (ls.notes && ls.notes.heardSounds) || ""
            )}</textarea>
          </div>

          <div class="form-field">
            <label for="memoUnclearInput">🔍 まだ曖昧な表現・次回意識したい音</label>
            <textarea id="memoUnclearInput" class="memo-textarea" placeholder="例: Solimões の鼻母音、Uma parte é preta のリエゾン 等">${escapeHtml(
              (ls.notes && ls.notes.unclearItems) || ""
            )}</textarea>
          </div>
        </div>
        ${this._renderStepCompleteButton()}
      `;

      container.querySelectorAll("[data-rqid]").forEach((btn) => {
        btn.addEventListener("click", () => {
          this.storage.saveReflectionAnswer(
            lesson.id,
            btn.dataset.rqid,
            Number(btn.dataset.oidx)
          );
          this._renderStep6(container);
        });
      });

      const heardEl = container.querySelector("#memoHeardInput");
      const unclearEl = container.querySelector("#memoUnclearInput");
      const statusEl = container.querySelector("#memoSavedStatus");

      const saveMemoNow = () => {
        const ts = this.storage.saveNotes(
          lesson.id,
          heardEl.value,
          unclearEl.value
        );
        if (statusEl) {
          statusEl.textContent = `自動保存済み ✓ (${new Date(
            ts
          ).toLocaleTimeString("ja-JP")})`;
        }
      };

      heardEl.addEventListener("input", saveMemoNow);
      unclearEl.addEventListener("input", saveMemoNow);

      this._bindStepDoneButton(container);
    }

    /* ==================== SYMBOL GROUNDING MODAL ==================== */

    openVocabModal(vocabId) {
      const v = this.vocabMap.get(vocabId);
      if (!v || !this.currentLesson) return;

      const backdrop = document.getElementById("vocabModalBackdrop");
      const sheet = document.getElementById("vocabModalSheet");
      const inDeck = this.storage.hasCard(this.currentLesson.id, v.id);

      sheet.innerHTML = `
        <div class="sheet-handle"></div>
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;">
          <div>
            <span class="lesson-level-tag">記号接地（Symbol Grounding）</span>
            <h3 style="margin:6px 0 2px;font-size:1.3rem;font-weight:900;">${escapeHtml(
              v.surface
            )}</h3>
            <span class="lesson-meta-tag">基本形: ${escapeHtml(
              v.lemma || v.surface
            )}</span>
          </div>
          <button type="button" class="icon-btn" id="closeVocabModalBtn">✕</button>
        </div>

        <div class="grounding-section">
          <span class="grounding-label">① コアイメージ（核となる感覚・空間図式）</span>
          <div style="font-size:0.88rem;">${escapeHtml(v.coreImage)}</div>
        </div>

        <div class="grounding-section">
          <span class="grounding-label">② この場面での意味</span>
          <div style="font-size:0.88rem;font-weight:700;">${escapeHtml(
            v.contextMeaning
          )}</div>
        </div>

        <div class="grounding-section">
          <span class="grounding-label">③ そのまま使える会話チャンク例</span>
          <div style="font-size:0.96rem;font-weight:800;">${escapeHtml(v.chunkPt)}</div>
          <div style="font-size:0.8rem;color:var(--text-secondary);margin-top:2px;">${escapeHtml(
            v.chunkJa
          )}</div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1.3fr;gap:8px;margin-top:14px;">
          <button type="button" class="icon-btn" id="modalPlayChunkBtn" style="min-height:46px;">
            🔊 チャンク音声
          </button>
          <button type="button" class="srs-start-btn" id="modalAddSrsBtn" style="margin-top:0;">
            ${inDeck ? "✓ 復習カード登録済み" : "＋ 復習カードに追加"}
          </button>
        </div>
      `;

      backdrop.classList.remove("hidden");

      sheet.querySelector("#closeVocabModalBtn").addEventListener("click", () => {
        backdrop.classList.add("hidden");
      });

      sheet.querySelector("#modalPlayChunkBtn").addEventListener("click", () => {
        this.player.playVocabChunk(v, "Ana");
      });

      sheet.querySelector("#modalAddSrsBtn").addEventListener("click", (e) => {
        const res = this.storage.addCard(this.currentLesson.id, v);
        e.currentTarget.textContent = "✓ 復習カード登録済み";
        this.showToast(
          res.added ? `「${v.surface}」をSRS復習カードに追加しました` : "すでに登録済みです"
        );
      });
    }

    /* ==================== SRS FLASHCARD REVIEW MODAL ==================== */

    async openSrsModal() {
      let allCards = this.storage.getAllCards();

      // If empty, offer quick seed of 3 core Manaus cards so user can experience SRS immediately
      if (allCards.length === 0 && this.catalog.length > 0) {
        try {
          const demoLesson = await this._fetchLesson(this.catalog[0]);
          (demoLesson.vocabulary || []).slice(0, 3).forEach((v) => {
            this.storage.addCard(demoLesson.id, v);
          });
          allCards = this.storage.getAllCards();
          this.renderHome();
          this.showToast("体験用に基本チャンク3枚をカード登録しました！");
        } catch (_) {}
      }

      const due = this.storage.getDueCards();
      this.srsQueue = due.length > 0 ? [...due] : [...allCards];
      this.srsFlipped = false;
      this.srsCurrentCard = this.srsQueue.shift() || null;

      document.getElementById("srsModalBackdrop").classList.remove("hidden");
      this._renderSrsSheet();
    }

    _renderSrsSheet() {
      const backdrop = document.getElementById("srsModalBackdrop");
      const sheet = document.getElementById("srsModalSheet");
      const card = this.srsCurrentCard;

      if (!card) {
        sheet.innerHTML = `
          <div class="sheet-handle"></div>
          <div style="text-align:center;padding:18px 8px;">
            <div style="font-size:2.2rem;">🎉</div>
            <h3 style="margin:8px 0 4px;">今回の復習セッション完了！</h3>
            <p style="font-size:0.84rem;color:var(--text-secondary);">
              忘却曲線（SM-2）に基づいて次回の復習タイミングをスケジュールしました。
            </p>
            <button type="button" class="complete-step-btn" id="closeSrsDoneBtn">ホームへ戻る</button>
          </div>
        `;
        sheet.querySelector("#closeSrsDoneBtn").addEventListener("click", () => {
          backdrop.classList.add("hidden");
          this.renderHome();
        });
        return;
      }

      const nextGoodDays = Math.max(
        3,
        Math.round(Math.max(1.2, card.intervalDays || 1) * 2.5)
      );

      sheet.innerHTML = `
        <div class="sheet-handle"></div>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span class="lesson-level-tag">残り ${this.srsQueue.length + 1} 枚</span>
          <button type="button" class="icon-btn" id="closeSrsBtn">✕ 閉じる</button>
        </div>

        <!-- Front Side: Audio + Cloze Phrase -->
        <div class="grounding-section" style="margin-top:12px;text-align:center;padding:18px 14px;">
          <span class="grounding-label">表面：音を聞いて空欄のチャンクを能動想起</span>
          <p style="font-size:1.18rem;font-weight:900;margin:10px 0 6px;">
            ${escapeHtml(this.srsFlipped ? card.chunkPt : card.clozePt)}
          </p>
          <p style="font-size:0.84rem;color:var(--text-secondary);margin:0 0 12px;">
            ヒント（意味）: ${escapeHtml(card.chunkJa)}
          </p>
          <button type="button" class="pill-btn" id="srsReplayBtn">🔊 音声を再生</button>
        </div>

        ${
          !this.srsFlipped
            ? `<button type="button" class="srs-start-btn" id="srsFlipBtn" style="margin-top:14px;">
                👀 裏面（答え＆コアイメージ）をめくる
              </button>`
            : `
              <div class="grounding-section">
                <span class="grounding-label">答え: ${escapeHtml(
                  card.clozeAnswer
                )}（基本形: ${escapeHtml(card.lemma)}）</span>
                <div style="font-size:0.86rem;margin-top:4px;">🧭 <strong>コアイメージ:</strong> ${escapeHtml(
                  card.coreImage
                )}</div>
                <div style="font-size:0.82rem;color:var(--text-secondary);margin-top:4px;">📌 <strong>文脈の意味:</strong> ${escapeHtml(
                  card.contextMeaning
                )}</div>
              </div>

              <div class="srs-rate-grid">
                <button type="button" class="srs-rate-btn again" data-rate="again">
                  <span>まだ</span>
                  <span style="font-size:0.7rem;font-weight:600;">再出題・翌日</span>
                </button>
                <button type="button" class="srs-rate-btn hard" data-rate="hard">
                  <span>微妙</span>
                  <span style="font-size:0.7rem;font-weight:600;">2日後</span>
                </button>
                <button type="button" class="srs-rate-btn good" data-rate="good">
                  <span>覚えた</span>
                  <span style="font-size:0.7rem;font-weight:600;">${nextGoodDays}日後 (×2.5)</span>
                </button>
              </div>
            `
        }
      `;

      // Auto-play audio on front reveal
      if (!this.srsFlipped) {
        this.player.playVocabChunk(card, "Ana");
      }

      sheet.querySelector("#closeSrsBtn").addEventListener("click", () => {
        backdrop.classList.add("hidden");
        this.renderHome();
      });

      sheet.querySelector("#srsReplayBtn").addEventListener("click", () => {
        this.player.playVocabChunk(card, "Ana");
      });

      const flipBtn = sheet.querySelector("#srsFlipBtn");
      if (flipBtn) {
        flipBtn.addEventListener("click", () => {
          this.srsFlipped = true;
          this._renderSrsSheet();
        });
      }

      sheet.querySelectorAll("[data-rate]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const rating = btn.dataset.rate;
          this.storage.reviewCard(card.key, rating);
          if (rating === "again") {
            // Re-queue once in current session for immediate active recall reinforcement
            if (!card._retriedInSession) {
              this.srsQueue.push(Object.assign({}, card, { _retriedInSession: true }));
            }
          }
          this.srsFlipped = false;
          this.srsCurrentCard = this.srsQueue.shift() || null;
          this._renderSrsSheet();
        });
      });
    }

    /* ==================== LOCAL AI GENERATOR MODAL (PHASE 5) ==================== */

    openApiKeyModal() {
      const backdrop = document.getElementById("aiModalBackdrop");
      const sheet = document.getElementById("aiModalSheet");
      backdrop.classList.remove("hidden");

      sheet.innerHTML = `
        <div class="sheet-handle"></div>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <h3 style="margin:0;font-size:1.05rem;">🔑 Gemini APIキーをローカル登録</h3>
          <button type="button" class="icon-btn" id="closeKeyModalBtn">✕</button>
        </div>
        <div class="guide-banner" style="margin-top:12px;">
          1. <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener" style="color:var(--accent);font-weight:800;text-decoration:underline;">Google AI Studio の API Keys ページ</a> を開いて <strong>Create API key</strong>（<code>AIza...</code> で始まる39文字）をコピー<br/>
          2. 下の欄に貼り付けて保存（Mac内の <code>.env</code> にのみ保存されます）
        </div>
        <div class="form-field">
          <label for="geminiKeyInput">GEMINI_API_KEY（AIza... で始まるキー）</label>
          <input id="geminiKeyInput" class="form-input" type="password" placeholder="AIzaSy..." autocomplete="off" />
        </div>
        <button type="button" class="srs-start-btn" id="saveKeyBtn" style="margin-top:14px;">
          💾 .env に保存する
        </button>
      `;

      sheet.querySelector("#closeKeyModalBtn").addEventListener("click", () => {
        backdrop.classList.add("hidden");
      });

      sheet.querySelector("#saveKeyBtn").addEventListener("click", async () => {
        const val = sheet.querySelector("#geminiKeyInput").value.trim();
        if (!val) {
          this.showToast("APIキーを貼り付けてください");
          return;
        }
        try {
          const res = await fetch("/api/config-key", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ apiKey: val }),
          });
          const data = await res.json();
          if (!res.ok || !data.ok) throw new Error(data.error || "保存失敗");
          this.apiKeyConfigured = true;
          const keyLabel = document.getElementById("apiKeyBtnLabel");
          if (keyLabel) keyLabel.textContent = "🟢 キー登録済";
          backdrop.classList.add("hidden");
          this.showToast(`APIキーを .env に保存しました (${data.masked})`);
        } catch (err) {
          this.showToast(`保存エラー: ${err.message}`);
        }
      });
    }

    openAiGeneratorModal() {
      const backdrop = document.getElementById("aiModalBackdrop");
      const sheet = document.getElementById("aiModalSheet");
      backdrop.classList.remove("hidden");

      if (!this.localServerAvailable) {
        sheet.innerHTML = `
          <div class="sheet-handle"></div>
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <h3 style="margin:0;font-size:1.05rem;">✨ AIに新しい教材を作ってもらう</h3>
            <button type="button" class="icon-btn" id="closeAiModalBtn">✕</button>
          </div>
          <div class="guide-banner" style="margin-top:12px;">
            現在は<strong>静的ビューアーモード</strong>で表示中です。<br/>
            PC上でローカル管理サーバーを起動すると、この画面から「題材入力 → 台本 → Gemini 3.8 TTS → 二重監査 → 一貫キャライラスト」を一括生成できます。
          </div>
          <div class="grounding-section">
            <span class="grounding-label">ローカル管理モードの起動コマンド</span>
            <pre style="margin:6px 0 0;font-size:0.78rem;overflow-x:auto;"><code>python3 scripts/server.py --port 8000</code></pre>
          </div>
          <button type="button" class="complete-step-btn" id="closeAiModalBtn2">閉じる</button>
        `;
        ["#closeAiModalBtn", "#closeAiModalBtn2"].forEach((sel) => {
          sheet.querySelector(sel).addEventListener("click", () => {
            backdrop.classList.add("hidden");
          });
        });
        return;
      }

      sheet.innerHTML = `
        <div class="sheet-handle"></div>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <h3 style="margin:0;font-size:1.05rem;">✨ AI教材自動生成パイプライン</h3>
          <button type="button" class="icon-btn" id="closeAiModalBtn">✕</button>
        </div>

        <div class="form-field">
          <label for="aiTopicInput">題材・シチュエーション（日本語）</label>
          <input id="aiTopicInput" class="form-input" type="text" placeholder="例: サンパウロのカフェでポン・デ・ケイジョとコーヒーを注文する" value="リオのビーチでココナッツウォーターを買う会話" />
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
          <div class="form-field">
            <label for="aiLessonIdInput">レッスンID（英数字）</label>
            <input id="aiLessonIdInput" class="form-input" type="text" value="rio-praia-a1" />
          </div>
          <div class="form-field">
            <label for="aiLinesInput">合計文数の目安</label>
            <input id="aiLinesInput" class="form-input" type="number" min="3" max="40" value="9" />
          </div>
        </div>

        <div class="grounding-section" style="margin-top:12px;">
          <span class="grounding-label">実行オプション（API消費コントロール）</span>
          <label style="display:flex;align-items:center;gap:8px;font-size:0.8rem;margin-top:6px;">
            <input type="checkbox" id="aiDryRunCheck" />
            ドライラン（APIを叩かずに構成・見積もりのみテスト生成）
          </label>
          <label style="display:flex;align-items:center;gap:8px;font-size:0.8rem;margin-top:6px;">
            <input type="checkbox" id="aiLimit3Check" checked />
            音声・監査を最初の3文だけに制限してテスト（--limit 3）
          </label>
          <label style="display:flex;align-items:center;gap:8px;font-size:0.8rem;margin-top:6px;">
            <input type="checkbox" id="aiVisualsCheck" />
            Ana / Pedro一貫キャラクター場面イラストも生成する
          </label>
          <label style="display:flex;align-items:center;gap:8px;font-size:0.8rem;margin-top:6px;">
            <input type="checkbox" id="aiVideoCheck" />
            重要場面のVeoショート情景ループ動画も生成する（--with-video）
          </label>
        </div>

        <div id="aiJobLogBox" class="grounding-section hidden" style="font-size:0.78rem;white-space:pre-wrap;max-height:150px;overflow-y:auto;"></div>

        <button type="button" class="srs-start-btn" id="runAiPipelineBtn" style="margin-top:14px;">
          🚀 パイプラインを実行する
        </button>
      `;

      sheet.querySelector("#closeAiModalBtn").addEventListener("click", () => {
        backdrop.classList.add("hidden");
      });

      sheet.querySelector("#runAiPipelineBtn").addEventListener("click", async (ev) => {
        const btn = ev.currentTarget;
        const logBox = sheet.querySelector("#aiJobLogBox");
        const payload = {
          topic: sheet.querySelector("#aiTopicInput").value.trim(),
          lessonId: sheet.querySelector("#aiLessonIdInput").value.trim(),
          lineCount: Number(sheet.querySelector("#aiLinesInput").value) || 9,
          dryRun: sheet.querySelector("#aiDryRunCheck").checked,
          limit: sheet.querySelector("#aiLimit3Check").checked ? 3 : 0,
          withVisuals: sheet.querySelector("#aiVisualsCheck").checked,
          withVideo: sheet.querySelector("#aiVideoCheck").checked,
        };

        if (!payload.topic || !payload.lessonId) {
          this.showToast("題材とレッスンIDを入力してください");
          return;
        }

        btn.disabled = true;
        logBox.classList.remove("hidden");
        logBox.textContent = "ジョブを開始しています...\n";

        try {
          const res = await fetch("/api/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          const data = await res.json();
          if (!res.ok || !data.jobId) {
            throw new Error(data.error || "生成開始に失敗しました");
          }
          await this._pollAiJob(data.jobId, logBox, btn);
        } catch (err) {
          logBox.textContent += `\nエラー: ${err.message}`;
          btn.disabled = false;
        }
      });
    }

    async _pollAiJob(jobId, logBox, btn) {
      while (true) {
        await new Promise((r) => setTimeout(r, 1200));
        const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
        const job = await res.json();
        logBox.textContent = (job.logs || []).join("\n");
        logBox.scrollTop = logBox.scrollHeight;

        if (job.status === "completed") {
          btn.disabled = false;
          await this._loadCatalog();
          this.renderHome();
          this.showToast("新しい教材の生成が完了しました！");
          return;
        }
        if (job.status === "failed") {
          btn.disabled = false;
          this.showToast("パイプライン実行中にエラーが発生しました");
          return;
        }
      }
    }

    /* ==================== TOAST ==================== */

    showToast(msg) {
      const el = document.getElementById("toastBanner");
      if (!el) return;
      el.textContent = msg;
      el.classList.remove("hidden");
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => {
        el.classList.add("hidden");
      }, 2400);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const app = new EscutaApp();
    global.escutaApp = app;
    app.init();
  });
})(window);
