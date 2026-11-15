// Leaving the box of a doubted drug name keeps the typed name (spec 15.10
// rulings 28, 33 and 37; the details of the mend run of step 6d, Leaving
// the box). In the room run of 15 Nov 2026 a name typed and then left was
// lost at the next press. When the focus leaves a row's box and its words
// differ from those the app gave it, this script posts the row's own form
// in the background with the press keep: the app saves the words into the
// line and does not settle the name. The answer is the page itself, put in
// place by fresh.js. The press that took the doctor out of the box is never
// lost: nothing loads, so a play plays; the row's own tick, or Enter in the
// box, sends one act, its own, which carries the words; and any other press
// that loads the page is held until every keep has answered, so the app
// always acts on saved words. One keep at a time, in the order the boxes
// were left. A keep that is refused, or gets no answer, is said at its row,
// and a held press is then dropped: nothing is drafted, approved or ticked
// from words that were not saved. The app holds every word; here is only
// what is on its way. And one click on a row's box selects all its words
// (ruling 39), so that typing replaces them with no second click.
(function () {
  const page = document.getElementById('review');
  if (!page || !window.freshPage) return;
  const WORDS = JSON.parse(document.getElementById('words').textContent);
  const BOX = 'input.doubted-field';
  let chain = Promise.resolve();    // the keeps, one after another
  let unanswered = [];              // a promise for each keep on its way: true when the app saved it
  const onWay = new WeakSet();      // the boxes whose keep is on its way
  let latest = null;                // the newest answer not yet put in place, with the row it came for
  let pressed = null;               // what the mouse went down on, until it lets go
  let forTick = null;               // a box left for its own row's tick: that press carries its words
  let sending = null;               // the form whose own press is on its way
  let through = null;               // a held press, sent again once every keep has answered

  // Pure: whether a box holds other words than the app gave it, and the sentence for a keep that was not taken.
  function changed(box) { return box.value.trim() !== box.defaultValue.trim(); }
  function notSaved(status) {
    const reason = status ? WORDS.NOT_SAVED_ERROR.replace('{status}', status) : WORDS.NOT_SAVED_NO_ANSWER;
    return WORDS.NAME_NOT_SAVED.replace('{reason}', reason);
  }

  function failed(rowId, box, status) {
    const row = document.getElementById(rowId);
    const slot = row && row.querySelector('p.refusal');
    if (slot) slot.textContent = notSaved(status);
    box.classList.add('unsaved');
  }
  function settle() {
    if (unanswered.length || !latest) return;
    const answer = latest;
    latest = null;
    if (!window.freshPage.from(answer[0], answer[1])) window.location.href = page.dataset.path;     // not the review page: the login ended
  }
  function keep(box) {
    const form = box.form, rowId = form.closest('li').id, sent = box.value;
    onWay.add(box);
    const done = chain.then(function () {
      return fetch(form.action, {method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                                 body: new URLSearchParams({words: sent, press: 'keep'}), keepalive: true});
    }).then(function (answer) {
      return answer.text().then(function (html) {
        if (!answer.ok && answer.status !== 400) { failed(rowId, box, answer.status); return false; }
        // Refused by the app: its sentence comes at the row with the words that stood, unless he has typed there since.
        if (!answer.ok && box.value === sent) box.value = box.defaultValue;
        // Saved: these are now the words the app holds for the box, also before its row has been put in place.
        if (answer.ok) box.defaultValue = sent.trim();
        latest = [html, rowId];
        return answer.ok;
      });
    }).catch(function () { failed(rowId, box, 0); return false; }).then(function (saved) {
      onWay.delete(box);
      unanswered = unanswered.filter(function (one) { return one !== done; });
      settle();
      return saved ? true : rowId;
    });
    unanswered.push(done);
    chain = done;
  }
  function tickOf(box) { return box && box.form ? box.form.querySelector('button.tick') : null; }
  function leave(box, to) {
    if (box.readOnly || !box.form || !changed(box) || onWay.has(box) || box.form === sending) return;
    // An empty box that is left takes nothing out of the line: only the tick or the Enter key does (ruling 40), so that a
    // stray click never takes a name out. Nothing is sent; the box stays as he left it and counts as not saved (ruling 12).
    if (!box.value.trim()) return;
    const tick = tickOf(box);
    if (to && tick && tick.contains(to)) { forTick = box; return; }
    keep(box);
  }
  // No press followed on the row's own tick: the box is kept after all.
  function tickPassed() {
    const box = forTick;
    forTick = null;
    if (box && box.isConnected && box.form !== sending) leave(box, null);
  }

  // The click that gives a row's box the focus selects all its words (ruling 39). A click in a box that already has
  // the focus places the caret as before, so one letter can still be mended; so does a stretch chosen by dragging.
  let entered = null;
  document.addEventListener('focusin', function (event) {
    const box = event.target.matches && event.target.matches(BOX) ? event.target : null;
    entered = box && pressed && box.contains(pressed) && !window.freshPage.busy ? box : null;
  });
  document.addEventListener('click', function (event) {
    if (entered && event.target === entered && !entered.readOnly && entered.selectionStart === entered.selectionEnd) entered.select();
    entered = null;
  });
  document.addEventListener('pointerdown', function (event) { pressed = event.target; }, true);
  document.addEventListener('pointerup', function () {
    window.setTimeout(function () { pressed = null; if (forTick && document.activeElement !== tickOf(forTick)) tickPassed(); }, 0);
  }, true);
  document.addEventListener('focusout', function (event) {
    if (window.freshPage.busy || !event.target.matches) return;
    if (event.target.matches(BOX)) leave(event.target, event.relatedTarget || pressed);
    else if (forTick && event.target === tickOf(forTick)) window.setTimeout(tickPassed, 0);
  });
  document.addEventListener('submit', function (event) {
    const form = event.target;
    if (!page.contains(form)) return;
    if (through === form) { through = null; return; }
    sending = form;
    document.querySelectorAll(BOX).forEach(function (box) { leave(box, null); });
    if (!unanswered.length) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const button = event.submitter;
    Promise.all(unanswered.slice()).then(function (kept) {
      const trouble = kept.find(function (one) { return one !== true; });
      // A part put in place is a new node: the press is sent from the control of the same name as it now stands.
      const now = (button && button.id && document.getElementById(button.id)) || button;
      const target = now ? now.form : form;
      if (trouble || !target || !target.isConnected) {
        sending = null;
        const row = trouble && document.getElementById(trouble);
        if (row) row.scrollIntoView({block: 'center'});
        return;
      }
      through = sending = target;
      target.requestSubmit(now);
    });
  }, true);
})();
