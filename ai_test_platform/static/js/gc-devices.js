// gc-devices.js - 群控：手机列表 + 养号计划创建

var controlDeviceListCache = [];
var controlDevicePage = 1;
var controlDevicePageSize = 12;
var nurtureModelsCache = [];
var nurtureDefaultModel = 'deepseek-chat';

function renderControlDevicesPage() {
  var list = controlDeviceListCache || [];
  var el = document.getElementById('controlDevicesList');
  var pagerEl = document.getElementById('controlDevicesPager');
  if (!el) return;
  var q = (document.getElementById('devicesSearchInput') || {}).value || '';
  q = q.toLowerCase().trim();
  if (q) list = list.filter(function(d) {
    return (d.device_label || '').toLowerCase().indexOf(q) >= 0
      || (d.alias || '').toLowerCase().indexOf(q) >= 0
      || String(d.id).indexOf(q) >= 0
      || String(d.device_no || '').indexOf(q) >= 0;
  });
  if (!list.length) {
    el.innerHTML = '<p class="meta">' + (q ? '未找到匹配设备' : '暂无在线设备，先启动本地 Agent 心跳。') + '</p>';
    if (pagerEl) pagerEl.innerHTML = '';
    return;
  }
  var total = list.length;
  var pageCount = Math.max(1, Math.ceil(total / controlDevicePageSize));
  if (controlDevicePage > pageCount) controlDevicePage = pageCount;
  if (controlDevicePage < 1) controlDevicePage = 1;
  var start = (controlDevicePage - 1) * controlDevicePageSize;
  var rows = list.slice(start, start + controlDevicePageSize);
  el.innerHTML = rows.map(function(d) {
    var deviceLabel = d.device_label || d.alias || d.serial;
    var meta = deviceLabel + ' · ADB:' + (d.adb_status || '-') + ' · Appium:' + (d.appium_status || '-');
    var attrs = d.account_attrs;
    if (attrs && typeof attrs === 'object') {
      meta += ' · ' + (attrs.niche ? 'niche:' + attrs.niche : '') + (attrs.phase ? ' phase:' + attrs.phase : '') + (attrs.karma != null ? ' karma:' + attrs.karma : '');
      if (Array.isArray(attrs.tags) && attrs.tags.length) meta += ' tags:' + attrs.tags.join('/');
    }
    if (d.model || d.brand) meta += ' · ' + [d.brand, d.model].filter(Boolean).join(' ');
    var runBadge = '';
    if (d.running_task_count > 0) {
      runBadge = '<span style="display:inline-block;margin-left:0.4rem;padding:1px 6px;border-radius:4px;font-size:0.7rem;background:#facc15;color:#000;font-weight:600;">' + d.running_task_count + ' 运行中</span>';
    }
    return '<div class="list-item"><div><div class="title">' + escapeHtml(deviceLabel || '') + runBadge + '</div><div class="meta">' + escapeHtml(meta) + '</div></div><div class="acts"><button type="button" class="btn btn-ghost btn-sm btn-device-nurture-plan" data-device-id="' + d.id + '">创建养号计划</button><span class="meta device-plan-msg" data-device-msg="' + d.id + '" style="margin-left:0.4rem;"></span></div></div>';
  }).join('');
  if (pagerEl) {
    pagerEl.innerHTML = '<button type="button" class="btn btn-ghost btn-sm" id="controlDevicesPrevBtn">上一页</button>' +
      '<span class="meta">第 ' + controlDevicePage + ' / ' + pageCount + ' 页（共' + total + '台）</span>' +
      '<button type="button" class="btn btn-ghost btn-sm" id="controlDevicesNextBtn">下一页</button>';
    var prev = document.getElementById('controlDevicesPrevBtn');
    var next = document.getElementById('controlDevicesNextBtn');
    if (prev) prev.disabled = controlDevicePage <= 1;
    if (next) next.disabled = controlDevicePage >= pageCount;
    if (prev) prev.addEventListener('click', function() { controlDevicePage -= 1; renderControlDevicesPage(); });
    if (next) next.addEventListener('click', function() { controlDevicePage += 1; renderControlDevicesPage(); });
  }
  el.querySelectorAll('.btn-device-nurture-plan').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var deviceId = parseInt(String(btn.getAttribute('data-device-id') || '').trim(), 10);
      if (!deviceId) return;
      openCreatePlanModal(deviceId, btn);
    });
  });
}

