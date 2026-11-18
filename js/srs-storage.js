/**
 * Escuta A1 — LocalStorage & SM-2 Spaced Repetition Manager
 * All learning history stays strictly in browser localStorage (100% private).
 */
(function (global) {
  "use strict";

  const STORAGE_KEY = "escuta_a1_state_v1";
  const DAY_MS = 24 * 60 * 60 * 1000;

  function createDefaultState() {
    return {
      schemaVersion: 1,
      theme: "dark",
      playbackRate: 0.85,
      lessons: {},
      srsCards: {},
      updatedAt: new Date().toISOString(),
    };
  }

  class SRSStorage {
    constructor() {
      this.state = this._load();
    }

    _load() {
      try {
        const raw = global.localStorage.getItem(STORAGE_KEY);
        if (!raw) return createDefaultState();
        const parsed = JSON.parse(raw);
        return Object.assign(createDefaultState(), parsed);
      } catch (err) {
        console.warn("[SRSStorage] Failed to load state, using defaults:", err);
        return createDefaultState();
      }
    }

    save() {
      this.state.updatedAt = new Date().toISOString();
      try {
        global.localStorage.setItem(STORAGE_KEY, JSON.stringify(this.state));
      } catch (err) {
        console.error("[SRSStorage] Failed to save state:", err);
      }
    }

    getTheme() {
      return this.state.theme || "dark";
    }

    setTheme(theme) {
      this.state.theme = theme === "light" ? "light" : "dark";
      this.save();
    }

    getPlaybackRate() {
      return this.state.playbackRate || 0.85;
    }

    setPlaybackRate(rate) {
      this.state.playbackRate = Number(rate) || 1.0;
      this.save();
    }

    _ensureLesson(lessonId) {
      if (!this.state.lessons[lessonId]) {
        this.state.lessons[lessonId] = {
          completedSteps: {},
          checkedKeywords: {},
          revealedGrammar: {},
          quizAnswers: {},
          reflectionAnswers: {},
          notes: {
            heardSounds: "",
            unclearItems: "",
            updatedAt: null,
          },
          lastStep: 1,
        };
      }
      return this.state.lessons[lessonId];
    }

    getLessonState(lessonId) {
      return this._ensureLesson(lessonId);
    }

    setLastStep(lessonId, stepNum) {
      const ls = this._ensureLesson(lessonId);
      ls.lastStep = stepNum;
      this.save();
    }

    isStepCompleted(lessonId, stepNum) {
      const ls = this._ensureLesson(lessonId);
      return Boolean(ls.completedSteps[String(stepNum)]);
    }

    setStepCompleted(lessonId, stepNum, done = true) {
      const ls = this._ensureLesson(lessonId);
      if (done) {
        ls.completedSteps[String(stepNum)] = true;
      } else {
        delete ls.completedSteps[String(stepNum)];
      }
      this.save();
    }

    getCompletedStepCount(lessonId) {
      const ls = this._ensureLesson(lessonId);
      let count = 0;
      for (let i = 1; i <= 6; i++) {
        if (ls.completedSteps[String(i)]) count++;
      }
      return count;
    }

    toggleKeyword(lessonId, keywordId) {
      const ls = this._ensureLesson(lessonId);
      ls.checkedKeywords[keywordId] = !ls.checkedKeywords[keywordId];
      this.save();
      return ls.checkedKeywords[keywordId];
    }

    isKeywordChecked(lessonId, keywordId) {
      const ls = this._ensureLesson(lessonId);
      return Boolean(ls.checkedKeywords[keywordId]);
    }

    setGrammarRevealed(lessonId, grammarId) {
      const ls = this._ensureLesson(lessonId);
      ls.revealedGrammar[grammarId] = true;
      this.save();
    }

    isGrammarRevealed(lessonId, grammarId) {
      const ls = this._ensureLesson(lessonId);
      return Boolean(ls.revealedGrammar[grammarId]);
    }

    saveQuizAnswer(lessonId, quizId, optionIndex) {
      const ls = this._ensureLesson(lessonId);
      ls.quizAnswers[quizId] = optionIndex;
      this.save();
    }

    saveReflectionAnswer(lessonId, refId, optionIndex) {
      const ls = this._ensureLesson(lessonId);
      ls.reflectionAnswers[refId] = optionIndex;
      this.save();
    }

    saveNotes(lessonId, heardSounds, unclearItems) {
      const ls = this._ensureLesson(lessonId);
      ls.notes = {
        heardSounds: String(heardSounds || ""),
        unclearItems: String(unclearItems || ""),
        updatedAt: new Date().toISOString(),
      };
      this.save();
      return ls.notes.updatedAt;
    }

    /* ==================== SRS Flashcards (SM-2 Variant) ==================== */

    makeCardKey(lessonId, vocabId) {
      return `${lessonId}::${vocabId}`;
    }

    hasCard(lessonId, vocabId) {
      return Boolean(this.state.srsCards[this.makeCardKey(lessonId, vocabId)]);
    }

    addCard(lessonId, vocabItem) {
      const key = this.makeCardKey(lessonId, vocabItem.id);
      if (this.state.srsCards[key]) {
        return { added: false, card: this.state.srsCards[key] };
      }
      const now = Date.now();
      const card = {
        key,
        lessonId,
        vocabId: vocabItem.id,
        lineId: vocabItem.lineId || null,
        surface: vocabItem.surface,
        lemma: vocabItem.lemma || vocabItem.surface,
        coreImage: vocabItem.coreImage,
        contextMeaning: vocabItem.contextMeaning,
        chunkPt: vocabItem.chunkPt,
        chunkJa: vocabItem.chunkJa,
        audioUrl: vocabItem.audioUrl || null,
        clozePt: vocabItem.clozePt || vocabItem.chunkPt,
        clozeAnswer: vocabItem.clozeAnswer || vocabItem.surface,
        intervalDays: 1,
        easeFactor: 2.5,
        repetitions: 0,
        dueAt: now, // Immediately eligible for first active recall review
        createdAt: now,
        lastReviewedAt: null,
      };
      this.state.srsCards[key] = card;
      this.save();
      return { added: true, card };
    }

    removeCard(key) {
      delete this.state.srsCards[key];
      this.save();
    }

    getAllCards() {
      return Object.values(this.state.srsCards);
    }

    getDueCards(now = Date.now()) {
      return this.getAllCards()
        .filter((c) => (c.dueAt || 0) <= now)
        .sort((a, b) => (a.dueAt || 0) - (b.dueAt || 0));
    }

    /**
     * Review rating per GEMINI.md:
     * - 'again' (まだ): immediate / next-day reset (interval = 0.5 ~ 1 day, ease -0.2)
     * - 'hard'  (微妙): 2 days later
     * - 'good'  (覚えた): interval * 2.5 (min 3 days on first pass so it beats 'hard')
     */
    reviewCard(key, rating) {
      const card = this.state.srsCards[key];
      if (!card) return null;
      const now = Date.now();

      if (rating === "again") {
        card.repetitions = 0;
        card.intervalDays = 1;
        card.easeFactor = Math.max(1.3, Number((card.easeFactor - 0.2).toFixed(2)));
        // Due tomorrow morning (or within 12 hours) & re-shown in current session
        card.dueAt = now + 12 * 60 * 60 * 1000;
      } else if (rating === "hard") {
        card.repetitions = (card.repetitions || 0) + 1;
        card.intervalDays = 2;
        card.easeFactor = Math.max(1.3, Number((card.easeFactor - 0.05).toFixed(2)));
        card.dueAt = now + 2 * DAY_MS;
      } else {
        // 'good' — multiply interval by 2.5x
        card.repetitions = (card.repetitions || 0) + 1;
        const base = Math.max(1.2, card.intervalDays || 1);
        card.intervalDays = Math.max(3, Math.round(base * 2.5));
        card.easeFactor = Math.min(3.0, Number((card.easeFactor + 0.1).toFixed(2)));
        card.dueAt = now + card.intervalDays * DAY_MS;
      }

      card.lastReviewedAt = now;
      this.save();
      return card;
    }

    /* ==================== JSON Export / Import ==================== */

    exportJSON() {
      return JSON.stringify(
        {
          app: "Escuta A1 (Gemini Edition)",
          exportedAt: new Date().toISOString(),
          data: this.state,
        },
        null,
        2
      );
    }

    importJSON(rawString) {
      const parsed = JSON.parse(rawString);
      const incoming = parsed && parsed.data ? parsed.data : parsed;
      if (!incoming || typeof incoming !== "object") {
        throw new Error("無効なバックアップJSON形式です。");
      }
      this.state = Object.assign(createDefaultState(), incoming);
      this.save();
      return {
        lessonCount: Object.keys(this.state.lessons || {}).length,
        cardCount: Object.keys(this.state.srsCards || {}).length,
      };
    }
  }

  global.Escuta = global.Escuta || {};
  global.Escuta.SRSStorage = SRSStorage;
})(window);
