// The player (spec 8.8; D51; 15.10 ruling 29). The browser's own controls
// give play, pause, the bar and the time. This script adds the presses: a
// line plays from its start to its end and stops, and is marked while it
// plays; a warning plays its stretch and stops at its end; the alarm's press
// and a press on the loudness strip play on. The strip is drawn from the
// stored loudness. Every figure comes from the app: each button carries its
// own start and end, and the player data the rest. No state is worked out
// here beyond which line holds the current time and where a press stops.
(function () {
  const audio = document.getElementById('audio');
  const data = document.getElementById('player-data');
  if (!audio || !data) return;
  const player = JSON.parse(data.textContent);
  let from = 0;
  let stopAt = null;      // where a pressed line or stretch ends; null when the sound plays on
  let watching = false;

  function stopIfReached() {
    if (stopAt === null) return;
    const t = audio.currentTime;
    // Moved away with the player's own bar: its controls play on as before.
    if (t < from - 0.25 || t > stopAt + 0.75) { stopAt = null; return; }
    if (t >= stopAt) { stopAt = null; audio.pause(); }
  }
  function watch() {
    stopIfReached();
    watching = stopAt !== null;
    if (watching) window.requestAnimationFrame(watch);           // closer than the browser's own time events, a quarter second apart
  }
  function playFrom(start, end) {
    from = start;
    stopAt = (end === undefined || Number.isNaN(end) || end <= start) ? null : end;
    audio.currentTime = start;
    audio.play();
    if (stopAt !== null && !watching) { watching = true; window.requestAnimationFrame(watch); }
  }
  // A pause with the player's own control before the end: the next play is the player's own and plays on.
  audio.addEventListener('pause', function () { if (stopAt !== null && audio.currentTime < stopAt) stopAt = null; });
  document.querySelectorAll('button.play-line, button.play-stretch').forEach(function (button) {
    button.addEventListener('click', function () { playFrom(Number(button.dataset.start), Number(button.dataset.end)); });
  });
  document.querySelectorAll('button.play-at').forEach(function (button) {
    button.addEventListener('click', function () { playFrom(Number(button.dataset.start)); });
  });
  audio.addEventListener('timeupdate', function () {
    const t = audio.currentTime;
    stopIfReached();
    document.querySelectorAll('.line.playing').forEach(function (line) { line.classList.remove('playing'); });
    const line = player.lines.find(function (l) { return t >= l.start_s && t < l.end_s; });
    if (line) { const node = document.getElementById('line-' + line.n); if (node) node.classList.add('playing'); }
    drawStrip(t);
  });

  const strip = document.getElementById('strip');
  function drawStrip(at) {
    if (!strip) return;
    const ctx = strip.getContext('2d');
    const w = strip.width, h = strip.height, columns = player.strip.length;
    ctx.clearRect(0, 0, w, h);
    if (!columns) return;
    const colWidth = w / columns;
    player.strip.forEach(function (level, k) {
      if (level === null) return;
      const height = Math.max(1, Math.min(1, (level + 60) / 60)) * h;    // -60 dBFS at the floor, 0 at the top
      ctx.fillStyle = level > -30 ? '#4E2A3A' : '#A39A91';
      ctx.fillRect(k * colWidth, h - height, Math.max(1, colWidth - 0.5), height);
    });
    if (player.length_s > 0 && at !== undefined) {
      ctx.fillStyle = '#C2402F';
      ctx.fillRect(Math.min(w - 1, at / player.length_s * w), 0, 2, h);
    }
  }
  if (strip) strip.addEventListener('click', function (event) {
    const rect = strip.getBoundingClientRect();
    if (player.length_s > 0) playFrom((event.clientX - rect.left) / rect.width * player.length_s);
  });
  drawStrip(0);
})();
