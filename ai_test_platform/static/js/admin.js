// admin.js - 管理员面板

var adminCapabilityRegistry = [];
var adminAssignedCapabilityIds = [];
var adminDevicePool = [];
var adminAccountPool = [];
var adminAssignedDeviceIds = [];
var adminAssignedAccountIds = [];

function isAdminUser() {
  var role = String((currentUserProfile && currentUserProfile.role) || '').toLowerCase();
  return role === 'admin';
}

function selectedIntValues(selectEl) {
  if (!selectEl) return [];
  return Array.from(selectEl.selectedOptions || []).map(function(o) { return parseInt(o.value, 10); }).filter(function(x) { return !isNaN(x); });
}

function toggleAdminOpsSection() {
  var navEl = document.getElementById('navAdminConsole');
  var contentEl = document.getElementById('content-admin-console');
  if (!navEl || !contentEl) return;
  if (isAdminUser()) {
    navEl.style.display = '';
    loadAdminOpsData();
  } else {
    navEl.style.display = 'none';
    if (currentView === 'admin-console') {
      currentView = 'group-control';
      document.querySelectorAll('.content-block').forEach(function(p) { p.classList.remove('visible'); });
      var gc = document.getElementById('content-group-control');
      if (gc) gc.classList.add('visible');
    }
  }
}

function loadAdminOpsData() {
  if (!isAdminUser()) return;
  Promise.all([loadAdminUsers(), loadAdminDevicesAndAccounts(), loadAdminCapabilities()])
    .then(function() {
      syncAdminUserSelectors();
    })
    .catch(function() {});
}

function loadAdminUsers() {
  return fetch(API_BASE + '/auth/admin/users', { headers: authHeaders() })
    .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
    .then(function(x) {
      var list = x.ok && Array.isArray(x.data) ? x.data : [];
      var opts = list.map(function(u) {
        return '<option value="' + u.id + '">' + escapeHtml('#' + u.id + ' ' + (u.email || '-') + ' (' + (u.credits || 0) + '积分)') + '</option>';
      }).join('');
      ['adminAssignUserSelect', 'adminSkillUserSelect', 'adminCreditUserSelect', 'adminNurtureTierUserSelect'].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.innerHTML = opts;
      });
      var tierSel = document.getElementById('adminNurtureTierUserSelect');
      if (tierSel) {
        tierSel.addEventListener('change', function() {
          var uid = parseInt(tierSel.value, 10);
          var u = list.find(function(x) { return x.id === uid; });
          var ts = document.getElementById('adminNurtureTierSelect');
          if (ts && u) ts.value = u.nurture_model_tier || 'basic';
        });
        var first = list[0];
        if (first) {
          var ts = document.getElementById('adminNurtureTierSelect');
          if (ts) ts.value = first.nurture_model_tier || 'basic';
        }
      }
      return list;
    });
}

function loadAdminDevicesAndAccounts() {
  var p1 = fetch(API_BASE + '/group-control/devices', { headers: authHeaders() })
    .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
    .then(function(x) {
      var list = x.ok && Array.isArray(x.data) ? x.data : [];
      adminDevicePool = list.slice();
      renderAdminDeviceAssignList();
      return list;
    });
  var p2 = fetch(API_BASE + '/group-control/reddit-accounts', { headers: authHeaders() })
    .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
    .then(function(x) {
      var list = x.ok && Array.isArray(x.data) ? x.data : [];
      var systemOnly = list.filter(function(a) { return String(a.source || '') === 'system'; });
      adminAccountPool = systemOnly.slice();
      renderAdminAccountAssignList();
      return systemOnly;
    });
  return Promise.all([p1, p2]);
}

