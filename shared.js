// ── Shared utilities across all VarGen games ──
const VarGen = {};

VarGen.$ = (sel) => document.querySelector(sel);
VarGen.$$ = (sel) => document.querySelectorAll(sel);

// Day index from epoch
VarGen.getDayIndex = function () {
  const epoch = new Date(2025, 0, 1);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.floor((today - epoch) / 86400000);
};

// Seeded PRNG (mulberry32)
VarGen.mulberry32 = function (seed) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};

VarGen.shuffle = function (arr, rng) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};

VarGen.showToast = function (msg, duration = 1800) {
  const container = VarGen.$("#toast-container");
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = msg;
  toast.style.animationDuration = "0.3s, 0.3s";
  toast.style.animationDelay = `0s, ${duration / 1000}s`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), duration + 500);
};

// Stats helpers (each game has its own storage key)
VarGen.defaultStats = function () {
  return { played: 0, won: 0, streak: 0, maxStreak: 0, dist: [0, 0, 0, 0, 0, 0] };
};

VarGen.loadStats = function (key) {
  try {
    return JSON.parse(localStorage.getItem(key)) || VarGen.defaultStats();
  } catch {
    return VarGen.defaultStats();
  }
};

VarGen.saveStats = function (key, stats) {
  localStorage.setItem(key, JSON.stringify(stats));
};

VarGen.loadState = function (key, dayIndex) {
  try {
    const state = JSON.parse(localStorage.getItem(key));
    if (state && state.dayIndex === dayIndex) return state;
  } catch {}
  return null;
};

VarGen.saveState = function (key, state) {
  localStorage.setItem(key, JSON.stringify(state));
};

VarGen.showStats = function (statsKey, gameOver, winRow) {
  const stats = VarGen.loadStats(statsKey);
  VarGen.$("#stat-played").textContent = stats.played;
  VarGen.$("#stat-win-pct").textContent =
    stats.played ? Math.round((stats.won / stats.played) * 100) : 0;
  VarGen.$("#stat-streak").textContent = stats.streak;
  VarGen.$("#stat-max-streak").textContent = stats.maxStreak;

  const distEl = VarGen.$("#distribution");
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
    if (gameOver && winRow === i + 1) {
      bar.classList.add("highlight");
    }
    row.appendChild(num);
    row.appendChild(bar);
    distEl.appendChild(row);
  }

  if (gameOver) {
    VarGen.$("#share-section").classList.remove("hidden");
  } else {
    VarGen.$("#share-section").classList.add("hidden");
  }

  VarGen.$("#modal-stats").classList.remove("hidden");
};

VarGen.recordResult = function (statsKey, won, numGuesses) {
  const stats = VarGen.loadStats(statsKey);
  stats.played++;
  if (won) {
    stats.won++;
    stats.streak++;
    stats.maxStreak = Math.max(stats.maxStreak, stats.streak);
    if (numGuesses >= 1 && numGuesses <= 6) stats.dist[numGuesses - 1]++;
  } else {
    stats.streak = 0;
  }
  VarGen.saveStats(statsKey, stats);
};

// Registry for games
VarGen.games = {};
VarGen.activeGame = null;
VarGen.keydownHandler = null;

VarGen.registerGame = function (id, game) {
  VarGen.games[id] = game;
};
