// The earlier-notes panel (spec 15.11 ruling 4): one line per note, the
// whole approved note one press away, folded again by a second press. The
// notes and every word are rendered by the app; this only shows and hides.
(function () {
  const panel = document.getElementById('earlier-notes');
  if (!panel) return;
  panel.querySelectorAll('button.note-line').forEach(function (button) {
    button.addEventListener('click', function () {
      const body = document.getElementById(button.getAttribute('aria-controls'));
      if (!body) return;
      const open = body.hidden;
      body.hidden = !open;
      button.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  });
})();
