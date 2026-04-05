(() => {
  "use strict";

  // ── Utility ──
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // ── Daily puzzle seed ──
  function getDayIndex() {
    const epoch = new Date(2025, 0, 1);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return Math.floor((today - epoch) / 86400000);
  }

  // Seeded PRNG (mulberry32)
  function mulberry32(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function shuffle(arr, rng) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  // ── Generate daily puzzle ──
  const dayIndex = getDayIndex();
  const rng = mulberry32(dayIndex * 31337);
  const answerWord = ANSWER_WORDS[dayIndex % ANSWER_WORDS.length];
  const answer = answerWord.toUpperCase().split("");

  // Build pool: the 5 correct letters + 3 decoy letters
  function pickDecoys() {
    const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    const answerSet = new Set(answer);
    const available = [...alphabet].filter((c) => !answerSet.has(c));
    const decoys = [];
    // Pick 3 random decoy letters
    const shuffled = shuffle(available, rng);
    for (let i = 0; i < 3 && i < shuffled.length; i++) {
      decoys.push(shuffled[i]);
    }
    return decoys;
  }

  const decoys = pickDecoys();
  const poolLetters = shuffle([...answer, ...decoys], rng);

  // ── Game state ──
  const MAX_GUESSES = 6;
  const WORD_LENGTH = 5;
  let currentRow = 0;
  let currentCol = 0;
  let currentGuess = Array(WORD_LENGTH).fill("");
  let guesses = [];
  let gameOver = false;
  let poolUsedIndices = new Set();

  // Track which pool letters have known states from guesses
  let poolStates = {}; // letter -> best state

  // ── Render ──
  function renderGrid() {
    const grid = $("#guess-grid");
    grid.innerHTML = "";
    for (let r = 0; r < MAX_GUESSES; r++) {
      const row = document.createElement("div");
      row.className = "guess-row";
      for (let c = 0; c < WORD_LENGTH; c++) {
        const tile = document.createElement("div");
        tile.className = "tile";
        if (r < guesses.length) {
          tile.textContent = guesses[r].letters[c];
          tile.classList.add(guesses[r].states[c]);
        } else if (r === currentRow) {
          tile.textContent = currentGuess[c];
          if (currentGuess[c]) tile.classList.add("filled");
          if (c === currentCol && !gameOver) tile.classList.add("cursor");
          tile.classList.add("active");
        }
        tile.dataset.row = r;
        tile.dataset.col = c;
        // Click to select position
        if (r === currentRow && !gameOver) {
          tile.addEventListener("click", () => selectCol(c));
        }
        row.appendChild(tile);
      }
      grid.appendChild(row);
    }
  }

  function renderPool() {
    const pool = $("#letter-pool");
    pool.innerHTML = "";
    poolLetters.forEach((letter, i) => {
      const tile = document.createElement("div");
      tile.className = "pool-tile";
      tile.textContent = letter;
      tile.dataset.index = i;

      // Apply pool coloring from past guesses
      const state = poolStates[letter];
      if (state === "correct") tile.classList.add("pool-correct");
      else if (state === "present") tile.classList.add("pool-present");
      else if (state === "absent") tile.classList.add("pool-absent");

      // Mark used in current guess
      if (poolUsedIndices.has(i)) tile.classList.add("used");

      if (!gameOver) {
        tile.addEventListener("click", () => poolTileClick(i));
      }

      pool.appendChild(tile);
    });
  }

  function selectCol(c) {
    currentCol = c;
    renderGrid();
  }

  function poolTileClick(index) {
    if (gameOver) return;
    if (poolUsedIndices.has(index)) return;

    // If current position already has a letter, un-use its pool index first
    if (currentGuess[currentCol]) {
      removeLetter(currentCol);
    }

    currentGuess[currentCol] = poolLetters[index];
    poolUsedIndices.add(index);

    // Track which pool index is at which guess position
    if (!currentGuess._poolMap) currentGuess._poolMap = {};
    currentGuess._poolMap[currentCol] = index;

    // Advance to next empty position
    let next = currentCol;
    for (let i = 1; i <= WORD_LENGTH; i++) {
      const c = (currentCol + i) % WORD_LENGTH;
      if (!currentGuess[c]) { next = c; break; }
    }
    currentCol = next;

    renderGrid();
    renderPool();
  }

  function removeLetter(col) {
    if (!currentGuess[col]) return;
    const poolIdx = currentGuess._poolMap?.[col];
    if (poolIdx !== undefined) {
      poolUsedIndices.delete(poolIdx);
      delete currentGuess._poolMap[col];
    }
    currentGuess[col] = "";
  }

  // ── Evaluate guess ──
  function evaluate(guess) {
    const states = Array(WORD_LENGTH).fill("absent");
    const answerCounts = {};
    answer.forEach((l) => (answerCounts[l] = (answerCounts[l] || 0) + 1));

    // First pass: correct
    for (let i = 0; i < WORD_LENGTH; i++) {
      if (guess[i] === answer[i]) {
        states[i] = "correct";
        answerCounts[guess[i]]--;
      }
    }
    // Second pass: present
    for (let i = 0; i < WORD_LENGTH; i++) {
      if (states[i] === "correct") continue;
      if (answerCounts[guess[i]] > 0) {
        states[i] = "present";
        answerCounts[guess[i]]--;
      }
    }
    return states;
  }

  function updatePoolStates(letters, states) {
    const priority = { correct: 3, present: 2, absent: 1 };
    for (let i = 0; i < letters.length; i++) {
      const l = letters[i];
      const s = states[i];
      const current = poolStates[l];
      if (!current || priority[s] > priority[current]) {
        poolStates[l] = s;
      }
    }
  }

  // ── Animations ──
  function revealRow(row, callback) {
    const tiles = $$(`[data-row="${row}"]`);
    tiles.forEach((tile, i) => {
      setTimeout(() => {
        tile.classList.add("reveal");
        // Apply color at midpoint of flip
        setTimeout(() => {
          tile.className = `tile ${guesses[row].states[i]}`;
        }, 250);
      }, i * 300);
    });
    // Callback after all animations
    setTimeout(callback, WORD_LENGTH * 300 + 300);
  }

  function bounceRow(row) {
    const tiles = $$(`[data-row="${row}"]`);
    tiles.forEach((tile, i) => {
      setTimeout(() => tile.classList.add("win-bounce"), i * 100);
    });
  }

  function shakeRow(row) {
    const rowEl = $$("#guess-grid .guess-row")[row];
    if (rowEl) {
      rowEl.classList.add("shake");
      setTimeout(() => rowEl.classList.remove("shake"), 500);
    }
  }

  // ── Submit ──
  function submitGuess() {
    if (gameOver) return;

    const guess = currentGuess.map((l) => l);
    if (guess.some((l) => !l)) {
      showToast("Fill all 5 letters");
      shakeRow(currentRow);
      return;
    }

    const word = guess.join("").toLowerCase();
    if (!VALID_WORDS.has(word)) {
      showToast("Not a valid word");
      shakeRow(currentRow);
      return;
    }

    const states = evaluate(guess);
    guesses.push({ letters: guess, states });
    updatePoolStates(guess, states);

    renderGrid();

    const row = currentRow;
    revealRow(row, () => {
      renderPool();

      const won = states.every((s) => s === "correct");
      if (won) {
        gameOver = true;
        bounceRow(row);
        const messages = ["Genius!", "Magnificent!", "Impressive!", "Splendid!", "Great!", "Phew!"];
        setTimeout(() => showToast(messages[row] || "Nice!"), 300);
        saveResult(true, row + 1);
        setTimeout(() => showStats(), 2000);
      } else if (guesses.length >= MAX_GUESSES) {
        gameOver = true;
        setTimeout(() => showToast(answerWord.toUpperCase(), 3000), 300);
        saveResult(false, null);
        setTimeout(() => showStats(), 2500);
      }

      if (!gameOver) {
        currentRow++;
        currentCol = 0;
        currentGuess = Array(WORD_LENGTH).fill("");
        currentGuess._poolMap = {};
        poolUsedIndices.clear();
        renderGrid();
        renderPool();
      }
    });
  }

  function clearGuess() {
    if (gameOver) return;
    currentGuess = Array(WORD_LENGTH).fill("");
    currentGuess._poolMap = {};
    poolUsedIndices.clear();
    currentCol = 0;
    renderGrid();
    renderPool();
  }

  // ── Keyboard support ──
  document.addEventListener("keydown", (e) => {
    if (gameOver) return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (document.querySelector(".modal:not(.hidden)")) return;

    const key = e.key;

    if (key === "Enter") {
      e.preventDefault();
      submitGuess();
      return;
    }
    if (key === "Backspace" || key === "Delete") {
      e.preventDefault();
      // Remove letter at current position, or the last filled position
      if (currentGuess[currentCol]) {
        removeLetter(currentCol);
      } else {
        // Find last filled
        for (let i = currentCol - 1; i >= 0; i--) {
          if (currentGuess[i]) {
            removeLetter(i);
            currentCol = i;
            break;
          }
        }
      }
      renderGrid();
      renderPool();
      return;
    }

    if (key === "ArrowLeft") {
      currentCol = Math.max(0, currentCol - 1);
      renderGrid();
      return;
    }
    if (key === "ArrowRight") {
      currentCol = Math.min(WORD_LENGTH - 1, currentCol + 1);
      renderGrid();
      return;
    }

    // Letter keys: find matching unused pool tile
    if (/^[a-zA-Z]$/.test(key)) {
      const letter = key.toUpperCase();
      const idx = poolLetters.findIndex(
        (l, i) => l === letter && !poolUsedIndices.has(i)
      );
      if (idx !== -1) {
        poolTileClick(idx);
      }
      return;
    }
  });

  // ── Toast ──
  function showToast(msg, duration = 1800) {
    const container = $("#toast-container");
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = msg;
    toast.style.animationDuration = `0.3s, 0.3s`;
    toast.style.animationDelay = `0s, ${duration / 1000}s`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), duration + 500);
  }

  // ── Stats / persistence ──
  const STORAGE_KEY = "vargen-stats";
  const STATE_KEY = "vargen-state";

  function loadStats() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || defaultStats();
    } catch {
      return defaultStats();
    }
  }

  function defaultStats() {
    return { played: 0, won: 0, streak: 0, maxStreak: 0, dist: [0, 0, 0, 0, 0, 0] };
  }

  function saveResult(won, numGuesses) {
    const stats = loadStats();
    stats.played++;
    if (won) {
      stats.won++;
      stats.streak++;
      stats.maxStreak = Math.max(stats.maxStreak, stats.streak);
      stats.dist[numGuesses - 1]++;
    } else {
      stats.streak = 0;
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stats));

    // Save game state
    const state = {
      dayIndex,
      guesses: guesses.map((g) => ({ letters: g.letters, states: g.states })),
      gameOver,
      won,
    };
    localStorage.setItem(STATE_KEY, JSON.stringify(state));
  }

  function loadState() {
    try {
      const state = JSON.parse(localStorage.getItem(STATE_KEY));
      if (state && state.dayIndex === dayIndex) {
        return state;
      }
    } catch {}
    return null;
  }

  function restoreState() {
    const state = loadState();
    if (!state) return;
    guesses = state.guesses;
    currentRow = guesses.length;
    gameOver = state.gameOver;

    // Rebuild pool states
    guesses.forEach((g) => updatePoolStates(g.letters, g.states));

    if (gameOver) {
      renderGrid();
      renderPool();
      if (state.won) {
        setTimeout(() => showStats(), 500);
      } else {
        setTimeout(() => {
          showToast(answerWord.toUpperCase(), 3000);
          setTimeout(() => showStats(), 1500);
        }, 300);
      }
    }
  }

  // ── Stats modal ──
  function showStats() {
    const stats = loadStats();
    $("#stat-played").textContent = stats.played;
    $("#stat-win-pct").textContent =
      stats.played ? Math.round((stats.won / stats.played) * 100) : 0;
    $("#stat-streak").textContent = stats.streak;
    $("#stat-max-streak").textContent = stats.maxStreak;

    const distEl = $("#distribution");
    distEl.innerHTML = "";
    const maxDist = Math.max(...stats.dist, 1);
    for (let i = 0; i < 6; i++) {
      const row = document.createElement("div");
      row.className = "dist-row";
      const num = document.createElement("span");
      num.className = "dist-num";
      num.textContent = i + 1;
      const bar = document.createElement("div");
      bar.className = "dist-bar";
      bar.style.width = `${Math.max(8, (stats.dist[i] / maxDist) * 100)}%`;
      bar.textContent = stats.dist[i];
      if (gameOver && guesses.length === i + 1 && guesses[i].states.every((s) => s === "correct")) {
        bar.classList.add("highlight");
      }
      row.appendChild(num);
      row.appendChild(bar);
      distEl.appendChild(row);
    }

    if (gameOver) {
      $("#share-section").classList.remove("hidden");
    }

    $("#modal-stats").classList.remove("hidden");
  }

  // ── Share ──
  function shareResults() {
    const emojiMap = { correct: "🟩", present: "🟨", absent: "⬛" };
    let text = `VarGen #${dayIndex} ${
      guesses[guesses.length - 1].states.every((s) => s === "correct")
        ? guesses.length
        : "X"
    }/6\n\n`;
    guesses.forEach((g) => {
      text += g.states.map((s) => emojiMap[s]).join("") + "\n";
    });
    text += "\nPlay at vargen.game";
    navigator.clipboard
      .writeText(text.trim())
      .then(() => showToast("Copied to clipboard!"))
      .catch(() => showToast("Couldn't copy"));
  }

  // ── Modal handling ──
  function openModal(id) {
    $(`#${id}`).classList.remove("hidden");
  }
  function closeModal(id) {
    $(`#${id}`).classList.add("hidden");
  }

  $$(".modal-close").forEach((btn) => {
    btn.addEventListener("click", () => {
      btn.closest(".modal").classList.add("hidden");
    });
  });

  $$(".modal").forEach((modal) => {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) modal.classList.add("hidden");
    });
  });

  $("#btn-help").addEventListener("click", () => openModal("modal-help"));
  $("#btn-stats").addEventListener("click", () => showStats());
  $("#btn-submit").addEventListener("click", submitGuess);
  $("#btn-clear").addEventListener("click", clearGuess);
  $("#btn-share").addEventListener("click", shareResults);

  // ── Init ──
  renderGrid();
  renderPool();
  restoreState();
  renderGrid();
  renderPool();

  // Show help on first visit
  if (!localStorage.getItem("vargen-visited")) {
    setTimeout(() => openModal("modal-help"), 500);
    localStorage.setItem("vargen-visited", "1");
  }
})();
