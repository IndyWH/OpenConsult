// The delete of a recording sent after Stop is answered while the doctor
// reads the note (the owner's ruling of 18 Nov 2026). Stop no longer
// waits for Speechmatics to delete the recording and to confirm it: the
// note is there first, and the line above it says that the answer is
// awaited. This script asks the app what the record holds, and when the
// answer has come it asks for the app's own page and lets fresh.js put
// the changed parts in place: the line above the note, the warning where
// the delete is not proven, the count on Approve. Nothing is worked out
// here and no sentence is held here: every word shown is the app's. The
// page is not loaded again and the window stays where it stood. Neither
// ask is use: the lock counts on as if the page had asked nothing.
(function () {
  const slot = document.getElementById('recording-sent-slot');
  if (!slot || !slot.hasAttribute('data-awaited') || !window.freshPage) return;
  const address = slot.dataset.address, page = slot.dataset.page;
  const line = document.getElementById('sent-no-script');
  if (line) line.remove();
  const EVERY_MS = 1000;
  // Under the bar of the app, which stays at the top of the window.
  const BAR_PX = 80;

  // The first part of the page that begins in the window, under the bar: it is held where it stands.
  function anchorId() {
    const found = Array.from(document.querySelectorAll('#review [id]')).find(function (node) {
      const box = node.getBoundingClientRect();
      return box.height > 0 && box.top >= BAR_PX;
    });
    return found ? found.id : 'review';
  }

  function ask() {
    fetch(address, {headers: {'Accept': 'application/json'}, cache: 'no-store'})
      .then(function (reply) { return reply.ok ? reply.json() : null; })
      .then(function (found) {
        if (!found || found.state === 'awaited') { window.setTimeout(ask, EVERY_MS); return null; }
        return fetch(page, {cache: 'no-store'})
          .then(function (reply) { return reply.ok ? reply.text() : null; })
          .then(function (html) { if (!html || !window.freshPage.from(html, anchorId())) window.setTimeout(ask, 4 * EVERY_MS); });
      })
      .catch(function () { window.setTimeout(ask, 4 * EVERY_MS); });
  }
  ask();
})();
