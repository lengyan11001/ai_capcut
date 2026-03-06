// gc-tasks.js - 群控：任务列表 + 分组管理 + Tab切换

function loadControlTasks() {
  return fetch(API_BASE + '/group-control/tasks?limit=100', { headers: authHeaders() })
    .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
    .then(function(x) {
      var list = x.ok && Array.isArray(x.data) ? x.data : [];
      var q = (document.getElementById('tasksSearchInput') || {}).value || '';
      q = q.toLowerCase().trim();
      if (q) list = list.filter(function(t) {
        return (t.title || '').toLowerCase().indexOf(q) >= 0 || String(t.id).indexOf(q) >= 0 || (t.status || '').toLowerCase().indexOf(q) >= 0 || (t.assigned_device_label || '').toLowerCase().indexOf(q) >= 0;
      });
      var el = document.getElementById('controlTasksList');
      if (!el) return;
      if (!list.length) { el.innerHTML = '<p class="meta">' + (q ? '未找到匹配任务' : '暂无任务') + '</p>'; return; }
      el.innerHTML = list.map(function(t) {
        var extra = [];
        if (t.target_device_id) extra.push('设备#' + t.target_device_id);
        if (t.assigned_device_label) extra.push('执行设备:' + t.assigned_device_label);
        if (t.dispatch_group_id) extra.push('分组#' + t.dispatch_group_id);
        return '<div class="list-item" data-task-id="' + t.id + '">' +
          '<div><div class="title">#' + t.id + ' ' + escapeHtml(t.title || '') + '</div><div class="meta">' +
          '状态: ' + escapeHtml(t.status || '-') + ' · 平台: ' + escapeHtml(t.platform || '-') + ' · 创建: ' +
          escapeHtml(t.created_at ? new Date(t.created_at).toLocaleString() : '-') +
          (extra.length ? (' · ' + escapeHtml(extra.join(' / '))) : '') +
          '</div></div>' +
          '<div class="acts">' +
          '<button type="button" class="btn btn-ghost btn-sm btn-task-detail">详情</button> ' +
          ((t.status === 'pending' || t.status === 'running') ? '<button type="button" class="btn btn-ghost btn-sm btn-task-cancel">取消</button> ' : '') +
          '<button type="button" class="btn btn-ghost btn-sm btn-task-delete" style="color:#b91c1c;">删除</button>' +
          '</div></div>';
      }).join('');
      el.querySelectorAll('.btn-task-detail').forEach(function(btn) {
        btn.addEventListener('click', function() {
          var id = parseInt(btn.closest('.list-item').dataset.taskId, 10);
          loadControlTaskDetail(id);
          var m = document.getElementById('modalTaskDetail');
          if (m) m.classList.add('visible');
        });
      });
      el.querySelectorAll('.btn-task-cancel').forEach(function(btn) {
        btn.addEventListener('click', function() {
          var id = parseInt(btn.closest('.list-item').dataset.taskId, 10);
          fetch(API_BASE + '/group-control/tasks/' + id + '/cancel', { method: 'POST', headers: authHeaders() })
            .then(function() { loadControlTasks(); })
            .catch(function() {});
        });
      });
      el.querySelectorAll('.btn-task-delete').forEach(function(btn) {
        btn.addEventListener('click', function() {
          var id = parseInt(btn.closest('.list-item').dataset.taskId, 10);
          if (!confirm('确定删除任务 #' + id + '？此操作不可恢复。')) return;
          fetch(API_BASE + '/group-control/tasks/' + id, { method: 'DELETE', headers: authHeaders() })
            .then(function() { loadControlTasks(); })
            .catch(function() {});
        });
      });
    });
}

