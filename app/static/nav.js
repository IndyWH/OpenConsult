// Shared app chrome: brand wordmark, pill tabs (Today | Consultation |
// Consultations, + Users/Audit for admin), identity block with Change
// password / Sign out, and the one-line footer disclaimer.
// Injects itself at the top of <body>; hides clinical tabs from the
// receptionist (cosmetic only — the server enforces the boundary).

// The one HTML-escaper for the whole front end.
//
// Server-held text is attacker-influenced: registration is public and sets
// display_name, the patient-name field is typed by a receptionist, and the
// audit detail carries free-text reasons. Any of it that reaches innerHTML
// must render as CHARACTERS, never as markup — a stored
// `<img src=x onerror=…>` in a display name once executed in the admin's
// session on the Users page (2026-07-31 audit, Finding 1).
//
// Lives in nav.js because nav.js loads before every page's inline script,
// so one definition serves them all. Kept a plain declaration (no `window.`
// wrapper) so tests can lift it verbatim and execute it under Node.
//
// RULE: if you add an innerHTML sink, every interpolated server value goes
// through esc(). The safer habit is textContent — see the el() helper on
// the review and live pages, which needs no escaping at all.
function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

(async function () {
  const response = await fetch('/api/me');
  if (response.status === 401) { location.href = '/login'; return; }
  const me = await response.json();
  window.ME = me;

  const header = document.createElement('header');
  header.className = 'app';
  const brand = document.createElement('a');
  brand.className = 'brand'; brand.href = '/today'; brand.textContent = 'Consultation AI';
  header.appendChild(brand);

  const nav = document.createElement('nav');
  nav.className = 'tabs';
  const clinical = me.role === 'doctor' || me.role === 'admin';
  const tabs = [
    ['/today', 'Today'],
    ...(clinical ? [['/live', 'Consultation']] : []),
    ['/consultations', 'Consultations'],
    ...(me.role === 'admin' ? [['/users', 'Users'], ['/audit', 'Audit']] : []),
  ];
  for (const [href, label] of tabs) {
    const a = document.createElement('a');
    a.href = href; a.textContent = label;
    const active = location.pathname === href ||
      (href === '/live' && location.pathname.startsWith('/review'));
    if (active) a.className = 'active';
    nav.appendChild(a);
  }
  header.appendChild(nav);

  const spacer = document.createElement('div');
  spacer.className = 'spacer';
  header.appendChild(spacer);

  const who = document.createElement('div');
  who.className = 'whoami';
  const name = document.createElement('b');
  name.textContent = me.display_name;
  who.appendChild(name);
  who.appendChild(document.createTextNode(' · ' + me.role));
  who.appendChild(document.createElement('br'));
  const pw = document.createElement('a');
  pw.textContent = 'Change password';
  pw.addEventListener('click', () => openPasswordDialog());
  who.appendChild(pw);
  who.appendChild(document.createTextNode(' · '));
  const out = document.createElement('a');
  out.textContent = 'Sign out';
  out.addEventListener('click', async () => {
    await fetch('/api/logout', {method: 'POST'}); location.href = '/login';
  });
  who.appendChild(out);
  header.appendChild(who);
  document.body.prepend(header);

  if (!document.querySelector('footer.disclaimer')) {
    const foot = document.createElement('footer');
    foot.className = 'disclaimer';
    foot.textContent = 'Research/educational prototype — not a medical device. ' +
      'Synthetic consultations only. All AI output is a draft until the doctor approves it.';
    document.body.appendChild(foot);
  }

  function openPasswordDialog() {
    const dialog = document.createElement('dialog');
    dialog.innerHTML =
      '<form method="dialog" style="display:flex;flex-direction:column;gap:.55rem;min-width:280px">' +
      '<strong style="font-family:var(--serif);font-size:1rem">Change password</strong>' +
      '<input name="current" type="password" placeholder="Current password" required ' +
      'autocomplete="current-password">' +
      '<input name="next" type="password" placeholder="New password (min 8)" required ' +
      'minlength="8" autocomplete="new-password">' +
      '<div class="err pwerr"></div>' +
      '<div style="display:flex;gap:.5rem;justify-content:flex-end">' +
      '<button value="cancel" formnovalidate>Cancel</button>' +
      '<button value="save" class="primary">Save</button>' +
      '</div></form>';
    const form = dialog.querySelector('form');
    form.addEventListener('submit', async (e) => {
      if (e.submitter && e.submitter.value === 'cancel') return;
      e.preventDefault();
      const response = await fetch('/api/change-password', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({current_password: form.current.value,
                              new_password: form.next.value}),
      });
      if (response.ok) { dialog.close(); dialog.remove(); return; }
      dialog.querySelector('.pwerr').textContent =
        (await response.json()).error || 'failed';
    });
    dialog.addEventListener('close', () => dialog.remove());
    document.body.appendChild(dialog);
    dialog.showModal();
  }
  document.dispatchEvent(new CustomEvent('me-ready', {detail: me}));
})();