function loadNurtureModels() {
  return fetch(API_BASE + '/group-control/nurture/models', { headers: authHeaders() })
    .then(function(r) { return r.ok ? r.json() : { models: [], default_model: 'deepseek-chat' }; })
    .then(function(data) {
      nurtureModelsCache = data.models || [];
      nurtureDefaultModel = data.default_model || 'deepseek-chat';
      _renderModelSelect();
    })
    .catch(function() {});
}

function _renderModelSelect() {
  var hiddenInput = document.getElementById('modalPlanModelSelect');
  var listEl = document.getElementById('modalPlanModelList');
  var toggleEl = document.getElementById('modalPlanModelToggle');
  var labelEl = document.getElementById('modalPlanModelLabel');
  if (!listEl || !hiddenInput) return;
  var saved = '';
  try { saved = localStorage.getItem('nurture_last_model') || ''; } catch(e) {}
  var pick = saved || nurtureDefaultModel;
  var found = nurtureModelsCache.some(function(m) { return m.id === pick; });
  if (!found && nurtureModelsCache.length) pick = nurtureModelsCache[0].id;
  hiddenInput.value = pick;
  listEl.innerHTML = nurtureModelsCache.map(function(m) {
    var tierCls = m.tier === 'pro' ? 'dd-tier-pro' : 'dd-tier-basic';
    var tierLabel = m.tier === 'pro' ? 'Pro' : 'Basic';
    var speedIcon = m.speed === 'fast' ? '<span class="dd-speed">\u26A1</span>' : '';
    var selCls = m.id === pick ? ' selected' : '';
    return '<div class="custom-dropdown-item' + selCls + '" data-value="' + escapeHtml(m.id) + '">' +
      '<span>' + escapeHtml(m.name) + speedIcon + '</span>' +
      '<span class="dd-tier ' + tierCls + '">' + tierLabel + '</span>' +
      '</div>';
  }).join('');
  var pickModel = nurtureModelsCache.find(function(m) { return m.id === pick; });
  if (labelEl) labelEl.textContent = pickModel ? pickModel.name : pick;
  listEl.querySelectorAll('.custom-dropdown-item').forEach(function(item) {
    item.addEventListener('click', function() {
      var val = item.getAttribute('data-value');
      hiddenInput.value = val;
      listEl.querySelectorAll('.custom-dropdown-item').forEach(function(x) { x.classList.remove('selected'); });
      item.classList.add('selected');
      var m = nurtureModelsCache.find(function(x) { return x.id === val; });
      if (labelEl) labelEl.textContent = m ? m.name : val;
      listEl.classList.remove('open');
      if (toggleEl) toggleEl.classList.remove('open');
    });
  });
  if (toggleEl) {
    toggleEl.onclick = function() {
      var isOpen = listEl.classList.contains('open');
      if (isOpen) { listEl.classList.remove('open'); toggleEl.classList.remove('open'); }
      else { listEl.classList.add('open'); toggleEl.classList.add('open'); }
    };
  }
}

var _pendingPlanDeviceId = null;
var _pendingPlanBtn = null;

function openCreatePlanModal(deviceId, triggerBtn) {
  _pendingPlanDeviceId = deviceId;
  _pendingPlanBtn = triggerBtn;
  _renderModelSelect();
  var info = document.getElementById('modalCreatePlanDeviceInfo');
  var device = (controlDeviceListCache || []).find(function(d) { return d.id === deviceId; });
  if (info) info.textContent = '\u2022 ' + (device ? (device.device_label || device.alias || device.serial) : '#' + deviceId);
  var objInput = document.getElementById('modalPlanObjective');
  if (objInput) objInput.value = '';
  var msgEl = document.getElementById('modalCreatePlanMsg');
  if (msgEl) { msgEl.className = 'msg'; msgEl.textContent = ''; }
  var confirmBtn = document.getElementById('modalCreatePlanConfirm');
  if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = '确认创建'; }
  fetch(API_BASE + '/group-control/nurture/last-objective?device_id=' + deviceId, { headers: authHeaders() })
    .then(function(r) { return r.ok ? r.json() : { objective: '' }; })
    .then(function(data) {
      if (objInput && data.objective) objInput.value = data.objective;
    })
    .catch(function() {});
  var modal = document.getElementById('modalCreatePlan');
  if (modal) modal.classList.add('visible');
  if (objInput) setTimeout(function() { objInput.focus(); }, 120);
}

