/*
  Screen 5: a guided warmup. Each step plays the pattern a semitone higher. "Sing now" plays
  the pattern once as a guide while the mic listens, and draws your pitch against the targets.
  Finish posts every frame plus the target notes to session-save, which scores pitch accuracy
  against the TARGETS (so a confident wrong note does not count as in tune).
*/
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const data = Vox.readJSON("warmup-data");
  const spb = 60 / data.bpm;
  let step = 0, shift = 0, frames = [], allTargets = [], started = Date.now();
  let detector = null, stopPlayback = null, singStart = 0, activeIndex = -1;
  const stats = new Vox.LiveStats();
  const canvas = $("trace"), g = canvas.getContext("2d");

  const notesFor = (s) => data.pattern.map((p) => data.start + shift + s + p);

  // Key selector: -5..+5 semitones from the suggested start, labelled with the start note.
  for (let k = -5; k <= 5; k++) {
    const o = document.createElement("option");
    o.value = k;
    o.textContent = `Start on ${Vox.midiToName(data.start + k)}${k === 0 ? " (suggested)" : ""}`;
    if (k === 0) o.selected = true;
    $("key-shift").appendChild(o);
  }
  $("key-shift").onchange = (e) => { shift = parseInt(e.target.value, 10); render(); };

  function render() {
    const notes = notesFor(step);
    $("step-label").textContent = `Step ${step + 1} of ${data.steps}`;
    $("progress").style.width = (100 * (step + 1) / data.steps) + "%";
    const box = $("syllables");
    box.innerHTML = "";
    notes.forEach((m, i) => {
      const s = document.createElement("span");
      s.textContent = data.syllables[i] || Vox.midiToName(m);
      if (i === activeIndex) s.className = "on";
      box.appendChild(s);
    });
    $("pattern-notes").textContent = notes.map(Vox.midiToName).join(" · ");
    $("prev").disabled = step === 0;
    $("next").disabled = step >= data.steps - 1;
    draw();
  }

  function draw() {
    const notes = notesFor(step), W = canvas.width, H = canvas.height;
    const lo = Math.min(...notes) - 3, hi = Math.max(...notes) + 3;
    const y = (m) => H - ((m - lo) / (hi - lo)) * H;
    const total = notes.length * spb;
    g.clearRect(0, 0, W, H);
    g.fillStyle = "rgba(17,17,17,.12)";
    notes.forEach((m, i) => g.fillRect((i * spb / total) * W, y(m) - 6, (spb / total) * W - 4, 12));
    g.strokeStyle = "#111"; g.lineWidth = 2.5; g.beginPath();
    let pen = false;
    frames.filter((f) => f.t >= singStart && f.t <= singStart + total).forEach((f) => {
      if (!f.f) { pen = false; return; }
      const x = ((f.t - singStart) / total) * W, yy = y(Vox.freqToMidi(f.f));
      pen ? g.lineTo(x, yy) : g.moveTo(x, yy);
      pen = true;
    });
    g.stroke();
  }

  function onFrame(fr) {
    frames.push({ t: fr.t, f: fr.f });
    const notes = notesFor(step);
    const idx = Math.floor((fr.t - singStart) / spb);
    const target = idx >= 0 && idx < notes.length ? notes[idx] : null;
    stats.addFrame(fr, target);
    if (fr.f) $("now-note").textContent = Vox.midiToName(Vox.freqToMidi(fr.f));
    $("target-note").textContent = target != null ? Vox.midiToName(target) : "–";
    const p = stats.pitch();
    if (p != null) $("txt-pitch").textContent = p + "%";
    draw();
  }

  function playPattern(onNote) {
    const notes = notesFor(step).map((m, i) => ({ midi: m, start: i, dur: 1 }));
    if (stopPlayback) stopPlayback();
    stopPlayback = Vox.playNotes(notes, data.bpm, (i) => { activeIndex = i; render(); if (onNote) onNote(i); });
  }

  $("play").onclick = () => playPattern();
  $("prev").onclick = () => { step = Math.max(0, step - 1); render(); };
  $("next").onclick = () => { step = Math.min(data.steps - 1, step + 1); render(); };

  $("sing").onclick = async (e) => {
    const btn = e.currentTarget;
    try {
      if (!detector) {
        detector = new Vox.PitchDetector(onFrame);
        await detector.start();
      }
      allTargets.push(...notesFor(step));
      singStart = (performance.now() - detector.t0) / 1000 + 0.1;
      btn.setAttribute("aria-pressed", "true");
      btn.textContent = "Listening…";
      playPattern((i) => {
        if (i === -1) {
          btn.setAttribute("aria-pressed", "false");
          btn.textContent = step < data.steps - 1 ? "Sing next step" : "Sing again";
          if (step < data.steps - 1) { step++; render(); }
        }
      });
    } catch (err) {
      $("now-note").textContent = "Microphone not available: " + err.message;
    }
  };

  $("finish").onclick = async () => {
    if (detector) detector.stop();
    if (stopPlayback) stopPlayback();
    const voiced = frames.filter((f) => f.f).length;
    $("summary").classList.remove("d-none");
    if (voiced < 10) { $("sum-text").textContent = "No singing was detected, so nothing was saved."; $("coach-btn").classList.add("d-none"); return; }
    try {
      const r = await Vox.postJSON(window.VOX_URLS.save, {
        kind: "warmup", warmup: data.slug, seconds: Math.round((Date.now() - started) / 1000),
        frames, targets: [...new Set(allTargets)],
      });
      $("sum-text").textContent =
        `Pitch on target: ${r.pitch == null ? "–" : Math.round(r.pitch) + "%"} · Tone steadiness: ${r.tone == null ? "–" : Math.round(r.tone) + "%"}. Saved to your profile.`;
      $("coach-btn").onclick = () => Vox.coach(window.VOX_URLS.coach.replace("/0/", `/${r.id}/`), $("coach"), $("coach-btn"));
    } catch (err) {
      $("sum-text").textContent = "Could not save: " + err.message;
    }
    detector = null;
  };

  render();
})();