function renderAdminDeviceAssignList() {
  var wrap = document.getElementById('adminDeviceAssignList');
  var countEl = document.getElementById('adminDeviceAssignCount');
  if (!wrap) return;
  var kw = String((document.getElementById('adminDeviceSearchInput') || {}).value || '').trim().toLowerCase();
  var assignedOnly = !!((document.getElementById('adminDeviceAssignedOnly') || {}).checked);
  var rows = (adminDevicePool || []).filter(function(d) {
    var did = parseInt(d.id, 10);
    if (assignedOnly && adminAssignedDeviceIds.indexOf(did) < 0) return false;
    if (!kw) return true;
    var text = ((d.alias || '') + ' ' + (d.device_label || '') + ' ' + (d.model || '') + ' ' + (d.brand || '')).toLowerCase();
    return text.indexOf(kw) >= 0;
  });
  if (countEl) countEl.textContent = '已分配 ' + adminAssignedDeviceIds.length + ' / 总设备 ' + (adminDevicePool || []).length + ' / 当前筛选 ' + rows.length;
  if (!rows.length) {
    wrap.innerHTML = '<div class="meta">无匹配设备</div>';
    return;
  }
  wrap.innerHTML = rows.map(function(d) {
    var did = parseInt(d.id, 10);
    var checked = adminAssignedDeviceIds.indexOf(did) >= 0 ? 'checked' : '';
    var label = (d.device_label || d.alias || d.serial || '');
    var meta = [d.brand, d.model, d.adb_status].filter(Boolean).join(' · ');
    return '<label style="display:flex;align-items:flex-start;gap:0.45rem;padding:0.3rem 0;border-bottom:1px solid rgba(255,255,255,0.05);">' +
      '<input type="checkbox" class="admin-device-item" value="' + did + '" ' + checked + '>' +
      '<span><div>' + escapeHtml(label) + '</div><div class="meta" style="font-size:0.78rem;">' + escapeHtml(meta || '-') + '</div></span></label>';
  }).join('');
}

function renderAdminAccountAssignList() {
  var wrap = document.getElementById('adminAccountAssignList');
  var countEl = document.getElementById('adminAccountAssignCount');
  if (!wrap) return;
  var kw = String((document.getElementById('adminAccountSearchInput') || {}).value || '').trim().toLowerCase();
  var assignedOnly = !!((document.getElementById('adminAccountAssignedOnly') || {}).checked);
  var rows = (adminAccountPool || []).filter(function(a) {
    var aid = parseInt(a.id, 10);
    if (assignedOnly && adminAssignedAccountIds.indexOf(aid) < 0) return false;
    if (!kw) return true;
    var text = ((a.username || '') + ' ' + (a.status || '')).toLowerCase();
    return text.indexOf(kw) >= 0;
  });
  if (countEl) countEl.textContent = '已分配 ' + adminAssignedAccountIds.length + ' / 总账号 ' + (adminAccountPool || []).length + ' / 当前筛选 ' + rows.length;
  if (!rows.length) {
    wrap.innerHTML = '<div class="meta">无匹配账号</div>';
    return;
  }
  wrap.innerHTML = rows.map(function(a) {
    var aid = parseInt(a.id, 10);
    var checked = adminAssignedAccountIds.indexOf(aid) >= 0 ? 'checked' : '';
    return '<label style="display:flex;align-items:flex-start;gap:0.45rem;padding:0.3rem 0;border-bottom:1px solid rgba(255,255,255,0.05);">' +
      '<input type="checkbox" class="admin-account-item" value="' + aid + '" ' + checked + '>' +
      '<span><div>' + escapeHtml(a.username || '') + '</div><div class="meta" style="font-size:0.78rem;">' + escapeHtml(a.status || 'active') + '</div></span></label>';
  }).join('');
}

function loadAdminCapabilities() {
  return fetch(API_BASE + '/capabilities/admin/registry', { headers: authHeaders() })
    .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
    .then(function(x) {
      var list = x.ok && Array.isArray(x.data) ? x.data : [];
      adminCapabilityRegistry = list.slice();
      renderAdminSkillCapabilityList('');
      return list;
    });
}

