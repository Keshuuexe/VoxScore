/*
  VoxScore shared browser audio (window.Vox), used by every interactive screen.

    Vox.PitchDetector   microphone -> {t, f, rms} about 30 times a second (autocorrelation)
    Vox.Metronome       click track with an accented beat 1 and a beat callback
    Vox.Drone           a sustained tanpura-like drone on any note
    Vox.playNote()      one synth note; Vox.playNotes() plays a list of {midi, start, dur}
    Vox.postJSON()      fetch() with Django's CSRF token

  Pitch detection runs entirely in the browser; only the list of pitch numbers is sent to the
  server, never the audio itself.
*/
(function () {
  "use strict";

  const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  let ctx = null;

  function audioContext() {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  }

  const freqToMidi = (f) => 69 + 12 * Math.log2(f / 440);
  const midiToFreq = (m) => 440 * Math.pow(2, (m - 69) / 12);
  const midiToName = (m) => {
    const r = Math.round(m);
    return NOTE_NAMES[((r % 12) + 12) % 12] + (Math.floor(r / 12) - 1);
  };

  /* Autocorrelation pitch detection (the "ACF2+" method). Returns Hz, or 0 for silence. */
  function detectPitch(buf, sampleRate) {
    let size = buf.length, rms = 0;
    for (let i = 0; i < size; i++) rms += buf[i] * buf[i];
    rms = Math.sqrt(rms / size);
    if (rms < 0.012) return { f: 0, rms };

    // Trim the quiet edges so the correlation sees whole cycles.
    let r1 = 0, r2 = size - 1;
    const thres = 0.2;
    for (let i = 0; i < size / 2; i++) if (Math.abs(buf[i]) < thres) { r1 = i; break; }
    for (let i = 1; i < size / 2; i++) if (Math.abs(buf[size - i]) < thres) { r2 = size - i; break; }
    buf = buf.slice(r1, r2);
    size = buf.length;

    const c = new Float32Array(size);
    for (let i = 0; i < size; i++)
      for (let j = 0; j < size - i; j++) c[i] += buf[j] * buf[j + i];

    let d = 0;
    while (d < size - 1 && c[d] > c[d + 1]) d++;
    let maxval = -1, maxpos = -1;
    for (let i = d; i < size; i++) if (c[i] > maxval) { maxval = c[i]; maxpos = i; }
    if (maxpos <= 0) return { f: 0, rms };
    let t0 = maxpos;
    // Parabolic interpolation for sub-sample accuracy.
    const x1 = c[t0 - 1] || 0, x2 = c[t0], x3 = c[t0 + 1] || 0;
    const a = (x1 + x3 - 2 * x2) / 2, b = (x3 - x1) / 2;
    if (a) t0 = t0 - b / (2 * a);
    const f = sampleRate / t0;
    return { f: f >= 60 && f <= 1400 ? f : 0, rms };
  }

  class PitchDetector {
    constructor(onFrame, intervalMs = 33) {
      this.onFrame = onFrame;
      this.intervalMs = intervalMs;
      this.running = false;
    }
    async start() {
      const ac = audioContext();
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      });
      const source = ac.createMediaStreamSource(this.stream);
      this.analyser = ac.createAnalyser();
      this.analyser.fftSize = 2048;
      source.connect(this.analyser);
      this.buf = new Float32Array(this.analyser.fftSize);
      this.t0 = performance.now();
      this.running = true;
      this.timer = setInterval(() => {
        this.analyser.getFloatTimeDomainData(this.buf);
        const { f, rms } = detectPitch(this.buf, ac.sampleRate);
        const t = (performance.now() - this.t0) / 1000;
        this.onFrame({ t: Math.round(t * 1000) / 1000, f: Math.round(f * 10) / 10, rms });
      }, this.intervalMs);
    }
    resetClock() { this.t0 = performance.now(); }
    stop() {
      this.running = false;
      clearInterval(this.timer);
      if (this.stream) this.stream.getTracks().forEach((tr) => tr.stop());
    }
  }

  function click(time, accent) {
    const ac = audioContext();
    const osc = ac.createOscillator(), gain = ac.createGain();
    osc.frequency.value = accent ? 1500 : 1000;
    gain.gain.setValueAtTime(0.0001, time);
    gain.gain.exponentialRampToValueAtTime(accent ? 0.5 : 0.3, time + 0.002);
    gain.gain.exponentialRampToValueAtTime(0.0001, time + 0.06);
    osc.connect(gain).connect(ac.destination);
    osc.start(time);
    osc.stop(time + 0.07);
  }

  class Metronome {
    constructor(bpm = 90, beatsPerBar = 4, onBeat = null) {
      this.bpm = bpm; this.beatsPerBar = beatsPerBar; this.onBeat = onBeat; this.running = false;
    }
    start() {
      const ac = audioContext();
      this.running = true;
      this.beat = 0;
      this.next = ac.currentTime + 0.1;
      this.timer = setInterval(() => {
        while (this.next < ac.currentTime + 0.12) {
          const beat = this.beat, when = this.next;
          click(when, beat % this.beatsPerBar === 0);
          const delay = Math.max(0, (when - ac.currentTime) * 1000);
          if (this.onBeat) setTimeout(() => this.running && this.onBeat(beat), delay);
          this.beat++;
          this.next += 60 / this.bpm;
        }
      }, 25);
    }
    stop() { this.running = false; clearInterval(this.timer); }
    toggle() { this.running ? this.stop() : this.start(); return this.running; }
  }

  class Drone {
    constructor() { this.nodes = null; }
    start(midi) {
      this.stop();
      const ac = audioContext();
      const out = ac.createGain();
      out.gain.setValueAtTime(0, ac.currentTime);
      out.gain.linearRampToValueAtTime(0.12, ac.currentTime + 0.8);
      const filter = ac.createBiquadFilter();
      filter.type = "lowpass"; filter.frequency.value = 1200;
      filter.connect(out).connect(ac.destination);
      // Root, fifth and octave, slightly detuned, like a tanpura's open strings.
      const oscs = [0, 7, 12].map((iv, i) => {
        const o = ac.createOscillator();
        o.type = "sawtooth";
        o.frequency.value = midiToFreq(midi + iv - 12);
        o.detune.value = (i - 1) * 3;
        o.connect(filter);
        o.start();
        return o;
      });
      this.nodes = { out, oscs };
      this.midi = midi;
    }
    stop() {
      if (!this.nodes) return;
      const ac = audioContext(), { out, oscs } = this.nodes;
      out.gain.linearRampToValueAtTime(0, ac.currentTime + 0.3);
      oscs.forEach((o) => o.stop(ac.currentTime + 0.35));
      this.nodes = null;
    }
    get running() { return !!this.nodes; }
  }

  function playNote(midi, durSec = 0.6, when = 0, volume = 0.25) {
    const ac = audioContext();
    const t = when || ac.currentTime;
    const osc = ac.createOscillator(), osc2 = ac.createOscillator(), gain = ac.createGain();
    osc.type = "triangle"; osc2.type = "sine";
    osc.frequency.value = midiToFreq(midi);
    osc2.frequency.value = midiToFreq(midi) * 2;
    const g2 = ac.createGain(); g2.gain.value = 0.15;
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(volume, t + 0.02);
    gain.gain.setValueAtTime(volume, t + Math.max(0.03, durSec - 0.08));
    gain.gain.exponentialRampToValueAtTime(0.0001, t + durSec);
    osc.connect(gain); osc2.connect(g2).connect(gain); gain.connect(ac.destination);
    osc.start(t); osc2.start(t); osc.stop(t + durSec + 0.02); osc2.stop(t + durSec + 0.02);
  }

  /* Play [{midi, start, dur}] (beats). Returns a stop() function. */
  function playNotes(notes, bpm, onNote) {
    const ac = audioContext(), spb = 60 / bpm, t0 = ac.currentTime + 0.1;
    const timers = [];
    notes.forEach((n, i) => {
      playNote(n.midi, Math.max(0.08, n.dur * spb * 0.95), t0 + n.start * spb);
      if (onNote) timers.push(setTimeout(() => onNote(i, n), (0.1 + n.start * spb) * 1000));
    });
    const end = notes.reduce((m, n) => Math.max(m, n.start + n.dur), 0);
    if (onNote) timers.push(setTimeout(() => onNote(-1, null), (0.1 + end * spb) * 1000));
    return () => { timers.forEach(clearTimeout); ctx && ctx.suspend().then(() => ctx.resume()); };
  }

  async function postJSON(url, data) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": window.VOX_CSRF },
      body: JSON.stringify(data || {}),
    });
    let body = {};
    try { body = await response.json(); } catch (e) { /* not JSON */ }
    if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
    return body;
  }

  function readJSON(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  /* Live feedback numbers shared by the tuner and warmups (the server recomputes the saved ones). */
  class LiveStats {
    constructor() { this.cents = []; this.onsets = []; this.lastVoiced = false; this.beatTimes = []; }
    addFrame(fr, targetMidi) {
      if (!fr.f) { this.lastVoiced = false; return; }
      const m = freqToMidi(fr.f);
      const ref = targetMidi != null ? targetMidi : Math.round(m);
      this.cents.push((m - ref) * 100);
      if (this.cents.length > 90) this.cents.shift();
      if (!this.lastVoiced) this.onsets.push(performance.now());
      this.lastVoiced = true;
    }
    addBeat() { this.beatTimes.push(performance.now()); if (this.beatTimes.length > 64) this.beatTimes.shift(); }
    pitch() {
      if (this.cents.length < 5) return null;
      return Math.round(100 * this.cents.filter((c) => Math.abs(c) <= 25).length / this.cents.length);
    }
    tone() {
      const recent = this.cents.slice(-12);
      if (recent.length < 6) return null;
      const mean = recent.reduce((a, b) => a + b, 0) / recent.length;
      const sd = Math.sqrt(recent.reduce((a, b) => a + (b - mean) ** 2, 0) / recent.length);
      return Math.max(0, Math.round(100 - sd * 2.5));
    }
    rhythm(bpm) {
      if (this.beatTimes.length < 2 || !this.onsets.length) return null;
      const half = 60000 / bpm / 4;  // half an eighth note, in ms
      const scores = this.onsets.slice(-12).map((t) => {
        const off = Math.min(...this.beatTimes.map((b) => {
          const d = Math.abs(t - b) % (60000 / bpm / 2);
          return Math.min(d, 60000 / bpm / 2 - d);
        }));
        return Math.max(0, 1 - off / half);
      });
      return Math.round(100 * scores.reduce((a, b) => a + b, 0) / scores.length);
    }
  }

  function setBar(name, value, label) {
    const bar = document.getElementById("bar-" + name), txt = document.getElementById("txt-" + name);
    if (bar) bar.style.width = (value == null ? 0 : value) + "%";
    if (txt && value != null) txt.textContent = label || value + "%";
  }

  /* Ask the AI coach about a saved session and render the answer into `el`. */
  async function coach(url, el, button) {
    if (button) { button.disabled = true; button.textContent = "Thinking…"; }
    try {
      const r = await postJSON(url);
      el.innerHTML = "";
      const p = document.createElement("p");
      p.className = "fw-semibold mb-2";
      p.textContent = r.summary;
      const ul = document.createElement("ul");
      r.tips.forEach((t) => { const li = document.createElement("li"); li.textContent = t; ul.appendChild(li); });
      const src = document.createElement("div");
      src.className = "small vx-sub";
      src.textContent = r.source === "groq" ? `Written by AI (${r.model}).` : "Built-in tips (no AI model was available).";
      el.append(p, ul, src);
      if (button) button.classList.add("d-none");
    } catch (e) {
      el.textContent = e.message;
      if (button) { button.disabled = false; button.textContent = "Try again"; }
    }
  }

  window.Vox = {
    NOTE_NAMES, audioContext, freqToMidi, midiToFreq, midiToName, detectPitch,
    PitchDetector, Metronome, Drone, playNote, playNotes, postJSON, readJSON,
    LiveStats, setBar, coach,
  };
})();
