// The review page brought up to date without a load (spec 15.10 ruling 33;
// the details of the mend run of step 6d, Leaving the box). When a name is
// kept on leaving its box the app answers with the page itself. The
// template marks, with data-part, each part that a press on a row can
// change; this script puts the answer's part in place of the page's where
// the two differ, and removes a row that is gone. It works nothing out:
// every word shown is the app's. Never replaced: the player, so a sound
// plays on, and the note. A part that holds words or a choice the doctor
// has not saved is left whole (ruling 12). The page is not changed while a
// mouse button is down, so a click in flight keeps its target; the window
// is held where it was; and the keyboard stays on the control it was on.
(function () {
  if (!document.getElementById('review') || !window.pageFields) return;
  const FIELDS = 'input:not([type=hidden]), select, textarea';
  const STOPS = 'a[href], button, input:not([type=hidden]), select, textarea';
  const served = {};        // each part as the app last gave it: a class a script set on the page is no difference
  let down = false;         // a mouse button is down
  let waiting = null;       // an answer that came while it was down: put in place when it lets go
  const fresh = {busy: false};

  // Pure: whether a part of the page holds a field that is neither what the app gave it nor what the answer gives it.
  function holdsUnsaved(part, answer) {
    const theirs = answer.querySelectorAll(FIELDS);
    return Array.from(part.querySelectorAll(FIELDS)).some(function (field, k) {
      if (!window.pageFields.unsaved(field)) return false;
      return !theirs[k] || String(field.value).trim() !== String(window.pageFields.given(theirs[k])).trim();
    });
  }

  function place(answer, anchorId) {
    const anchor = function () { return document.getElementById(anchorId); };
    const before = anchor() ? anchor().getBoundingClientRect().top : null;
    const active = document.activeElement;
    fresh.busy = true;
    document.querySelectorAll('[data-part]').forEach(function (part) {
      const theirs = answer.getElementById(part.id);
      if (!theirs) {
        if (!Array.from(part.querySelectorAll(FIELDS)).some(window.pageFields.unsaved)) { delete served[part.id]; part.remove(); }
        return;
      }
      if (theirs.outerHTML === served[part.id] || holdsUnsaved(part, theirs)) return;
      const stop = part.contains(active) ? Array.from(part.querySelectorAll(STOPS)).indexOf(active) : -1;
      const caret = stop >= 0 && active.matches('input[type=text], input:not([type])') ? [active.selectionStart, active.selectionEnd] : null;
      served[part.id] = theirs.outerHTML;
      const node = document.importNode(theirs, true);
      part.replaceWith(node);
      const again = stop >= 0 ? node.querySelectorAll(STOPS)[stop] : null;
      if (again) {
        again.focus({preventScroll: true});
        if (caret && again.setSelectionRange) again.setSelectionRange(caret[0], caret[1]);
      }
    });
    const rows = document.getElementById('drug-rows');
    if (rows && !rows.children.length && !answer.getElementById('drug-rows')) rows.remove();
    fresh.busy = false;
    if (before !== null && anchor()) window.scrollBy(0, anchor().getBoundingClientRect().top - before);
  }

  // The app's answer, as the text of a page. False when it is not the review page: the caller sends the browser there.
  fresh.from = function (html, anchorId) {
    const answer = new DOMParser().parseFromString(html, 'text/html');
    if (!answer.getElementById('review')) return false;
    window.pageFields.left(answer.getElementById('review').dataset.secondsLeft);      // the request was use: the lock's count starts again
    if (down) waiting = [answer, anchorId]; else place(answer, anchorId);
    return true;
  };
  // Another piece of the page put in place by a script (an entry of the note saved where it stands, review.js) waits
  // in the same way: not while a mouse button is down.
  let later = [];
  fresh.whenUp = function (act) { if (down) later.push(act); else act(); };
  document.querySelectorAll('[data-part]').forEach(function (part) { served[part.id] = part.outerHTML; });
  document.addEventListener('pointerdown', function () { down = true; }, true);
  ['pointerup', 'pointercancel'].forEach(function (name) {
    document.addEventListener(name, function () {
      down = false;
      // After the click that this release makes has been dealt with.
      window.setTimeout(function () {
        if (down) return;
        if (waiting) { const held = waiting; waiting = null; place(held[0], held[1]); }
        const acts = later;
        later = [];
        acts.forEach(function (act) { act(); });
      }, 0);
    }, true);
  });
  window.freshPage = fresh;
})();
