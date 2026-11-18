// The Start screen is shown at once and its connection tests fill in
// after (spec 15.13, ruling 51). In run 9b the page showed nothing until
// the tests had answered: about 2 seconds, 10 when a service did not
// answer, with a patient in the room. The app now sends the page at once
// and runs the tests beside it. This script asks the app for their result
// and writes it into the places the page has, without loading it again:
// the Start control is offered, or says the reason with its link; and
// where the control never waited, the notice that the better transcript
// may not be made. Every sentence is the app's: this script holds none.
// The rule that no consultation begins on a connection that is down is
// kept by the app, which reads the same run when Start is pressed.
(function () {
  const box = document.getElementById('start-tests');
  if (!box) return;
  const line = document.getElementById('start-no-script');
  if (line) line.remove();
  const control = document.getElementById('start');
  const slot = document.getElementById('start-refusal');
  const waits = box.dataset.waits === 'yes';
  const EVERY_MS = 500;

  function paragraph(id, className) {
    let found = document.getElementById(id);
    if (!found) {
      found = document.createElement('p');
      found.id = id;
      if (className) found.className = className;
      slot.after(found);
    }
    return found;
  }

  function show(found) {
    if (waits) {
      slot.textContent = found.problem || '';
      control.disabled = Boolean(found.problem);
      if (found.problem && found.lead) {
        const link = document.createElement('a');
        link.href = found.lead[0];
        link.textContent = found.lead[1];
        paragraph('start-lead').replaceChildren(link);
      }
    }
    if (found.notice && !document.getElementById('start-notice')) paragraph('start-notice', 'failed').textContent = found.notice;
  }

  function ask() {
    fetch(box.dataset.address, {headers: {'Accept': 'application/json'}, cache: 'no-store'})
      .then(function (reply) { return reply.ok ? reply.json() : null; })
      .then(function (found) {
        if (found && found.state === 'answered') show(found);
        else if (found && found.state === 'gone') window.location.reload();     // the path changed or the app started again: the page is made anew
        else window.setTimeout(ask, EVERY_MS);
      })
      .catch(function () { window.setTimeout(ask, 4 * EVERY_MS); });
  }
  ask();
})();
