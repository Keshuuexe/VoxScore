/*
  Screen 7: Score editor.
    - abcjs draws each part from the ABC the server wrote.
    - The note strip lists the selected part's notes; click one, then change its pitch or
      length, or delete it. Each edit is pushed on an undo stack and auto-saved to part-save,
      which validates the notes and returns fresh ABC to redraw.
    - Play plays every accepted part together; "Hear it" previews a pending AI suggestion.
*/
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const data = Vox.readJSON("editor-data");
  const parts = data.parts.filter((p) => !p.pending);
  const byId = Object.fromEntries(data.parts.map((p) => [p.id, p]));
  let current = parts[0] || null, selected = -1, undo = [], redo = [], saveTimer = null, stopPlay = null;

  function renderSheet() {
    const sheet = $("sheet");
    sheet.innerHTML = "";
    if (!window.ABCJS) { sheet.textContent = "Sheet music could not load (check your internet connection)."; return; }
    parts.forEach((p) => {
      const div = document.createElement("div");
      div.style.opacity = current && p.id === current.id ? "1" : ".55";
      sheet.appendChild(div);
      ABCJS.renderAbc(div, p.abc, { responsive: "resize", staffwidth: 760, add_classes: true });
    });
    if (!parts.length) sheet.innerHTML = '<p class="p-3 vx-sub mb-0">No parts yet. Record a melody to get started.</p>';
    document.querySelectorAll("[data-abc-pending]").forEach((el) => {
      ABCJS.renderAbc(el, byId[el.dataset.abcPending].abc, { responsive: "resize", staffwidth: 300, scale: 0.7 });
    });
  }

  function renderStrip() {
    const strip = $("strip");
    strip.innerHTML = "";
    $("delete-part-form").hidden = !current;
    if (!current) return;
    current.notes.forEach((n, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn btn-sm " + (i === selected ? "btn-vx" : "btn-outline-vx");
      b.setAttribute("role", "option");
      b.setAttribute("aria-selected", i === selected);
      b.innerHTML = `<span class="vx-mono">${Vox.midiToName(n.midi)}</span><br><small>${n.dur}b</small>`;
      b.onclick = () => { selected = i; Vox.playNote(n.midi, 0.4); refreshSelection(); };
      strip.appendChild(b);
    });
    const del = $("delete-part-form");
    del.action = window.VOX_URLS.del.replace("/0/", `/${current.id}/`);
  }

  function refreshSelection() {
    const n = current && current.notes[selected];
    $("selected-label").textContent = n ? `Selected: ${Vox.midiToName(n.midi)}, ${n.dur} beat${n.dur === 1 ? "" : "s"} at beat ${n.start + 1}` : "Select a note below";
    if (n) $("dur").value = String(n.dur);
    ["up", "down", "dur", "del"].forEach((id) => { $(id).disabled = !n; });
    $("undo").disabled = !undo.length;
    $("redo").disabled = !redo.length;
    renderStrip();
  }

  function edit(fn) {
    if (!current || selected < 0) return;
    undo.push(JSON.stringify(current.notes));
    redo = [];
    fn(current.notes);
    current.notes.sort((a, b) => a.start - b.start);
    scheduleSave();
    refreshSelection();
  }

  function scheduleSave() {
    $("save-state").textContent = "Saving…";
    clearTimeout(saveTimer);
    const part = current;
    saveTimer = setTimeout(async () => {
      try {
        const r = await Vox.postJSON(window.VOX_URLS.save.replace("/0/", `/${part.id}/`), { notes: part.notes });
        part.abc = r.abc;
        renderSheet();
        $("save-state").textContent = "All changes saved";
      } catch (e) {
        $("save-state").textContent = "Not saved: " + e.message;
      }
    }, 350);
  }

  $("up").onclick = () => edit((ns) => { ns[selected].midi = Math.min(108, ns[selected].midi + 1); Vox.playNote(ns[selected].midi, 0.35); });
  $("down").onclick = () => edit((ns) => { ns[selected].midi = Math.max(21, ns[selected].midi - 1); Vox.playNote(ns[selected].midi, 0.35); });
  $("dur").onchange = (e) => edit((ns) => {
    const d = parseFloat(e.target.value), delta = d - ns[selected].dur;
    ns[selected].dur = d;
    // Ripple: later notes move with the change, so nothing overlaps.
    for (let i = selected + 1; i < ns.length; i++) ns[i].start = Math.max(0, ns[i].start + delta);
  });
  $("del").onclick = () => edit((ns) => { ns.splice(selected, 1); selected = Math.min(selected, ns.length - 1); });
  $("undo").onclick = () => {
    if (!undo.length) return;
    redo.push(JSON.stringify(current.notes));
    current.notes = JSON.parse(undo.pop());
    scheduleSave(); refreshSelection();
  };
  $("redo").onclick = () => {
    if (!redo.length) return;
    undo.push(JSON.stringify(current.notes));
    current.notes = JSON.parse(redo.pop());
    scheduleSave(); refreshSelection();
  };

  document.querySelectorAll("[data-part]").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll("[data-part]").forEach((b) => b.setAttribute("aria-pressed", "false"));
      btn.setAttribute("aria-pressed", "true");
      current = byId[btn.dataset.part];
      selected = -1; undo = []; redo = [];
      renderSheet(); refreshSelection();
    };
  });

  $("play").onclick = () => {
    if (stopPlay) stopPlay();
    const all = parts.flatMap((p) => p.notes);
    stopPlay = Vox.playNotes(all, data.bpm, (i) => {
      if (current && i >= 0 && current.notes.includes(all[i])) { selected = current.notes.indexOf(all[i]); renderStrip(); }
    });
  };
  $("stop").onclick = () => { if (stopPlay) stopPlay(); stopPlay = null; };
  document.querySelectorAll("[data-preview]").forEach((btn) => {
    btn.onclick = () => {
      if (stopPlay) stopPlay();
      const p = byId[btn.dataset.preview];
      stopPlay = Vox.playNotes(parts.flatMap((x) => x.notes).concat(p.notes), data.bpm);
    };
  });

  renderSheet();
  refreshSelection();
})();
