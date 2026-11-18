/**
 * Escuta A1 — Voice Recorder & Immediate A/B Comparison Module
 * - Records learner's pronunciation in memory only (never stored or uploaded)
 * - Releases MediaStream tracks immediately on stop so iOS Safari restores full speaker volume
 * - Plays [Model Audio -> 320ms pause -> Learner Recording] sequentially for motor feedback
 */
(function (global) {
  "use strict";

  class VoiceRecorder {
    constructor() {
      this.mediaRecorder = null;
      this.stream = null;
      this.chunks = [];
      this.isRecording = false;
      this.recordingLineId = null;
      // In-memory map: lineId -> objectURL
      this.recordings = new Map();
      this.selfAudioEl = new Audio();
      this.selfAudioEl.setAttribute("playsinline", "");
    }

    isSupported() {
      return Boolean(
        navigator.mediaDevices &&
          typeof navigator.mediaDevices.getUserMedia === "function" &&
          typeof global.MediaRecorder !== "undefined"
      );
    }

    _pickMimeType() {
      if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) {
        return "";
      }
      const candidates = [
        "audio/mp4",
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/ogg;codecs=opus",
      ];
      for (const mime of candidates) {
        if (MediaRecorder.isTypeSupported(mime)) {
          return mime;
        }
      }
      return "";
    }

    hasRecording(lineId) {
      return this.recordings.has(lineId);
    }

    async startRecording(lineId) {
      if (!this.isSupported()) {
        throw new Error("お使いのブラウザはマイク録音に対応していません。");
      }
      if (this.isRecording) {
        await this.stopRecording();
      }

      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      const mimeType = this._pickMimeType();
      this.chunks = [];
      this.mediaRecorder = mimeType
        ? new MediaRecorder(this.stream, { mimeType })
        : new MediaRecorder(this.stream);

      this.recordingLineId = lineId;
      this.isRecording = true;

      this.mediaRecorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) {
          this.chunks.push(ev.data);
        }
      };

      this.mediaRecorder.start();
    }

    stopRecording() {
      return new Promise((resolve) => {
        if (!this.mediaRecorder || !this.isRecording) {
          resolve(null);
          return;
        }

        const lineId = this.recordingLineId;
        const mimeType = this.mediaRecorder.mimeType || "audio/webm";

        this.mediaRecorder.onstop = () => {
          this._stopStreamTracks();
          this.isRecording = false;
          this.recordingLineId = null;

          const blob = new Blob(this.chunks, { type: mimeType });
          this.chunks = [];

          if (this.recordings.has(lineId)) {
            URL.revokeObjectURL(this.recordings.get(lineId));
          }
          const url = URL.createObjectURL(blob);
          this.recordings.set(lineId, url);
          resolve(url);
        };

        this.mediaRecorder.stop();
      });
    }

    _stopStreamTracks() {
      if (this.stream) {
        this.stream.getTracks().forEach((track) => track.stop());
        this.stream = null;
      }
    }

    playSelfRecording(lineId) {
      return new Promise((resolve, reject) => {
        const url = this.recordings.get(lineId);
        if (!url) {
          reject(new Error("まだ録音データがありません。"));
          return;
        }
        this.selfAudioEl.src = url;
        this.selfAudioEl.onended = () => resolve();
        this.selfAudioEl.onerror = () => resolve();
        this.selfAudioEl.play().catch(reject);
      });
    }

    /**
     * Sequential A/B playback: Model -> 320ms pause -> User's recorded voice
     */
    async compareAB(line, audioPlayer, onPhaseChange = () => {}) {
      if (!this.hasRecording(line.id)) {
        throw new Error("先にマイクボタンで自分の発音を録音してください。");
      }
      onPhaseChange("model");
      await audioPlayer.playLineOrText({ line });

      onPhaseChange("pause");
      await new Promise((r) => setTimeout(r, 320));

      onPhaseChange("self");
      await this.playSelfRecording(line.id);

      onPhaseChange("done");
    }

    disposeAll() {
      this._stopStreamTracks();
      for (const url of this.recordings.values()) {
        URL.revokeObjectURL(url);
      }
      this.recordings.clear();
    }
  }

  global.Escuta = global.Escuta || {};
  global.Escuta.VoiceRecorder = VoiceRecorder;
})(window);
