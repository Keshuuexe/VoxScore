/*
  Screen 6: record a take. Record -> (optional count-in bar) -> sing along to the click while
  the pitch trace draws on the beat grid -> Stop posts every pitch frame to studio-transcribe,
  which builds the notes on the server (voxscore/music.py) and returns the editor URL.
*/
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const existing = Vox.readJSON("score-data");      // null for a brand-new score
  const abcParts = Vox.readJSON("abc-parts") || [];
  const canvas = $("trace"), g = canvas.getContext("2d");
  let detector = null, metro = null, frames = [], startedAt = 0, stopBacking = null;

  if (abcParts.length && window.ABCJS) {
    const box = $("existing");
    abcParts.forEach((abc, i) => {
      const div = document.createElement("div");
      box.appendChild(div);
      ABCJS.renderAbc(div, abc, { responsive: "resize", staffwidth: 900 });
    });
  }

  function settings() {
    if (existing) {
      return { bpm: existing.bpm, beatsPerBar: existing.beatsPerBar, beatUnit: existing.beatUnit };
    }
    const [b, u] = $("meter").value.split("/").map(Number);
    return { bpm: Math.max(40, Math.min(200, parseInt($("bpm").value, 10) || 96)), beatsPerBar: b, beatUnit: u };
  }

  function draw(beatsPerBar, bpm, countIn) {
    const W = canvas.width, H = canvas.height, spb = 60 / bpm;
    const now = frames.length ? frames[frames.length - 1].t : 0;
    const windowSec = Math.max(8 * spb * beatsPerBar / 2, now + 1);
    g.clearRect(0, 0, W, H);
    // Beat grid: bar lines darker than beats.
    for (let beat = 0; beat * spb < windowSec; beat++) {
      const x = (beat * spb / windowSec) * W;
      g.fillStyle = (beat - countIn) % beatsPerBar === 0 ? "#8F8C84" : "#E8E6E0";
      g.fillRect(x, 0, 1.5, H);
    }
    if (countIn) { g.fillStyle = "rgba(17,17,17,.06)"; g.fillRect(0, 0, (countIn * spb / windowSec) * W, H); }
    g.strokeStyle = "#111"; g.lineWidth = 3; g.beginPath();
    let pen = false;
    frames.forEach((f) => {
      if (!f.f) { pen = false; return; }
      const m = Vox.freqToMidi(f.f), x = (f.t / windowSec) * W, y = H - ((m - 40) / 45) * H;
      pen ? g.lineTo(x, y) : g.moveTo(x, y);
      pen = true;
    });
    g.stroke();
  }

  $("record").onclick = async () => {
    if (detector) return;
    const s = settings(), countIn = $("count-in").checked ? s.beatsPerBar : 0;
    frames = [];
    try {
      detector = new Vox.PitchDetector((fr) => { frames.push({ t: fr.t, f: fr.f }); draw(s.beatsPerBar, s.bpm, countIn); });
      await detector.start();
    } catch (err) {
      $("status").textContent = "Microphone not available: " + err.message;
      detector = null;
      return;
    }
    // Start the clock and the click together, so frame t=0 is the first click.
    metro = new Vox.Metronome(s.bpm, s.beatsPerBar, (beat) => {
      const bar = Math.floor((beat - countIn) / s.beatsPerBar) + 1;
      $("status").textContent = beat < countIn ? `Count-in… ${countIn - beat}` : `Listening… bar ${bar}, beat ${(beat - countIn) % s.beatsPerBar + 1}`;
      if (beat === countIn && existing && $("play-parts") && $("play-parts").checked) {
        const notes = existing.parts.flat();
        stopBacking = Vox.playNotes(notes, s.bpm);
      }
    });
    metro.start();
    // The metronome's first click sounds 100 ms after start(); put t = 0 exactly there.
    // Frames before it get a negative t, which the server ignores.
    detector.t0 = performance.now() + 100;
    startedAt = Date.now();
    $("record").setAttribute("aria-pressed", "true");
    $("stop").disabled = false; $("discard").disabled = false;
    $("stop").dataset.countIn = countIn;
  };

  function halt() {
    if (detector) detector.stop();
    if (metro) metro.stop();
    if (stopBacking) stopBacking();
    detector = null; metro = null; stopBacking = null;
    $("record").setAttribute("aria-pressed", "false");
    $("stop").disabled = true; $("discard").disabled = true;
  }

  $("discard").onclick = () => { halt(); frames = []; g.clearRect(0, 0, canvas.width, canvas.height); $("status").textContent = "Take discarded. Ready"; };

  $("stop").onclick = async () => {
    const countIn = parseInt($("stop").dataset.countIn || "0", 10), s = settings();
    halt();
    $("status").textContent = "Transcribing…";
    const body = {
      frames, bpm: s.bpm, beats_per_bar: s.beatsPerBar, beat_unit: s.beatUnit,
      count_in_beats: countIn, seconds: Math.round((Date.now() - startedAt) / 1000),
    };
    if (existing) {
      body.score = existing.id;
      body.part_name = $("part-name").value;
    } else {
      body.title = $("title").value;
      body.key = $("key").value;
    }
    try {
      const r = await Vox.postJSON(window.VOX_URLS.transcribe, body);
      $("status").textContent = `Found ${r.notes} notes in ${r.key || "an unknown key"}. Opening the editor…`;
      window.location = r.url;
    } catch (err) {
      $("status").textContent = err.message;
    }
  };
})();
