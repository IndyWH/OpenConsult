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
    ...(me.role === 'admin' ? [['/audit', 'Audit']] : []),
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
  const out = document.createElement('button');
  out.textContent = 'Log out';
  out.style.cssText = 'font-size:.8rem;padding:.25rem .6rem;border-radius:6px;' +
    'border:1px solid #888;background:transparent;cursor:pointer';
  out.addEventListener('click', async () => {
    await fetch('/api/logout', {method: 'POST'}); location.href = '/login';
  });
  nav.appendChild(out);
  document.body.prepend(nav);
  document.dispatchEvent(new CustomEvent('me-ready', {detail: me}));
})();
