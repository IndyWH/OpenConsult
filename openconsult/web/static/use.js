// Typing counts as use (spec 15.10, ruling 12). Every keystroke in the
// element marked data-use (a form, or the whole review page) marks the page
// edited and, not more than once in 30 s, tells the app it is in use; the
// page's own timed move runs from the seconds the app gives and never while
// an edit is unsaved. No state logic beyond that lives here.
(function () {
  const form = document.querySelector('[data-use]');
  if (!form) return;
  let secondsLeft = Number(form.dataset.secondsLeft);
  let edited = false;
  let lastTold = 0;
  const PING_EVERY_MS = 30000;
  function tell() {
    fetch('/use', {method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: ''})
      .then((r) => r.json()).then((j) => { secondsLeft = Number(j.seconds_left); }).catch(() => {});
  }
  form.addEventListener('input', () => {
    edited = true;
    const now = Date.now();
    if (now - lastTold > PING_EVERY_MS) { lastTold = now; tell(); }
  });
  form.addEventListener('submit', () => { edited = false; });
  if (!Number.isFinite(secondsLeft)) return;
  setInterval(() => {
    secondsLeft -= 1;
    if (secondsLeft <= 0 && !edited) { window.location.href = form.dataset.path + '?quiet'; }
  }, 1000);
})();