function _doCreatePlan() {
  var deviceId = _pendingPlanDeviceId;
  if (!deviceId) return;
  var sel = document.getElementById('modalPlanModelSelect');
  var model = sel ? sel.value : nurtureDefaultModel;
  var objInput = document.getElementById('modalPlanObjective');
  var objective = objInput ? objInput.value.trim() : '';
  var confirmBtn = document.getElementById('modalCreatePlanConfirm');
  var msgEl = document.getElementById('modalCreatePlanMsg');
  if (!objective) {
    if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '请输入养号方向'; }
    if (objInput) objInput.focus();
    return;
  }
  try { localStorage.setItem('nurture_last_model', model); } catch(e) {}
  if (confirmBtn) { confirmBtn.disabled = true; confirmBtn.textContent = '创建中...'; }
  if (msgEl) { msgEl.className = 'msg'; msgEl.textContent = ''; }
  fetch(API_BASE + '/group-control/nurture/plans/generate-by-device', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ device_id: deviceId, auto_approve: false, model: model, objective: objective })
  })
    .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
    .then(function(x) {
      if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = '确认创建'; }
      if (x.ok) {
        var modal = document.getElementById('modalCreatePlan');
        if (modal) modal.classList.remove('visible');
        var inlineMsg = document.querySelector('[data-device-msg="' + deviceId + '"]');
        if (inlineMsg) { inlineMsg.style.color = '#f59e0b'; inlineMsg.textContent = '计划#' + (x.data && x.data.id) + ' 生成中'; }
        loadNurturePanel();
      } else {
        var detail = (x.data && x.data.detail) || '创建失败';
        if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = detail; }
      }
    })
    .catch(function(err) {
      if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = '确认创建'; }
      if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '网络错误: ' + (err.message || ''); }
    });
}

function loadControlDevices() {
  return fetch(API_BASE + '/group-control/devices', { headers: authHeaders() })
    .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
    .then(function(x) {
      var list = x.ok && Array.isArray(x.data) ? x.data : [];
      list = list.slice().sort(function(a, b) {
        var na = parseInt(a.device_no, 10);
        var nb = parseInt(b.device_no, 10);
        var va = Number.isFinite(na) ? na : 999999;
        var vb = Number.isFinite(nb) ? nb : 999999;
        if (va !== vb) return va - vb;
        return String(a.device_label || a.alias || '').localeCompare(String(b.device_label || b.alias || ''));
      });
      controlDeviceListCache = list.slice();
      var selectEl = document.getElementById('controlTargetDeviceSelect');
      var selectModalEl = document.getElementById('controlTargetDeviceSelectModal');
      if (selectEl) selectEl.innerHTML = list.map(function(d) {
        var deviceLabel = d.device_label || d.alias || d.serial;
        var label = deviceLabel + (d.model ? (' [' + d.model + ']') : '');
        return '<option value="' + d.id + '">' + escapeHtml(label) + '</option>';
      }).join('');
      if (selectModalEl) selectModalEl.innerHTML = list.map(function(d) {
        var deviceLabel = d.device_label || d.alias || d.serial;
        var label = deviceLabel + (d.model ? (' [' + d.model + ']') : '');
        return '<option value="' + d.id + '">' + escapeHtml(label) + '</option>';
      }).join('');
      renderControlDevicesPage();
      return list;
    });
}

