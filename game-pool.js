// ── Letter Pool: pick from 8 tiles (5 correct + 3 decoys) to find the word ──
VarGen.registerGame("pool", {
  name: "Letter Pool",
  icon: "🎱",
  iconBg: "#2d4a6f",
  desc: "Pick from 8 tiles — 3 are decoys",
  tagline: "Arrange the letters. Find the word.",
  statsKey: "vargen-pool-stats",
  stateKey: "vargen-pool-state",

  // Help content
  helpHTML: `
    <h2>Letter Pool</h2>
    <p>Find the hidden <strong>5-letter word</strong> in 6 guesses.</p>
    <ul>
      <li>You're given <b>8 letter tiles</b> — 5 are correct, 3 are decoys.</li>
      <li>Tap letters from the pool to build your guess.</li>
      <li>Each guess must be a <b>valid English word</b>.</li>
      <li>After each guess, tiles change color:</li>
    </ul>
    <div class="examples">
      <div class="example-row">
        <span class="tile-example correct">S</span>
        <span class="desc"><b>Green</b> — Correct letter, correct spot.</span>
      </div>
      <div class="example-row">
        <span class="tile-example present">A</span>
        <span class="desc"><b>Yellow</b> — Correct letter, wrong spot.</span>
      </div>
      <div class="example-row">
        <span class="tile-example absent">X</span>
        <span class="desc"><b>Gray</b> — Letter not in the word.</span>
      </div>
    </div>
    <p class="hint-text">The pool always contains the answer's letters plus 3 extras — use logic to eliminate!</p>
    <p class="hint-text">A new puzzle every day.</p>
  `,

  init() {
    const dayIndex = VarGen.getDayIndex();
    const rng = VarGen.mulberry32(dayIndex * 31337);
    const answerWord = ANSWER_WORDS[dayIndex % ANSWER_WORDS.length];
    const answer = answerWord.toUpperCase().split("");

    // Pick 3 decoy letters
    const answerSet = new Set(answer);
    const available = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").filter((c) => !answerSet.has(c));
    const shuffledAvail = VarGen.shuffle(available, rng);
    const decoys = shuffledAvail.slice(0, 3);
    const poolLetters = VarGen.shuffle([...answer, ...decoys], rng);

    const MAX_GUESSES = 6;
    const WORD_LENGTH = 5;
    let currentRow = 0;
    let currentCol = 0;
    let currentGuess = Array(WORD_LENGTH).fill("");
    let guesses = [];
    let gameOver = false;
    let poolUsedIndices = new Set();
    let poolStates = {};
    let poolMap = {};

    const container = VarGen.$("#game-container");

    function render() {
      container.innerHTML = "";

      // Pool
      const poolEl = document.createElement("div");
      poolEl.className = "letter-pool";
      poolLetters.forEach((letter, i) => {
        const tile = document.createElement("div");
        tile.className = "pool-tile";
        tile.textContent = letter;
        const state = poolStates[letter];
        if (state === "correct") tile.classList.add("pool-correct");
        else if (state === "present") tile.classList.add("pool-present");
        else if (state === "absent") tile.classList.add("pool-absent");
        if (poolUsedIndices.has(i)) tile.classList.add("used");
        if (!gameOver) tile.addEventListener("click", () => poolClick(i));
        poolEl.appendChild(tile);
      });
      container.appendChild(poolEl);

      // Grid
      const gridEl = document.createElement("div");
      gridEl.className = "guess-grid";
      for (let r = 0; r < MAX_GUESSES; r++) {
        const row = document.createElement("div");
        row.className = "guess-row";
        for (let c = 0; c < WORD_LENGTH; c++) {
          const tile = document.createElement("div");
          tile.className = "tile";
          tile.dataset.row = r;
          tile.dataset.col = c;
          if (r < guesses.length) {
            tile.textContent = guesses[r].letters[c];
            tile.classList.add(guesses[r].states[c]);
          } else if (r === currentRow && !gameOver) {
            tile.textContent = currentGuess[c];
            if (currentGuess[c]) tile.classList.add("filled");
            if (c === currentCol) tile.classList.add("cursor");
            tile.classList.add("active");
            tile.addEventListener("click", () => { currentCol = c; render(); });
          }
          row.appendChild(tile);
        }
        gridEl.appendChild(row);
      }
      container.appendChild(gridEl);

      // Action bar
      const bar = document.createElement("div");
      bar.className = "action-bar";
      const clearBtn = document.createElement("button");
      clearBtn.className = "action-btn secondary";
      clearBtn.textContent = "Clear";
      clearBtn.addEventListener("click", clearGuess);
      const submitBtn = document.createElement("button");
      submitBtn.className = "action-btn primary";
      submitBtn.textContent = "Submit";
      submitBtn.addEventListener("click", submitGuess);
      bar.appendChild(clearBtn);
      bar.appendChild(submitBtn);
      container.appendChild(bar);
    }

    function poolClick(index) {
      if (gameOver || poolUsedIndices.has(index)) return;
      if (currentGuess[currentCol]) removeLetter(currentCol);
      currentGuess[currentCol] = poolLetters[index];
      poolUsedIndices.add(index);
      poolMap[currentCol] = index;
      // Advance
      for (let i = 1; i <= WORD_LENGTH; i++) {
        const c = (currentCol + i) % WORD_LENGTH;
        if (!currentGuess[c]) { currentCol = c; break; }
      }
      render();
    }

    function removeLetter(col) {
      if (!currentGuess[col]) return;
      if (poolMap[col] !== undefined) {
        poolUsedIndices.delete(poolMap[col]);
        delete poolMap[col];
      }
      currentGuess[col] = "";
    }

    function evaluate(guess) {
      const states = Array(WORD_LENGTH).fill("absent");
      const counts = {};
      answer.forEach((l) => (counts[l] = (counts[l] || 0) + 1));
      for (let i = 0; i < WORD_LENGTH; i++) {
        if (guess[i] === answer[i]) { states[i] = "correct"; counts[guess[i]]--; }
      }
      for (let i = 0; i < WORD_LENGTH; i++) {
        if (states[i] !== "correct" && counts[guess[i]] > 0) {
          states[i] = "present"; counts[guess[i]]--;
        }
      }
      return states;
    }

    function updatePoolStates(letters, states) {
      const pri = { correct: 3, present: 2, absent: 1 };
      for (let i = 0; i < letters.length; i++) {
        const cur = poolStates[letters[i]];
        if (!cur || pri[states[i]] > pri[cur]) poolStates[letters[i]] = states[i];
      }
    }

    function submitGuess() {
      if (gameOver) return;
      const guess = [...currentGuess];
      if (guess.some((l) => !l)) { VarGen.showToast("Fill all 5 letters"); shakeCurrentRow(); return; }
      const word = guess.join("").toLowerCase();
      if (!VALID_WORDS.has(word)) { VarGen.showToast("Not a valid word"); shakeCurrentRow(); return; }

      const states = evaluate(guess);
      guesses.push({ letters: guess, states });
      updatePoolStates(guess, states);

      const row = currentRow;
      render();
      revealRow(row, () => {
        const won = states.every((s) => s === "correct");
        if (won) {
          gameOver = true;
          bounceRow(row);
          const msgs = ["Genius!", "Magnificent!", "Impressive!", "Splendid!", "Great!", "Phew!"];
          setTimeout(() => VarGen.showToast(msgs[row] || "Nice!"), 300);
          VarGen.recordResult(this.statsKey, true, row + 1);
          saveGameState(true);
          setTimeout(() => VarGen.showStats(this.statsKey, true, row + 1), 2000);
        } else if (guesses.length >= MAX_GUESSES) {
          gameOver = true;
          setTimeout(() => VarGen.showToast(answerWord.toUpperCase(), 3000), 300);
          VarGen.recordResult(this.statsKey, false, null);
          saveGameState(false);
          setTimeout(() => VarGen.showStats(this.statsKey, true, null), 2500);
        }
        if (!gameOver) {
          currentRow++;
          currentCol = 0;
          currentGuess = Array(WORD_LENGTH).fill("");
          poolMap = {};
          poolUsedIndices.clear();
          render();
        }
      });
    }
    submitGuess = submitGuess.bind(this);

    function clearGuess() {
      if (gameOver) return;
      currentGuess = Array(WORD_LENGTH).fill("");
      poolMap = {};
      poolUsedIndices.clear();
      currentCol = 0;
      render();
    }

    function revealRow(row, callback) {
      const tiles = container.querySelectorAll(`[data-row="${row}"]`);
      tiles.forEach((tile, i) => {
        setTimeout(() => {
          tile.classList.add("reveal");
          setTimeout(() => { tile.className = `tile ${guesses[row].states[i]}`; }, 250);
        }, i * 300);
      });
      setTimeout(callback, WORD_LENGTH * 300 + 300);
    }

    function bounceRow(row) {
      const tiles = container.querySelectorAll(`[data-row="${row}"]`);
      tiles.forEach((tile, i) => setTimeout(() => tile.classList.add("win-bounce"), i * 100));
    }

    function shakeCurrentRow() {
      const rows = container.querySelectorAll(".guess-row");
      if (rows[currentRow]) {
        rows[currentRow].classList.add("shake");
        setTimeout(() => rows[currentRow]?.classList.remove("shake"), 500);
      }
    }

    const saveGameState = (won) => {
      VarGen.saveState(this.stateKey, {
        dayIndex, guesses: guesses.map((g) => ({ letters: g.letters, states: g.states })),
        gameOver, won,
      });
    };

    // Restore state
    const saved = VarGen.loadState(this.stateKey, dayIndex);
    if (saved) {
      guesses = saved.guesses;
      currentRow = guesses.length;
      gameOver = saved.gameOver;
      guesses.forEach((g) => updatePoolStates(g.letters, g.states));
    }

    render();

    if (saved?.gameOver) {
      if (saved.won) {
        setTimeout(() => VarGen.showStats(this.statsKey, true, guesses.length), 500);
      } else {
        setTimeout(() => {
          VarGen.showToast(answerWord.toUpperCase(), 3000);
          setTimeout(() => VarGen.showStats(this.statsKey, true, null), 1500);
        }, 300);
      }
    }

    // Keyboard
    VarGen.keydownHandler = (e) => {
      if (gameOver || e.ctrlKey || e.metaKey || e.altKey) return;
      if (document.querySelector(".modal:not(.hidden)")) return;
      if (e.key === "Enter") { e.preventDefault(); submitGuess(); return; }
      if (e.key === "Backspace" || e.key === "Delete") {
        e.preventDefault();
        if (currentGuess[currentCol]) { removeLetter(currentCol); }
        else {
          for (let i = currentCol - 1; i >= 0; i--) {
            if (currentGuess[i]) { removeLetter(i); currentCol = i; break; }
          }
        }
        render();
        return;
      }
      if (e.key === "ArrowLeft") { currentCol = Math.max(0, currentCol - 1); render(); return; }
      if (e.key === "ArrowRight") { currentCol = Math.min(WORD_LENGTH - 1, currentCol + 1); render(); return; }
      if (/^[a-zA-Z]$/.test(e.key)) {
        const letter = e.key.toUpperCase();
        const idx = poolLetters.findIndex((l, i) => l === letter && !poolUsedIndices.has(i));
        if (idx !== -1) poolClick(idx);
      }
    };

    // Share handler
    this._shareHandler = () => {
      const emojiMap = { correct: "🟩", present: "🟨", absent: "⬛" };
      const won = guesses.length > 0 && guesses[guesses.length - 1].states.every((s) => s === "correct");
      let text = `VarGen: Letter Pool #${dayIndex} ${won ? guesses.length : "X"}/6\n\n`;
      guesses.forEach((g) => { text += g.states.map((s) => emojiMap[s]).join("") + "\n"; });
      navigator.clipboard.writeText(text.trim()).then(() => VarGen.showToast("Copied!")).catch(() => VarGen.showToast("Couldn't copy"));
    };
  },

  showHelp() {
    VarGen.$("#help-body").innerHTML = this.helpHTML;
    VarGen.$("#modal-help").classList.remove("hidden");
  },

  showGameStats() {
    VarGen.$("#stats-game-label").textContent = "Letter Pool";
    const saved = VarGen.loadState(this.stateKey, VarGen.getDayIndex());
    const won = saved?.won;
    const numGuesses = saved?.guesses?.length;
    VarGen.showStats(this.statsKey, saved?.gameOver, won ? numGuesses : null);
  },

  share() { this._shareHandler?.(); },
});
