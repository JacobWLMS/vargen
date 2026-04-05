// ── Memory Flash: memorize a pattern, then recreate it ──
// A 5x5 grid flashes a pattern briefly — recreate it from memory
VarGen.registerGame("memory", {
  name: "Memory Flash",
  icon: "🧠",
  iconBg: "#4a2d6f",
  desc: "Memorize the grid, rebuild it",
  tagline: "Remember the pattern. Prove it.",
  statsKey: "vargen-memory-stats",
  stateKey: "vargen-memory-state",

  helpHTML: `
    <h2>Memory Flash</h2>
    <p>A pattern of <strong>filled cells</strong> will flash on a 5x5 grid. <b>Memorize it</b>, then recreate it.</p>
    <ul>
      <li>The pattern shows for <b>3 seconds</b>, then disappears.</li>
      <li>Click cells to toggle them on/off.</li>
      <li>Press <b>Check</b> when ready — you get <b>3 attempts</b>.</li>
      <li>Score is based on how many cells you got right.</li>
    </ul>
    <div class="examples">
      <div class="example-row">
        <span class="tile-example correct" style="width:28px;height:28px;"></span>
        <span class="desc"><b>Green</b> — Correctly filled or correctly empty.</span>
      </div>
      <div class="example-row">
        <span class="tile-example" style="background:#8b2020;width:28px;height:28px;"></span>
        <span class="desc"><b>Red</b> — Wrong (should be filled/empty but isn't).</span>
      </div>
    </div>
    <p class="hint-text">Patterns are symmetric to help memory. Focus on the shape!</p>
    <p class="hint-text">A new pattern every day.</p>
  `,

  init() {
    const dayIndex = VarGen.getDayIndex();
    const rng = VarGen.mulberry32(dayIndex * 44449);
    const SIZE = 5;
    const MAX_ATTEMPTS = 3;
    const FLASH_TIME = 3000;

    // Generate a symmetric pattern (8-12 filled cells)
    // Use vertical symmetry for aesthetics
    const pattern = Array.from({ length: SIZE }, () => Array(SIZE).fill(false));
    const targetFilled = 8 + Math.floor(rng() * 5); // 8-12 cells
    let filled = 0;

    while (filled < targetFilled) {
      const r = Math.floor(rng() * SIZE);
      const c = Math.floor(rng() * Math.ceil(SIZE / 2));
      if (!pattern[r][c]) {
        pattern[r][c] = true;
        pattern[r][SIZE - 1 - c] = true; // Mirror
        filled += (c === SIZE - 1 - c) ? 1 : 2;
      }
    }

    let userGrid = Array.from({ length: SIZE }, () => Array(SIZE).fill(false));
    let showingPattern = false;
    let hasFlashed = false;
    let attempts = 0;
    let gameOver = false;
    let lastCheckResult = null;
    let score = 0;

    const container = VarGen.$("#game-container");

    function render() {
      container.innerHTML = "";

      // Grid
      const gridEl = document.createElement("div");
      gridEl.style.cssText = `display:grid;grid-template-columns:repeat(${SIZE},48px);gap:4px;margin-top:20px;justify-content:center;`;

      for (let r = 0; r < SIZE; r++) {
        for (let c = 0; c < SIZE; c++) {
          const cell = document.createElement("div");
          cell.style.cssText = "width:48px;height:48px;border-radius:6px;cursor:pointer;transition:all 0.15s;border:2px solid #3a3a3c;";

          if (showingPattern) {
            // Show target
            cell.style.background = pattern[r][c] ? "#7cc5ff" : "#1a1a1b";
            cell.style.borderColor = pattern[r][c] ? "#7cc5ff" : "#3a3a3c";
            cell.style.cursor = "default";
          } else if (lastCheckResult) {
            // Show check results
            const correct = userGrid[r][c] === pattern[r][c];
            if (correct) {
              cell.style.background = userGrid[r][c] ? "#538d4e" : "#1a1a1b";
              cell.style.borderColor = userGrid[r][c] ? "#538d4e" : "#2a3a2a";
            } else {
              cell.style.background = "#8b2020";
              cell.style.borderColor = "#8b2020";
            }
          } else if (gameOver) {
            // Show final state
            cell.style.background = pattern[r][c] ? "#538d4e" : "#1a1a1b";
            cell.style.borderColor = pattern[r][c] ? "#538d4e" : "#3a3a3c";
            cell.style.cursor = "default";
          } else {
            // User input mode
            cell.style.background = userGrid[r][c] ? "#7cc5ff" : "#2c2c2e";
            cell.style.borderColor = userGrid[r][c] ? "#7cc5ff" : "#3a3a3c";
            cell.addEventListener("click", () => {
              userGrid[r][c] = !userGrid[r][c];
              render();
            });
          }

          gridEl.appendChild(cell);
        }
      }
      container.appendChild(gridEl);

      // Status text
      const status = document.createElement("p");
      status.style.cssText = "margin-top:12px;font-size:0.85rem;color:#818384;text-align:center;";
      if (showingPattern) {
        status.textContent = "Memorize the pattern...";
        status.style.color = "#7cc5ff";
      } else if (!hasFlashed) {
        status.textContent = "Press Start to reveal the pattern";
      } else if (lastCheckResult && !gameOver) {
        status.textContent = `${lastCheckResult.correct}/${SIZE * SIZE} correct — ${MAX_ATTEMPTS - attempts} attempt${MAX_ATTEMPTS - attempts !== 1 ? "s" : ""} left`;
      } else if (gameOver) {
        status.textContent = score === SIZE * SIZE ? "Perfect!" : `Final score: ${score}/${SIZE * SIZE}`;
      } else {
        status.textContent = `Recreate the pattern (${MAX_ATTEMPTS - attempts} attempt${MAX_ATTEMPTS - attempts !== 1 ? "s" : ""} left)`;
      }
      container.appendChild(status);

      // Action buttons
      const bar = document.createElement("div");
      bar.className = "action-bar";
      bar.style.marginTop = "12px";

      if (!hasFlashed && !gameOver) {
        const startBtn = document.createElement("button");
        startBtn.className = "action-btn primary";
        startBtn.textContent = "Start";
        startBtn.addEventListener("click", flashPattern);
        bar.appendChild(startBtn);
      } else if (!showingPattern && !gameOver && hasFlashed) {
        const clearBtn = document.createElement("button");
        clearBtn.className = "action-btn secondary";
        clearBtn.textContent = "Clear";
        clearBtn.addEventListener("click", () => {
          userGrid = Array.from({ length: SIZE }, () => Array(SIZE).fill(false));
          lastCheckResult = null;
          render();
        });
        const checkBtn = document.createElement("button");
        checkBtn.className = "action-btn primary";
        checkBtn.textContent = "Check";
        checkBtn.addEventListener("click", checkGuess);
        bar.appendChild(clearBtn);
        bar.appendChild(checkBtn);
      }

      if (bar.children.length > 0) container.appendChild(bar);
    }

    function flashPattern() {
      showingPattern = true;
      hasFlashed = true;
      render();
      setTimeout(() => {
        showingPattern = false;
        render();
      }, FLASH_TIME);
    }

    function checkGuess() {
      if (gameOver) return;

      attempts++;
      let correct = 0;
      for (let r = 0; r < SIZE; r++) {
        for (let c = 0; c < SIZE; c++) {
          if (userGrid[r][c] === pattern[r][c]) correct++;
        }
      }

      lastCheckResult = { correct };
      score = correct;
      render();

      if (correct === SIZE * SIZE) {
        gameOver = true;
        setTimeout(() => {
          lastCheckResult = null;
          VarGen.showToast("Perfect memory!");
          VarGen.recordResult(this.statsKey, true, attempts);
          saveGameState(true);
          render();
          setTimeout(() => VarGen.showStats(this.statsKey, true, attempts), 1500);
        }, 1200);
      } else if (attempts >= MAX_ATTEMPTS) {
        gameOver = true;
        setTimeout(() => {
          lastCheckResult = null;
          VarGen.showToast(`${correct}/${SIZE * SIZE} correct`);
          VarGen.recordResult(this.statsKey, false, null);
          saveGameState(false);
          render();
          setTimeout(() => VarGen.showStats(this.statsKey, true, null), 1500);
        }, 1200);
      } else {
        // Clear check result after showing
        setTimeout(() => {
          lastCheckResult = null;
          render();
        }, 1500);
      }
    }
    checkGuess = checkGuess.bind(this);

    const saveGameState = (won) => {
      VarGen.saveState(this.stateKey, {
        dayIndex, attempts, gameOver, won, score,
        userGrid: userGrid.map((row) => [...row]),
      });
    };

    // Restore
    const saved = VarGen.loadState(this.stateKey, dayIndex);
    if (saved) {
      attempts = saved.attempts;
      gameOver = saved.gameOver;
      score = saved.score || 0;
      userGrid = saved.userGrid || Array.from({ length: SIZE }, () => Array(SIZE).fill(false));
      hasFlashed = true;
    }

    render();

    if (saved?.gameOver) {
      setTimeout(() => VarGen.showStats(this.statsKey, true, saved.won ? saved.attempts : null), 500);
    }

    VarGen.keydownHandler = (e) => {
      if (document.querySelector(".modal:not(.hidden)")) return;
      if (e.key === "Enter") {
        e.preventDefault();
        if (!hasFlashed && !gameOver) flashPattern();
        else if (hasFlashed && !showingPattern && !gameOver) checkGuess();
      }
    };

    this._shareHandler = () => {
      const won = gameOver && score === SIZE * SIZE;
      let text = `VarGen: Memory Flash #${dayIndex} ${won ? attempts : "X"}/3\n`;
      text += `Score: ${score}/${SIZE * SIZE}`;
      navigator.clipboard.writeText(text.trim()).then(() => VarGen.showToast("Copied!")).catch(() => VarGen.showToast("Couldn't copy"));
    };
  },

  showHelp() {
    VarGen.$("#help-body").innerHTML = this.helpHTML;
    VarGen.$("#modal-help").classList.remove("hidden");
  },

  showGameStats() {
    VarGen.$("#stats-game-label").textContent = "Memory Flash";
    const saved = VarGen.loadState(this.stateKey, VarGen.getDayIndex());
    VarGen.showStats(this.statsKey, saved?.gameOver, saved?.won ? saved.attempts : null);
  },

  share() { this._shareHandler?.(); },
});