function loadDispatchGroups() {
  return fetch(API_BASE + '/group-control/dispatch-groups', { headers: authHeaders() })
    .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
    .then(function(x) {
      var list = x.ok && Array.isArray(x.data) ? x.data : [];
      var selectEl = document.getElementById('controlTargetGroupSelect');
      var modalSelectEl = document.getElementById('controlTargetGroupSelectModal');
      var html = '<option value="">不使用分组</option>' + list.map(function(g) {
        var label = g.name + ' (设备' + ((g.device_ids || []).length) + ')';
        return '<option value="' + g.id + '">' + escapeHtml(label) + '</option>';
      }).join('');
      if (selectEl) {
        selectEl.innerHTML = html;
        selectEl.dataset.groupMap = JSON.stringify(list || []);
      }
      if (modalSelectEl) {
        modalSelectEl.innerHTML = html;
        modalSelectEl.dataset.groupMap = JSON.stringify(list || []);
      }
      return list;
    });
}

// ── Event bindings (run after DOM ready) ──
var devSearch = document.getElementById('devicesSearchInput');
if (devSearch) devSearch.addEventListener('input', function() { controlDevicePage = 1; renderControlDevicesPage(); });

var modalCreatePlan = document.getElementById('modalCreatePlan');
if (modalCreatePlan) {
  modalCreatePlan.addEventListener('click', function(e) {
    if (e.target === modalCreatePlan) modalCreatePlan.classList.remove('visible');
  });
}
document.addEventListener('click', function(e) {
  var dd = document.getElementById('modalPlanModelDropdown');
  if (!dd) return;
  if (!dd.contains(e.target)) {
    var list = document.getElementById('modalPlanModelList');
    var toggle = document.getElementById('modalPlanModelToggle');
    if (list) list.classList.remove('open');
    if (toggle) toggle.classList.remove('open');
  }
});
var modalCreatePlanConfirm = document.getElementById('modalCreatePlanConfirm');
if (modalCreatePlanConfirm) {
  modalCreatePlanConfirm.addEventListener('click', _doCreatePlan);
}
var modalCreatePlanCancel = document.getElementById('modalCreatePlanCancel');
if (modalCreatePlanCancel) {
  modalCreatePlanCancel.addEventListener('click', function() {
    var m = document.getElementById('modalCreatePlan');
    if (m) m.classList.remove('visible');
  });
}
var batchCreatePlansBtn = document.getElementById('batchCreatePlansBtn');
if (batchCreatePlansBtn) {
  batchCreatePlansBtn.addEventListener('click', function() {
    var msgEl = document.getElementById('batchCreateMsg');
    if (!confirm('确定为所有设备批量创建养号计划？')) return;
    batchCreatePlansBtn.disabled = true;
    batchCreatePlansBtn.textContent = '批量创建中...';
    if (msgEl) { msgEl.style.color = 'var(--text-muted)'; msgEl.textContent = '正在为所有设备创建计划，请稍候（可能需要几十秒）...'; }
    fetch(API_BASE + '/group-control/nurture/plans/generate-batch', { method: 'POST', headers: authHeaders() })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .then(function(x) {
        batchCreatePlansBtn.disabled = false;
        batchCreatePlansBtn.textContent = '批量创建养号计划';
        if (x.ok && x.data) {
          var results = x.data.results || [];
          var okCount = results.filter(function(r) { return r.ok; }).length;
          var failCount = results.length - okCount;
          var txt = '批量完成: ' + okCount + '/' + results.length + ' 成功';
          if (failCount > 0) {
            var failDevices = results.filter(function(r) { return !r.ok; }).map(function(r) { return '设备#' + r.device_id + '(' + (r.error || '未知') + ')'; });
            txt += ' · 失败: ' + failDevices.join(', ');
          }
          if (msgEl) { msgEl.style.color = failCount > 0 ? '#b91c1c' : '#16a34a'; msgEl.textContent = txt; }
          loadNurturePanel();
          renderControlDevicesPage();
        } else {
          if (msgEl) { msgEl.style.color = '#b91c1c'; msgEl.textContent = (x.data && x.data.detail) || '批量创建失败'; }
        }
      })
      .catch(function(err) {
        batchCreatePlansBtn.disabled = false;
        batchCreatePlansBtn.textContent = '批量创建养号计划';
        if (msgEl) { msgEl.style.color = '#b91c1c'; msgEl.textContent = '网络错误: ' + (err.message || ''); }
      });
  });
}
