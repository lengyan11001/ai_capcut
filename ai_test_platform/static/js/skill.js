// skill.js - 能力库模块

var capabilityListCache = [];
var capabilityViewEntries = [];
var currentCapabilityId = '';
var currentCapabilityEntry = null;
var currentCapabilityCallLogs = [];
var currentCapabilityChatLogs = [];

function buildCapabilityViewEntries(rawList) {
  var raw = Array.isArray(rawList) ? rawList.slice() : [];
  var sutuiCaps = raw.filter(function(x) { return String((x && x.upstream) || '').toLowerCase() === 'sutui'; });
  var others = raw.filter(function(x) { return String((x && x.upstream) || '').toLowerCase() !== 'sutui'; });
  var out = [];
  if (sutuiCaps.length) {
    var primary = sutuiCaps.find(function(x) { return (x.capability_id || '') === 'image.generate'; }) || sutuiCaps[0];
    out.push({
      entry_id: 'sutui.material',
      display_id: 'SUTUI.MATERIAL',
      display_name: '素材生成',
      description: '图片生成与任务查询（统一入口）',
      member_ids: sutuiCaps.map(function(x) { return x.capability_id; }),
      primary_id: primary.capability_id,
      is_default: true,
      unit_credits: Number(primary.unit_credits || 0),
      upstream: 'sutui',
      is_group: true
    });
  }
  others.forEach(function(cap) {
    out.push({
      entry_id: cap.capability_id,
      display_id: String(cap.capability_id || '').toUpperCase(),
      display_name: cap.description || cap.capability_id,
      description: cap.description || cap.capability_id,
      member_ids: [cap.capability_id],
      primary_id: cap.capability_id,
      is_default: !!cap.is_default,
      unit_credits: Number(cap.unit_credits || 0),
      upstream: cap.upstream || '',
      is_group: false
    });
  });
  return out;
}

function getCurrentCapabilityMemberIds() {
  if (currentCapabilityEntry && Array.isArray(currentCapabilityEntry.member_ids) && currentCapabilityEntry.member_ids.length) {
    return currentCapabilityEntry.member_ids.slice();
  }
  return currentCapabilityId ? [currentCapabilityId] : [];
}

function getCurrentCapabilityContextId() {
  if (currentCapabilityEntry && currentCapabilityEntry.primary_id) return currentCapabilityEntry.primary_id;
  return currentCapabilityId || null;
}

function renderCapabilityNavItems(list) {
  var wrap = document.getElementById('navCapabilityItems');
  if (!wrap) return;
  if (!Array.isArray(list) || !list.length) {
    wrap.innerHTML = '<div class="meta" style="padding:0.4rem 0.6rem;">暂无其他能力</div>';
    return;
  }
  var rows = list.map(function(cap) {
    var cid = cap.entry_id || '';
    var text = cap.display_name || cid;
    return '<div class="nav-left-item" data-view="skill-capability" data-dynamic-capability="1" data-capability-id="' + escapeAttr(cid) + '" data-capability-title="' + escapeAttr(text) + '">' + escapeHtml(text) + '</div>';
  }).join('');
  wrap.innerHTML = rows;
}