function loadControlTaskDetail(taskId) {
  return fetch(API_BASE + '/group-control/tasks/' + taskId, { headers: authHeaders() })
    .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
    .then(function(x) {
      var el = document.getElementById('controlTaskDetail');
      if (!el) return;
      if (!x.ok) {
        el.innerHTML = '<p class="msg err">' + escapeHtml((x.data && x.data.detail) || '加载失败') + '</p>';
        return;
      }
      var task = x.data.task || {};
      var logs = Array.isArray(x.data.logs) ? x.data.logs : [];
      var head = '<div class="meta">#' + task.id + ' · ' + escapeHtml(task.status || '-') + '</div>' +
        '<div style="margin-top:0.35rem;"><strong>' + escapeHtml(task.title || '') + '</strong></div>' +
        (task.assigned_device_label ? ('<div class="meta" style="margin-top:0.3rem;">执行设备: ' + escapeHtml(task.assigned_device_label) + '</div>') : '');
      if (!logs.length) {
        el.innerHTML = head + '<p class="meta" style="margin-top:0.5rem;">暂无日志</p>';
        return;
      }
      el.innerHTML = head + logs.map(function(log) {
        var t = log.created_at ? new Date(log.created_at).toLocaleString() : '-';
        return '<div class="list-item" style="display:block;margin-top:0.5rem;">' +
          '<div class="meta">[' + escapeHtml(log.level || 'info') + '] ' + escapeHtml(t) + '</div>' +
          '<div style="margin-top:0.25rem;">' + escapeHtml(log.message || '') + '</div>' +
          (log.payload ? '<pre style="margin-top:0.35rem;white-space:pre-wrap;">' + escapeHtml(JSON.stringify(log.payload, null, 2)) + '</pre>' : '') +
          '</div>';
      }).join('');
    });
}

function loadGroupControl() {
  Promise.all([loadControlDevices(), loadNurtureModels()])
    .then(function() {
      return Promise.all([loadDispatchGroups(), loadControlTasks(), loadNurturePanel(), loadStatsPanel()]);
    })
    .catch(function() {});
}

function submitControlTask(formEl, msgElId, closeModalAfterSuccess) {
  if (!formEl) return;
  formEl.addEventListener('submit', function(e) {
    e.preventDefault();
    var fd = new FormData(formEl);
    var groupRaw = String(fd.get('target_group_id') || '').trim();
    var isModal = formEl.id === 'controlTaskModalForm';
    var deviceSel = document.getElementById(isModal ? 'controlTargetDeviceSelectModal' : 'controlTargetDeviceSelect');
    var targetDeviceIds = deviceSel ? Array.from(deviceSel.selectedOptions || []).map(function(o){ return parseInt(o.value, 10); }).filter(function(x){ return !isNaN(x); }) : [];
    var payload = {
      title: String(fd.get('title') || '').trim(),
      platform: 'reddit',
      task_type: 'reddit_flow',
      payload: {
        keyword: String(fd.get('keyword') || '').trim(),
        action: String(fd.get('action') || 'browse').trim()
      }
    };
    var extraRaw = String(fd.get('payload_extra_json') || '').trim();
    if (extraRaw) {
      try {
        var extraObj = JSON.parse(extraRaw);
        if (extraObj && typeof extraObj === 'object' && !Array.isArray(extraObj)) {
          payload.payload = Object.assign(payload.payload, extraObj);
        } else {
          var msgEl1 = document.getElementById('controlTaskMsg');
          if (msgEl1) { msgEl1.className = 'msg err'; msgEl1.textContent = '其他参数必须是 JSON 对象'; }
          return;
        }
      } catch (err) {
        var msgEl2 = document.getElementById('controlTaskMsg');
        if (msgEl2) { msgEl2.className = 'msg err'; msgEl2.textContent = '其他参数 JSON 解析失败'; }
        return;
      }
    }
    if (targetDeviceIds.length) payload.target_device_ids = targetDeviceIds;
    if (groupRaw) payload.target_group_id = parseInt(groupRaw, 10);
    var niche = String(fd.get('device_filter_niche') || '').trim();
    var minPhase = String(fd.get('device_filter_min_phase') || '').trim();
    var minKarma = String(fd.get('device_filter_min_karma') || '').trim();
    var tagsRaw = String(fd.get('device_filter_tags') || '').trim();
    if (niche || minPhase || minKarma || tagsRaw) {
      payload.device_filter = {};
      if (niche) payload.device_filter.niche = niche;
      if (minPhase) payload.device_filter.min_phase = minPhase;
      if (minKarma) payload.device_filter.min_karma = parseInt(minKarma, 10);
      if (tagsRaw) payload.device_filter.tags = tagsRaw.split(',').map(function(t){ return t.trim(); }).filter(Boolean);
    }
    fetch(API_BASE + '/group-control/tasks', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(payload)
    })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .then(function(x) {
        var msgEl = document.getElementById(msgElId);
        if (!msgEl) return;
        if (x.ok) {
          msgEl.className = 'msg ok';
          var count = (x.data && x.data.created_count) || 1;
          msgEl.textContent = '任务已创建，数量=' + count + '，首个ID=' + (x.data && x.data.id);
          formEl.reset();
          loadDispatchGroups();
          loadControlTasks();
          if (closeModalAfterSuccess) {
            var modal = document.getElementById('modalControlTask');
            if (modal) modal.classList.remove('visible');
          }
        } else {
          msgEl.className = 'msg err';
          msgEl.textContent = (x.data && x.data.detail) || '创建失败';
        }
      })
      .catch(function(err) {
        var msgEl = document.getElementById(msgElId);
        if (!msgEl) return;
        msgEl.className = 'msg err';
        msgEl.textContent = '网络错误: ' + (err.message || '');
      });
  });
}

