const form = document.querySelector('#create-form');
const urlInput = document.querySelector('#url-input');
const aliasInput = document.querySelector('#alias-input');
const formMessage = document.querySelector('#form-message');
const linksBody = document.querySelector('#links-body');
const emptyState = document.querySelector('#empty-state');
const loadMessage = document.querySelector('#load-message');
const toast = document.querySelector('#toast');
let toastTimer;


function showToast(message) {
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2200);
}

function setFormMessage(message, isError = false) {
  formMessage.textContent = message;
  formMessage.classList.toggle('error', isError);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch (_) { /* Response did not contain JSON. */ }
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function makeCell(className) {
  const td = document.createElement('td');
  if (className) td.className = className;
  return td;
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown';
  return new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' }).format(date);
}

function safeExternalLink(url, label, className) {
  const anchor = el('a', className, label);
  anchor.href = url;
  anchor.target = '_blank';
  anchor.rel = 'noopener noreferrer';
  return anchor;
}

function renderLink(link) {
  const row = document.createElement('tr');

  const shortCell = makeCell('short-cell');
  const shortLink = safeExternalLink(link.short_url, link.short_url.replace(/^https?:\/\//, ''), 'short-link');
  shortCell.append(shortLink);
  row.append(shortCell);

  const destinationCell = makeCell('destination-cell');
  const destination = safeExternalLink(link.url, link.url, 'destination');
  destination.title = link.url;
  destinationCell.append(destination);
  row.append(destinationCell);

  const clicksCell = makeCell();
  clicksCell.append(el('span', 'click-count', Number(link.clicks).toLocaleString()));
  row.append(clicksCell);

  const dateCell = makeCell();
  dateCell.append(el('span', 'date-text', formatDate(link.created_at)));
  row.append(dateCell);

  const actionsCell = makeCell();
  const actionWrap = el('div', 'action-wrap');
  const copy = el('button', 'copy-button', 'Copy');
  copy.type = 'button';
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(link.short_url);
      showToast('Short link copied.');
    } catch (_) {
      window.prompt('Copy your short link:', link.short_url);
    }
  });
  const remove = el('button', 'delete-button', 'Delete');
  remove.type = 'button';
  remove.setAttribute('aria-label', `Delete short link ${link.code}`);
  remove.addEventListener('click', async () => {
    if (!window.confirm(`Delete ${link.short_url}? This cannot be undone.`)) return;
    remove.disabled = true;
    try {
      await api(`/api/links/${encodeURIComponent(link.code)}`, { method: 'DELETE' });
      showToast('Link deleted.');
      await loadLinks();
    } catch (error) {
      showToast(error.message);
      remove.disabled = false;
    }
  });
  actionWrap.append(copy, remove);
  actionsCell.append(actionWrap);
  row.append(actionsCell);
  return row;
}

async function loadLinks() {
  loadMessage.textContent = '';
  try {
    const data = await api('/api/links');
    linksBody.replaceChildren(...data.links.map(renderLink));
    document.querySelector('#total-links').textContent = data.total_links.toLocaleString();
    document.querySelector('#total-clicks').textContent = data.total_clicks.toLocaleString();
    document.querySelector('#link-count').textContent = data.total_links.toLocaleString();
    emptyState.hidden = data.links.length > 0;
    document.querySelector('table').hidden = data.links.length === 0;
  } catch (error) {
    loadMessage.textContent = `Could not load links: ${error.message}`;
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  setFormMessage('');
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  const buttonLabel = button.querySelector('span');
  const oldLabel = buttonLabel.textContent;
  buttonLabel.textContent = 'Creating…';
  try {
    const payload = { url: urlInput.value.trim() };
    if (aliasInput.value.trim()) payload.custom_alias = aliasInput.value.trim();
    const data = await api('/api/links', { method: 'POST', body: JSON.stringify(payload) });
    setFormMessage(`Created ${data.link.short_url}`);
    aliasInput.value = '';
    urlInput.value = '';
    await loadLinks();
    showToast('Your link is ready.');
  } catch (error) {
    setFormMessage(error.message, true);
  } finally {
    button.disabled = false;
    buttonLabel.textContent = oldLabel;
  }
});

document.querySelector('#refresh-button').addEventListener('click', loadLinks);

async function initialize() {
  try {
    const config = await api('/api/config');
    const host = config.base_url.replace(/^https?:\/\//, '').replace(/\/$/, '');
    document.querySelector('#origin-prefix').textContent = `${host}/`;
  } catch (_) {
    document.querySelector('#origin-prefix').textContent = `${window.location.host}/`;
  }
  await loadLinks();
}

initialize();
