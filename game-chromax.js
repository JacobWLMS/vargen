// ── Chromax: Guess the daily color by its RGB values ──
// A visual color-matching puzzle — no words, no numbers
VarGen.registerGame("chromax", {
  name: "Chromax",
  icon: "🎨",
  iconBg: "#6f2d5a",
  desc: "Guess the secret color",
  tagline: "Match the color. Trust your eyes.",
  statsKey: "vargen-chromax-stats",
  stateKey: "vargen-chromax-state",

  helpHTML: `
    <h2>Chromax</h2>
    <p>Guess the hidden color's <strong>RGB values</strong> in 6 tries.</p>
    <ul>
      <li>You see the <b>target color</b> — study it carefully.</li>
      <li>Use the sliders to set <b style="color:#ff6b6b">R</b>, <b style="color:#6bff6b">G</b>, <b style="color:#6b9fff">B</b> values (0–255).</li>
      <li>After each guess, arrows show if each channel is <b>too high</b>, <b>too low</b>, or <b>correct</b>.</li>
      <li>A guess is <b>correct</b> when all three channels are within 5 of the target.</li>
    </ul>
    <div class="examples">
      <div class="example-row">
        <span class="tile-example correct" style="font-size:1rem;">R</span>
        <span class="desc"><b>Green</b> — Channel within 5 of target.</span>
      </div>
      <div class="example-row">
        <span class="tile-example present" style="font-size:1rem;">G</span>
        <span class="desc"><b>Yellow</b> — Channel within 30 of target.</span>
      </div>
      <div class="example-row">
        <span class="tile-example absent" style="font-size:1rem;">B</span>
        <span class="desc"><b>Gray</b> — Channel is far off. Arrow shows direction.</span>
      </div>
    </div>
    <p class="hint-text">A new color every day. Train your eye!</p>
  `,

  init() {
    const dayIndex = VarGen.getDayIndex();
    const rng = VarGen.mulberry32(dayIndex * 88813);

    // Generate a pleasant target color (avoid very dark or very light)
    const targetR = Math.floor(rng() * 200) + 28;
    const targetG = Math.floor(rng() * 200) + 28;
    const targetB = Math.floor(rng() * 200) + 28;

    const MAX_GUESSES = 6;
    const TOLERANCE = 5;
    const CLOSE = 30;
    let guesses = [];
    let gameOver = false;
    let sliderR = 128, sliderG = 128, sliderB = 128;

    const container = VarGen.$("#game-container");

    function rgbStr(r, g, b) { return `rgb(${r},${g},${b})`; }
    function hexStr(r, g, b) {
      return "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("");
    }

    function channelState(guess, target) {
      const diff = Math.abs(guess - target);
      if (diff <= TOLERANCE) return "correct";
      if (diff <= CLOSE) return "close";
      return "far";
    }

    function channelArrow(guess, target) {
      const diff = Math.abs(guess - target);
      if (diff <= TOLERANCE) return "=";
      return guess < target ? "↑" : "↓";
    }

    function render() {
      container.innerHTML = "";

      // Target color swatch
      const swatchArea = document.createElement("div");
      swatchArea.style.cssText = "display:flex;gap:16px;align-items:center;justify-content:center;margin-top:16px;width:100%;";

      const targetSwatch = document.createElement("div");
      targetSwatch.style.cssText = `width:90px;height:90px;border-radius:12px;background:${rgbStr(targetR, targetG, targetB)};border:2px solid #555;`;
      const targetLabel = document.createElement("div");
      targetLabel.style.cssText = "text-align:center;font-size:0.7rem;color:#818384;margin-top:4px;";
      targetLabel.textContent = "TARGET";
      const targetWrap = document.createElement("div");
      targetWrap.style.cssText = "text-align:center;";
      targetWrap.appendChild(targetSwatch);
      targetWrap.appendChild(targetLabel);

      const vs = document.createElement("div");
      vs.style.cssText = "font-size:1.2rem;color:#555;font-weight:700;";
      vs.textContent = "vs";

      const guessSwatch = document.createElement("div");
      guessSwatch.style.cssText = `width:90px;height:90px;border-radius:12px;background:${rgbStr(sliderR, sliderG, sliderB)};border:2px solid #555;transition:background 0.15s;`;
      const guessHex = document.createElement("div");
      guessHex.style.cssText = "text-align:center;font-size:0.7rem;color:#818384;margin-top:4px;font-family:monospace;";
      guessHex.textContent = gameOver ? (guesses.length > 0 ? hexStr(...guesses[guesses.length - 1].rgb) : "") : hexStr(sliderR, sliderG, sliderB);
      const guessWrap = document.createElement("div");
      guessWrap.style.cssText = "text-align:center;";
      guessWrap.appendChild(guessSwatch);
      guessWrap.appendChild(guessHex);

      swatchArea.appendChild(targetWrap);
      swatchArea.appendChild(vs);
      swatchArea.appendChild(guessWrap);
      container.appendChild(swatchArea);

      // Sliders (only if game is active)
      if (!gameOver) {
        const slidersEl = document.createElement("div");
        slidersEl.style.cssText = "width:100%;max-width:380px;margin-top:20px;";

        [["R", sliderR, "#ff6b6b", (v) => { sliderR = v; }],
         ["G", sliderG, "#6bff6b", (v) => { sliderG = v; }],
         ["B", sliderB, "#6b9fff", (v) => { sliderB = v; }],
        ].forEach(([label, val, color, setter]) => {
          const row = document.createElement("div");
          row.style.cssText = "display:flex;align-items:center;gap:10px;margin:8px 0;";

          const lbl = document.createElement("span");
          lbl.style.cssText = `font-weight:700;font-size:1rem;width:20px;color:${color};`;
          lbl.textContent = label;

          const slider = document.createElement("input");
          slider.type = "range";
          slider.min = 0;
          slider.max = 255;
          slider.value = val;
          slider.style.cssText = `flex:1;accent-color:${color};height:8px;`;
          slider.addEventListener("input", () => {
            setter(parseInt(slider.value));
            numInput.value = slider.value;
            guessSwatch.style.background = rgbStr(sliderR, sliderG, sliderB);
            guessHex.textContent = hexStr(sliderR, sliderG, sliderB);
          });

          const numInput = document.createElement("input");
          numInput.type = "number";
          numInput.min = 0;
          numInput.max = 255;
          numInput.value = val;
          numInput.style.cssText = "width:52px;background:#2c2c2e;border:1px solid #555;border-radius:4px;color:white;text-align:center;font-size:0.9rem;padding:4px;";
          numInput.addEventListener("input", () => {
            let v = parseInt(numInput.value) || 0;
            v = Math.max(0, Math.min(255, v));
            setter(v);
            slider.value = v;
            guessSwatch.style.background = rgbStr(sliderR, sliderG, sliderB);
            guessHex.textContent = hexStr(sliderR, sliderG, sliderB);
          });

          row.appendChild(lbl);
          row.appendChild(slider);
          row.appendChild(numInput);
          slidersEl.appendChild(row);
        });

        container.appendChild(slidersEl);
      }

      // Previous guesses
      if (guesses.length > 0) {
        const historyEl = document.createElement("div");
        historyEl.style.cssText = "width:100%;max-width:400px;margin-top:16px;";

        guesses.forEach((g, idx) => {
          const row = document.createElement("div");
          row.style.cssText = "display:flex;align-items:center;gap:8px;margin:6px 0;padding:6px 8px;background:#1a1a1b;border-radius:8px;border:1px solid #3a3a3c;";

          // Mini swatch
          const mini = document.createElement("div");
          mini.style.cssText = `width:32px;height:32px;border-radius:6px;background:${rgbStr(...g.rgb)};flex-shrink:0;`;
          row.appendChild(mini);

          // Channel feedback
          const channels = [
            ["R", g.rgb[0], targetR, "#ff6b6b"],
            ["G", g.rgb[1], targetG, "#6bff6b"],
            ["B", g.rgb[2], targetB, "#6b9fff"],
          ];
          channels.forEach(([lbl, guessVal, targetVal, color]) => {
            const chip = document.createElement("div");
            const state = channelState(guessVal, targetVal);
            const arrow = channelArrow(guessVal, targetVal);
            let bg = "#3a3a3c";
            if (state === "correct") bg = "#538d4e";
            else if (state === "close") bg = "#b59f3b";
            chip.style.cssText = `background:${bg};padding:3px 8px;border-radius:4px;font-size:0.75rem;font-weight:700;font-family:monospace;display:flex;align-items:center;gap:3px;`;
            chip.innerHTML = `<span style="color:${color}">${lbl}</span>${guessVal} ${arrow}`;
            row.appendChild(chip);
          });

          // Guess number
          const num = document.createElement("span");
          num.style.cssText = "margin-left:auto;font-size:0.7rem;color:#555;";
          num.textContent = `#${idx + 1}`;
          row.appendChild(num);

          historyEl.appendChild(row);
        });

        container.appendChild(historyEl);
      }

      // Submit button
      if (!gameOver) {
        const bar = document.createElement("div");
        bar.className = "action-bar";
        bar.style.marginTop = "12px";
        const submitBtn = document.createElement("button");
        submitBtn.className = "action-btn primary";
        submitBtn.textContent = `Guess (${MAX_GUESSES - guesses.length} left)`;
        submitBtn.addEventListener("click", submitGuess);
        bar.appendChild(submitBtn);
        container.appendChild(bar);
      }

      // Show answer if game over and lost
      if (gameOver) {
        const answerEl = document.createElement("div");
        answerEl.style.cssText = "margin-top:12px;font-size:0.85rem;color:#818384;text-align:center;font-family:monospace;";
        answerEl.textContent = `Answer: rgb(${targetR}, ${targetG}, ${targetB}) = ${hexStr(targetR, targetG, targetB)}`;
        container.appendChild(answerEl);
      }
    }

    function submitGuess() {
      if (gameOver) return;

      const r = sliderR, g = sliderG, b = sliderB;
      const rState = channelState(r, targetR);
      const gState = channelState(g, targetG);
      const bState = channelState(b, targetB);

      guesses.push({ rgb: [r, g, b], states: [rState, gState, bState] });

      const won = rState === "correct" && gState === "correct" && bState === "correct";
      if (won) {
        gameOver = true;
        VarGen.showToast("Perfect match!");
        VarGen.recordResult(this.statsKey, true, guesses.length);
        saveGameState(true);
        render();
        setTimeout(() => VarGen.showStats(this.statsKey, true, guesses.length), 1500);
      } else if (guesses.length >= MAX_GUESSES) {
        gameOver = true;
        VarGen.showToast("So close!");
        VarGen.recordResult(this.statsKey, false, null);
        saveGameState(false);
        render();
        setTimeout(() => VarGen.showStats(this.statsKey, true, null), 1500);
      } else {
        render();
      }
    }
    submitGuess = submitGuess.bind(this);

    const saveGameState = (won) => {
      VarGen.saveState(this.stateKey, {
        dayIndex, guesses: guesses.map((g) => ({ rgb: g.rgb, states: g.states })),
        gameOver, won,
      });
    };

    // Restore
    const saved = VarGen.loadState(this.stateKey, dayIndex);
    if (saved) {
      guesses = saved.guesses;
      gameOver = saved.gameOver;
      if (guesses.length > 0) {
        const last = guesses[guesses.length - 1].rgb;
        sliderR = last[0]; sliderG = last[1]; sliderB = last[2];
      }
    }

    render();

    if (saved?.gameOver) {
      setTimeout(() => VarGen.showStats(this.statsKey, true, saved.won ? saved.guesses.length : null), 500);
    }

    // Keyboard: Enter to submit
    VarGen.keydownHandler = (e) => {
      if (gameOver) return;
      if (document.querySelector(".modal:not(.hidden)")) return;
      if (e.key === "Enter") { e.preventDefault(); submitGuess(); }
    };

    this._shareHandler = () => {
      const stateMap = { correct: "🟩", close: "🟨", far: "⬛" };
      const won = guesses.length > 0 && guesses[guesses.length - 1].states.every((s) => s === "correct");
      let text = `VarGen: Chromax #${dayIndex} ${won ? guesses.length : "X"}/6\n\n`;
      guesses.forEach((g) => { text += g.states.map((s) => stateMap[s]).join("") + "\n"; });
      navigator.clipboard.writeText(text.trim()).then(() => VarGen.showToast("Copied!")).catch(() => VarGen.showToast("Couldn't copy"));
    };
  },

  showHelp() {
    VarGen.$("#help-body").innerHTML = this.helpHTML;
    VarGen.$("#modal-help").classList.remove("hidden");
  },

  showGameStats() {
    VarGen.$("#stats-game-label").textContent = "Chromax";
    const saved = VarGen.loadState(this.stateKey, VarGen.getDayIndex());
    VarGen.showStats(this.statsKey, saved?.gameOver, saved?.won ? saved.guesses.length : null);
  },

  share() { this._shareHandler?.(); },
});