var refreshControlBtn = document.getElementById('refreshControlBtn');
if (refreshControlBtn) {
  refreshControlBtn.addEventListener('click', function() { loadGroupControl(); });
}

var tabBtns = document.querySelectorAll('.gc-tabs button[data-gc-tab]');
var panelMap = { stats: 'gcPanelStats', devices: 'gcPanelDevices', plans: 'gcPanelPlans', running: 'gcPanelRunning', tasks: 'gcPanelTasks' };
tabBtns.forEach(function(btn) {
  btn.addEventListener('click', function() {
    tabBtns.forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    Object.keys(panelMap).forEach(function(k) {
      var p = document.getElementById(panelMap[k]);
      if (p) p.classList.toggle('visible', k === btn.dataset.gcTab);
    });
    if (btn.dataset.gcTab === 'stats') loadStatsPanel();
    if (btn.dataset.gcTab === 'tasks') loadControlTasks();
    if (btn.dataset.gcTab === 'plans') loadNurturePanel();
    if (btn.dataset.gcTab === 'running') loadRunningPanel();
  });
});

var gcAddTaskBtn = document.getElementById('gcAddTaskBtn');
if (gcAddTaskBtn) {
  gcAddTaskBtn.addEventListener('click', function() {
    var modal = document.getElementById('modalControlTask');
    if (modal) modal.classList.add('visible');
  });
}

var closeTaskDetailBtn = document.getElementById('closeTaskDetailBtn');
if (closeTaskDetailBtn) {
  closeTaskDetailBtn.addEventListener('click', function() {
    var m = document.getElementById('modalTaskDetail');
    if (m) m.classList.remove('visible');
  });
}

var openControlTaskModalBtn = document.getElementById('openControlTaskModalBtn');
if (openControlTaskModalBtn) {
  openControlTaskModalBtn.addEventListener('click', function() {
    var modal = document.getElementById('modalControlTask');
    if (modal) modal.classList.add('visible');
  });
}

var closeControlTaskModalBtn = document.getElementById('closeControlTaskModalBtn');
if (closeControlTaskModalBtn) {
  closeControlTaskModalBtn.addEventListener('click', function() {
    var modal = document.getElementById('modalControlTask');
    if (modal) modal.classList.remove('visible');
  });
}

var modalControlTask = document.getElementById('modalControlTask');
if (modalControlTask) {
  modalControlTask.addEventListener('click', function(e) {
    if (e.target === modalControlTask) modalControlTask.classList.remove('visible');
  });
}

var createDispatchGroupBtn = document.getElementById('createDispatchGroupBtn');
if (createDispatchGroupBtn) {
  createDispatchGroupBtn.addEventListener('click', function() {
    var name = String((document.getElementById('newDispatchGroupName') || {}).value || '').trim();
    var msgEl = document.getElementById('controlTaskMsg');
    if (!name) {
      if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '请先输入分组名称'; }
      return;
    }
    var deviceSel = document.getElementById('controlTargetDeviceSelect');
    var deviceIds = deviceSel ? Array.from(deviceSel.selectedOptions || []).map(function(o){ return parseInt(o.value, 10); }).filter(function(x){ return !isNaN(x); }) : [];
    fetch(API_BASE + '/group-control/dispatch-groups', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ name: name, device_ids: deviceIds })
    })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .then(function(x) {
        if (!msgEl) return;
        if (x.ok) {
          msgEl.className = 'msg ok';
          msgEl.textContent = '分组已创建：' + name;
          document.getElementById('newDispatchGroupName').value = '';
          loadDispatchGroups();
        } else {
          msgEl.className = 'msg err';
          msgEl.textContent = (x.data && x.data.detail) || '创建分组失败';
        }
      })
      .catch(function(err) {
        if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '网络错误: ' + (err.message || ''); }
      });
  });
}