function renderCapabilityCards(list) {
  var el = document.getElementById('capabilityCards');
  if (!el) return;
  if (!Array.isArray(list) || !list.length) {
    el.innerHTML = '<div class="card"><div class="card-label">能力</div><div class="meta">暂无可用能力</div></div>';
    return;
  }
  el.innerHTML = list.map(function(cap) {
    var cid = cap.entry_id || '';
    var desc = cap.display_name || cid;
    var badge = cap.is_default ? '<span class="btn btn-primary btn-sm" style="cursor:default;">默认</span>' : '';
    var price = (cap.unit_credits || 0) > 0 ? (cap.unit_credits + ' 积分/次') : '按实际计费或免费';
    return '<div class="card">' +
      '<div class="card-label">' + escapeHtml(cap.display_id || cid) + '</div>' +
      '<div class="card-value" style="font-size:1.1rem;">' + escapeHtml(desc) + '</div>' +
      '<div class="meta" style="margin-top:0.35rem;">' + escapeHtml(price) + '</div>' +
      '<div class="card-actions" style="margin-top:0.9rem;">' + badge +
      '<button type="button" class="btn btn-ghost btn-sm" data-open-capability="' + escapeAttr(cid) + '">进入</button></div>' +
    '</div>';
  }).join('');
  el.querySelectorAll('button[data-open-capability]').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var cid = btn.getAttribute('data-open-capability') || '';
      if (!cid) return;
      currentCapabilityId = cid;
      document.querySelectorAll('.nav-left-item').forEach(function(b) { b.classList.remove('active'); });
      document.querySelectorAll('.nav-left-item[data-view="skill"]').forEach(function(b) { b.classList.add('active'); });
      document.getElementById('navSkillSub').style.display = 'block';
      document.querySelectorAll('.content-block').forEach(function(p) { p.classList.remove('visible'); });
      var contentEl = document.getElementById('content-skill-capability');
      if (contentEl) contentEl.classList.add('visible');
      currentView = 'skill-capability';
      openCapabilityView(cid);
    });
  });
}

function loadAvailableCapabilities() {
  fetch(API_BASE + '/capabilities/available', { headers: authHeaders() })
    .then(function(r) {
      if (r.status === 401) { token = null; localStorage.removeItem('token'); loadDashboard(); return null; }
      return r.json();
    })
    .then(function(d) {
      var arr = (d && Array.isArray(d.capabilities)) ? d.capabilities : [];
      capabilityListCache = arr
        .filter(function(x) { return (x.capability_id || '') !== 'testAI'; })
        .sort(function(a, b) {
          var ad = a && a.is_default ? 1 : 0;
          var bd = b && b.is_default ? 1 : 0;
          if (ad !== bd) return bd - ad;
          return String(a.capability_id || '').localeCompare(String(b.capability_id || ''));
        });
      capabilityViewEntries = buildCapabilityViewEntries(capabilityListCache);
      renderCapabilityNavItems(capabilityViewEntries);
      renderCapabilityCards(capabilityViewEntries);
    })
    .catch(function() {
      capabilityListCache = [];
      capabilityViewEntries = [];
      renderCapabilityNavItems([]);
      renderCapabilityCards([]);
    });
}

function openCapabilityView(capabilityId) {
  currentCapabilityId = capabilityId || '';
  currentCapabilityCallLogs = [];
  currentCapabilityChatLogs = [];
  currentCapabilityEntry = capabilityViewEntries.find(function(x) { return (x.entry_id || '') === currentCapabilityId; }) || null;
  var titleEl = document.getElementById('capabilityTitle');
  var descEl = document.getElementById('capabilityDesc');
  if (titleEl) titleEl.textContent = currentCapabilityEntry ? (currentCapabilityEntry.display_name || currentCapabilityEntry.entry_id) : (currentCapabilityId || '能力记录');
  if (descEl) {
    if (currentCapabilityEntry && currentCapabilityEntry.is_group) {
      descEl.textContent = '速推能力统一入口。已聚合图片生成、任务查询等接口记录。';
    } else if (currentCapabilityEntry) {
      descEl.textContent = '能力ID：' + currentCapabilityEntry.primary_id + '。在此查看调用记录与会话归档。';
    } else {
      descEl.textContent = '查看该能力的调用记录与相关智能会话归档。';
    }
  }
  renderCapabilityDomainStats();
  loadCapabilityCallLogs();
  loadCapabilityChatLogs();
}

