// Shared tab bar: Today | Consultation | Consultations (+ Audit for admin).
// Injects itself at the top of <body>; hides clinical tabs from the
// receptionist (cosmetic only — the server enforces the boundary).
(async function () {
  const response = await fetch('/api/me');
  if (response.status === 401) { location.href = '/login'; return; }
  const me = await response.json();
  window.ME = me;

  const nav = document.createElement('nav');
  nav.style.cssText = 'display:flex;gap:.35rem;align-items:center;margin-bottom:1rem;' +
    'border-bottom:1px solid #8884;padding-bottom:.6rem;flex-wrap:wrap';
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
    a.style.cssText = 'padding:.35rem .8rem;border-radius:7px;text-decoration:none;' +
      'color:inherit;' + (active ? 'background:#1a7f3722;font-weight:600;' : '');
    nav.appendChild(a);
  }
  const who = document.createElement('span');
  who.style.cssText = 'margin-left:auto;font-size:.85rem;opacity:.7';
  who.textContent = `${me.display_name} (${me.role})`;
  nav.appendChild(who);
  const pw = document.createElement('button');
  pw.textContent = 'Change password';
  pw.style.cssText = 'font-size:.8rem;padding:.25rem .6rem;border-radius:6px;' +
    'border:1px solid #888;background:transparent;color:inherit;cursor:pointer';
  pw.addEventListener('click', () => openPasswordDialog());
  nav.appendChild(pw);
  const out = document.createElement('button');
  out.textContent = 'Log out';
  out.style.cssText = 'font-size:.8rem;padding:.25rem .6rem;border-radius:6px;' +
    'border:1px solid #888;background:transparent;color:inherit;cursor:pointer';
  out.addEventListener('click', async () => {
    await fetch('/api/logout', {method: 'POST'}); location.href = '/login';
  });
  nav.appendChild(out);
  document.body.prepend(nav);

  function openPasswordDialog() {
    const dialog = document.createElement('dialog');
    dialog.style.cssText = 'border:1px solid #8886;border-radius:8px;padding:1rem;' +
      'min-width:280px;background:Canvas;color:CanvasText';
    dialog.innerHTML =
      '<form method="dialog" style="display:flex;flex-direction:column;gap:.5rem">' +
      '<strong style="font-size:.95rem">Change password</strong>' +
      '<input name="current" type="password" placeholder="Current password" required ' +
      'autocomplete="current-password">' +
      '<input name="next" type="password" placeholder="New password (min 8)" required ' +
      'minlength="8" autocomplete="new-password">' +
      '<div style="color:#d32f2f;font-size:.82rem;min-height:1.1em" class="pwerr"></div>' +
      '<div style="display:flex;gap:.5rem;justify-content:flex-end">' +
      '<button value="cancel" formnovalidate>Cancel</button>' +
      '<button value="save" style="background:#1a7f37;border-color:#1a7f37;color:white">Save</button>' +
      '</div></form>';
    for (const input of dialog.querySelectorAll('input, button')) {
      input.style.cssText += ';padding:.4rem .6rem;border-radius:6px;border:1px solid #8886;' +
        'background:transparent;color:inherit';
    }
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
