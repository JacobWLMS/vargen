// ── Router: handles game switching, hamburger menu, modal wiring ──
(() => {
  "use strict";
  const $ = VarGen.$;
  const $$ = VarGen.$$;

  const GAME_ORDER = ["pool", "cipher", "grid", "chain"];
  const LAST_GAME_KEY = "vargen-last-game";

  // ── Sidebar rendering ──
  function renderSidebar() {
    const container = $("#sidebar-games");
    container.innerHTML = "";
    GAME_ORDER.forEach((id) => {
      const game = VarGen.games[id];
      if (!game) return;
      const card = document.createElement("div");
      card.className = "game-card";
      card.dataset.game = id;
      if (VarGen.activeGame === id) card.classList.add("active");

      card.innerHTML = `
        <div class="game-card-icon" style="background:${game.iconBg}">${game.icon}</div>
        <div class="game-card-info">
          <div class="game-card-name">${game.name}</div>
          <div class="game-card-desc">${game.desc}</div>
        </div>
      `;

      // Check if today's puzzle was completed
      const stateKey = game.stateKey;
      const dayIndex = VarGen.getDayIndex();
      const saved = VarGen.loadState(stateKey, dayIndex);
      if (saved?.gameOver && saved?.won) {
        const badge = document.createElement("span");
        badge.className = "game-card-badge";
        badge.textContent = "Done";
        card.appendChild(badge);
      }

      card.addEventListener("click", () => switchGame(id));
      container.appendChild(card);
    });
  }

  // ── Menu open/close ──
  function openMenu() {
    $("#sidebar").classList.add("open");
    $("#menu-overlay").classList.remove("hidden");
    $("#menu-overlay").setAttribute("aria-hidden", "false");
    renderSidebar();
  }

  function closeMenu() {
    $("#sidebar").classList.remove("open");
    $("#menu-overlay").classList.add("hidden");
    $("#menu-overlay").setAttribute("aria-hidden", "true");
  }

  $("#btn-menu").addEventListener("click", openMenu);
  $("#menu-overlay").addEventListener("click", closeMenu);

  // ── Game switching ──
  function switchGame(id) {
    if (!VarGen.games[id]) return;
    closeMenu();

    // Remove old keyboard handler
    if (VarGen.keydownHandler) {
      document.removeEventListener("keydown", VarGen.keydownHandler);
      VarGen.keydownHandler = null;
    }

    VarGen.activeGame = id;
    localStorage.setItem(LAST_GAME_KEY, id);

    const game = VarGen.games[id];
    $("#header-title").textContent = game.name;
    $("#tagline").textContent = game.tagline;
    $("#game-container").innerHTML = "";

    // Init game
    game.init();

    // Attach new keyboard handler
    if (VarGen.keydownHandler) {
      document.addEventListener("keydown", VarGen.keydownHandler);
    }
  }

  // ── Modal wiring ──
  $$(".modal-close").forEach((btn) => {
    btn.addEventListener("click", () => btn.closest(".modal").classList.add("hidden"));
  });
  $$(".modal").forEach((modal) => {
    modal.addEventListener("click", (e) => { if (e.target === modal) modal.classList.add("hidden"); });
  });

  // Escape key closes modals and sidebar
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      $$(".modal:not(.hidden)").forEach((m) => m.classList.add("hidden"));
      closeMenu();
    }
  });

  $("#btn-help").addEventListener("click", () => {
    const game = VarGen.games[VarGen.activeGame];
    if (game) game.showHelp();
  });

  $("#btn-stats").addEventListener("click", () => {
    const game = VarGen.games[VarGen.activeGame];
    if (game) game.showGameStats();
  });

  $("#sidebar-stats-btn").addEventListener("click", () => {
    closeMenu();
    const game = VarGen.games[VarGen.activeGame];
    if (game) game.showGameStats();
  });

  // Share button
  $("#btn-share").addEventListener("click", () => {
    const game = VarGen.games[VarGen.activeGame];
    if (game?.share) game.share();
  });

  // ── Boot ──
  const lastGame = localStorage.getItem(LAST_GAME_KEY);
  const initialGame = (lastGame && VarGen.games[lastGame]) ? lastGame : "pool";
  switchGame(initialGame);

  // Show help on very first visit
  if (!localStorage.getItem("vargen-visited")) {
    setTimeout(() => {
      const game = VarGen.games[VarGen.activeGame];
      if (game) game.showHelp();
    }, 500);
    localStorage.setItem("vargen-visited", "1");
  }
})();
