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
  // Since step 9f the transcript has two views, and every such press works in both (spec 15.13, the details of step
  // 9f): in the simple view the passage that holds the line is shown, with that line's words marked inside it.
  function simpleTranscript() {
    const transcript = document.getElementById('transcript');
    return Boolean(transcript) && transcript.dataset.view === 'simple';
  }
  function mark(shown) {
    document.querySelectorAll('.marked').forEach(function (node) { node.classList.remove('marked'); });
    if (!shown) return;
    shown.classList.add('marked');
    shown.scrollIntoView({block: 'center'});
  }
  function show(n) {
    if (simpleTranscript()) { mark(document.getElementById('passage-line-' + n)); return; }
    const line = document.getElementById('line-' + n);
    const turn = line ? line.closest('details.turn') : null;
    mark(turn && !turn.open ? document.getElementById('turn-line-' + n) : line);
  }
  // A chip pressed (ruling 71): the turn of that number is shown in the transcript, in the middle of the window, marked
  // whole, in whichever view the transcript stands: its passage, or the turn that carries the number. It opens
  // nothing and plays nothing.
  function showTurn(k) {
    const number = document.getElementById('turn-number-' + k);
    mark(simpleTranscript() ? document.getElementById('passage-' + k) : (number ? number.closest('details.turn') : null));
  }
  // One listener for the page: a row or a line that fresh.js put in place is a new node, and its line number must work as after a load.
  document.addEventListener('click', function (event) {
    const button = event.target.closest ? event.target.closest('button.cite') : null;
    if (button) show(button.dataset.line);
    const chip = event.target.closest ? event.target.closest('button.chip') : null;
    if (chip) showTurn(chip.dataset.turn);
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
    function change() {
      const before = press.getBoundingClientRect().top;
      setView(name, press.dataset.view);
      window.scrollBy(0, press.getBoundingClientRect().top - before);
    }
    // The other way round: an entry's field of the simple note that is open is saved first, and the view changes only
    // when the app has answered. Where the save failed the view stays, and the field stays open with its sentence.
    const saves = name === 'note' ? leaveFields() : [];
    if (!saves.length) { change(); return; }
    Promise.all(saves).then(function (all) { if (all.every(function (one) { return one === true; })) change(); });
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

  // ------------------------------------------------------------------ an entry corrected where it stands
  // In the simple view a click on an entry's words, or Enter on an entry that has the keyboard, turns the words into a
  // field in place that holds them whole (spec 15.13, ruling 72). Enter, or leaving the field, saves through the
  // address and the function an edit has always used: the script posts the entry's own form. The app answers with the
  // page, and its own piece of that entry is put in place of the old one: nothing loads, the window is not moved, and
  // the entry says that it was saved until the next press or keystroke. Words left as they stood send nothing and say
  // nothing; Escape puts them back. An empty field is refused by the app with its own sentence and the words come
  // back. Any other refusal, an error or no answer leaves the field open with what was typed, and the entry says so:
  // nothing typed is lost without a word. The field carries the words as they stood as what the app gave it, so the
  // page's timed move does not come while it holds others (use.js; 15.10 ruling 12). A press that loads the page
  // while a save is on its way is held until the app has answered and dropped if the save failed (rows.js), so that
  // a note is never approved without the words just typed. Only where the app sends an entry's form, that is where
  // entries can be edited: read only, the words are not a press and do not look like one (R15).
  const note = document.getElementById('note');
  const onWay = new Map();      // the fields whose save is on its way, each with its promise
  const STOPS = 'a[href], button, input:not([type=hidden]), select, textarea, [tabindex]';
  const SAVE_LIMIT_MS = 30000;  // the app answers a save in well under a second; the limit the app gives its own asks of a service
  let saidSaved = null;         // the place that says Saved, until the next press or keystroke

  // Pure: an entry is one line in the note, so a line break that was typed or pasted is sent as a space; and the
  // sentence for words that were not saved, from the app's own words.
  function oneLine(text) { return String(text).replace(/\s*[\r\n]+\s*/g, ' ').trim(); }
  function notSaved(reason) { return WORDS.ENTRY_NOT_SAVED.replace('{reason}', reason); }

  function formOf(block) { return block.querySelector('form.entry-form'); }
  function shownOf(block) { return block.querySelector('span.entry-text'); }
  function fieldOf(block) { return block.querySelector('textarea.entry-field'); }
  function entrySays(block, sentence, trouble) {
    const slot = block.querySelector('.entry-said');
    if (!slot) return;
    slot.textContent = sentence;
    slot.classList.toggle('not-saved', Boolean(trouble));
    slot.setAttribute('role', trouble ? 'alert' : 'status');
    if (saidSaved === slot) saidSaved = null;
  }
  function ready(block) {
    const shown = shownOf(block);
    if (!shown || !formOf(block)) return;
    shown.classList.add('can-edit');
    shown.setAttribute('tabindex', '0');
    shown.setAttribute('aria-describedby', 'entry-says');
  }
  function fit(field) { field.style.height = 'auto'; field.style.height = field.scrollHeight + 'px'; }
  function open(block) {
    const shown = shownOf(block), form = formOf(block);
    if (!shown || !form || fieldOf(block) || !note || note.dataset.view !== 'simple') return;
    const field = document.createElement('textarea');
    field.className = 'entry-field';
    field.rows = 1;
    field.defaultValue = shown.textContent;      // the words as they stood: what the app gave this field
    field.setAttribute('aria-label', form.querySelector('input[name=text]').getAttribute('aria-label'));
    block.classList.add('editing');
    shown.after(field);
    fit(field);
    field.focus();
  }
  function close(block, keyboardBack) {
    const field = fieldOf(block);
    if (field) { field.dataset.closed = 'yes'; field.remove(); }
    block.classList.remove('editing');
    if (keyboardBack && shownOf(block)) shownOf(block).focus({preventScroll: true});
  }
  // The app's answer to a save, as the text of a page: true when the words were saved, else the entry's own name.
  function answered(block, field, typed, status, html, keyboardBack) {
    // An answer that is neither the page nor a refusal on the page is an error: the field stays, with what was typed.
    if (status !== 200 && status !== 400) {
      field.readOnly = false;
      entrySays(block, notSaved(WORDS.NOT_SAVED_ERROR.replace('{status}', status)), true);
      return block.id;
    }
    const got = new DOMParser().parseFromString(html, 'text/html');
    if (!got.getElementById('review')) {      // a page, and not the review page: the login has ended. The words stay in the box.
      field.readOnly = false;
      entrySays(block, notSaved(WORDS.NOT_SAVED_LOGIN), true);
      return block.id;
    }
    if (window.pageFields) window.pageFields.left(got.getElementById('review').dataset.secondsLeft);      // the request was use
    const theirs = got.getElementById(block.id);
    if (status === 200 && theirs) {
      const place = function () {
        const node = document.importNode(theirs, true);
        close(block, false);
        // The keyboard stays where it was: on the same control of the new piece, as fresh.js keeps it for a part.
        const stop = block.contains(document.activeElement) ? Array.from(block.querySelectorAll(STOPS)).indexOf(document.activeElement) : -1;
        block.replaceWith(node);
        ready(node);
        entrySays(node, WORDS.ENTRY_SAVED, false);
        saidSaved = node.querySelector('.entry-said');
        const again = keyboardBack ? shownOf(node) : (stop >= 0 ? node.querySelectorAll(STOPS)[stop] : null);
        if (again) again.focus({preventScroll: true});
      };
      if (window.freshPage && window.freshPage.whenUp) window.freshPage.whenUp(place); else place();
      return true;
    }
    const slot = status === 400 ? got.getElementById(formOf(block).querySelector('button').id + '-refusal') : null;
    const sentence = slot ? slot.textContent.trim() : '';
    if (sentence && !typed) {      // an empty field: the app's sentence, and the words as they stood
      close(block, keyboardBack);
      entrySays(block, sentence, true);
      return block.id;
    }
    field.readOnly = false;
    if (sentence) entrySays(block, sentence, true);
    else if (status === 200) entrySays(block, notSaved(WORDS.NOT_SAVED_NEW_DRAFT), true);      // the entry is no longer on the app's page
    else entrySays(block, notSaved(WORDS.NOT_SAVED_ERROR.replace('{status}', status)), true);  // a refusal with no sentence for this entry
    return block.id;
  }
  function save(block, keyboardBack) {
    const field = fieldOf(block);
    if (!field) return Promise.resolve(true);
    if (onWay.has(field)) return onWay.get(field);
    const typed = oneLine(field.value);
    if (typed === oneLine(field.defaultValue)) { close(block, keyboardBack); entrySays(block, '', false); return Promise.resolve(true); }
    field.readOnly = true;
    // An app that takes the request and never answers is an app that does not answer: after this long the save is
    // given up and said as not saved, so that the field and a held press are never left waiting without a word.
    const limit = new AbortController();
    const timer = window.setTimeout(function () { limit.abort(); }, SAVE_LIMIT_MS);
    const sent = fetch(formOf(block).action, {method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                                              body: new URLSearchParams({text: typed}), keepalive: true, signal: limit.signal})
      .then(function (answer) { return answer.text().then(function (html) { return answered(block, field, typed, answer.status, html, keyboardBack); }); })
      .catch(function () { field.readOnly = false; entrySays(block, notSaved(WORDS.NOT_SAVED_NO_ANSWER), true); return block.id; })
      .then(function (outcome) { window.clearTimeout(timer); onWay.delete(field); return outcome; });
    // The save joins the line of keeps: a press that loads the page waits for it, and is dropped if it failed.
    const done = window.reviewSaves ? window.reviewSaves.join(sent) : sent;
    onWay.set(field, done);
    return done;
  }
  // Every open field is left: saved where its words changed, closed where they did not. The saves on their way.
  function leaveFields() {
    const saves = [];
    if (note) note.querySelectorAll('textarea.entry-field').forEach(function (field) {
      const done = save(field.closest('.entry'), false);
      if (onWay.has(field)) saves.push(done);
    });
    return saves;
  }
  if (note) {
    note.querySelectorAll('.entry').forEach(ready);
    note.addEventListener('click', function (event) {
      const shown = event.target.closest ? event.target.closest('span.entry-text.can-edit') : null;
      const chosen = window.getSelection ? window.getSelection() : null;
      if (shown && !(chosen && !chosen.isCollapsed && shown.contains(chosen.anchorNode))) open(shown.closest('.entry'));
    });
    note.addEventListener('keydown', function (event) {
      const target = event.target;
      if (target.matches('span.entry-text.can-edit') && event.key === 'Enter') { event.preventDefault(); open(target.closest('.entry')); return; }
      if (!target.matches('textarea.entry-field') || onWay.has(target)) return;      // while a save is on its way the field waits
      if (event.key === 'Enter') { event.preventDefault(); save(target.closest('.entry'), true); }
      if (event.key === 'Escape') { const block = target.closest('.entry'); close(block, true); entrySays(block, '', false); }
    });
    note.addEventListener('input', function (event) { if (event.target.matches('textarea.entry-field')) fit(event.target); });
    note.addEventListener('focusout', function (event) {
      const field = event.target;
      if (!field.matches || !field.matches('textarea.entry-field') || field.dataset.closed || (window.freshPage && window.freshPage.busy)) return;
      save(field.closest('.entry'), false);
    });
    // A press that loads the page while a field is open: the field is left first, so its save is in the line that holds the press.
    document.addEventListener('submit', function () { leaveFields(); }, true);
    ['click', 'keydown'].forEach(function (kind) {
      document.addEventListener(kind, function () { if (saidSaved) { saidSaved.textContent = ''; saidSaved = null; } }, true);
    });
  }

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
