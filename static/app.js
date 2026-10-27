// LinkForge — Client Application Logic
(function () {
  'use strict';

  // --- State ---
  let state = {
    links: [],
    summary: { total_links: 0, total_clicks: 0, active_links: 0, expired_links: 0, disabled_links: 0, campaigns: [] },
    baseUrl: window.location.origin,
    authRequired: false,
    authenticated: true,
    activeModal: null,
    currentAnalyticsCode: null,
    deleteTargetCode: null,
  };

  // --- DOM Elements ---
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => document.querySelectorAll(selector);

  const els = {
    linksBody: $('#links-body'),
    linksTable: $('#links-table'),
    emptyState: $('#empty-state'),
    filterEmptyState: $('#filter-empty-state'),
    emptyCreateBtn: $('#empty-create-btn'),
    resetFiltersBtn: $('#reset-filters-btn'),
    filteredBadge: $('#filtered-badge'),
    loadErrorMessage: $('#load-error-message'),

    // Search and Filters
    searchInput: $('#search-input'),
    searchClearBtn: $('#search-clear-btn'),
    filterStatus: $('#filter-status'),
    filterCampaign: $('#filter-campaign'),
    sortBy: $('#sort-by'),
    refreshButton: $('#refresh-button'),

    // KPI Summary
    summaryTotalLinks: $('#summary-total-links'),
    summaryTotalClicks: $('#summary-total-clicks'),
    summaryActiveLinks: $('#summary-active-links'),
    summaryInactiveLinks: $('#summary-inactive-links'),

    // Config & Auth
    originPrefix: $('#origin-prefix'),
    createOriginSlugPrefix: $('#create-origin-slug-prefix'),
    authButton: $('#auth-button'),
    authIcon: $('#auth-icon'),

    // Modals
    openCreateModalBtn: $('#open-create-modal-btn'),
    createModal: $('#create-modal'),
    createForm: $('#create-form'),
    createUrl: $('#create-url'),
    createAlias: $('#create-alias'),
    createTitle: $('#create-title'),
    createCampaign: $('#create-campaign'),
    createExpires: $('#create-expires'),
    createErrorMessage: $('#create-error-message'),
    createSubmitBtn: $('#create-submit-btn'),

    editModal: $('#edit-modal'),
    editForm: $('#edit-form'),
    editSlugDisplay: $('#edit-slug-display'),
    editCodeHidden: $('#edit-code-hidden'),
    editUrl: $('#edit-url'),
    editTitle: $('#edit-title'),
    editCampaign: $('#edit-campaign'),
    editExpires: $('#edit-expires'),
    clearEditExpiresBtn: $('#clear-edit-expires-btn'),
    editIsActive: $('#edit-is-active'),
    editErrorMessage: $('#edit-error-message'),
    editSubmitBtn: $('#edit-submit-btn'),

    qrModal: $('#qr-modal'),
    qrImg: $('#qr-img'),
    qrShortUrl: $('#qr-short-url'),
    qrCopyBtn: $('#qr-copy-btn'),
    qrDownloadLink: $('#qr-download-link'),

    analyticsModal: $('#analytics-modal'),
    analyticsSlugDisplay: $('#analytics-slug-display'),
    analyticsDestinationLink: $('#analytics-destination-link'),
    analyticsStatusBadge: $('#analytics-status-badge'),
    analyticsCreatedDate: $('#analytics-created-date'),
    analyticsExpiresDate: $('#analytics-expires-date'),
    analyticsTotalClicks: $('#analytics-total-clicks'),
    analyticsTopReferrer: $('#analytics-top-referrer'),
    analyticsTopDevice: $('#analytics-top-device'),
    clicksChartSvg: $('#clicks-chart-svg'),
    chartEmptyState: $('#chart-empty-state'),
    referrersList: $('#referrers-list'),
    devicesList: $('#devices-list'),
    recentClicksTbody: $('#recent-clicks-tbody'),
    recentClicksEmpty: $('#recent-clicks-empty'),

    deleteModal: $('#delete-modal'),
    deleteSlugDisplay: $('#delete-slug-display'),
    confirmDeleteBtn: $('#confirm-delete-btn'),

    authModal: $('#auth-modal'),
    authForm: $('#auth-form'),
    adminKeyInput: $('#admin-key-input'),
    authErrorMsg: $('#auth-error-msg'),

    toast: $('#toast'),
  };

  let toastTimeout;
  function showToast(message) {
    if (!els.toast) return;
    els.toast.textContent = message;
    els.toast.classList.add('show');
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => els.toast.classList.remove('show'), 2400);
  }

  // --- API Client ---
  async function api(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    const savedKey = sessionStorage.getItem('linkforge_admin_key');
    if (savedKey) {
      headers['X-Admin-Key'] = savedKey;
    }

    const response = await fetch(path, {
      ...options,
      headers,
    });

    if (response.status === 204) {
      return null;
    }

    let body = null;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      try {
        body = await response.json();
      } catch (_) {}
    }

    if (!response.ok) {
      const message = (body && body.detail) ? body.detail : `Request failed (${response.status})`;
      const error = new Error(message);
      error.status = response.status;
      error.data = body;
      throw error;
    }

    return body;
  }

  // --- Modal Utilities ---
  function openModal(modalEl) {
    if (state.activeModal) {
      closeModal(state.activeModal);
    }
    modalEl.hidden = false;
    state.activeModal = modalEl;
    document.body.style.overflow = 'hidden';
  }

  function closeModal(modalEl) {
    if (!modalEl) return;
    modalEl.hidden = true;
    if (state.activeModal === modalEl) {
      state.activeModal = null;
      document.body.style.overflow = '';
    }
    if (modalEl === els.analyticsModal && window.location.pathname.startsWith('/analytics/')) {
      window.history.pushState({}, '', '/');
    }
  }

  // Close modals when clicking close buttons or background overlay
  document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-close-btn') || e.target.classList.contains('modal-cancel-btn')) {
      const modal = e.target.closest('.modal-overlay');
      if (modal) closeModal(modal);
    } else if (e.target.classList.contains('modal-overlay')) {
      closeModal(e.target);
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && state.activeModal) {
      closeModal(state.activeModal);
    }
  });

  // --- Date & Formatting Helpers ---
  function formatDate(isoString) {
    if (!isoString) return '—';
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return '—';
    return new Intl.DateTimeFormat(undefined, {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(date);
  }

  function formatDateTime(isoString) {
    if (!isoString) return '—';
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return '—';
    return new Intl.DateTimeFormat(undefined, {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  }

  function toLocalDatetimeInput(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return '';
    const pad = (n) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  async function copyText(text, label = 'Copied to clipboard.') {
    try {
      await navigator.clipboard.writeText(text);
      showToast(label);
    } catch (_) {
      window.prompt('Copy short link:', text);
    }
  }

  // --- Rendering Functions ---

  function renderStatusBadge(status) {
    const badge = document.createElement('span');
    badge.className = `badge badge-${status}`;
    const dot = document.createElement('span');
    dot.className = 'dot';
    badge.append(dot);

    let text = 'Active';
    if (status === 'expired') text = 'Expired';
    if (status === 'disabled') text = 'Paused';

    badge.append(document.createTextNode(` ${text}`));
    return badge;
  }

  function renderTableRow(link) {
    const tr = document.createElement('tr');
    tr.dataset.code = link.code;

    // 1. Title & Destination
    const tdTitle = document.createElement('td');
    tdTitle.className = 'title-destination-cell';

    const titleEl = document.createElement('span');
    titleEl.className = 'link-title-text';
    titleEl.textContent = link.title || link.code;
    tdTitle.append(titleEl);

    const destLink = document.createElement('a');
    destLink.className = 'destination-subtext';
    destLink.href = link.url;
    destLink.target = '_blank';
    destLink.rel = 'noopener noreferrer';
    destLink.textContent = link.url;
    destLink.title = `Destination: ${link.url}`;
    tdTitle.append(destLink);

    if (link.campaign) {
      const campTag = document.createElement('span');
      campTag.className = 'campaign-tag';
      campTag.textContent = `#${link.campaign}`;
      tdTitle.append(campTag);
    }
    tr.append(tdTitle);

    // 2. Short Link
    const tdShort = document.createElement('td');
    tdShort.className = 'short-link-cell';
    const shortWrap = document.createElement('div');
    shortWrap.className = 'short-link-wrap';

    const shortLink = document.createElement('a');
    shortLink.className = 'short-url-link';
    shortLink.href = link.short_url;
    shortLink.target = '_blank';
    shortLink.rel = 'noopener noreferrer';
    shortLink.textContent = link.short_url.replace(/^https?:\/\//, '');
    shortWrap.append(shortLink);

    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-mini-btn';
    copyBtn.type = 'button';
    copyBtn.title = 'Copy short link';
    copyBtn.textContent = 'Copy';
    copyBtn.addEventListener('click', () => copyText(link.short_url, 'Short link copied.'));
    shortWrap.append(copyBtn);

    tdShort.append(shortWrap);
    tr.append(tdShort);

    // 3. Status Badge
    const tdStatus = document.createElement('td');
    tdStatus.append(renderStatusBadge(link.status));
    tr.append(tdStatus);

    // 4. Click Count
    const tdClicks = document.createElement('td');
    const clicksSpan = document.createElement('span');
    clicksSpan.className = 'click-number';
    clicksSpan.textContent = Number(link.clicks).toLocaleString();
    tdClicks.append(clicksSpan);
    tr.append(tdClicks);

    // 5. Schedule (Created & Expiration)
    const tdSchedule = document.createElement('td');
    tdSchedule.className = 'schedule-cell';
    const createdSpan = document.createElement('span');
    createdSpan.textContent = formatDate(link.created_at);
    tdSchedule.append(createdSpan);

    if (link.expires_at) {
      const expiresSpan = document.createElement('span');
      expiresSpan.className = 'schedule-expires';
      expiresSpan.textContent = link.is_expired ? `Expired ${formatDate(link.expires_at)}` : `Exp: ${formatDate(link.expires_at)}`;
      tdSchedule.append(expiresSpan);
    }
    tr.append(tdSchedule);

    // 6. Action Buttons
    const tdActions = document.createElement('td');
    tdActions.className = 'text-right';
    const actionsWrap = document.createElement('div');
    actionsWrap.className = 'row-actions';

    // Analytics button
    const analyticsBtn = document.createElement('button');
    analyticsBtn.className = 'action-btn analytics-btn';
    analyticsBtn.type = 'button';
    analyticsBtn.title = 'View click analytics';
    analyticsBtn.innerHTML = '<span aria-hidden="true">📊</span> Analytics';
    analyticsBtn.addEventListener('click', () => openAnalytics(link.code));
    actionsWrap.append(analyticsBtn);

    // QR Code button
    const qrBtn = document.createElement('button');
    qrBtn.className = 'action-btn';
    qrBtn.type = 'button';
    qrBtn.title = 'Generate QR code';
    qrBtn.innerHTML = '<span aria-hidden="true">▦</span> QR';
    qrBtn.addEventListener('click', () => openQrModal(link));
    actionsWrap.append(qrBtn);

    // Edit button
    const editBtn = document.createElement('button');
    editBtn.className = 'action-btn';
    editBtn.type = 'button';
    editBtn.title = 'Edit link metadata';
    editBtn.innerHTML = '<span aria-hidden="true">✎</span> Edit';
    editBtn.addEventListener('click', () => openEditModal(link));
    actionsWrap.append(editBtn);

    // Toggle Active / Pause button
    const toggleBtn = document.createElement('button');
    toggleBtn.className = 'action-btn';
    toggleBtn.type = 'button';
    toggleBtn.title = link.is_active ? 'Pause routing for this link' : 'Resume routing for this link';
    toggleBtn.innerHTML = link.is_active ? '<span aria-hidden="true">⏸</span>' : '<span aria-hidden="true">▶</span>';
    toggleBtn.addEventListener('click', () => handleToggleLink(link.code));
    actionsWrap.append(toggleBtn);

    // Delete button
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'action-btn danger';
    deleteBtn.type = 'button';
    deleteBtn.title = 'Delete link permanently';
    deleteBtn.innerHTML = '<span aria-hidden="true">🗑</span>';
    deleteBtn.addEventListener('click', () => openDeleteModal(link.code));
    actionsWrap.append(deleteBtn);

    tdActions.append(actionsWrap);
    tr.append(tdActions);

    return tr;
  }

  function updateCampaignDropdown(campaigns) {
    const currentVal = els.filterCampaign.value;
    els.filterCampaign.innerHTML = '<option value="all">All campaigns</option>';
    if (Array.isArray(campaigns)) {
      campaigns.forEach((camp) => {
        if (!camp) return;
        const opt = document.createElement('option');
        opt.value = camp;
        opt.textContent = camp;
        els.filterCampaign.append(opt);
      });
    }
    if (campaigns && campaigns.includes(currentVal)) {
      els.filterCampaign.value = currentVal;
    }
  }

  function renderLinks() {
    els.linksBody.innerHTML = '';
    const totalLinks = state.summary.total_links || 0;
    const currentList = state.links || [];

    els.filteredBadge.textContent = currentList.length.toLocaleString();

    if (totalLinks === 0) {
      els.linksTable.hidden = true;
      els.emptyState.hidden = false;
      els.filterEmptyState.hidden = true;
      return;
    }

    if (currentList.length === 0) {
      els.linksTable.hidden = true;
      els.emptyState.hidden = true;
      els.filterEmptyState.hidden = false;
      return;
    }

    els.linksTable.hidden = false;
    els.emptyState.hidden = true;
    els.filterEmptyState.hidden = true;

    const fragment = document.createDocumentFragment();
    currentList.forEach((link) => {
      fragment.append(renderTableRow(link));
    });
    els.linksBody.append(fragment);
  }

  function updateSummaryCards(summary) {
    els.summaryTotalLinks.textContent = Number(summary.total_links || 0).toLocaleString();
    els.summaryTotalClicks.textContent = Number(summary.total_clicks || 0).toLocaleString();
    els.summaryActiveLinks.textContent = Number(summary.active_links || 0).toLocaleString();
    const inactive = (summary.expired_links || 0) + (summary.disabled_links || 0);
    els.summaryInactiveLinks.textContent = Number(inactive).toLocaleString();
  }

  // --- Data Loading ---
  async function loadLinks() {
    els.loadErrorMessage.hidden = true;
    els.loadErrorMessage.textContent = '';

    const params = new URLSearchParams();
    const search = els.searchInput.value.trim();
    if (search) params.set('search', search);

    const status = els.filterStatus.value;
    if (status && status !== 'all') params.set('status', status);

    const campaign = els.filterCampaign.value;
    if (campaign && campaign !== 'all') params.set('campaign', campaign);

    const sort = els.sortBy.value;
    if (sort) params.set('sort', sort);

    try {
      const data = await api(`/api/links?${params.toString()}`);
      state.links = data.links;
      state.summary = data.summary;
      updateSummaryCards(state.summary);
      updateCampaignDropdown(state.summary.campaigns);
      renderLinks();
    } catch (err) {
      els.loadErrorMessage.hidden = false;
      els.loadErrorMessage.textContent = `Error loading links: ${err.message}`;
    }
  }

  // --- Create Link Handler ---
  els.openCreateModalBtn.addEventListener('click', () => {
    els.createErrorMessage.hidden = true;
    els.createForm.reset();
    openModal(els.createModal);
    els.createUrl.focus();
  });

  if (els.emptyCreateBtn) {
    els.emptyCreateBtn.addEventListener('click', () => {
      els.createErrorMessage.hidden = true;
      els.createForm.reset();
      openModal(els.createModal);
      els.createUrl.focus();
    });
  }

  els.createForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    els.createErrorMessage.hidden = true;
    els.createSubmitBtn.disabled = true;

    const payload = {
      url: els.createUrl.value.trim(),
    };

    const alias = els.createAlias.value.trim();
    if (alias) payload.custom_alias = alias;

    const title = els.createTitle.value.trim();
    if (title) payload.title = title;

    const campaign = els.createCampaign.value.trim();
    if (campaign) payload.campaign = campaign;

    const expires = els.createExpires.value;
    if (expires) {
      payload.expires_at = new Date(expires).toISOString();
    }

    try {
      const res = await api('/api/links', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      closeModal(els.createModal);
      showToast(`Forged short link: ${res.link.short_url}`);
      await loadLinks();
    } catch (err) {
      els.createErrorMessage.hidden = false;
      els.createErrorMessage.textContent = err.message;
    } finally {
      els.createSubmitBtn.disabled = false;
    }
  });

  // --- Edit Link Handler ---
  function openEditModal(link) {
    els.editErrorMessage.hidden = true;
    els.editCodeHidden.value = link.code;
    els.editSlugDisplay.textContent = `/${link.code}`;
    els.editUrl.value = link.url;
    els.editTitle.value = link.title || '';
    els.editCampaign.value = link.campaign || '';
    els.editExpires.value = link.expires_at ? toLocalDatetimeInput(link.expires_at) : '';
    els.editIsActive.checked = Boolean(link.is_active);

    openModal(els.editModal);
    els.editUrl.focus();
  }

  els.clearEditExpiresBtn.addEventListener('click', () => {
    els.editExpires.value = '';
  });

  els.editForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    els.editErrorMessage.hidden = true;
    els.editSubmitBtn.disabled = true;

    const code = els.editCodeHidden.value;
    const expiresVal = els.editExpires.value;

    const payload = {
      url: els.editUrl.value.trim(),
      title: els.editTitle.value.trim(),
      campaign: els.editCampaign.value.trim(),
      expires_at: expiresVal ? new Date(expiresVal).toISOString() : '',
      is_active: els.editIsActive.checked,
    };

    try {
      await api(`/api/links/${encodeURIComponent(code)}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });

      closeModal(els.editModal);
      showToast('Link settings updated.');
      await loadLinks();
    } catch (err) {
      els.editErrorMessage.hidden = false;
      els.editErrorMessage.textContent = err.message;
    } finally {
      els.editSubmitBtn.disabled = false;
    }
  });

  // --- Toggle Active Link ---
  async function handleToggleLink(code) {
    try {
      const res = await api(`/api/links/${encodeURIComponent(code)}/toggle`, {
        method: 'POST',
      });
      showToast(`Link is now ${res.link.is_active ? 'active' : 'paused'}.`);
      await loadLinks();
    } catch (err) {
      showToast(`Error: ${err.message}`);
    }
  }

  // --- Delete Link Handler ---
  function openDeleteModal(code) {
    state.deleteTargetCode = code;
    els.deleteSlugDisplay.textContent = `/${code}`;
    openModal(els.deleteModal);
  }

  els.confirmDeleteBtn.addEventListener('click', async () => {
    if (!state.deleteTargetCode) return;
    els.confirmDeleteBtn.disabled = true;

    try {
      await api(`/api/links/${encodeURIComponent(state.deleteTargetCode)}`, {
        method: 'DELETE',
      });
      closeModal(els.deleteModal);
      showToast('Link permanently deleted.');
      state.deleteTargetCode = null;
      await loadLinks();
    } catch (err) {
      showToast(`Delete failed: ${err.message}`);
    } finally {
      els.confirmDeleteBtn.disabled = false;
    }
  });

  // --- QR Code Modal ---
  function openQrModal(link) {
    const qrUrl = `/api/links/${encodeURIComponent(link.code)}/qr`;
    els.qrImg.src = qrUrl;
    els.qrShortUrl.textContent = link.short_url;
    els.qrDownloadLink.href = `${qrUrl}?download=true`;
    els.qrCopyBtn.onclick = () => copyText(link.short_url, 'Short link copied.');

    openModal(els.qrModal);
  }

  // --- Analytics Modal & SVG Chart ---
  async function openAnalytics(code) {
    state.currentAnalyticsCode = code;
    els.analyticsSlugDisplay.textContent = `/${code}`;

    openModal(els.analyticsModal);
    window.history.pushState({}, '', `/analytics/${code}`);

    try {
      const data = await api(`/api/links/${encodeURIComponent(code)}/analytics`);
      renderAnalyticsView(data);
    } catch (err) {
      showToast(`Could not load analytics: ${err.message}`);
    }
  }

  function renderAnalyticsView(data) {
    const link = data.link;

    // Header meta
    els.analyticsDestinationLink.href = link.url;
    els.analyticsDestinationLink.textContent = link.url;
    els.analyticsDestinationLink.title = link.url;

    els.analyticsStatusBadge.className = `badge badge-${link.status}`;
    els.analyticsStatusBadge.textContent = link.status.toUpperCase();

    els.analyticsCreatedDate.textContent = formatDate(link.created_at);
    els.analyticsExpiresDate.textContent = link.expires_at ? formatDate(link.expires_at) : 'Never';

    // KPIs
    els.analyticsTotalClicks.textContent = Number(data.total_clicks).toLocaleString();

    const topRef = (data.referrers && data.referrers.length > 0) ? data.referrers[0].referrer : 'None yet';
    els.analyticsTopReferrer.textContent = topRef;

    const topDev = (data.devices && data.devices.length > 0) ? data.devices[0].device : 'None yet';
    els.analyticsTopDevice.textContent = topDev;

    // Chart
    renderClicksChart(data.clicks_by_date || []);

    // Referrers List
    renderBreakdownList(els.referrersList, data.referrers || [], 'referrer', 'Direct / None');

    // Devices List
    renderBreakdownList(els.devicesList, data.devices || [], 'device', 'Desktop');

    // Recent Activity Table
    renderRecentClicks(data.recent_clicks || []);
  }

  function renderClicksChart(clicksByDate) {
    const svg = els.clicksChartSvg;
    svg.innerHTML = '';

    if (!clicksByDate || clicksByDate.length === 0) {
      els.chartEmptyState.hidden = false;
      return;
    }
    els.chartEmptyState.hidden = true;

    const width = 600;
    const height = 180;
    const padding = { top: 20, right: 20, bottom: 35, left: 40 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const maxCount = Math.max(...clicksByDate.map((d) => d.count), 1);
    const numBars = clicksByDate.length;
    const barWidth = Math.min(36, Math.max(12, (chartW / numBars) - 10));
    const step = chartW / numBars;

    // Draw horizontal grid lines
    const gridY = [0, 0.5, 1];
    gridY.forEach((ratio) => {
      const y = padding.top + chartH * (1 - ratio);
      const val = Math.round(maxCount * ratio);

      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', padding.left);
      line.setAttribute('y1', y);
      line.setAttribute('x2', width - padding.right);
      line.setAttribute('y2', y);
      line.setAttribute('stroke', '#242a42');
      line.setAttribute('stroke-dasharray', '3,3');
      svg.append(line);

      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.setAttribute('x', padding.left - 8);
      label.setAttribute('y', y + 3);
      label.setAttribute('fill', '#8c94b0');
      label.setAttribute('font-size', '10');
      label.setAttribute('font-family', 'DM Mono, monospace');
      label.setAttribute('text-anchor', 'end');
      label.textContent = val;
      svg.append(label);
    });

    // Draw bars
    clicksByDate.forEach((item, idx) => {
      const x = padding.left + idx * step + (step - barWidth) / 2;
      const barH = (item.count / maxCount) * chartH;
      const y = padding.top + chartH - barH;

      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', x);
      rect.setAttribute('y', y);
      rect.setAttribute('width', barWidth);
      rect.setAttribute('height', Math.max(barH, 3));
      rect.setAttribute('fill', '#8b7dff');
      rect.setAttribute('rx', '4');

      const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
      title.textContent = `${item.date}: ${item.count} click${item.count === 1 ? '' : 's'}`;
      rect.append(title);
      svg.append(rect);

      // Value label on top of bar
      if (barH > 15) {
        const valText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        valText.setAttribute('x', x + barWidth / 2);
        valText.setAttribute('y', y - 4);
        valText.setAttribute('fill', '#eef2fa');
        valText.setAttribute('font-size', '9');
        valText.setAttribute('font-weight', '700');
        valText.setAttribute('font-family', 'DM Mono, monospace');
        valText.setAttribute('text-anchor', 'middle');
        valText.textContent = item.count;
        svg.append(valText);
      }

      // Date label below axis
      const dateText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      dateText.setAttribute('x', x + barWidth / 2);
      dateText.setAttribute('y', height - 12);
      dateText.setAttribute('fill', '#8c94b0');
      dateText.setAttribute('font-size', '9');
      dateText.setAttribute('font-family', 'DM Mono, monospace');
      dateText.setAttribute('text-anchor', 'middle');
      // Format YYYY-MM-DD -> MM/DD
      const shortDate = item.date.length >= 10 ? item.date.slice(5) : item.date;
      dateText.textContent = shortDate;
      svg.append(dateText);
    });
  }

  function renderBreakdownList(container, items, keyName, emptyDefault) {
    container.innerHTML = '';
    if (!items || items.length === 0) {
      const p = document.createElement('p');
      p.className = 'table-empty-sub';
      p.textContent = `No data recorded yet.`;
      container.append(p);
      return;
    }

    items.forEach((item) => {
      const row = document.createElement('div');
      row.className = 'breakdown-item';

      const info = document.createElement('div');
      info.className = 'breakdown-info';

      const name = document.createElement('span');
      name.className = 'breakdown-name';
      name.textContent = item[keyName] || emptyDefault;
      info.append(name);

      const count = document.createElement('span');
      count.className = 'breakdown-count';
      count.textContent = `${item.count} (${item.percentage}%)`;
      info.append(count);

      const track = document.createElement('div');
      track.className = 'progress-track';
      const fill = document.createElement('div');
      fill.className = 'progress-fill';
      fill.style.width = `${Math.min(100, Math.max(0, item.percentage))}%`;
      track.append(fill);

      row.append(info, track);
      container.append(row);
    });
  }

  function renderRecentClicks(recentClicks) {
    els.recentClicksTbody.innerHTML = '';
    if (!recentClicks || recentClicks.length === 0) {
      els.recentClicksEmpty.hidden = false;
      return;
    }
    els.recentClicksEmpty.hidden = true;

    recentClicks.forEach((click) => {
      const tr = document.createElement('tr');

      const tdTime = document.createElement('td');
      tdTime.textContent = formatDateTime(click.clicked_at);
      tr.append(tdTime);

      const tdIp = document.createElement('td');
      const ipBadge = document.createElement('code');
      ipBadge.className = 'ip-badge';
      ipBadge.textContent = click.ip_address || '127.0.0.1';
      tdIp.append(ipBadge);
      tr.append(tdIp);

      const tdDev = document.createElement('td');
      tdDev.textContent = click.device_name || click.device || 'Desktop';
      tr.append(tdDev);

      const tdRef = document.createElement('td');
      tdRef.textContent = click.referrer || 'Direct / None';
      tr.append(tdRef);

      els.recentClicksTbody.append(tr);
    });
  }

  // --- Search & Filter Events ---
  let searchDebounce;
  els.searchInput.addEventListener('input', () => {
    els.searchClearBtn.hidden = !els.searchInput.value;
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(loadLinks, 200);
  });

  els.searchClearBtn.addEventListener('click', () => {
    els.searchInput.value = '';
    els.searchClearBtn.hidden = true;
    loadLinks();
    els.searchInput.focus();
  });

  els.filterStatus.addEventListener('change', loadLinks);
  els.filterCampaign.addEventListener('change', loadLinks);
  els.sortBy.addEventListener('change', loadLinks);
  els.refreshButton.addEventListener('click', loadLinks);

  if (els.resetFiltersBtn) {
    els.resetFiltersBtn.addEventListener('click', () => {
      els.searchInput.value = '';
      els.searchClearBtn.hidden = true;
      els.filterStatus.value = 'all';
      els.filterCampaign.value = 'all';
      els.sortBy.value = 'newest';
      loadLinks();
    });
  }

  // --- Auth Management ---
  async function checkAuthStatus() {
    try {
      const res = await api('/api/auth/status');
      state.authRequired = res.auth_required;
      state.authenticated = res.authenticated;

      if (state.authRequired) {
        els.authButton.hidden = false;
        els.authIcon.textContent = state.authenticated ? '🔓' : '🔒';
        els.authButton.title = state.authenticated ? 'Admin authenticated' : 'Admin key required';
      } else {
        els.authButton.hidden = true;
      }
    } catch (_) {}
  }

  els.authButton.addEventListener('click', () => {
    els.authErrorMsg.hidden = true;
    els.adminKeyInput.value = '';
    openModal(els.authModal);
  });

  els.authForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const key = els.adminKeyInput.value.trim();
    els.authErrorMsg.hidden = true;

    try {
      await api('/api/auth/verify', {
        method: 'POST',
        body: JSON.stringify({ key }),
      });
      sessionStorage.setItem('linkforge_admin_key', key);
      closeModal(els.authModal);
      showToast('Admin authenticated successfully.');
      await checkAuthStatus();
      await loadLinks();
    } catch (err) {
      els.authErrorMsg.hidden = false;
      els.authErrorMsg.textContent = err.message;
    }
  });

  // --- App Initialization ---
  async function init() {
    try {
      const config = await api('/api/config');
      state.baseUrl = config.base_url;
      const cleanHost = config.base_url.replace(/^https?:\/\//, '').replace(/\/$/, '');
      els.originPrefix.textContent = cleanHost;
      els.createOriginSlugPrefix.textContent = `${cleanHost}/`;
    } catch (_) {
      els.originPrefix.textContent = window.location.host;
      els.createOriginSlugPrefix.textContent = `${window.location.host}/`;
    }

    await checkAuthStatus();
    await loadLinks();

    // Check if initial URL is an analytics view (e.g. /analytics/code)
    const match = window.location.pathname.match(/^\/analytics\/([a-zA-Z0-9_-]+)$/);
    if (match && match[1]) {
      openAnalytics(match[1]);
    }
  }

  // Handle browser back/forward buttons
  window.addEventListener('popstate', () => {
    const match = window.location.pathname.match(/^\/analytics\/([a-zA-Z0-9_-]+)$/);
    if (match && match[1]) {
      openAnalytics(match[1]);
    } else if (state.activeModal === els.analyticsModal) {
      closeModal(els.analyticsModal);
    }
  });

  init();
})();
