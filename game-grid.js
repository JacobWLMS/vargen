// ── Equation Grid: fill in numbers to make all equations valid ──
// A 5x3 grid: two horizontal equations stacked with operators between
// e.g.  A + B = C
//       ×   -
//       D + E = F
//       =   =
//       G   H
VarGen.registerGame("grid", {
  name: "Math Grid",
  icon: "🧮",
  iconBg: "#6f4a2d",
  desc: "Fill the grid — make every equation work",
  tagline: "Make every equation true.",
  statsKey: "vargen-grid-stats",
  stateKey: "vargen-grid-state",

  helpHTML: `
    <h2>Math Grid</h2>
    <p>Fill in the missing numbers to make <strong>every equation</strong> true — across and down.</p>
    <ul>
      <li>The grid shows two horizontal equations and two vertical equations.</li>
      <li>Some numbers are <b>given</b> as clues. Fill in the blanks.</li>
      <li>Each blank is a single digit (<b>1–9</b>).</li>
      <li>Tap a blank cell, then tap a number to fill it.</li>
      <li>Hit <b>Check</b> to see which cells are correct.</li>
    </ul>
    <div class="examples">
      <div class="example-row">
        <span class="tile-example correct" style="font-size:1rem;">5</span>
        <span class="desc"><b>Green</b> — Correct number.</span>
      </div>
      <div class="example-row">
        <span class="tile-example" style="background:#8b2020;font-size:1rem;">3</span>
        <span class="desc"><b>Red</b> — Wrong number.</span>
      </div>
    </div>
    <p class="hint-text">All equations use basic math: +, −, ×. Every puzzle has exactly one solution.</p>
    <p class="hint-text">A new grid every day.</p>
  `,

  init() {
    const dayIndex = VarGen.getDayIndex();
    const rng = VarGen.mulberry32(dayIndex * 54321);

    // Generate a valid puzzle deterministically
    // Layout:
    //   a [op1] b = r1
    //  [op3]   [op4]
    //   c [op2] d = r2
    //   =       =
    //   r3      r4

    const ops = ["+", "-", "×"];

    function calc(a, op, b) {
      if (op === "+") return a + b;
      if (op === "-") return a - b;
      if (op === "×") return a * b;
      return NaN;
    }

    // Try random combos until we find one that works with digits 1-9
    let puzzle = null;
    for (let attempts = 0; attempts < 2000; attempts++) {
      const a = Math.floor(rng() * 9) + 1;
      const b = Math.floor(rng() * 9) + 1;
      const c = Math.floor(rng() * 9) + 1;
      const d = Math.floor(rng() * 9) + 1;
      const op1 = ops[Math.floor(rng() * 3)];
      const op2 = ops[Math.floor(rng() * 3)];
      const op3 = ops[Math.floor(rng() * 3)];
      const op4 = ops[Math.floor(rng() * 3)];

      const r1 = calc(a, op1, b);
      const r2 = calc(c, op2, d);
      const r3 = calc(a, op3, c);
      const r4 = calc(b, op4, d);

      // All results must be positive integers 1-99
      if ([r1, r2, r3, r4].every((r) => Number.isInteger(r) && r >= 1 && r <= 99)) {
        puzzle = { a, b, c, d, op1, op2, op3, op4, r1, r2, r3, r4 };
        break;
      }
    }

    // Fallback puzzle if generation fails
    if (!puzzle) {
      puzzle = { a: 3, b: 2, c: 4, d: 1, op1: "+", op2: "+", op3: "+", op4: "+", r1: 5, r2: 5, r3: 7, r4: 3 };
    }

    // Decide which cells to hide (always hide 2–3 of a,b,c,d)
    const allCells = ["a", "b", "c", "d"];
    const numHidden = 2 + (Math.floor(rng() * 2)); // 2 or 3
    const hidden = new Set(VarGen.shuffle(allCells, rng).slice(0, numHidden));

    let selectedCell = null;
    let userValues = {};
    hidden.forEach((k) => (userValues[k] = null));
    let checked = false;
    let checkResults = {};
    let gameOver = false;
    let guessCount = 0;
    const MAX_CHECKS = 6;

    const container = VarGen.$("#game-container");

    function render() {
      container.innerHTML = "";

      // Build the grid visually
      // Row 0:  a  op1  b  =  r1
      // Row 1: op3  .  op4  .  .
      // Row 2:  c  op2  d  =  r2
      // Row 3:  =   .   =  .  .
      // Row 4: r3   .  r4  .  .

      const grid = document.createElement("div");
      grid.className = "eq-grid eq-grid-5";

      const layout = [
        [cellVal("a"), cellOp(puzzle.op1), cellVal("b"), cellOp("="), cellRes(puzzle.r1)],
        [cellOp(puzzle.op3), cellEmpty(), cellOp(puzzle.op4), cellEmpty(), cellEmpty()],
        [cellVal("c"), cellOp(puzzle.op2), cellVal("d"), cellOp("="), cellRes(puzzle.r2)],
        [cellOp("="), cellEmpty(), cellOp("="), cellEmpty(), cellEmpty()],
        [cellRes(puzzle.r3), cellEmpty(), cellRes(puzzle.r4), cellEmpty(), cellEmpty()],
      ];

      layout.forEach((row) => row.forEach((cell) => grid.appendChild(cell)));
      container.appendChild(grid);

      // Numpad
      const numpad = document.createElement("div");
      numpad.className = "numpad";
      for (let n = 1; n <= 9; n++) {
        const btn = document.createElement("button");
        btn.className = "num-key";
        btn.textContent = n;
        btn.addEventListener("click", () => numInput(n));
        numpad.appendChild(btn);
      }
      const delBtn = document.createElement("button");
      delBtn.className = "num-key wide";
      delBtn.textContent = "DEL";
      delBtn.addEventListener("click", () => numInput(null));
      numpad.appendChild(delBtn);
      container.appendChild(numpad);

      // Check button
      const bar = document.createElement("div");
      bar.className = "action-bar";
      const checkBtn = document.createElement("button");
      checkBtn.className = "action-btn primary";
      checkBtn.textContent = gameOver ? (checked ? "Solved!" : "Game Over") : `Check (${MAX_CHECKS - guessCount} left)`;
      checkBtn.addEventListener("click", checkAnswer);
      if (gameOver) checkBtn.disabled = true;
      bar.appendChild(checkBtn);
      container.appendChild(bar);

      // Remaining guesses
      const info = document.createElement("p");
      info.style.cssText = "color:#818384;font-size:0.8rem;margin-top:8px;";
      info.textContent = `Fill in ${hidden.size} hidden cell${hidden.size > 1 ? "s" : ""}`;
      container.appendChild(info);
    }

    function cellVal(key) {
      const el = document.createElement("div");
      el.className = "eq-cell";
      if (hidden.has(key)) {
        el.classList.add("input");
        const val = userValues[key];
        if (val !== null) {
          el.textContent = val;
          el.classList.add("filled");
        }
        if (checked && checkResults[key] !== undefined) {
          el.classList.add(checkResults[key] ? "eq-correct" : "eq-wrong");
        }
        if (selectedCell === key && !gameOver) el.classList.add("selected");
        if (!gameOver) el.addEventListener("click", () => { selectedCell = key; render(); });
      } else {
        el.classList.add("given");
        el.textContent = puzzle[key];
      }
      return el;
    }

    function cellOp(op) {
      const el = document.createElement("div");
      el.className = "eq-cell operator";
      el.textContent = op;
      return el;
    }

    function cellRes(val) {
      const el = document.createElement("div");
      el.className = "eq-cell result";
      el.textContent = val;
      return el;
    }

    function cellEmpty() {
      const el = document.createElement("div");
      el.className = "eq-cell empty";
      return el;
    }

    function numInput(n) {
      if (gameOver || !selectedCell) return;
      userValues[selectedCell] = n;
      checked = false;
      checkResults = {};
      // Auto-advance to next empty
      const keys = [...hidden];
      const idx = keys.indexOf(selectedCell);
      if (n !== null) {
        const next = keys.find((k, i) => i > idx && userValues[k] === null);
        if (next) selectedCell = next;
      }
      render();
    }

    function checkAnswer() {
      if (gameOver) return;
      // All cells must be filled
      for (const k of hidden) {
        if (userValues[k] === null) {
          VarGen.showToast("Fill all cells first");
          return;
        }
      }

      guessCount++;
      checked = true;

      // Build full values
      const vals = {};
      for (const k of allCells) {
        vals[k] = hidden.has(k) ? userValues[k] : puzzle[k];
      }

      // Check each hidden cell
      let allCorrect = true;
      for (const k of hidden) {
        const correct = vals[k] === puzzle[k];
        checkResults[k] = correct;
        if (!correct) allCorrect = false;
      }

      if (allCorrect) {
        gameOver = true;
        VarGen.showToast("Solved!");
        VarGen.recordResult(this.statsKey, true, guessCount);
        saveGameState(true);
        render();
        setTimeout(() => VarGen.showStats(this.statsKey, true, guessCount), 1500);
      } else if (guessCount >= MAX_CHECKS) {
        gameOver = true;
        // Reveal answer
        for (const k of hidden) userValues[k] = puzzle[k];
        checkResults = {};
        VarGen.showToast("Game over — answer revealed");
        VarGen.recordResult(this.statsKey, false, null);
        saveGameState(false);
        render();
        setTimeout(() => VarGen.showStats(this.statsKey, true, null), 2000);
      } else {
        VarGen.showToast(`${Object.values(checkResults).filter(Boolean).length}/${hidden.size} correct`);
        render();
      }
    }
    checkAnswer = checkAnswer.bind(this);

    const saveGameState = (won) => {
      VarGen.saveState(this.stateKey, {
        dayIndex, userValues: { ...userValues }, guessCount, gameOver, won,
      });
    };

    // Restore
    const saved = VarGen.loadState(this.stateKey, dayIndex);
    if (saved) {
      userValues = saved.userValues;
      guessCount = saved.guessCount;
      gameOver = saved.gameOver;
      if (gameOver) checked = false; // Don't show red/green after restore
    }

    render();

    if (saved?.gameOver) {
      if (saved.won) {
        setTimeout(() => VarGen.showStats(this.statsKey, true, saved.guessCount), 500);
      } else {
        for (const k of hidden) userValues[k] = puzzle[k];
        render();
        setTimeout(() => VarGen.showStats(this.statsKey, true, null), 500);
      }
    }

    // Keyboard
    VarGen.keydownHandler = (e) => {
      if (gameOver || e.ctrlKey || e.metaKey || e.altKey) return;
      if (document.querySelector(".modal:not(.hidden)")) return;
      if (e.key === "Enter") { e.preventDefault(); checkAnswer(); return; }
      if (e.key === "Backspace" || e.key === "Delete") { e.preventDefault(); numInput(null); return; }
      if (/^[1-9]$/.test(e.key)) { numInput(parseInt(e.key)); return; }
      if (e.key === "Tab") {
        e.preventDefault();
        const keys = [...hidden];
        const idx = keys.indexOf(selectedCell);
        selectedCell = keys[(idx + 1) % keys.length];
        render();
      }
    };

    this._shareHandler = () => {
      const saved2 = VarGen.loadState(this.stateKey, dayIndex);
      const won = saved2?.won;
      let text = `VarGen: Math Grid #${dayIndex} ${won ? saved2.guessCount : "X"}/${MAX_CHECKS}\n`;
      text += `${hidden.size} unknowns`;
      navigator.clipboard.writeText(text.trim()).then(() => VarGen.showToast("Copied!")).catch(() => VarGen.showToast("Couldn't copy"));
    };
  },

  showHelp() {
    VarGen.$("#help-body").innerHTML = this.helpHTML;
    VarGen.$("#modal-help").classList.remove("hidden");
  },

  showGameStats() {
    VarGen.$("#stats-game-label").textContent = "Math Grid";
    const saved = VarGen.loadState(this.stateKey, VarGen.getDayIndex());
    VarGen.showStats(this.statsKey, saved?.gameOver, saved?.won ? saved.guessCount : null);
  },

  share() { this._shareHandler?.(); },
});
