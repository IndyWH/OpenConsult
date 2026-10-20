// The player (spec 8.8; D51). The browser's own controls give play, pause,
// the bar and the time. This script adds the presses: a line plays from its
// start and is marked while it plays; a warning plays its stretch and stops
// at its end; the loudness strip is drawn from the stored loudness and a
// press on it seeks there. Every figure comes from the app's player data;
// no state is worked out here beyond which line holds the current time.
(function () {
  const audio = document.getElementById('audio');
  const data = document.getElementById('player-data');
  if (!audio || !data) return;
  const player = JSON.parse(data.textContent);
  let stopAt = null;

  function playFrom(start, end) {
    stopAt = end === undefined ? null : end;
    audio.currentTime = start;
    audio.play();
  }
  document.querySelectorAll('button.play-line').forEach(function (button) {
    button.addEventListener('click', function () {
      const line = player.lines.find(function (l) { return String(l.n) === button.dataset.line; });
      if (line) playFrom(line.start_s);
    });
  });
  document.querySelectorAll('button.play-stretch').forEach(function (button) {
    button.addEventListener('click', function () { playFrom(Number(button.dataset.start), Number(button.dataset.end)); });
  });
  audio.addEventListener('timeupdate', function () {
    const t = audio.currentTime;
    if (stopAt !== null && t >= stopAt) { audio.pause(); stopAt = null; }
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
