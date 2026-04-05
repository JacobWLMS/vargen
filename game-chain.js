// ── Word Chain: morph start word into end word one letter at a time ──
// Uses runtime BFS to generate chains — supports unlimited daily puzzles
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

  // Build word graph once (lazy, cached)
  _graph: null,
  _wordList: null,

  _buildGraph() {
    if (this._graph) return;

    // Collect all 5-letter words
    const words = [...VALID_WORDS].filter((w) => w.length === 5);
    this._wordList = words;

    // Build adjacency using wildcard patterns for O(n) neighbor lookup
    // e.g. "crane" -> ["_rane", "c_ane", "cr_ne", "cra_e", "cran_"]
    const buckets = {};
    for (const word of words) {
      for (let i = 0; i < 5; i++) {
        const pattern = word.slice(0, i) + "_" + word.slice(i + 1);
        if (!buckets[pattern]) buckets[pattern] = [];
        buckets[pattern].push(word);
      }
    }

    // Build adjacency list
    const graph = {};
    for (const word of words) {
      graph[word] = new Set();
    }
    for (const bucket of Object.values(buckets)) {
      for (let i = 0; i < bucket.length; i++) {
        for (let j = i + 1; j < bucket.length; j++) {
          graph[bucket[i]].add(bucket[j]);
          graph[bucket[j]].add(bucket[i]);
        }
      }
    }

    this._graph = graph;
  },

  // BFS to find shortest path between two words
  _bfs(start, end) {
    if (!this._graph[start] || !this._graph[end]) return null;
    if (start === end) return [start];

    const visited = new Set([start]);
    const queue = [[start]];

    while (queue.length > 0) {
      const path = queue.shift();
      const current = path[path.length - 1];

      for (const neighbor of this._graph[current]) {
        if (visited.has(neighbor)) continue;
        const newPath = [...path, neighbor];
        if (neighbor === end) return newPath;
        if (newPath.length > 6) continue; // Cap at 6 to avoid long searches
        visited.add(neighbor);
        queue.push(newPath);
      }
    }
    return null;
  },

  // Generate a daily chain using seeded RNG + BFS
  _generateChain(rng) {
    this._buildGraph();

    // Pick start words from ANSWER_WORDS (more interesting/common)
    const candidates = ANSWER_WORDS.filter(
      (w) => w.length === 5 && this._graph[w] && this._graph[w].size >= 3
    );

    // Try random pairs until we find one with a path of length 4-5 (3-4 steps)
    for (let attempt = 0; attempt < 200; attempt++) {
      const startIdx = Math.floor(rng() * candidates.length);
      const endIdx = Math.floor(rng() * candidates.length);
      if (startIdx === endIdx) continue;

      const start = candidates[startIdx];
      const end = candidates[endIdx];
      const path = this._bfs(start, end);

      if (path && path.length >= 4 && path.length <= 5) {
        return path;
      }
    }

    // Fallback: find any working pair with a 4-step path
    for (let attempt = 0; attempt < 100; attempt++) {
      const start = candidates[Math.floor(rng() * candidates.length)];
      // Pick a random neighbor chain via BFS with depth limit
      const visited = new Set([start]);
      let current = start;
      const path = [start];
      for (let step = 0; step < 4; step++) {
        const neighbors = [...this._graph[current]].filter((n) => !visited.has(n));
        if (neighbors.length === 0) break;
        current = neighbors[Math.floor(rng() * neighbors.length)];
        visited.add(current);
        path.push(current);
      }
      if (path.length === 5) return path;
    }

    // Ultimate fallback
    return ["crane", "crate", "grate", "grape", "drape"];
  },

  init() {
    const dayIndex = VarGen.getDayIndex();
    const rng = VarGen.mulberry32(dayIndex * 99991);

    // Generate today's chain
    const chain = this._generateChain(rng);
    const startWord = chain[0].toUpperCase();
    const endWord = chain[chain.length - 1].toUpperCase();
    const STEPS = chain.length - 1;
    const WORD_LENGTH = 5;

    let currentStep = 0;
    let currentCol = 0;
    let currentGuess = Array(WORD_LENGTH).fill("");
    let submittedSteps = [];
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

      // Target word
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
