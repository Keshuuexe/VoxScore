/*
  Screen 9: the range test. Each button listens for ~3 seconds and takes the median pitch of
  the steadiest part of what was sung, which ignores the scoop at the start of a note.
*/
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const result = { low: null, high: null };

  async function listen(which, button) {
    const pitches = [];
    const detector = new Vox.PitchDetector((fr) => { if (fr.f) pitches.push(Vox.freqToMidi(fr.f)); });
    try {
      await detector.start();
    } catch (err) {
      $("range-status").textContent = "Microphone not available: " + err.message;
      return;
    }
    button.disabled = true;
    let left = 3;
    button.textContent = `Listening… ${left}`;
    const tick = setInterval(() => { left--; button.textContent = `Listening… ${left}`; }, 1000);
    setTimeout(() => {
      clearInterval(tick);
      detector.stop();
      button.disabled = false;
      button.textContent = which === "low" ? "Sing my lowest note" : "Sing my highest note";
      if (pitches.length < 15) { $("range-status").textContent = "I couldn't hear a steady note. Try again a little louder."; return; }
      const middle = pitches.slice(Math.floor(pitches.length / 3)).sort((a, b) => a - b);
      const midi = Math.round(middle[Math.floor(middle.length / 2)]);
      result[which] = midi;
      $(which + "-note").textContent = Vox.midiToName(midi);
      $("save-range").disabled = !(result.low && result.high);
    }, 3000);
  }

  $("test-low").onclick = (e) => listen("low", e.currentTarget);
  $("test-high").onclick = (e) => listen("high", e.currentTarget);
  $("save-range").onclick = async () => {
    try {
      const r = await Vox.postJSON(window.VOX_URLS.range, result);
      $("range-label").textContent = r.range;
      $("voice-type").textContent = r.voice_type;
      $("range-status").textContent = "Saved. Warmups will now start in your range.";
    } catch (err) {
      $("range-status").textContent = err.message;
    }
  };
})();
