/**
 * Escuta A1 — Triple-Redundant Permanent Storage & SM-2 Spaced Repetition Manager
 *
 * Guarantees SRS flashcards & progress NEVER disappear across lesson updates or SW upgrades:
 * 1. localStorage (`escuta_a1_state_v1`)
 * 2. IndexedDB (`EscutaA1PermanentDB` -> `kv` -> `state`)
 * 3. Permanent CacheStorage (`escuta-a1-user-data-permanent` — never deleted by sw.js)
 * 4. Optional localhost disk mirror (`/api/user-state` -> `.user_state_backup.json`)
 * 5. Non-destructive Union Merge + `navigator.storage.persist()` + `#sync=` cross-origin transfer
 */
(function (global) {
  "use strict";

  const STORAGE_KEY = "escuta_a1_state_v1";
  const IDB_NAME = "EscutaA1PermanentDB";
  const IDB_STORE = "kv";
  const PERMANENT_CACHE_NAME = "escuta-a1-user-data-permanent";
  const PERMANENT_CACHE_REQ = "/__escuta_permanent_user_state__.json";
  const DAY_MS = 24 * 60 * 60 * 1000;

  function createDefaultState() {
    return {
      schemaVersion: 2,
      theme: "dark",
      playbackRate: 0.85,
      lessons: {},
      srsCards: {},
      deletedCards: {},
      updatedAt: new Date(0).toISOString(),
    };
  }

  function openIdb() {
    return new Promise((resolve, reject) => {
      if (!("indexedDB" in global)) {
        resolve(null);
        return;
      }
      try {
        const req = global.indexedDB.open(IDB_NAME, 1);
        req.onupgradeneeded = () => {
          const db = req.result;
          if (!db.objectStoreNames.contains(IDB_STORE)) {
            db.createObjectStore(IDB_STORE);
          }
        };
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      } catch (e) {
        resolve(null);
      }
    });
  }

  async function idbGetState() {
    const db = await openIdb();
    if (!db) return null;
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(IDB_STORE, "readonly");
        const req = tx.objectStore(IDB_STORE).get(STORAGE_KEY);
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => resolve(null);
      } catch (_) {
        resolve(null);
      }
    });
  }

  async function idbSetState(stateObj) {
    const db = await openIdb();
    if (!db) return;
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(IDB_STORE, "readwrite");
        tx.objectStore(IDB_STORE).put(stateObj, STORAGE_KEY);
        tx.oncomplete = () => resolve();
        tx.onerror = () => resolve();
      } catch (_) {
        resolve();
      }
    });
  }

  async function cacheGetState() {
    if (!("caches" in global)) return null;
    try {
      const cache = await global.caches.open(PERMANENT_CACHE_NAME);
      const res = await cache.match(PERMANENT_CACHE_REQ);
      if (!res) return null;
      return await res.json();
    } catch (_) {
      return null;
    }
  }

  async function cacheSetState(stateObj) {
    if (!("caches" in global)) return;
    try {
      const cache = await global.caches.open(PERMANENT_CACHE_NAME);
      const body = JSON.stringify(stateObj);
      await cache.put(
        PERMANENT_CACHE_REQ,
        new Response(body, {
          headers: { "Content-Type": "application/json; charset=utf-8" },
        })
      );
    } catch (_) {}
  }

  function toUtf8Base64Url(str) {
    const bytes = new TextEncoder().encode(str);
    let bin = "";
    bytes.forEach((b) => {
      bin += String.fromCharCode(b);
    });
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function fromUtf8Base64Url(b64url) {
    let b64 = b64url.replace(/-/g, "+").replace(/_/g, "/");
    while (b64.length % 4 !== 0) b64 += "=";
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder().decode(bytes);
  }

  /**
   * Non-destructive union merge of two state snapshots.
   * Ensures an app update or empty storage layer NEVER wipes existing SRS cards or progress.
   */
  function mergeStates(base, incoming) {
    if (!incoming || typeof incoming !== "object") return base;
    const out = Object.assign(createDefaultState(), base);

    const baseTime = Date.parse(base.updatedAt || 0) || 0;
    const incTime = Date.parse(incoming.updatedAt || 0) || 0;
    if (incTime > baseTime) {
      if (incoming.theme) out.theme = incoming.theme;
      if (incoming.playbackRate) out.playbackRate = incoming.playbackRate;
      out.updatedAt = incoming.updatedAt;
    }

    // Merge tombstones
    out.deletedCards = Object.assign({}, base.deletedCards || {}, incoming.deletedCards || {});

    // Union SRS cards (never lose a card unless explicitly deleted after creation)
    const mergedCards = Object.assign({}, base.srsCards || {});
    for (const [key, incCard] of Object.entries(incoming.srsCards || {})) {
      if (!incCard || typeof incCard !== "object") continue;
      const delTs = out.deletedCards[key] || 0;
      const cardTs = Math.max(incCard.lastReviewedAt || 0, incCard.createdAt || 0);
      if (delTs > cardTs) continue;

      const existing = mergedCards[key];
      if (!existing) {
        mergedCards[key] = incCard;
      } else {
        const exRev = existing.lastReviewedAt || 0;
        const inRev = incCard.lastReviewedAt || 0;
        const exReps = existing.repetitions || 0;
        const inReps = incCard.repetitions || 0;
        if (inRev > exRev || (inRev === exRev && inReps > exReps)) {
          mergedCards[key] = Object.assign({}, existing, incCard);
        }
      }
    }
    for (const key of Object.keys(mergedCards)) {
      const c = mergedCards[key];
      const delTs = out.deletedCards[key] || 0;
      if (delTs > Math.max(c.lastReviewedAt || 0, c.createdAt || 0)) {
        delete mergedCards[key];
      }
    }
    out.srsCards = mergedCards;

    // Union per-lesson progress, keywords, quizzes, and keep newest notes
    const allLessonIds = new Set([
      ...Object.keys(base.lessons || {}),
      ...Object.keys(incoming.lessons || {}),
    ]);
    const mergedLessons = {};
    for (const lid of allLessonIds) {
      const a = (base.lessons && base.lessons[lid]) || {};
      const b = (incoming.lessons && incoming.lessons[lid]) || {};
      const aNoteTs = Date.parse((a.notes && a.notes.updatedAt) || 0) || 0;
      const bNoteTs = Date.parse((b.notes && b.notes.updatedAt) || 0) || 0;
      const bestNotes =
        bNoteTs > aNoteTs
          ? b.notes
          : aNoteTs > 0
          ? a.notes
          : (b.notes && (b.notes.heardSounds || b.notes.unclearItems) ? b.notes : a.notes) || {
              heardSounds: "",
              unclearItems: "",
              updatedAt: null,
            };

      mergedLessons[lid] = {
        completedSteps: Object.assign({}, a.completedSteps || {}, b.completedSteps || {}),
        checkedKeywords: Object.assign({}, a.checkedKeywords || {}, b.checkedKeywords || {}),
        revealedGrammar: Object.assign({}, a.revealedGrammar || {}, b.revealedGrammar || {}),
        quizAnswers: Object.assign({}, a.quizAnswers || {}, b.quizAnswers || {}),
        reflectionAnswers: Object.assign(
          {},
          a.reflectionAnswers || {},
          b.reflectionAnswers || {}
        ),
        notes: bestNotes,
        lastStep: b.lastStep || a.lastStep || 1,
      };
    }
    out.lessons = mergedLessons;
    return out;
  }

  class SRSStorage {
    constructor() {
      this.localServerMirrorEnabled = false;
      this.state = this._loadSync();
      this._requestPersistentStorage();
    }

    _requestPersistentStorage() {
      try {
        if (navigator.storage && typeof navigator.storage.persist === "function") {
          navigator.storage.persist().catch(() => {});
        }
      } catch (_) {}
    }

    _loadSync() {
      try {
        const raw = global.localStorage.getItem(STORAGE_KEY);
        if (!raw) return createDefaultState();
        const parsed = JSON.parse(raw);
        return mergeStates(createDefaultState(), parsed);
      } catch (err) {
        console.warn("[SRSStorage] localStorage parse warning:", err);
        return createDefaultState();
      }
    }

    /**
     * Restores & merges state across IndexedDB, Permanent CacheStorage,
     * optional `#sync=` transfer hash, and localhost disk backup.
     */
    async hydrate(localServerAvailable = false) {
      this.localServerMirrorEnabled = Boolean(localServerAvailable);
      const beforeCount = Object.keys(this.state.srsCards || {}).length;

      const [idbState, cacheState] = await Promise.all([
        idbGetState(),
        cacheGetState(),
      ]);

      if (idbState) this.state = mergeStates(this.state, idbState);
      if (cacheState) this.state = mergeStates(this.state, cacheState);

      if (this.localServerMirrorEnabled) {
        try {
          const res = await fetch("/api/user-state", { cache: "no-store" });
          if (res.ok) {
            const diskJson = await res.json();
            if (diskJson && diskJson.state) {
              this.state = mergeStates(this.state, diskJson.state);
            }
          }
        } catch (_) {}
      }

      // Check URL hash `#sync=...` for 1-tap cross-domain / Safari-to-PWA card transfer
      let importedFromHash = false;
      if (global.location.hash && global.location.hash.startsWith("#sync=")) {
        try {
          const encoded = global.location.hash.slice("#sync=".length);
          const decoded = JSON.parse(fromUtf8Base64Url(encoded));
          const incoming = decoded && decoded.data ? decoded.data : decoded;
          this.state = mergeStates(this.state, incoming);
          importedFromHash = true;
          history.replaceState(null, "", global.location.pathname + global.location.search);
        } catch (err) {
          console.warn("[SRSStorage] Failed to parse #sync hash:", err);
        }
      }

      const afterCount = Object.keys(this.state.srsCards || {}).length;
      this.save();
      return {
        restoredCount: Math.max(0, afterCount - beforeCount),
        totalCards: afterCount,
        importedFromHash,
      };
    }

    save() {
      this.state.updatedAt = new Date().toISOString();
      const serialized = JSON.stringify(this.state);
      try {
        global.localStorage.setItem(STORAGE_KEY, serialized);
      } catch (err) {
        console.error("[SRSStorage] localStorage save failed:", err);
      }
      idbSetState(this.state);
      cacheSetState(this.state);

      if (this.localServerMirrorEnabled) {
        fetch("/api/user-state", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: serialized,
        }).catch(() => {});
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
      if (this.state.deletedCards && this.state.deletedCards[key]) {
        delete this.state.deletedCards[key];
      }
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
        dueAt: now,
        createdAt: now,
        lastReviewedAt: null,
      };
      this.state.srsCards[key] = card;
      this.save();
      return { added: true, card };
    }

    removeCard(key) {
      delete this.state.srsCards[key];
      this.state.deletedCards = this.state.deletedCards || {};
      this.state.deletedCards[key] = Date.now();
      this.save();
    }

    getAllCards() {
      return Object.values(this.state.srsCards || {});
    }

    getDueCards(now = Date.now()) {
      return this.getAllCards()
        .filter((c) => (c.dueAt || 0) <= now)
        .sort((a, b) => (a.dueAt || 0) - (b.dueAt || 0));
    }

    reviewCard(key, rating) {
      const card = this.state.srsCards[key];
      if (!card) return null;
      const now = Date.now();

      if (rating === "again") {
        card.repetitions = 0;
        card.intervalDays = 1;
        card.easeFactor = Math.max(1.3, Number((card.easeFactor - 0.2).toFixed(2)));
        card.dueAt = now + 12 * 60 * 60 * 1000;
      } else if (rating === "hard") {
        card.repetitions = (card.repetitions || 0) + 1;
        card.intervalDays = 2;
        card.easeFactor = Math.max(1.3, Number((card.easeFactor - 0.05).toFixed(2)));
        card.dueAt = now + 2 * DAY_MS;
      } else {
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

    /* ==================== JSON Export / Non-Destructive Merge Import / Sync Link ==================== */

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

    /**
     * Merges incoming backup JSON with existing cards & progress (never wipes existing cards!).
     */
    importJSON(rawString) {
      const parsed = JSON.parse(rawString);
      const incoming = parsed && parsed.data ? parsed.data : parsed;
      if (!incoming || typeof incoming !== "object") {
        throw new Error("無効なバックアップJSON形式です。");
      }
      this.state = mergeStates(this.state, incoming);
      this.save();
      return {
        lessonCount: Object.keys(this.state.lessons || {}).length,
        cardCount: Object.keys(this.state.srsCards || {}).length,
      };
    }

    buildSyncUrl(targetBaseUrl = "https://degaullev.github.io/escuta-a1/") {
      const payload = toUtf8Base64Url(JSON.stringify(this.state));
      return `${targetBaseUrl.replace(/#.*$/, "")}#sync=${payload}`;
    }
  }

  global.Escuta = global.Escuta || {};
  global.Escuta.SRSStorage = SRSStorage;
})(window);
