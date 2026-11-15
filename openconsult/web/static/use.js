// Typing counts as use (spec 15.10, ruling 12). Every keystroke in the
// element marked data-use (a form, or the whole review page) tells the app,
// not more than once in 30 s, that it is in use; the page's own timed move
// runs from the seconds the app gives and never while a box holds words or
// a choice that are not saved. That is asked of the page at the moment, not
// remembered: a name kept on leaving its box sends no form (ruling 33), and
// a page that only remembered typing would never again go to the login
// page when the lock falls. A keep is use, and its answer is a page that
// carries the seconds then left: fresh.js hands them here, so the timed
// move still comes when the lock falls. No state logic beyond that lives here.
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
  // the page's check never comes before the lock has fallen: a check that came early showed the page again, and on the
  // review page that page's own request for the recording then put the lock off, time after time.
  let secondsLeft = NaN;
  function left(seconds) { if (Number.isFinite(Number(seconds))) secondsLeft = Number(seconds) + 1; }
  window.pageFields = {given: given, unsaved: unsaved, left: left};

  const form = document.querySelector('[data-use]');
  if (!form) return;
  left(form.dataset.secondsLeft === '' ? NaN : form.dataset.secondsLeft);
  let lastTold = 0;
  const PING_EVERY_MS = 30000;
  function tell() {
    fetch('/use', {method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: ''})
      .then((r) => r.json()).then((j) => { left(j.seconds_left); }).catch(() => {});
  }
  form.addEventListener('input', () => {
    const now = Date.now();
    if (now - lastTold > PING_EVERY_MS) { lastTold = now; tell(); }
  });
  if (!Number.isFinite(secondsLeft)) return;
  setInterval(() => {
    secondsLeft -= 1;
    const held = Array.from(form.querySelectorAll('input, select, textarea')).some(unsaved);
    if (secondsLeft <= 0 && !held) { window.location.href = form.dataset.path + '?quiet'; }
  }, 1000);
})();
