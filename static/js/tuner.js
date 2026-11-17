/* Screen 3: tuner, live feedback bars, metronome, drone and note player. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const bpmInput = $("bpm");
  const bpm = () => Math.max(30, Math.min(240, parseInt(bpmInput.value, 10) || 90));
  const stats = new Vox.LiveStats();
  let frames = [], detector = null, started = 0;

  // ---- Metronome
  const metro = new Vox.Metronome(bpm(), 4, () => stats.addBeat());
  $("bpm-down").onclick = () => { bpmInput.value = bpm() - 5; metro.bpm = bpm(); };
  $("bpm-up").onclick = () => { bpmInput.value = bpm() + 5; metro.bpm = bpm(); };
  bpmInput.onchange = () => { metro.bpm = bpm(); };
  $("metro-toggle").onclick = (e) => {
    const on = metro.toggle();
    e.target.setAttribute("aria-pressed", on);
    e.target.textContent = on ? "Metronome off" : "Metronome on";
  };

  // ---- Drone (on the 3rd octave below middle C's octave, like a tanpura)
  const drone = new Vox.Drone();
  const droneMidi = () => 48 + parseInt($("drone-note").value, 10);
  $("drone-toggle").onclick = (e) => {
    if (drone.running) drone.stop(); else drone.start(droneMidi());
    e.target.setAttribute("aria-pressed", drone.running);
    e.target.textContent = drone.running ? "Stop" : "Play";
  };
  $("drone-note").onchange = () => { if (drone.running) drone.start(droneMidi()); };

  // ---- Note player: one octave from C4
  const keys = $("keys");
  for (let m = 60; m < 72; m++) {
    const b = document.createElement("button");
    b.type = "button";
    const name = Vox.midiToName(m);
    b.textContent = name.replace("4", "");
    b.className = name.includes("#") ? "black" : "";
    b.setAttribute("aria-label", "Play " + name);
    b.onclick = () => Vox.playNote(m, 0.9);
    keys.appendChild(b);
  }

  // ---- Live tuner
  function onFrame(fr) {
    frames.push({ t: fr.t, f: fr.f });
    stats.addFrame(fr);
    if (!fr.f) return;
    const m = Vox.freqToMidi(fr.f), nearest = Math.round(m), cents = Math.round((m - nearest) * 100);
    $("note").textContent = Vox.midiToName(nearest);
    $("cents").textContent = cents === 0 ? "In tune" :
      `${cents > 0 ? "+" : ""}${cents} cents · ${Math.abs(cents) <= 10 ? "in tune" : cents > 0 ? "sharp, go down" : "flat, go up"}`;
    $("needle").style.left = Math.max(2, Math.min(98, 50 + cents)) + "%";
    Vox.setBar("pitch", stats.pitch(), stats.pitch() + "% on target");
    const t = stats.tone();
    Vox.setBar("tone", t, t == null ? "" : (t >= 75 ? "Steady" : t >= 50 ? "A little wobbly" : "Wobbly") + ` (${t}%)`);
    if (metro.running) { const r = stats.rhythm(bpm()); Vox.setBar("rhythm", r, r == null ? "" : r + "% on beat"); }
  }

  $("mic").onclick = async (e) => {
    const btn = e.currentTarget;
    if (detector && detector.running) {
      detector.stop();
      btn.setAttribute("aria-pressed", "false");
      btn.textContent = "Start microphone";
      await save();
      return;
    }
    try {
      frames = []; started = Date.now();
      detector = new Vox.PitchDetector(onFrame);
      await detector.start();
      btn.setAttribute("aria-pressed", "true");
      btn.textContent = "Stop and save";
    } catch (err) {
      $("cents").textContent = "Microphone not available: " + err.message;
    }
  };

  async function save() {
    if (frames.filter((f) => f.f).length < 10) { $("cents").textContent = "Not enough singing to save a session."; return; }
    try {
      const r = await Vox.postJSON(window.VOX_URLS.save, {
        kind: "tuner", seconds: Math.round((Date.now() - started) / 1000), frames,
      });
      $("summary").classList.remove("d-none");
      $("sum-pitch").textContent = r.pitch == null ? "Pitch –" : `Pitch ${Math.round(r.pitch)}%`;
      $("sum-tone").textContent = r.tone == null ? "Tone –" : `Tone ${Math.round(r.tone)}%`;
      const coachUrl = window.VOX_URLS.coach.replace("/0/", `/${r.id}/`);
      const old = $("coach-btn");
      const btn = old.cloneNode(true);  // drop the previous session's click handler
      old.replaceWith(btn);
      btn.classList.remove("d-none");
      btn.disabled = false;
      btn.textContent = "Get tips from the AI coach";
      $("coach").innerHTML = "";
      btn.onclick = () => Vox.coach(coachUrl, $("coach"), btn);
    } catch (err) {
      $("cents").textContent = "Could not save: " + err.message;
    }
  }
})();
