// The player (spec 8.8; D51; 15.10 ruling 29; the mend run of step 6d,
// fault one). The browser's own controls give play, pause, the bar and the
// time. This script adds the presses: a line plays from its start to its end
// and stops, and is marked while it plays; a warning plays its stretch and
// stops at its end; the alarm's press and a press on the loudness strip play
// on. The strip is drawn from the stored loudness. Every figure comes from
// the app: each button carries its own start and end, and the player data
// the rest. The review page is shown before the WAV is converted to Opus,
// so a player shown with the WAV holds a file that is then gone, and its
// first play stalled without a word. At a press the script now asks the app
// for the recording's file as it is now; when the name has changed it gives
// the player the address afresh and plays the press. No state is worked out
// here beyond which line holds the current time, where a press stops, and
// which file the player holds.
(function () {
  const audio = document.getElementById('audio');
  const data = document.getElementById('player-data');
  if (!audio || !data) return;
  const player = JSON.parse(data.textContent);
  const address = audio.getAttribute('src');
  let held = player.file;   // the file the player holds: the one the page was shown with, until the app names another
  let press = null;         // the press being played, {start, end}: played again once the address has been taken afresh
  let retaken = false;      // a failed play takes the address again once for a press, never twice
  let byPress = false;      // true from a press's own play() until the player's play event has come
  let stopAt = null;        // where a pressed line or stretch ends; null when the sound plays on
  let timer = null;
  let moving = false;       // true while this script itself moves the sound to a press's start

  // Pure: whether the app names another file than the player holds, and the address that makes the browser start afresh.
  function changed(holds, now) { return Boolean(now) && now !== holds; }
  function addressFor(base, name) { return base + '?file=' + encodeURIComponent(name); }

  // Stops at the end of the press's stretch. The browser's own time events come a quarter second apart, so a timer
  // is set for what is left; it sets itself again when the sound started late.
  function stopIfReached() {
    if (stopAt === null) return;
    const left = stopAt - audio.currentTime;
    if (left <= 0) { stopAt = null; audio.pause(); return; }
    window.clearTimeout(timer);
    timer = window.setTimeout(stopIfReached, Math.max(10, left * 1000 / (audio.playbackRate || 1)));
  }
  function begin() {
    stopAt = press.end;
    moving = true;
    audio.currentTime = press.start;
    window.setTimeout(function () { moving = false; }, 500);
    byPress = audio.paused;
    const played = audio.play();
    if (played) played.catch(failed);
    stopIfReached();
  }
  // The address taken afresh: the browser forgets the file it held, reads the head of the one that is there, and the press plays.
  function retake(name) {
    held = name;
    audio.addEventListener('loadedmetadata', begin, {once: true});
    audio.src = addressFor(address, name);
    audio.load();
  }
  function failed(error) {
    if ((error && error.name === 'AbortError') || retaken || !press) return;      // a newer press or a fresh address took its place
    retaken = true;
    retake(held);
  }
  // Only a page shown with the WAV asks: the conversion goes one way, and an Ogg stays. The question is the page's own
  // and is not use (15.6): it must not put off the lock behind the back of the page's count.
  function ask() {
    if (!/\.wav$/.test(held || '')) return;
    fetch(address + '/file?quiet').then(function (r) { return r.ok && !r.redirected ? r.text() : ''; }).then(function (name) {
      if (changed(held, name.trim())) retake(name.trim());
    }).catch(function () {});
  }
  function playFrom(start, end) {
    press = {start: start, end: (end === undefined || Number.isNaN(end) || end <= start) ? null : end};
    retaken = false;
    begin();
    ask();
  }
  // The browser's own play control: the same question, and the sound plays on from where its bar stands.
  audio.addEventListener('play', function () {
    if (byPress) { byPress = false; return; }
    press = {start: audio.currentTime, end: null};
    retaken = false;
    ask();
  });
  audio.addEventListener('error', function () { failed(null); });
  // The player's own controls play on as before: a move with its bar, or a pause before the end, ends a press's stop.
  audio.addEventListener('seeking', function () { if (moving) moving = false; else stopAt = null; });
  audio.addEventListener('pause', function () { if (stopAt !== null && audio.currentTime < stopAt) stopAt = null; });
  // One listener for the page: a row or a line that fresh.js put in place is a new node, and its play must work as after a load.
  document.addEventListener('click', function (event) {
    const button = event.target.closest ? event.target.closest('button.play-line, button.play-stretch, button.play-at') : null;
    if (!button) return;
    if (button.classList.contains('play-at')) playFrom(Number(button.dataset.start));
    else playFrom(Number(button.dataset.start), Number(button.dataset.end));
  });
  audio.addEventListener('timeupdate', function () {
    const t = audio.currentTime;
    stopIfReached();
    document.querySelectorAll('.playing').forEach(function (line) { line.classList.remove('playing'); });
    const line = player.lines.find(function (l) { return t >= l.start_s && t < l.end_s; });
    // The sounding line is marked on the line, and on its words inside its turn: the one in sight shows it (step 6e).
    if (line) ['line-', 'turn-line-'].forEach(function (name) {
      const node = document.getElementById(name + line.n);
      if (node) node.classList.add('playing');
    });
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
