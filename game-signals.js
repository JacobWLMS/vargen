// ── Signals: a Mastermind-style sequence puzzle with colors ──
// Guess the hidden sequence of 5 colored signals
VarGen.registerGame("signals", {
  name: "Signals",
  icon: "🚦",
  iconBg: "#2d5a6f",
  desc: "Crack the color code",
  tagline: "Decode the hidden signal sequence.",
  statsKey: "vargen-signals-stats",
  stateKey: "vargen-signals-state",

  helpHTML: `
    <h2>Signals</h2>
    <p>Crack the hidden sequence of <strong>5 colored signals</strong> in 6 guesses.</p>
    <ul>
      <li>Choose from <b>6 colors</b> to build your guess.</li>
      <li>Colors can repeat in the sequence.</li>
      <li>After each guess, you get <b>two types of feedback</b>:</li>
    </ul>
    <div class="examples">
      <div class="example-row">
        <span class="tile-example" style="background:#fff;width:20px;height:20px;border-radius:50%;"></span>
        <span class="desc"><b>White peg</b> — Right color, right position.</span>
      </div>
      <div class="example-row">
        <span class="tile-example" style="background:#666;width:20px;height:20px;border-radius:50%;"></span>
        <span class="desc"><b>Gray peg</b> — Right color, wrong position.</span>
      </div>
      <div class="example-row">
        <span class="tile-example" style="background:transparent;border:2px solid #444;width:20px;height:20px;border-radius:50%;"></span>
        <span class="desc"><b>Empty</b> — No match for this slot.</span>
      </div>
    </div>
    <p class="hint-text">Pegs are sorted (white first) and don't indicate WHICH position matched — you must deduce that!</p>
    <p class="hint-text">A new signal every day.</p>
  `,

  COLORS: [
    { name: "red", hex: "#e74c3c" },
    { name: "blue", hex: "#3498db" },
    { name: "green", hex: "#2ecc71" },
    { name: "yellow", hex: "#f1c40f" },
    { name: "purple", hex: "#9b59b6" },
    { name: "orange", hex: "#e67e22" },
  ],

  init() {
    const dayIndex = VarGen.getDayIndex();
    const rng = VarGen.mulberry32(dayIndex * 55577);
    const COLORS = this.COLORS;
    const SEQ_LEN = 5;
    const MAX_GUESSES = 6;

    // Generate target sequence
    const target = [];
    for (let i = 0; i < SEQ_LEN; i++) {
      target.push(Math.floor(rng() * COLORS.length));
    }

    let guesses = [];
    let currentGuess = Array(SEQ_LEN).fill(-1);
    let currentCol = 0;
    let gameOver = false;

    const container = VarGen.$("#game-container");

    function evaluate(guess) {
      // Mastermind scoring: exact matches (white pegs), color matches (gray pegs)
      const exact = [];
      const colorOnly = [];
      const targetCounts = {};
      const guessCounts = {};

      // First pass: exact matches
      for (let i = 0; i < SEQ_LEN; i++) {
        if (guess[i] === target[i]) {
          exact.push(i);
        } else {
          targetCounts[target[i]] = (targetCounts[target[i]] || 0) + 1;
          guessCounts[guess[i]] = (guessCounts[guess[i]] || 0) + 1;
        }
      }

      // Second pass: color-only matches
      let colorMatches = 0;
      for (const color in guessCounts) {
        if (targetCounts[color]) {
          colorMatches += Math.min(guessCounts[color], targetCounts[color]);
        }
      }

      return { exactCount: exact.length, colorCount: colorMatches };
    }

    function render() {
      container.innerHTML = "";

      // Guess history + current
      const boardEl = document.createElement("div");
      boardEl.style.cssText = "display:flex;flex-direction:column;gap:8px;margin-top:16px;width:100%;max-width:400px;";

      for (let r = 0; r < MAX_GUESSES; r++) {
        const row = document.createElement("div");
        row.style.cssText = "display:flex;align-items:center;gap:8px;";

        // Row number
        const rowNum = document.createElement("span");
        rowNum.style.cssText = "width:18px;font-size:0.75rem;color:#555;text-align:right;";
        rowNum.textContent = r + 1;
        row.appendChild(rowNum);

        // Guess circles
        const circlesWrap = document.createElement("div");
        circlesWrap.style.cssText = "display:flex;gap:6px;";

        if (r < guesses.length) {
          // Submitted guess
          for (let c = 0; c < SEQ_LEN; c++) {
            const circle = document.createElement("div");
            const colorIdx = guesses[r].guess[c];
            circle.style.cssText = `width:42px;height:42px;border-radius:50%;background:${COLORS[colorIdx].hex};border:2px solid rgba(255,255,255,0.15);`;
            circlesWrap.appendChild(circle);
          }
        } else if (r === guesses.length && !gameOver) {
          // Current guess input
          for (let c = 0; c < SEQ_LEN; c++) {
            const circle = document.createElement("div");
            const filled = currentGuess[c] >= 0;
            const isSelected = c === currentCol;
            circle.style.cssText = `width:42px;height:42px;border-radius:50%;background:${filled ? COLORS[currentGuess[c]].hex : "#2c2c2e"};border:2px solid ${isSelected ? "#fff" : filled ? "rgba(255,255,255,0.15)" : "#555"};cursor:pointer;transition:all 0.15s;${isSelected ? "box-shadow:0 0 0 2px rgba(255,255,255,0.3);" : ""}`;
            circle.addEventListener("click", () => { currentCol = c; render(); });
            circlesWrap.appendChild(circle);
          }
        } else {
          // Empty future row
          for (let c = 0; c < SEQ_LEN; c++) {
            const circle = document.createElement("div");
            circle.style.cssText = "width:42px;height:42px;border-radius:50%;background:#1a1a1b;border:2px solid #2a2a2c;";
            circlesWrap.appendChild(circle);
          }
        }

        row.appendChild(circlesWrap);

        // Feedback pegs (for submitted guesses)
        if (r < guesses.length) {
          const pegWrap = document.createElement("div");
          pegWrap.style.cssText = "display:flex;gap:3px;margin-left:8px;flex-wrap:wrap;width:40px;";

          const fb = guesses[r].feedback;
          const pegs = [];
          for (let i = 0; i < fb.exactCount; i++) pegs.push("white");
          for (let i = 0; i < fb.colorCount; i++) pegs.push("gray");
          while (pegs.length < SEQ_LEN) pegs.push("empty");

          pegs.forEach((type) => {
            const peg = document.createElement("div");
            let style = "width:14px;height:14px;border-radius:50%;";
            if (type === "white") style += "background:#fff;";
            else if (type === "gray") style += "background:#666;";
            else style += "background:transparent;border:2px solid #444;";
            peg.style.cssText = style;
            pegWrap.appendChild(peg);
          });

          row.appendChild(pegWrap);
        }

        boardEl.appendChild(row);
      }

      container.appendChild(boardEl);

      // Color palette (only if game active)
      if (!gameOver) {
        const paletteEl = document.createElement("div");
        paletteEl.style.cssText = "display:flex;gap:10px;margin-top:20px;justify-content:center;";

        COLORS.forEach((color, idx) => {
          const btn = document.createElement("div");
          btn.style.cssText = `width:44px;height:44px;border-radius:50%;background:${color.hex};cursor:pointer;border:3px solid transparent;transition:all 0.15s;`;
          btn.addEventListener("mouseenter", () => { btn.style.transform = "scale(1.15)"; });
          btn.addEventListener("mouseleave", () => { btn.style.transform = "scale(1)"; });
          btn.addEventListener("click", () => {
            currentGuess[currentCol] = idx;
            if (currentCol < SEQ_LEN - 1) currentCol++;
            render();
          });
          paletteEl.appendChild(btn);
        });

        container.appendChild(paletteEl);

        // Action bar
        const bar = document.createElement("div");
        bar.className = "action-bar";
        bar.style.marginTop = "16px";
        const clearBtn = document.createElement("button");
        clearBtn.className = "action-btn secondary";
        clearBtn.textContent = "Clear";
        clearBtn.addEventListener("click", () => {
          currentGuess = Array(SEQ_LEN).fill(-1);
          currentCol = 0;
          render();
        });
        const submitBtn = document.createElement("button");
        submitBtn.className = "action-btn primary";
        submitBtn.textContent = "Submit";
        submitBtn.addEventListener("click", submitGuess);
        bar.appendChild(clearBtn);
        bar.appendChild(submitBtn);
        container.appendChild(bar);
      }

      // Show answer if lost
      if (gameOver && guesses.length > 0 && guesses[guesses.length - 1].feedback.exactCount < SEQ_LEN) {
        const answerEl = document.createElement("div");
        answerEl.style.cssText = "display:flex;gap:6px;margin-top:16px;justify-content:center;align-items:center;";
        const label = document.createElement("span");
        label.style.cssText = "font-size:0.8rem;color:#818384;margin-right:8px;";
        label.textContent = "Answer:";
        answerEl.appendChild(label);
        target.forEach((idx) => {
          const dot = document.createElement("div");
          dot.style.cssText = `width:28px;height:28px;border-radius:50%;background:${COLORS[idx].hex};`;
          answerEl.appendChild(dot);
        });
        container.appendChild(answerEl);
      }
    }

    function submitGuess() {
      if (gameOver) return;
      if (currentGuess.some((c) => c < 0)) {
        VarGen.showToast("Fill all 5 positions");
        return;
      }

      const guess = [...currentGuess];
      const feedback = evaluate(guess);
      guesses.push({ guess, feedback });

      const won = feedback.exactCount === SEQ_LEN;
      if (won) {
        gameOver = true;
        const msgs = ["Genius!", "Brilliant!", "Impressive!", "Nice!", "Good!", "Phew!"];
        VarGen.showToast(msgs[guesses.length - 1] || "Solved!");
        VarGen.recordResult(this.statsKey, true, guesses.length);
        saveGameState(true);
        render();
        setTimeout(() => VarGen.showStats(this.statsKey, true, guesses.length), 1500);
      } else if (guesses.length >= MAX_GUESSES) {
        gameOver = true;
        VarGen.showToast("Game over!");
        VarGen.recordResult(this.statsKey, false, null);
        saveGameState(false);
        render();
        setTimeout(() => VarGen.showStats(this.statsKey, true, null), 1500);
      } else {
        currentGuess = Array(SEQ_LEN).fill(-1);
        currentCol = 0;
        render();
      }
    }
    submitGuess = submitGuess.bind(this);

    const saveGameState = (won) => {
      VarGen.saveState(this.stateKey, {
        dayIndex, guesses: guesses.map((g) => ({ guess: g.guess, feedback: g.feedback })),
        gameOver, won,
      });
    };

    // Restore
    const saved = VarGen.loadState(this.stateKey, dayIndex);
    if (saved) {
      guesses = saved.guesses;
      gameOver = saved.gameOver;
    }

    render();

    if (saved?.gameOver) {
      setTimeout(() => VarGen.showStats(this.statsKey, true, saved.won ? saved.guesses.length : null), 500);
    }

    // Keyboard: 1-6 for colors, arrows, enter, backspace
    VarGen.keydownHandler = (e) => {
      if (gameOver || e.ctrlKey || e.metaKey || e.altKey) return;
      if (document.querySelector(".modal:not(.hidden)")) return;
      if (e.key === "Enter") { e.preventDefault(); submitGuess(); return; }
      if (e.key === "Backspace" || e.key === "Delete") {
        e.preventDefault();
        if (currentGuess[currentCol] >= 0) { currentGuess[currentCol] = -1; }
        else if (currentCol > 0) { currentCol--; currentGuess[currentCol] = -1; }
        render();
        return;
      }
      if (e.key === "ArrowLeft") { currentCol = Math.max(0, currentCol - 1); render(); return; }
      if (e.key === "ArrowRight") { currentCol = Math.min(SEQ_LEN - 1, currentCol + 1); render(); return; }
      if (/^[1-6]$/.test(e.key)) {
        const idx = parseInt(e.key) - 1;
        currentGuess[currentCol] = idx;
        if (currentCol < SEQ_LEN - 1) currentCol++;
        render();
      }
    };

    this._shareHandler = () => {
      const won = guesses.length > 0 && guesses[guesses.length - 1].feedback.exactCount === SEQ_LEN;
      const colorEmoji = ["🔴", "🔵", "🟢", "🟡", "🟣", "🟠"];
      let text = `VarGen: Signals #${dayIndex} ${won ? guesses.length : "X"}/6\n\n`;
      guesses.forEach((g) => {
        text += g.guess.map((c) => colorEmoji[c]).join("") + " ";
        text += "⚪".repeat(g.feedback.exactCount) + "⚫".repeat(g.feedback.colorCount) + "\n";
      });
      navigator.clipboard.writeText(text.trim()).then(() => VarGen.showToast("Copied!")).catch(() => VarGen.showToast("Couldn't copy"));
    };
  },

  showHelp() {
    VarGen.$("#help-body").innerHTML = this.helpHTML;
    VarGen.$("#modal-help").classList.remove("hidden");
  },

  showGameStats() {
    VarGen.$("#stats-game-label").textContent = "Signals";
    const saved = VarGen.loadState(this.stateKey, VarGen.getDayIndex());
    VarGen.showStats(this.statsKey, saved?.gameOver, saved?.won ? saved.guesses.length : null);
  },

  share() { this._shareHandler?.(); },
});