function renderCapabilityDomainStats() {
  var el = document.getElementById('capabilityDomainStats');
  if (!el) return;
  if (!currentCapabilityId) { el.innerHTML = ''; return; }
  var totalCalls = Array.isArray(currentCapabilityCallLogs) ? currentCapabilityCallLogs.length : 0;
  var totalChats = Array.isArray(currentCapabilityChatLogs) ? currentCapabilityChatLogs.length : 0;
  var totalCharged = (currentCapabilityCallLogs || []).reduce(function(s, x) { return s + (x && x.credits_charged ? x.credits_charged : 0); }, 0);
  var successCount = (currentCapabilityCallLogs || []).filter(function(x) { return x && x.success; }).length;
  var successRate = totalCalls ? Math.round((successCount * 10000) / totalCalls) / 100 : 0;
  var cards = [
    { label: '调用次数', value: String(totalCalls) },
    { label: '成功率', value: totalCalls ? (successRate + '%') : '-' },
    { label: '累计扣费', value: String(totalCharged) + ' 积分' },
    { label: '会话归档', value: String(totalChats) }
  ];
  var memberIdsForStats = getCurrentCapabilityMemberIds();
  var isStockView = memberIdsForStats.some(function(id) { return String(id || '').indexOf('stock') === 0; });
  if (isStockView) {
    var symbols = [];
    (currentCapabilityCallLogs || []).forEach(function(row) {
      var req = row && row.request_payload ? row.request_payload : {};
      var s = req.symbol || req.ticker || req.stock || '';
      if (s && symbols.indexOf(s) < 0) symbols.push(s);
    });
    cards.push({ label: '近期关注标的', value: symbols.length ? symbols.slice(0, 5).join(', ') : '-' });
  }
  el.innerHTML = cards.map(function(c) {
    return '<div class="card"><div class="card-label">' + escapeHtml(c.label) + '</div><div class="card-value" style="font-size:1.1rem;">' + escapeHtml(c.value) + '</div></div>';
  }).join('');
}

function loadCapabilityCallLogs() {
  var el = document.getElementById('capabilityCallLogsList');
  if (!el) return;
  if (!currentCapabilityId) { el.innerHTML = '<p class="meta">请选择能力</p>'; return; }
  el.innerHTML = '<p class="meta">加载中…</p>';
  var memberIds = getCurrentCapabilityMemberIds();
  if (!memberIds.length) { el.innerHTML = '<p class="meta">暂无能力配置</p>'; return; }
  var reqs = memberIds.map(function(id) {
    return fetch(API_BASE + '/capabilities/my-call-logs?capability_id=' + encodeURIComponent(id) + '&limit=100', { headers: authHeaders() })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .catch(function() { return { ok: false, data: [] }; });
  });
  Promise.all(reqs)
    .then(function(results) {
      var all = [];
      results.forEach(function(x) {
        if (x && x.ok && Array.isArray(x.data)) all = all.concat(x.data);
      });
      all.sort(function(a, b) { return String(b.created_at || '').localeCompare(String(a.created_at || '')); });
      currentCapabilityCallLogs = all.slice(0, 200);
      renderCapabilityDomainStats();
      if (!all.length) { el.innerHTML = '<p class="meta">暂无调用记录</p>'; return; }
      el.innerHTML = '<div class="table-wrap"><table><thead><tr><th>时间</th><th>结果</th><th>扣费</th><th>耗时</th><th>请求</th><th>响应</th></tr></thead><tbody>' +
        all.map(function(r) {
          var okText = r.success ? '成功' : '失败';
          var okCls = r.success ? 'ok' : 'err';
          var req = escapeHtml(JSON.stringify(r.request_payload || {}, null, 0));
          var rsp = escapeHtml(JSON.stringify(r.response_payload || {}, null, 0));
          var reqShort = req.length > 160 ? req.slice(0, 160) + '…' : req;
          var rspShort = rsp.length > 200 ? rsp.slice(0, 200) + '…' : rsp;
          var t = r.created_at ? new Date(r.created_at).toLocaleString() : '-';
          return '<tr><td>' + t + '</td><td class="' + okCls + '">' + okText + '</td><td>' + (r.credits_charged || 0) + '</td><td>' + (r.latency_ms || '-') + 'ms</td><td title="' + escapeAttr(req) + '">' + reqShort + '</td><td title="' + escapeAttr(rsp) + '">' + rspShort + '</td></tr>';
        }).join('') +
        '</tbody></table></div>';
    })
    .catch(function() { el.innerHTML = '<p class="msg err">加载失败</p>'; });
}

