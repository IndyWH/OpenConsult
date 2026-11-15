// The review page's presses (spec 15.10, rulings 4, 11, 12, 34 and 43; the
// details of step 6e): a line number beside an entry shows that line of
// the transcript and marks it; the copy control fetches the note's plain
// text from the app and puts it on the clipboard; and the turns of the
// reading view. The text is the app's: nothing is built here.
// A turn is the browser's own disclosure element and opens and closes with
// no script. This script adds what the element cannot do. After a press
// that loads the page, whatever stood open is open again: when the page is
// left it notes, in the browser's session store, the numbers of the lines
// that stood open and the time, never a word of the consultation; the next
// load reads the note once, if it is fresh, and opens each turn that holds
// a line that stood open, so a line whose speaker was corrected and is now
// a turn of its own is still open under the doctor's hand. It runs before
// place.js, which then puts the page's place back. The control at the top
// opens every turn in place and closes them again. A turn that holds words
// or a choice not saved is never closed, by that control or by the doctor's
// own press: a line's box is saved only by its Save, and words hidden in a
// closed turn would be lost without a word; the turn says so. And a drag
// that selects words in a turn does not end in a press that opens it.
(function () {
  const page = document.getElementById('review');
  if (!page) return;
  const WORDS = JSON.parse(document.getElementById('words').textContent);
  // A line number pressed: the turn that holds the line is shown, with that line's words marked inside it, in the middle
  // of the window; the turn is not opened. On an opened turn the line itself is marked, as before the reading view.
  function show(n) {
    document.querySelectorAll('.marked').forEach(function (node) { node.classList.remove('marked'); });
    const line = document.getElementById('line-' + n);
    if (!line) return;
    const turn = line.closest('details.turn');
    const shown = turn && !turn.open ? document.getElementById('turn-line-' + n) : line;
    if (!shown) return;
    shown.classList.add('marked');
    shown.scrollIntoView({block: 'center'});
  }
  // One listener for the page: a row or a line that fresh.js put in place is a new node, and its line number must work as after a load.
  document.addEventListener('click', function (event) {
    const button = event.target.closest ? event.target.closest('button.cite') : null;
    if (button) show(button.dataset.line);
  });
  // The red mark beside the assessment (15.11 ruling 9): a press shows the alarm the app matched.
  const marksNode = document.getElementById('marks');
  const marks = marksNode ? JSON.parse(marksNode.textContent) : {};
  document.querySelectorAll('button.red-name').forEach(function (button) {
    button.addEventListener('click', function () {
      const alarm = marks[button.dataset.name];
      if (alarm && window.alarmDialog) window.alarmDialog.show(alarm.reasoning, alarm.actions, WORDS);
    });
  });
  const copy = document.getElementById('copy-note');
  const result = document.getElementById('copy-note-result');
  if (copy) copy.addEventListener('click', function () {
    fetch(page.dataset.path + '/note.txt').then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.text();
    }).then(function (text) {
      // The fetch was use: the app is told once more, and its answer sets the page's count, so the two agree (ruling 41).
      if (window.pageFields && window.pageFields.tell) window.pageFields.tell(true);
      return navigator.clipboard.writeText(text);
    })
      .then(function () { result.textContent = WORDS.COPIED; })
      .catch(function (error) { result.textContent = WORDS.COPY_FAILED.replace('{reason}', error && error.message ? error.message : String(error)); });
  });

  // ------------------------------------------------------------------ the turns
  const pane = document.getElementById('final-transcript');
  if (!pane) return;
  const all = document.getElementById('open-all');
  const KEY = 'openconsult.open:' + page.dataset.path;
  const FRESH_MS = 15000;      // a note older than this belongs to a load that never came

  // Pure: whether a turn of these lines holds one that stood open, and whether a note is one to act on.
  function holdsOne(numbers, stoodOpen) { return numbers.some(function (n) { return stoodOpen.indexOf(n) >= 0; }); }
  function fresh(noted, now) { return Boolean(noted) && Array.isArray(noted.lines) && now - noted.at < FRESH_MS; }

  function turns() { return Array.from(pane.querySelectorAll('details.turn')); }
  function numbers(turn) { return Array.from(turn.querySelectorAll('.line')).map(function (line) { return Number(line.id.replace('line-', '')); }); }
  function unsaved(turn) {
    return Boolean(window.pageFields) && Array.from(turn.querySelectorAll('input, select, textarea')).some(window.pageFields.unsaved);
  }
  function name() {
    if (all) all.textContent = turns().every(function (turn) { return turn.open; }) ? WORDS.CLOSE_ALL_LINES : WORDS.OPEN_ALL_LINES;
  }
  // The sentence of a turn that was not closed because it holds unsaved words; it goes when the turn holds none.
  function says(turn, on) {
    let slot = turn.querySelector('p.turn-holds');
    if (!on) { if (slot) slot.remove(); return; }
    if (!slot) {
      slot = document.createElement('p');
      slot.className = 'refusal turn-holds';
      slot.setAttribute('role', 'alert');
      turn.querySelector('summary').after(slot);
    }
    slot.textContent = WORDS.TURN_NOT_SAVED;
  }

  let store = null;
  try { store = window.sessionStorage; store.getItem('x'); } catch (error) { store = null; }     // no store: turns open by a press, as with no script
  if (store) {
    let noted = null;
    try { noted = JSON.parse(store.getItem(KEY)); } catch (error) { noted = null; }
    store.removeItem(KEY);
    if (fresh(noted, Date.now())) turns().forEach(function (turn) { if (holdsOne(numbers(turn), noted.lines)) turn.open = true; });
    window.addEventListener('pagehide', function () {
      const lines = [];
      turns().forEach(function (turn) { if (turn.open) lines.push.apply(lines, numbers(turn)); });
      try { store.setItem(KEY, JSON.stringify({at: Date.now(), lines: lines})); } catch (error) { /* a full store: the turns come back closed */ }
    });
  }
  name();

  pane.addEventListener('click', function (event) {
    const summary = event.target.closest ? event.target.closest('summary') : null;
    // A press on a control inside a turn does its own work; the browser does not open or close the turn for it.
    if (!summary || !pane.contains(summary) || event.target.closest('button, a')) return;
    const turn = summary.parentElement;
    const chosen = window.getSelection ? window.getSelection() : null;
    if (chosen && !chosen.isCollapsed && summary.contains(chosen.anchorNode)) { event.preventDefault(); return; }
    if (turn.open && unsaved(turn)) { event.preventDefault(); says(turn, true); }
  });
  ['input', 'change'].forEach(function (kind) {
    pane.addEventListener(kind, function (event) {
      const turn = event.target.closest ? event.target.closest('details.turn') : null;
      if (turn && !unsaved(turn)) says(turn, false);
    });
  });
  pane.addEventListener('toggle', name, true);
  if (all) all.addEventListener('click', function (event) {
    event.preventDefault();      // with no script the control is a link that loads the page with every turn open
    const open = !turns().every(function (turn) { return turn.open; });
    turns().forEach(function (turn) { if (open || !unsaved(turn)) turn.open = open; });
    name();
  });
})();