var updateDispatchGroupBtn = document.getElementById('updateDispatchGroupBtn');
if (updateDispatchGroupBtn) {
  updateDispatchGroupBtn.addEventListener('click', function() {
    var selectEl = document.getElementById('controlTargetGroupSelect');
    var gid = parseInt(String(selectEl && selectEl.value || '').trim(), 10);
    var msgEl = document.getElementById('controlTaskMsg');
    if (!gid) {
      if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '请先选择分组'; }
      return;
    }
    var deviceSel = document.getElementById('controlTargetDeviceSelect');
    var deviceIds = deviceSel ? Array.from(deviceSel.selectedOptions || []).map(function(o){ return parseInt(o.value, 10); }).filter(function(x){ return !isNaN(x); }) : [];
    var gMap = [];
    try { gMap = JSON.parse(selectEl.dataset.groupMap || '[]'); } catch (e) {}
    var current = (gMap || []).find(function(g){ return g.id === gid; }) || {};
    fetch(API_BASE + '/group-control/dispatch-groups/' + gid, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({
        name: current.name || ('group-' + gid),
        device_ids: deviceIds,
        notes: current.notes || null
      })
    })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .then(function(x) {
        if (!msgEl) return;
        if (x.ok) {
          msgEl.className = 'msg ok';
          msgEl.textContent = '分组已更新';
          loadDispatchGroups();
        } else {
          msgEl.className = 'msg err';
          msgEl.textContent = (x.data && x.data.detail) || '更新分组失败';
        }
      })
      .catch(function(err) {
        if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '网络错误: ' + (err.message || ''); }
      });
  });
}

var deleteDispatchGroupBtn = document.getElementById('deleteDispatchGroupBtn');
if (deleteDispatchGroupBtn) {
  deleteDispatchGroupBtn.addEventListener('click', function() {
    var selectEl = document.getElementById('controlTargetGroupSelect');
    var gid = parseInt(String(selectEl && selectEl.value || '').trim(), 10);
    var msgEl = document.getElementById('controlTaskMsg');
    if (!gid) {
      if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '请先选择分组'; }
      return;
    }
    if (!confirm('确认删除当前分组？')) return;
    fetch(API_BASE + '/group-control/dispatch-groups/' + gid, {
      method: 'DELETE',
      headers: authHeaders()
    })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .then(function(x) {
        if (!msgEl) return;
        if (x.ok) {
          msgEl.className = 'msg ok';
          msgEl.textContent = '分组已删除';
          loadDispatchGroups();
        } else {
          msgEl.className = 'msg err';
          msgEl.textContent = (x.data && x.data.detail) || '删除分组失败';
        }
      })
      .catch(function(err) {
        if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '网络错误: ' + (err.message || ''); }
      });
  });
}

var controlTargetGroupSelect = document.getElementById('controlTargetGroupSelect');
if (controlTargetGroupSelect) {
  controlTargetGroupSelect.addEventListener('change', function() {
    var gid = parseInt(String(controlTargetGroupSelect.value || '').trim(), 10);
    if (!gid) return;
    var gMap = [];
    try { gMap = JSON.parse(controlTargetGroupSelect.dataset.groupMap || '[]'); } catch (e) {}
    var current = (gMap || []).find(function(g){ return g.id === gid; }) || null;
    if (!current) return;
    var deviceSel = document.getElementById('controlTargetDeviceSelect');
    if (deviceSel) {
      Array.from(deviceSel.options || []).forEach(function(opt){
        opt.selected = (current.device_ids || []).indexOf(parseInt(opt.value, 10)) >= 0;
      });
    }
  });
}

var controlTargetGroupSelectModal = document.getElementById('controlTargetGroupSelectModal');
if (controlTargetGroupSelectModal) {
  controlTargetGroupSelectModal.addEventListener('change', function() {
    var gid = parseInt(String(controlTargetGroupSelectModal.value || '').trim(), 10);
    if (!gid) return;
    var gMap = [];
    try { gMap = JSON.parse(controlTargetGroupSelectModal.dataset.groupMap || '[]'); } catch (e) {}
    var current = (gMap || []).find(function(g){ return g.id === gid; }) || null;
    if (!current) return;
    var deviceSel = document.getElementById('controlTargetDeviceSelectModal');
    if (deviceSel) {
      Array.from(deviceSel.options || []).forEach(function(opt){
        opt.selected = (current.device_ids || []).indexOf(parseInt(opt.value, 10)) >= 0;
      });
    }
  });
}

var controlTaskForm = document.getElementById('controlTaskForm');
submitControlTask(controlTaskForm, 'controlTaskMsg', false);
var controlTaskModalForm = document.getElementById('controlTaskModalForm');
submitControlTask(controlTaskModalForm, 'controlTaskModalMsg', true);

var taskSearch = document.getElementById('tasksSearchInput');
if (taskSearch) taskSearch.addEventListener('input', function() { loadControlTasks(); });