function loadCapabilityChatLogs() {
  var el = document.getElementById('capabilityChatLogsList');
  if (!el) return;
  if (!currentCapabilityId) { el.innerHTML = '<p class="meta">请选择能力</p>'; return; }
  el.innerHTML = '<p class="meta">加载中…</p>';
  var memberIds = getCurrentCapabilityMemberIds();
  if (!memberIds.length) { el.innerHTML = '<p class="meta">暂无能力配置</p>'; return; }
  var reqs = memberIds.map(function(id) {
    return fetch(API_BASE + '/chat/history?context_id=' + encodeURIComponent(id) + '&limit=100', { headers: authHeaders() })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .catch(function() { return { ok: false, data: [] }; });
  });
  Promise.all(reqs)
    .then(function(results) {
      var all = [];
      results.forEach(function(x) {
        if (x && x.ok && Array.isArray(x.data)) all = all.concat(x.data);
      });
      all.sort(function(a, b) { return String(b.created_at || '').localeCompare(String(a.created_at || '')); });
      currentCapabilityChatLogs = all.slice(0, 200);
      renderCapabilityDomainStats();
      if (!all.length) { el.innerHTML = '<p class="meta">暂无会话归档</p>'; return; }
      el.innerHTML = all.map(function(row) {
        var t = row.created_at ? new Date(row.created_at).toLocaleString() : '-';
        return '<div class="list-item" style="display:block;">' +
          '<div class="meta">' + t + '</div>' +
          '<div style="margin-top:0.35rem;"><strong>问：</strong>' + escapeHtml(row.user_message || '') + '</div>' +
          '<div style="margin-top:0.35rem;"><strong>答：</strong>' + escapeHtml(row.assistant_reply || '') + '</div>' +
        '</div>';
      }).join('');
    })
    .catch(function() { el.innerHTML = '<p class="msg err">加载失败</p>'; });
}

var navCapabilityItems = document.getElementById('navCapabilityItems');
if (navCapabilityItems) {
  navCapabilityItems.addEventListener('click', function(e) {
    var el = e.target && e.target.closest ? e.target.closest('.nav-left-item[data-dynamic-capability="1"]') : null;
    if (!el) return;
    var view = el.dataset.view || '';
    var capabilityId = el.dataset.capabilityId || '';
    if (!view) return;
    if (currentView === 'chat' && view !== 'chat' && typeof saveCurrentSessionToStore === 'function') saveCurrentSessionToStore();
    document.querySelectorAll('.nav-left-item').forEach(function(b) { b.classList.remove('active'); });
    document.querySelectorAll('.nav-left-item[data-view="skill"]').forEach(function(b) { b.classList.add('active'); });
    document.getElementById('navSkillSub').style.display = 'block';
    el.classList.add('active');
    document.querySelectorAll('.content-block').forEach(function(p) { p.classList.remove('visible'); });
    var contentEl = document.getElementById('content-skill-capability');
    if (contentEl) contentEl.classList.add('visible');
    currentView = 'skill-capability';
    openCapabilityView(capabilityId);
  });
}
var refreshCapabilityLogsBtn = document.getElementById('refreshCapabilityLogsBtn');
if (refreshCapabilityLogsBtn) {
  refreshCapabilityLogsBtn.addEventListener('click', function() {
    loadCapabilityCallLogs();
    loadCapabilityChatLogs();
  });
}
document.querySelectorAll('#content-skill-testAI .dash-tabs button[data-skill-panel]').forEach(function(btn) {
  btn.addEventListener('click', function() {
    var panelId = btn.dataset.skillPanel;
    if (!panelId) return;
    document.querySelectorAll('#content-skill-testAI .dash-tabs button').forEach(function(b) { b.classList.remove('active'); });
    document.querySelectorAll('#content-skill-testAI .dash-panel').forEach(function(p) { p.classList.remove('visible'); });
    btn.classList.add('active');
    var panel = document.getElementById(panelId);
    if (panel) panel.classList.add('visible');
    if (panelId === 'panel-templates') { loadTemplates(); loadGenerateRecords(); }
    if (panelId === 'panel-libraries') { loadLibraries(); loadLlmModels(); }
    if (panelId === 'panel-accounts') loadAccounts();
  });
});
