// ── Cipher Shift: the word is Caesar-shifted, decode it ──
// A unique twist: you see the encrypted word and must figure out the shift + the word
VarGen.registerGame("cipher", {
  name: "Cipher Shift",
  icon: "🔐",
  iconBg: "#5a2d6f",
  desc: "Crack the Caesar cipher",
  tagline: "Decode the shifted word.",
  statsKey: "vargen-cipher-stats",
  stateKey: "vargen-cipher-state",

  helpHTML: `
    <h2>Cipher Shift</h2>
    <p>A 5-letter word has been <strong>encrypted</strong> with a Caesar cipher (every letter shifted by the same amount).</p>
    <ul>
      <li>You see the <b>encrypted</b> word at the top.</li>
      <li>Type your guess for the <b>original</b> word.</li>
      <li>Each guess must be a valid English word.</li>
      <li>Feedback shows how close each letter is:</li>
    </ul>
    <div class="examples">
      <div class="example-row">
        <span class="tile-example correct">R</span>
        <span class="desc"><b>Green</b> — Correct letter, correct spot.</span>
      </div>
      <div class="example-row">
        <span class="tile-example present">E</span>
        <span class="desc"><b>Yellow</b> — Correct letter, wrong spot.</span>
      </div>
      <div class="example-row">
        <span class="tile-example absent">Z</span>
        <span class="desc"><b>Gray</b> — Letter not in the word.</span>
      </div>
    </div>
    <p class="hint-text">Tip: If you figure out one letter's shift, you know ALL the shifts! They're all the same amount.</p>
    <p class="hint-text">A new cipher every day.</p>
  `,

  init() {
    const dayIndex = VarGen.getDayIndex();
    const rng = VarGen.mulberry32(dayIndex * 77773);
    const answerWord = ANSWER_WORDS[(dayIndex * 7 + 3) % ANSWER_WORDS.length];
    const answer = answerWord.toUpperCase().split("");

    // Pick a shift 1-25
    const shift = Math.floor(rng() * 25) + 1;
    const cipherText = answer.map((c) => {
      const code = ((c.charCodeAt(0) - 65 + shift) % 26) + 65;
      return String.fromCharCode(code);
    }).join("");

    const MAX_GUESSES = 6;
    const WORD_LENGTH = 5;
    let currentRow = 0;
    let currentCol = 0;
    let currentGuess = Array(WORD_LENGTH).fill("");
    let guesses = [];
    let gameOver = false;

    const container = VarGen.$("#game-container");

    function render() {
      container.innerHTML = "";

      // Cipher display
      const cipherEl = document.createElement("div");
      cipherEl.className = "cipher-display";
      cipherEl.innerHTML = `
        <div class="cipher-hint">Encrypted word (shift = ?)</div>
        <div class="cipher-text">${cipherText}</div>
        <div class="cipher-arrow">↓</div>
        <div class="cipher-hint">Decode it below</div>
      `;
      container.appendChild(cipherEl);

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

    function submitGuess() {
      if (gameOver) return;
      const guess = [...currentGuess];
      if (guess.some((l) => !l)) { VarGen.showToast("Fill all 5 letters"); shakeCurrentRow(); return; }
      const word = guess.join("").toLowerCase();
      if (!VALID_WORDS.has(word)) { VarGen.showToast("Not a valid word"); shakeCurrentRow(); return; }

      const states = evaluate(guess);
      guesses.push({ letters: guess, states });

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
          setTimeout(() => VarGen.showToast(`${answerWord.toUpperCase()} (shift ${shift})`, 3000), 300);
          VarGen.recordResult(this.statsKey, false, null);
          saveGameState(false);
          setTimeout(() => VarGen.showStats(this.statsKey, true, null), 2500);
        }
        if (!gameOver) {
          currentRow++;
          currentCol = 0;
          currentGuess = Array(WORD_LENGTH).fill("");
          render();
        }
      });
    }
    submitGuess = submitGuess.bind(this);

    function clearGuess() {
      if (gameOver) return;
      currentGuess = Array(WORD_LENGTH).fill("");
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

    // Restore
    const saved = VarGen.loadState(this.stateKey, dayIndex);
    if (saved) {
      guesses = saved.guesses;
      currentRow = guesses.length;
      gameOver = saved.gameOver;
    }

    render();

    if (saved?.gameOver) {
      if (saved.won) {
        setTimeout(() => VarGen.showStats(this.statsKey, true, guesses.length), 500);
      } else {
        setTimeout(() => {
          VarGen.showToast(`${answerWord.toUpperCase()} (shift ${shift})`, 3000);
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
      const emojiMap = { correct: "🟩", present: "🟨", absent: "⬛" };
      const won = guesses.length > 0 && guesses[guesses.length - 1].states.every((s) => s === "correct");
      let text = `VarGen: Cipher Shift #${dayIndex} ${won ? guesses.length : "X"}/6\n\n`;
      guesses.forEach((g) => { text += g.states.map((s) => emojiMap[s]).join("") + "\n"; });
      navigator.clipboard.writeText(text.trim()).then(() => VarGen.showToast("Copied!")).catch(() => VarGen.showToast("Couldn't copy"));
    };
  },

  showHelp() {
    VarGen.$("#help-body").innerHTML = this.helpHTML;
    VarGen.$("#modal-help").classList.remove("hidden");
  },

  showGameStats() {
    VarGen.$("#stats-game-label").textContent = "Cipher Shift";
    const saved = VarGen.loadState(this.stateKey, VarGen.getDayIndex());
    VarGen.showStats(this.statsKey, saved?.gameOver, saved?.won ? saved.guesses.length : null);
  },

  share() { this._shareHandler?.(); },
});
