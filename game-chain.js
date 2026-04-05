// ── Word Chain: morph start word into end word one letter at a time ──
// Pre-computed valid chains ensure every puzzle is solvable
VarGen.registerGame("chain", {
  name: "Word Chain",
  icon: "🔗",
  iconBg: "#2d6f5a",
  desc: "Morph one word into another",
  tagline: "Change one letter at a time.",
  statsKey: "vargen-chain-stats",
  stateKey: "vargen-chain-state",

  helpHTML: `
    <h2>Word Chain</h2>
    <p>Transform the <b style="color:#7cc5ff">start word</b> into the <b style="color:#ffd866">target word</b> by changing <strong>one letter at a time</strong>.</p>
    <ul>
      <li>Each step must be a <b>valid English word</b>.</li>
      <li>You can only change <b>one letter</b> per step.</li>
      <li>You get a set number of steps — use them wisely!</li>
      <li>Feedback shows how your guess relates to the <b>target</b>:</li>
    </ul>
    <div class="examples">
      <div class="example-row">
        <span class="tile-example correct">A</span>
        <span class="desc"><b>Green</b> — This letter matches the target word's letter in the same position.</span>
      </div>
      <div class="example-row">
        <span class="tile-example present">R</span>
        <span class="desc"><b>Yellow</b> — This letter is in the target but in a different position.</span>
      </div>
      <div class="example-row">
        <span class="tile-example absent">X</span>
        <span class="desc"><b>Gray</b> — This letter is not in the target word.</span>
      </div>
    </div>
    <p class="hint-text">Each step must differ from the previous word by exactly one letter. The chain is always solvable!</p>
    <p class="hint-text">A new chain every day.</p>
  `,

  // Pre-defined chains (start -> steps -> end), all verified as valid words
  // Each chain has length 4 (start + 3 intermediate + end = 5 words, 4 steps)
  chains: [
    ["crane", "crate", "grate", "grape", "drape"],
    ["brave", "grave", "grape", "gripe", "grime"],
    ["globe", "glove", "grove", "grave", "brave"],
    ["glaze", "graze", "grace", "trace", "truce"],
    ["grain", "groin", "grown", "growl", "prowl"],
    ["drove", "grove", "grave", "graze", "glaze"],
    ["blaze", "glaze", "graze", "grace", "trace"],
    ["crisp", "crimp", "crime", "grime", "gripe"],
    ["brine", "brink", "blink", "blank", "plank"],
    ["flint", "faint", "paint", "point", "joint"],
    ["drape", "grape", "grope", "grove", "drove"],
    ["prime", "grime", "gripe", "grape", "grace"],
    ["irate", "grate", "graze", "glaze", "blaze"],
    ["scout", "shout", "short", "shore", "store"],
    ["cider", "rider", "river", "rover", "hover"],
    ["snare", "spare", "space", "spice", "spine"],
    ["shawl", "shall", "stall", "stale", "stare"],
    ["truce", "trace", "grace", "grate", "irate"],
    ["stave", "stale", "stall", "shall", "shawl"],
    ["blink", "brink", "brine", "bride", "pride"],
    ["trace", "grace", "grave", "crave", "crane"],
    ["pride", "prime", "crime", "crimp", "crisp"],
    ["clasp", "class", "glass", "gloss", "floss"],
    ["whale", "whole", "whose", "chose", "close"],
    ["joker", "poker", "power", "lower", "lover"],
    ["trick", "brick", "brink", "blink", "blank"],
    ["hitch", "pitch", "patch", "match", "march"],
    ["rover", "lover", "lower", "tower", "towel"],
    ["plank", "blank", "blink", "brink", "bring"],
    ["hover", "lover", "lower", "power", "poker"],
    ["moose", "mouse", "house", "horse", "worse"],
    ["leapt", "least", "lease", "leave", "heave"],
    ["token", "woken", "women", "woman", "roman"],
    ["marsh", "march", "match", "watch", "witch"],
    ["joint", "point", "paint", "faint", "feint"],
    ["rouse", "house", "horse", "worse", "worst"],
    ["patch", "match", "march", "marsh", "harsh"],
    ["feast", "least", "lease", "leave", "weave"],
    ["route", "rouse", "mouse", "moose", "loose"],
    ["plant", "plank", "blank", "bland", "blend"],
  ],

  init() {
    const dayIndex = VarGen.getDayIndex();
    const rng = VarGen.mulberry32(dayIndex * 99991);

    // Pick today's chain
    const chainIdx = dayIndex % this.chains.length;
    const chain = this.chains[chainIdx];
    const startWord = chain[0].toUpperCase();
    const endWord = chain[chain.length - 1].toUpperCase();
    const STEPS = chain.length - 1; // number of steps needed
    const WORD_LENGTH = 5;

    let currentStep = 0;
    let currentCol = 0;
    let currentGuess = Array(WORD_LENGTH).fill("");
    let submittedSteps = []; // { letters, states }
    let gameOver = false;
    let lastWord = startWord;

    const container = VarGen.$("#game-container");

    function render() {
      container.innerHTML = "";

      // Endpoints display
      const endpoints = document.createElement("div");
      endpoints.className = "chain-endpoints";
      endpoints.innerHTML = `
        <span class="chain-word start">${startWord}</span>
        <div class="chain-arrow">
          <span>${STEPS} steps</span>
          <svg viewBox="0 0 32 16"><path d="M0 8h28l-6-6M28 8l-6 6" stroke="currentColor" stroke-width="2" fill="none"/></svg>
        </div>
        <span class="chain-word end">${endWord}</span>
      `;
      container.appendChild(endpoints);

      // Steps grid
      const gridEl = document.createElement("div");
      gridEl.className = "guess-grid";

      // Show start word (fixed)
      const startRow = document.createElement("div");
      startRow.className = "guess-row";
      for (let c = 0; c < WORD_LENGTH; c++) {
        const tile = document.createElement("div");
        tile.className = "tile";
        tile.textContent = startWord[c];
        tile.style.background = "#1e3a5f";
        tile.style.borderColor = "#1e3a5f";
        startRow.appendChild(tile);
      }
      gridEl.appendChild(startRow);

      // Submitted steps
      for (let r = 0; r < submittedSteps.length; r++) {
        const row = document.createElement("div");
        row.className = "guess-row";
        for (let c = 0; c < WORD_LENGTH; c++) {
          const tile = document.createElement("div");
          tile.className = "tile";
          tile.dataset.row = r;
          tile.dataset.col = c;
          tile.textContent = submittedSteps[r].letters[c];
          tile.classList.add(submittedSteps[r].states[c]);
          row.appendChild(tile);
        }
        gridEl.appendChild(row);
      }

      // Current input row
      if (!gameOver && currentStep < STEPS) {
        const row = document.createElement("div");
        row.className = "guess-row";
        for (let c = 0; c < WORD_LENGTH; c++) {
          const tile = document.createElement("div");
          tile.className = "tile active";
          tile.dataset.row = submittedSteps.length;
          tile.dataset.col = c;
          tile.textContent = currentGuess[c];
          if (currentGuess[c]) tile.classList.add("filled");
          if (c === currentCol) tile.classList.add("cursor");
          tile.addEventListener("click", () => { currentCol = c; render(); });
          row.appendChild(tile);
        }
        gridEl.appendChild(row);
      }

      // Empty future rows
      const remainingRows = STEPS - submittedSteps.length - (gameOver ? 0 : 1);
      for (let r = 0; r < remainingRows; r++) {
        const row = document.createElement("div");
        row.className = "guess-row";
        for (let c = 0; c < WORD_LENGTH; c++) {
          const tile = document.createElement("div");
          tile.className = "tile";
          row.appendChild(tile);
        }
        gridEl.appendChild(row);
      }

      // Target word (shown dimmed if not reached)
      const endRow = document.createElement("div");
      endRow.className = "guess-row";
      for (let c = 0; c < WORD_LENGTH; c++) {
        const tile = document.createElement("div");
        tile.className = "tile";
        tile.textContent = endWord[c];
        if (gameOver && submittedSteps.length > 0 &&
            submittedSteps[submittedSteps.length - 1].letters.join("") === endWord) {
          tile.style.background = "#538d4e";
          tile.style.borderColor = "#538d4e";
        } else {
          tile.style.background = "#3a3520";
          tile.style.borderColor = "#3a3520";
        }
        endRow.appendChild(tile);
      }
      gridEl.appendChild(endRow);

      container.appendChild(gridEl);

      // Action bar
      if (!gameOver) {
        const bar = document.createElement("div");
        bar.className = "action-bar";
        const clearBtn = document.createElement("button");
        clearBtn.className = "action-btn secondary";
        clearBtn.textContent = "Clear";
        clearBtn.addEventListener("click", clearGuess);
        const submitBtn = document.createElement("button");
        submitBtn.className = "action-btn primary";
        submitBtn.textContent = "Submit";
        submitBtn.addEventListener("click", submitStep);
        bar.appendChild(clearBtn);
        bar.appendChild(submitBtn);
        container.appendChild(bar);
      }
    }

    function evaluateVsTarget(guess) {
      const target = endWord.split("");
      const states = Array(WORD_LENGTH).fill("absent");
      const counts = {};
      target.forEach((l) => (counts[l] = (counts[l] || 0) + 1));
      for (let i = 0; i < WORD_LENGTH; i++) {
        if (guess[i] === target[i]) { states[i] = "correct"; counts[guess[i]]--; }
      }
      for (let i = 0; i < WORD_LENGTH; i++) {
        if (states[i] !== "correct" && counts[guess[i]] > 0) {
          states[i] = "present"; counts[guess[i]]--;
        }
      }
      return states;
    }

    function submitStep() {
      if (gameOver) return;
      const guess = [...currentGuess];
      if (guess.some((l) => !l)) { VarGen.showToast("Fill all letters"); shakeCurrentRow(); return; }

      const word = guess.join("").toLowerCase();
      if (!VALID_WORDS.has(word)) { VarGen.showToast("Not a valid word"); shakeCurrentRow(); return; }

      // Must differ by exactly 1 letter from last word
      const prev = lastWord.split("");
      let diffs = 0;
      for (let i = 0; i < WORD_LENGTH; i++) {
        if (guess[i] !== prev[i]) diffs++;
      }
      if (diffs !== 1) {
        VarGen.showToast("Change exactly 1 letter");
        shakeCurrentRow();
        return;
      }

      const states = evaluateVsTarget(guess);
      submittedSteps.push({ letters: guess, states });
      lastWord = guess.join("");
      currentStep++;

      render();
      const row = submittedSteps.length - 1;
      revealRow(row, () => {
        const reachedTarget = guess.join("") === endWord;
        if (reachedTarget) {
          gameOver = true;
          VarGen.showToast("Solved!");
          VarGen.recordResult(this.statsKey, true, submittedSteps.length);
          saveGameState(true);
          render();
          setTimeout(() => VarGen.showStats(this.statsKey, true, submittedSteps.length), 1500);
        } else if (currentStep >= STEPS) {
          gameOver = true;
          VarGen.showToast("Out of steps!");
          VarGen.recordResult(this.statsKey, false, null);
          saveGameState(false);
          render();
          setTimeout(() => VarGen.showStats(this.statsKey, true, null), 1500);
        } else {
          currentCol = 0;
          currentGuess = Array(WORD_LENGTH).fill("");
          render();
        }
      });
    }
    submitStep = submitStep.bind(this);

    function clearGuess() {
      if (gameOver) return;
      currentGuess = Array(WORD_LENGTH).fill("");
      currentCol = 0;
      render();
    }

    function revealRow(stepIdx, callback) {
      const tiles = container.querySelectorAll(`[data-row="${stepIdx}"]`);
      tiles.forEach((tile, i) => {
        setTimeout(() => {
          tile.classList.add("reveal");
          setTimeout(() => { tile.className = `tile ${submittedSteps[stepIdx].states[i]}`; }, 250);
        }, i * 200);
      });
      setTimeout(callback, WORD_LENGTH * 200 + 300);
    }

    function shakeCurrentRow() {
      const rows = container.querySelectorAll(".guess-row");
      // Current input row = submittedSteps.length + 1 (for start row)
      const rowEl = rows[submittedSteps.length + 1];
      if (rowEl) {
        rowEl.classList.add("shake");
        setTimeout(() => rowEl?.classList.remove("shake"), 500);
      }
    }

    const saveGameState = (won) => {
      VarGen.saveState(this.stateKey, {
        dayIndex,
        submittedSteps: submittedSteps.map((s) => ({ letters: s.letters, states: s.states })),
        lastWord, currentStep, gameOver, won,
      });
    };

    // Restore
    const saved = VarGen.loadState(this.stateKey, dayIndex);
    if (saved) {
      submittedSteps = saved.submittedSteps;
      lastWord = saved.lastWord;
      currentStep = saved.currentStep;
      gameOver = saved.gameOver;
    }

    render();

    if (saved?.gameOver) {
      if (saved.won) {
        setTimeout(() => VarGen.showStats(this.statsKey, true, submittedSteps.length), 500);
      } else {
        setTimeout(() => VarGen.showStats(this.statsKey, true, null), 500);
      }
    }

    // Keyboard
    VarGen.keydownHandler = (e) => {
      if (gameOver || e.ctrlKey || e.metaKey || e.altKey) return;
      if (document.querySelector(".modal:not(.hidden)")) return;
      if (e.key === "Enter") { e.preventDefault(); submitStep(); return; }
      if (e.key === "Backspace" || e.key === "Delete") {
        e.preventDefault();
        if (currentGuess[currentCol]) { currentGuess[currentCol] = ""; }
        else if (currentCol > 0) { currentCol--; currentGuess[currentCol] = ""; }
        render();
        return;
      }
      if (e.key === "ArrowLeft") { currentCol = Math.max(0, currentCol - 1); render(); return; }
      if (e.key === "ArrowRight") { currentCol = Math.min(WORD_LENGTH - 1, currentCol + 1); render(); return; }
      if (/^[a-zA-Z]$/.test(e.key)) {
        currentGuess[currentCol] = e.key.toUpperCase();
        if (currentCol < WORD_LENGTH - 1) currentCol++;
        render();
      }
    };

    this._shareHandler = () => {
      const saved2 = VarGen.loadState(this.stateKey, dayIndex);
      const won = saved2?.won;
      const emojiMap = { correct: "🟩", present: "🟨", absent: "⬛" };
      let text = `VarGen: Word Chain #${dayIndex} ${won ? submittedSteps.length : "X"}/${STEPS}\n`;
      text += `${startWord} → ${endWord}\n\n`;
      submittedSteps.forEach((s) => { text += s.states.map((st) => emojiMap[st]).join("") + "\n"; });
      navigator.clipboard.writeText(text.trim()).then(() => VarGen.showToast("Copied!")).catch(() => VarGen.showToast("Couldn't copy"));
    };
  },

  showHelp() {
    VarGen.$("#help-body").innerHTML = this.helpHTML;
    VarGen.$("#modal-help").classList.remove("hidden");
  },

  showGameStats() {
    VarGen.$("#stats-game-label").textContent = "Word Chain";
    const saved = VarGen.loadState(this.stateKey, VarGen.getDayIndex());
    VarGen.showStats(this.statsKey, saved?.gameOver, saved?.won ? saved.submittedSteps.length : null);
  },

  share() { this._shareHandler?.(); },
});