function renderAdminSkillCapabilityList(filterText) {
  var wrap = document.getElementById('adminSkillAssignList');
  if (!wrap) return;
  var kw = String(filterText || '').trim().toLowerCase();
  var rows = (adminCapabilityRegistry || []).filter(function(c) {
    if (!kw) return true;
    var text = ((c.capability_id || '') + ' ' + (c.description || '') + ' ' + (c.upstream || '')).toLowerCase();
    return text.indexOf(kw) >= 0;
  });
  if (!rows.length) {
    wrap.innerHTML = '<div class="meta">未匹配到能力</div>';
    return;
  }
  wrap.innerHTML = rows.map(function(c) {
    var cid = String(c.capability_id || '');
    var checked = adminAssignedCapabilityIds.indexOf(cid) >= 0 ? 'checked' : '';
    var status = c.enabled ? 'enabled' : 'disabled';
    var title = c.description || cid;
    return '<label style="display:flex;align-items:flex-start;gap:0.45rem;padding:0.35rem 0;border-bottom:1px solid rgba(255,255,255,0.05);">' +
      '<input type="checkbox" class="admin-skill-cap-item" value="' + escapeAttr(cid) + '" ' + checked + '>' +
      '<span style="display:block;"><div style="font-size:0.9rem;">' + escapeHtml(title) + '</div>' +
      '<div class="meta" style="font-size:0.78rem;">' + escapeHtml((c.upstream || '-') + ' · ' + status + ' · ' + cid) + '</div></span></label>';
  }).join('');
}

function toggleAdminSkillSelection(capabilityId, checked) {
  var cid = String(capabilityId || '').trim();
  if (!cid) return;
  var idx = adminAssignedCapabilityIds.indexOf(cid);
  if (checked && idx < 0) adminAssignedCapabilityIds.push(cid);
  if (!checked && idx >= 0) adminAssignedCapabilityIds.splice(idx, 1);
}

function syncAdminUserSelectors() {
  var ids = ['adminAssignUserSelect', 'adminSkillUserSelect', 'adminCreditUserSelect', 'adminNurtureTierUserSelect'];
  var firstVal = '';
  ids.forEach(function(id) {
    var el = document.getElementById(id);
    if (!el || !el.options.length) return;
    if (!firstVal) firstVal = el.value || el.options[0].value;
  });
  if (!firstVal) return;
  ids.forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.value = firstVal;
  });
  loadAdminAssignmentsForUser(parseInt(firstVal, 10));
  loadAdminSkillForUser(parseInt(firstVal, 10));
}

function loadAdminAssignmentsForUser(userId) {
  if (!userId) return;
  fetch(API_BASE + '/group-control/admin/user-assignments/' + userId, { headers: authHeaders() })
    .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
    .then(function(x) {
      if (!x.ok) return;
      adminAssignedDeviceIds = ((x.data && x.data.device_ids) || []).map(function(v) { return parseInt(v, 10); }).filter(function(v) { return !isNaN(v); });
      adminAssignedAccountIds = ((x.data && x.data.account_ids) || []).map(function(v) { return parseInt(v, 10); }).filter(function(v) { return !isNaN(v); });
      renderAdminDeviceAssignList();
      renderAdminAccountAssignList();
    });
}

function loadAdminSkillForUser(userId) {
  if (!userId) return;
  fetch(API_BASE + '/capabilities/admin/policies?user_id=' + userId, { headers: authHeaders() })
    .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
    .then(function(x) {
      if (!x.ok) return;
      adminAssignedCapabilityIds = (Array.isArray(x.data) ? x.data : [])
        .filter(function(p) { return String(p.effect || '') === 'allow' && !!p.enabled; })
        .map(function(p) { return String(p.capability_id || ''); });
      var keyword = String((document.getElementById('adminSkillSearchInput') || {}).value || '').trim();
      renderAdminSkillCapabilityList(keyword);
    });
}

