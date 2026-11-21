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
  const FRESH_MS = 15000;      // a note older than this belongs to a load that never came
  let store = null;
  try { store = window.sessionStorage; store.getItem('x'); } catch (error) { store = null; }     // no store: as with no script
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

  // ------------------------------------------------------------------ the two views
  // An area of the page, the note or the transcript, says its view in data-view, and the style sheet shows that one
  // (spec 15.13, ruling 46). A press on Simple or Advanced changes it in place: nothing loads, and the press stays
  // where it stood in the window. The choice holds while the page is in use, as the opened lines do: when the page
  // is left the two names and the time are noted in the session store, never a word of the consultation; the next
  // load reads the note once and, if it is fresh, sets the views, before place.js puts the page's place back. An
  // area the app holds in its view (data-view-held, while the check of who spoke runs) is left as the app sent it.
  // A press on Simple changes nothing where the advanced view holds a box or a choice that is not saved: hidden,
  // those words would be lost without a word, and a note approved without them (15.10, ruling 12). The area says why.
  const AREAS = ['note', 'transcript'];
  const VIEWS_KEY = 'openconsult.views:' + page.dataset.path;
  const ADVANCED_FIELDS = '.entry-form input, #final-transcript input, #final-transcript select';
  // Pure: the view a name stands for, and whether a noted choice is one to act on.
  function viewOf(name) { return name === 'advanced' ? 'advanced' : 'simple'; }
  function freshChoice(noted, now) { return Boolean(noted) && now - noted.at < FRESH_MS; }
  function setView(name, view) {
    const node = document.getElementById(name);
    if (!node || node.hasAttribute('data-view-held')) return;
    node.dataset.view = viewOf(view);
    node.querySelectorAll('a.view').forEach(function (press) {
      if (press.dataset.view === node.dataset.view) press.setAttribute('aria-current', 'true'); else press.removeAttribute('aria-current');
    });
  }
  function advancedHolds(node) {
    return Boolean(window.pageFields) && Array.from(node.querySelectorAll(ADVANCED_FIELDS)).some(window.pageFields.unsaved);
  }
  function viewSays(name, sentence) {
    const slot = document.getElementById(name + '-view-says');
    if (slot) slot.textContent = sentence;
  }
  if (store) {
    let chosen = null;
    try { chosen = JSON.parse(store.getItem(VIEWS_KEY)); } catch (error) { chosen = null; }
    store.removeItem(VIEWS_KEY);
    if (freshChoice(chosen, Date.now())) AREAS.forEach(function (name) { setView(name, chosen[name]); });
    window.addEventListener('pagehide', function () {
      const noted = {at: Date.now()};
      AREAS.forEach(function (name) { const node = document.getElementById(name); if (node) noted[name] = node.dataset.view; });
      try { store.setItem(VIEWS_KEY, JSON.stringify(noted)); } catch (error) { /* a full store: the page comes back simple */ }
    });
  }
  document.addEventListener('click', function (event) {
    const press = event.target.closest ? event.target.closest('a.view') : null;
    if (!press) return;
    event.preventDefault();      // with no script the press is a link that loads the page with that view, at that area
    const name = press.dataset.area, node = document.getElementById(name);
    if (!node || node.dataset.view === press.dataset.view) return;
    if (press.dataset.view === 'simple' && advancedHolds(node)) { viewSays(name, WORDS.VIEW_NOT_SAVED); return; }
    viewSays(name, '');
    const before = press.getBoundingClientRect().top;
    setView(name, press.dataset.view);
    window.scrollBy(0, press.getBoundingClientRect().top - before);
  });
  // The sentence goes when the area holds nothing unsaved any more.
  ['input', 'change'].forEach(function (kind) {
    document.addEventListener(kind, function (event) {
      AREAS.forEach(function (name) {
        const node = document.getElementById(name);
        if (node && node.contains(event.target) && !advancedHolds(node)) viewSays(name, '');
      });
    });
  });

  // ------------------------------------------------------------------ the turns
  const pane = document.getElementById('final-transcript');
  if (!pane) return;
  const all = document.getElementById('open-all');
  const KEY = 'openconsult.open:' + page.dataset.path;

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

  if (store) {      // no store: turns open by a press, as with no script
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
