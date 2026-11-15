// What counts as use (spec 15.10, rulings 12 and 41). Every keystroke in
// the element marked data-use (a form, or the whole review page) tells the
// app, not more than once in 30 s, that it is in use; where the element is
// also marked data-presses, the review page, every press of the doctor
// does the same. The player tells through here too: while sound plays, and
// once more when it stops, so that the lock's time runs from the end of
// the sound. Each answer carries the seconds left, and the page's own
// timed move runs from them: so the page's count and the app agree. The
// move never comes while a box holds words or a choice that are not saved,
// nor while sound is playing. That is asked of the page at the moment, not
// remembered: a name kept on leaving its box sends no form (ruling 33), and
// a page that only remembered typing would never again go to the login
// page when the lock falls. A keep is use, and its answer is a page that
// carries the seconds then left: fresh.js hands them here. The page's own
// requests, for the recording and for its file's name, are never use.
(function () {
  // Pure: what the app gave a field, and whether the field now holds something else.
  function given(field) {
    if (field.tagName === 'SELECT') {
      const option = Array.from(field.options).find(function (o) { return o.defaultSelected; }) || field.options[0];
      return option ? option.value : '';
    }
    return field.defaultValue;
  }
  function unsaved(field) {
    if (field.type === 'checkbox' || field.type === 'radio') return field.checked !== field.defaultChecked;
    return String(field.value).trim() !== String(given(field)).trim();
  }
  // The app counts whole seconds, rounded down. One second is added, as the timed pages without a script have it, so that
  // the page's check never comes before the lock has fallen: a check that came early showed the page again.
  let secondsLeft = NaN;
  function left(seconds) { if (Number.isFinite(Number(seconds))) secondsLeft = Number(seconds) + 1; }
  window.pageFields = {given: given, unsaved: unsaved, left: left};

  const form = document.querySelector('[data-use]');
  if (!form) return;
  left(form.dataset.secondsLeft === '' ? NaN : form.dataset.secondsLeft);
  let lastTold = 0;
  const TELL_EVERY_MS = 30000;
  // Pure: whether the app is to be told now. Always when asked so (the end of sound; a use the page itself made).
  function due(now, last, always) { return Boolean(always) || now - last > TELL_EVERY_MS; }
  function tell(always) {
    const now = Date.now();
    if (!due(now, lastTold, always)) return;
    lastTold = now;
    fetch('/use', {method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: ''})
      .then((r) => r.json()).then((j) => { left(j.seconds_left); }).catch(() => {});
  }
  window.pageFields.tell = tell;
  form.addEventListener('input', () => { tell(false); });
  if (form.hasAttribute('data-presses')) form.addEventListener('click', () => { tell(false); });
  if (!Number.isFinite(secondsLeft)) return;
  setInterval(() => {
    secondsLeft -= 1;
    const held = Array.from(form.querySelectorAll('input, select, textarea')).some(unsaved);
    const sounding = Array.from(form.querySelectorAll('audio')).some(function (player) { return !player.paused && !player.ended; });
    if (secondsLeft <= 0 && !held && !sounding) { window.location.href = form.dataset.path + '?quiet'; }
  }, 1000);
})();