var refreshAdminOpsBtn = document.getElementById('refreshAdminOpsBtn');
if (refreshAdminOpsBtn) {
  refreshAdminOpsBtn.addEventListener('click', function() { loadAdminOpsData(); });
}
var adminReloadCapabilitiesBtn = document.getElementById('adminReloadCapabilitiesBtn');
if (adminReloadCapabilitiesBtn) {
  adminReloadCapabilitiesBtn.addEventListener('click', function() {
    var msgEl = document.getElementById('adminSkillMsg');
    fetch(API_BASE + '/capabilities/admin/registry/rescan?include_cursor_mcp=true&overwrite_existing=true', {
      method: 'POST',
      headers: authHeaders()
    })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .then(function(x) {
        if (!x.ok) {
          showMsg(msgEl, (x.data && x.data.detail) || '重扫失败', true);
          return;
        }
        return loadAdminCapabilities().then(function(list) {
          var d = x.data || {};
          var text = '重扫完成：新增 ' + (d.created || 0) + '，更新 ' + (d.updated || 0) + '，总计 ' + (d.total_from_scan || (list || []).length);
          showMsg(msgEl, text, false);
        });
      })
      .catch(function(err) {
        showMsg(msgEl, String((err && err.message) || err || '重扫失败'), true);
      });
  });
}
var adminAssignUserSelect = document.getElementById('adminAssignUserSelect');
if (adminAssignUserSelect) {
  adminAssignUserSelect.addEventListener('change', function() {
    var v = parseInt(String(adminAssignUserSelect.value || '').trim(), 10);
    if (!isNaN(v)) {
      var s2 = document.getElementById('adminSkillUserSelect');
      var s3 = document.getElementById('adminCreditUserSelect');
      if (s2) s2.value = String(v);
      if (s3) s3.value = String(v);
      loadAdminAssignmentsForUser(v);
      loadAdminSkillForUser(v);
    }
  });
}
var adminSkillUserSelect = document.getElementById('adminSkillUserSelect');
if (adminSkillUserSelect) {
  adminSkillUserSelect.addEventListener('change', function() {
    var v = parseInt(String(adminSkillUserSelect.value || '').trim(), 10);
    if (!isNaN(v)) loadAdminSkillForUser(v);
  });
}
var adminSkillSearchInput = document.getElementById('adminSkillSearchInput');
if (adminSkillSearchInput) {
  adminSkillSearchInput.addEventListener('input', function() {
    renderAdminSkillCapabilityList(adminSkillSearchInput.value || '');
  });
}
var adminSkillAssignList = document.getElementById('adminSkillAssignList');
if (adminSkillAssignList) {
  adminSkillAssignList.addEventListener('change', function(e) {
    var target = e.target;
    if (!target || !target.classList || !target.classList.contains('admin-skill-cap-item')) return;
    toggleAdminSkillSelection(target.value, !!target.checked);
  });
}
var adminDeviceSearchInput = document.getElementById('adminDeviceSearchInput');
if (adminDeviceSearchInput) {
  adminDeviceSearchInput.addEventListener('input', function() { renderAdminDeviceAssignList(); });
}
var adminAccountSearchInput = document.getElementById('adminAccountSearchInput');
if (adminAccountSearchInput) {
  adminAccountSearchInput.addEventListener('input', function() { renderAdminAccountAssignList(); });
}
var adminDeviceAssignedOnly = document.getElementById('adminDeviceAssignedOnly');
if (adminDeviceAssignedOnly) {
  adminDeviceAssignedOnly.addEventListener('change', function() { renderAdminDeviceAssignList(); });
}
var adminAccountAssignedOnly = document.getElementById('adminAccountAssignedOnly');
if (adminAccountAssignedOnly) {
  adminAccountAssignedOnly.addEventListener('change', function() { renderAdminAccountAssignList(); });
}
var adminCreateCapabilityBtn = document.getElementById('adminCreateCapabilityBtn');
if (adminCreateCapabilityBtn) {
  adminCreateCapabilityBtn.addEventListener('click', function() {
    var capId = String((document.getElementById('adminCapIdInput') || {}).value || '').trim();
    var tool = String((document.getElementById('adminCapToolInput') || {}).value || '').trim();
    var desc = String((document.getElementById('adminCapDescInput') || {}).value || '').trim();
    var upstream = String((document.getElementById('adminCapUpstreamInput') || {}).value || '').trim() || 'sutui';
    var msgEl = document.getElementById('adminSkillMsg');
    if (!capId || !tool) {
      if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '请填写 capability_id 与 upstream_tool'; }
      return;
    }
    fetch(API_BASE + '/capabilities/admin/registry', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        capability_id: capId,
        description: desc || capId,
        upstream: upstream,
        upstream_tool: tool,
        enabled: true,
        is_default: false,
        unit_credits: 0
      })
    })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .then(function(x) {
        if (!msgEl) return;
        if (x.ok) {
          msgEl.className = 'msg ok';
          msgEl.textContent = '能力已新增到目录，可立即分配给用户';
          if (document.getElementById('adminCapIdInput')) document.getElementById('adminCapIdInput').value = '';
          if (document.getElementById('adminCapToolInput')) document.getElementById('adminCapToolInput').value = '';
          if (document.getElementById('adminCapDescInput')) document.getElementById('adminCapDescInput').value = '';
          loadAdminCapabilities();
        } else {
          msgEl.className = 'msg err';
          msgEl.textContent = (x.data && x.data.detail) || '新增能力失败';
        }
      })
      .catch(function(err) {
        if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '网络错误: ' + (err.message || ''); }
      });
  });
}
var adminSaveDeviceAssignBtn = document.getElementById('adminSaveDeviceAssignBtn');
if (adminSaveDeviceAssignBtn) {
  adminSaveDeviceAssignBtn.addEventListener('click', function() {
    var userId = parseInt(String((document.getElementById('adminAssignUserSelect') || {}).value || '').trim(), 10);
    var deviceIds = Array.from(document.querySelectorAll('.admin-device-item:checked'))
      .map(function(o) { return parseInt(o.value, 10); })
      .filter(function(x) { return !isNaN(x); });
    var msgEl = document.getElementById('adminAssignMsg');
    if (!userId) { if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '请选择用户'; } return; }
    fetch(API_BASE + '/group-control/admin/assign-devices', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ user_id: userId, device_ids: deviceIds })
    })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .then(function(x) {
        if (!msgEl) return;
        msgEl.className = x.ok ? 'msg ok' : 'msg err';
        msgEl.textContent = x.ok ? ('设备分配已保存，数量=' + ((x.data && x.data.assigned_count) || 0)) : ((x.data && x.data.detail) || '保存失败');
        if (x.ok) {
          adminAssignedDeviceIds = deviceIds.slice();
          renderAdminDeviceAssignList();
        }
      })
      .catch(function(err) { if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '网络错误: ' + (err.message || ''); } });
  });
}
var adminSaveAccountAssignBtn = document.getElementById('adminSaveAccountAssignBtn');
if (adminSaveAccountAssignBtn) {
  adminSaveAccountAssignBtn.addEventListener('click', function() {
    var userId = parseInt(String((document.getElementById('adminAssignUserSelect') || {}).value || '').trim(), 10);
    var accountIds = Array.from(document.querySelectorAll('.admin-account-item:checked'))
      .map(function(o) { return parseInt(o.value, 10); })
      .filter(function(x) { return !isNaN(x); });
    var msgEl = document.getElementById('adminAssignMsg');
    if (!userId) { if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '请选择用户'; } return; }
    fetch(API_BASE + '/group-control/admin/assign-reddit-accounts', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ user_id: userId, account_ids: accountIds })
    })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .then(function(x) {
        if (!msgEl) return;
        msgEl.className = x.ok ? 'msg ok' : 'msg err';
        msgEl.textContent = x.ok ? ('账号分配已保存，数量=' + ((x.data && x.data.assigned_count) || 0)) : ((x.data && x.data.detail) || '保存失败');
        if (x.ok) {
          adminAssignedAccountIds = accountIds.slice();
          renderAdminAccountAssignList();
        }
      })
      .catch(function(err) { if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '网络错误: ' + (err.message || ''); } });
  });
}
var adminSaveSkillAssignBtn = document.getElementById('adminSaveSkillAssignBtn');
if (adminSaveSkillAssignBtn) {
  adminSaveSkillAssignBtn.addEventListener('click', function() {
    var userId = parseInt(String((document.getElementById('adminSkillUserSelect') || {}).value || '').trim(), 10);
    var skillIds = (adminAssignedCapabilityIds || []).map(function(v) { return String(v || '').trim(); }).filter(Boolean);
    var msgEl = document.getElementById('adminSkillMsg');
    if (!userId) { if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '请选择用户'; } return; }
    fetch(API_BASE + '/capabilities/admin/assign-user', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ user_id: userId, capability_ids: skillIds, effect: 'allow' })
    })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .then(function(x) {
        if (!msgEl) return;
        msgEl.className = x.ok ? 'msg ok' : 'msg err';
        msgEl.textContent = x.ok ? ('能力分配已保存，数量=' + ((x.data && x.data.assigned_count) || 0)) : ((x.data && x.data.detail) || '保存失败');
        if (x.ok) {
          adminAssignedCapabilityIds = skillIds.slice();
          renderAdminSkillCapabilityList(String((document.getElementById('adminSkillSearchInput') || {}).value || '').trim());
        }
      })
      .catch(function(err) { if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '网络错误: ' + (err.message || ''); } });
  });
}
var adminRechargeBtn = document.getElementById('adminRechargeBtn');
if (adminRechargeBtn) {
  adminRechargeBtn.addEventListener('click', function() {
    var userId = parseInt(String((document.getElementById('adminCreditUserSelect') || {}).value || '').trim(), 10);
    var amount = parseInt(String((document.getElementById('adminRechargeAmount') || {}).value || '').trim(), 10);
    var desc = String((document.getElementById('adminRechargeDesc') || {}).value || '').trim();
    var msgEl = document.getElementById('adminRechargeMsg');
    if (!userId || !amount || amount <= 0) {
      if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '请选择用户并输入正确积分'; }
      return;
    }
    fetch(API_BASE + '/auth/admin/recharge', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ user_id: userId, amount: amount, description: desc || null })
    })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .then(function(x) {
        if (!msgEl) return;
        msgEl.className = x.ok ? 'msg ok' : 'msg err';
        msgEl.textContent = x.ok ? ('充值成功，余额=' + ((x.data && x.data.credits) || '-')) : ((x.data && x.data.detail) || '充值失败');
        if (x.ok) loadDashboard();
      })
      .catch(function(err) { if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '网络错误: ' + (err.message || ''); } });
  });
}
var adminSetNurtureTierBtn = document.getElementById('adminSetNurtureTierBtn');
if (adminSetNurtureTierBtn) {
  adminSetNurtureTierBtn.addEventListener('click', function() {
    var userId = parseInt(String((document.getElementById('adminNurtureTierUserSelect') || {}).value || '').trim(), 10);
    var tier = String((document.getElementById('adminNurtureTierSelect') || {}).value || '').trim();
    var msgEl = document.getElementById('adminNurtureTierMsg');
    if (!userId || !tier) { if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '请选择用户和等级'; } return; }
    fetch(API_BASE + '/group-control/admin/set-nurture-tier', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ user_id: userId, tier: tier })
    })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .then(function(x) {
        if (!msgEl) return;
        msgEl.className = x.ok ? 'msg ok' : 'msg err';
        msgEl.textContent = x.ok ? ('已设置 tier=' + tier) : ((x.data && x.data.detail) || '设置失败');
        if (x.ok) loadNurtureModels();
      })
      .catch(function(err) { if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '网络错误'; } });
  });
}
