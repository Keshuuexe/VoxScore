/*
  Click notes: a few music symbols float up from wherever the user clicks a button, link,
  chip, tab or card, like notes rising off the page.

  Purely visual (no sound), and deliberately skipped on controls that already make sound
  (play, record, microphone, metronome, drone, the piano keys...), so the effect never
  competes with real music. Also skipped when the user's system asks for reduced motion.

  To exclude any other element, give it (or a parent) the attribute data-no-notes.
*/
(function () {
  "use strict";

  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  // Eighth note, beamed eighths, quarter note, beamed sixteenths, quarter rest, sharp, flat, natural.
  const GLYPHS = ["♪", "♫", "♩", "♬", "\u{1D13D}", "♯", "♭", "♮"];

  // Things that respond to a click.
  const CLICKABLE = "a, button, .btn, .vx-chip, [role='option'], .vx-part-tab, .form-check-input, summary";

  // Controls that make or stop real sound: no visual notes on these.
  const AUDIO_CONTROLS = [
    "#play", "#stop", "#record", "#discard", "#mic", "#sing", "#play-example", "#hear",
    "#metro-toggle", "#drone-toggle", "#test-low", "#test-high",
    "[data-preview]", ".vx-keys button", "#strip button", "[data-no-notes]",
  ].join(", ");

  function burst(x, y) {
    const count = 2 + Math.floor(Math.random() * 2);
    for (let i = 0; i < count; i++) {
      const el = document.createElement("span");
      el.className = "vx-fx-note";
      el.setAttribute("aria-hidden", "true");
      el.textContent = GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
      el.style.left = x + "px";
      el.style.top = y + "px";
      el.style.fontSize = (22 + Math.random() * 16) + "px";
      el.style.setProperty("--dx", ((Math.random() - 0.5) * 70).toFixed(0) + "px");
      el.style.setProperty("--rise", (55 + Math.random() * 55).toFixed(0) + "px");
      el.style.setProperty("--rot", ((Math.random() - 0.5) * 50).toFixed(0) + "deg");
      el.style.setProperty("--life", (750 + Math.random() * 450).toFixed(0) + "ms");
      el.style.animationDelay = (i * 60) + "ms";
      document.body.appendChild(el);
      el.addEventListener("animationend", () => el.remove());
    }
  }

  document.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    const target = e.target.closest(CLICKABLE);
    if (!target || target.disabled || target.closest(AUDIO_CONTROLS)) return;
    burst(e.clientX, e.clientY);
  }, { passive: true });

  // Keyboard users get the effect too, from the centre of the focused control.
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const target = document.activeElement && document.activeElement.closest(CLICKABLE);
    if (!target || target.closest(AUDIO_CONTROLS)) return;
    const r = target.getBoundingClientRect();
    burst(r.left + r.width / 2, r.top + r.height / 2);
  });
})();
