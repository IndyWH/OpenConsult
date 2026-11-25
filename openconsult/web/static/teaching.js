// A teaching case in the browser (spec 15.14, the details of run 10b: The
// history, Words typed are never lost). Two things, and nothing is worked
// out here: every word and every number shown comes from the app's page.
//
// One. A line of the history, or an examination request, is sent without
// a load. The line stands on the page at once, with the number the app
// gave the box, and the page says that the answer is awaited. The app
// answers with its own page; the parts marked data-part are put in place
// of the page's, the window is moved by what was added so that the box
// stays where it was, and the box keeps the keyboard. Where the answer is
// not a page of the case, the login has ended: the page is left as it is,
// the words go back into their box, and the page says so. Where the app
// does not answer, the same. A press while an answer is awaited sends
// nothing a second time.
//
// Two. What is typed and not sent is kept in the browser's own session
// store, by case and box, as it is typed, and put back after any load;
// it is dropped when the app has taken the words, or when the case has
// moved on and its box is gone. So a load, a failed call and a login
// that has ended lose no word.
//
// Where this script has not run, every press is an ordinary form post
// answered by the app's page, and the page says at its top that the
// script did not run.
(function () {
  const page = document.getElementById('teaching-case');
  if (!page) return;
  const KEY = 'openconsult-teaching:' + page.dataset.case + ':';
  const notRun = document.getElementById('no-script');
  if (notRun) notRun.remove();

  function kept(name) { try { return sessionStorage.getItem(KEY + name); } catch (e) { return null; } }
  function keep(name, value) {
    try { if (value) sessionStorage.setItem(KEY + name, value); else sessionStorage.removeItem(KEY + name); } catch (e) { /* no store: the box still holds the words */ }
  }
  function boxes() { return Array.from(page.querySelectorAll('[data-keep]')); }
  // After a load: a box the app sent empty gets back what was typed in it; a box the app sent with words keeps the app's.
  function putBack() {
    const names = boxes().map(function (box) {
      const was = kept(box.dataset.keep);
      if (box.value === '' && was) box.value = was; else keep(box.dataset.keep, box.value);
      return KEY + box.dataset.keep;
    });
    try {
      Object.keys(sessionStorage).forEach(function (key) { if (key.indexOf(KEY) === 0 && names.indexOf(key) < 0) sessionStorage.removeItem(key); });
    } catch (e) { /* no store */ }
  }
  putBack();
  page.addEventListener('input', function (event) {
    if (event.target.dataset && event.target.dataset.keep) keep(event.target.dataset.keep, event.target.value);
  });

  function says(form, words, trouble) {
    const slot = form.querySelector('[data-status]');
    if (!slot) return;
    slot.textContent = words || '';
    slot.setAttribute('role', trouble ? 'alert' : 'status');
  }
  // The line as it will stand, shown at once: the number the app gave the box, the words as typed.
  function pending(form, typed) {
    const turns = page.querySelector('[data-part="turns"]');
    if (!turns || !form.dataset.pendingClass) return null;
    const line = document.createElement('p');
    line.className = form.dataset.pendingClass + ' pending';
    const number = document.createElement('span');
    number.className = 'line-number';
    number.textContent = form.dataset.number + '.';
    const who = document.createElement('span');
    who.className = 'speaker';
    who.textContent = form.dataset.you;
    const said = document.createElement('span');
    said.className = 'said';
    said.textContent = typed;
    line.append(number, ' ', who, ' ', said);
    turns.appendChild(line);
    return line;
  }
  // The app's page in place of this one's, part by part; the window moved by what was added above the box.
  function putInPlace(theirs, name) {
    const before = page.querySelector('[data-keep="' + name + '"]');
    const top = before ? before.getBoundingClientRect().top : null;
    Array.from(page.querySelectorAll('[data-part]')).forEach(function (mine) {
      const fresh = theirs.querySelector('[data-part="' + mine.dataset.part + '"]');
      if (fresh) mine.replaceWith(document.importNode(fresh, true)); else mine.remove();
    });
    Array.from(theirs.querySelectorAll('[data-part]')).forEach(function (fresh) {      // a part the page did not have yet
      if (!page.querySelector('[data-part="' + fresh.dataset.part + '"]')) page.appendChild(document.importNode(fresh, true));
    });
    if (theirs.dataset.secondsLeft && window.pageFields) window.pageFields.left(theirs.dataset.secondsLeft);
    const after = page.querySelector('[data-keep="' + name + '"]');
    if (after && top !== null) window.scrollBy(0, after.getBoundingClientRect().top - top);
    return after;
  }

  let waiting = false;
  page.addEventListener('submit', function (event) {
    const form = event.target;
    if (!form.hasAttribute('data-send')) return;
    const by = event.submitter;
    if (by && by.hasAttribute('formaction')) return;      // End the history, Finish the examination: an ordinary press
    event.preventDefault();
    if (waiting) return;
    const box = form.querySelector('[data-keep]');
    const name = box.dataset.keep, typed = box.value;
    const body = new URLSearchParams(new FormData(form));
    waiting = true;
    const line = typed.trim() ? pending(form, typed) : null;
    box.value = '';
    const send = form.querySelector('[data-send-press]');
    if (send) send.disabled = true;
    says(form, form.dataset.waiting, false);
    function back(words) {
      // Nothing came of it: the words go back into their box, before anything typed since.
      const now = page.querySelector('[data-keep="' + name + '"]');
      if (line) line.remove();
      if (now) { now.value = typed + (now.value ? ' ' + now.value : ''); keep(name, now.value); now.focus(); }
      if (send) send.disabled = false;
      says(form, words, true);
      waiting = false;
    }
    fetch(form.action, {method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: body.toString()})
      .then(function (answer) { return answer.text().then(function (html) { return {status: answer.status, html: html}; }); })
      .then(function (got) {
        const theirs = new DOMParser().parseFromString(got.html, 'text/html').getElementById('teaching-case');
        if (!theirs || (got.status !== 200 && got.status !== 400)) { back(form.dataset.loginEnded); return; }
        const since = (page.querySelector('[data-keep="' + name + '"]') || {value: ''}).value;      // typed while the answer was awaited
        const fresh = putInPlace(theirs, name);
        waiting = false;
        if (fresh) {
          // The app's box: empty when it took the words, holding them when it did not. What was typed since follows.
          fresh.value = fresh.value + (fresh.value && since ? ' ' : '') + since;
          keep(name, fresh.value);
          fresh.focus();
        } else {
          keep(name, '');
        }
      })
      .catch(function () { back(form.dataset.noAnswer); });
  });
})();
