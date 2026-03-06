// fb-ads.js - FB投放 + 账号管理模块

var currentEditingAccountId = null;

function loadAccounts() {
  fetch(API_BASE + '/accounts', { headers: authHeaders() })
    .then(function(r) {
      if (r.status === 401) { token = null; localStorage.removeItem('token'); loadDashboard(); return null; }
      return r.json();
    })
    .then(function(list) {
      if (!list) return;
      var el = document.getElementById('accountList');
      if (!list.length) { el.innerHTML = '<p class="meta">暂无账号，请先新建。</p>'; return; }
      el.innerHTML = list.map(function(a) {
        return '<div class="list-item" data-id="' + a.id + '">' +
          '<div><div class="title">' + escapeHtml(a.name) + '</div><div class="meta">' + (a.account_type === 'login' ? '登录' : '固定Token') + '</div></div>' +
          '<div class="acts"><button type="button" class="btn btn-ghost btn-edit-account">编辑</button> <button type="button" class="btn btn-ghost btn-delete-account">删除</button></div></div>';
      }).join('');
      el.querySelectorAll('.btn-edit-account').forEach(function(b) {
        b.addEventListener('click', function() {
          var id = parseInt(b.closest('.list-item').dataset.id, 10);
          fetch(API_BASE + '/accounts/' + id, { headers: authHeaders() })
            .then(function(r) { return r.json(); })
            .then(function(a) {
              if (a.detail) { alert(a.detail); return; }
              currentEditingAccountId = id;
              document.getElementById('accountFormTitle').textContent = '编辑账号';
              document.getElementById('accountSubmitBtn').textContent = '保存修改';
              document.getElementById('accountCancelEditBtn').style.display = 'inline-block';
              var f = document.getElementById('accountForm');
              f.querySelector('[name="name"]').value = a.name || '';
              f.querySelector('[name="account_type"]').value = a.account_type || 'login';
              f.querySelector('[name="login_url"]').value = a.login_url || '';
              f.querySelector('[name="username"]').value = a.username || '';
              f.querySelector('[name="password"]').value = '';
              f.querySelector('[name="token_response_path"]').value = a.token_response_path || 'access_token';
              f.querySelector('[name="token_header_name"]').value = a.token_header_name || '';
              f.querySelector('[name="token_header_prefix"]').value = a.token_header_prefix || '';
              f.querySelector('[name="login_body"]').value = (a.login_body && typeof a.login_body === 'object') ? JSON.stringify(a.login_body, null, 2) : (a.login_body || '');
              f.querySelector('[name="static_headers"]').value = (a.static_headers && typeof a.static_headers === 'object') ? JSON.stringify(a.static_headers) : (a.static_headers || '');
              document.getElementById('accountLoginFields').style.display = (a.account_type === 'login') ? 'block' : 'none';
              document.getElementById('accountStaticFields').style.display = (a.account_type === 'static') ? 'block' : 'none';
            })
            .catch(function() { alert('加载失败'); });
        });
      });
      el.querySelectorAll('.btn-delete-account').forEach(function(b) {
        b.addEventListener('click', function() {
          if (!confirm('确定删除该账号？')) return;
          var id = parseInt(b.closest('.list-item').dataset.id, 10);
          fetch(API_BASE + '/accounts/' + id, { method: 'DELETE', headers: { 'Authorization': 'Bearer ' + token } })
            .then(function(r) {
              if (r.status === 204) loadAccounts();
              else r.json().then(function(d) { alert(d.detail || '删除失败'); });
            })
            .catch(function() { alert('网络错误'); });
        });
      });
    })
    .catch(function() { document.getElementById('accountList').innerHTML = '<p class="msg err">加载失败</p>'; });
}

document.getElementById('accountTypeSelect').addEventListener('change', function() {
  var isLogin = this.value === 'login';
  document.getElementById('accountLoginFields').style.display = isLogin ? 'block' : 'none';
  document.getElementById('accountStaticFields').style.display = isLogin ? 'none' : 'block';
});

function exitAccountEditMode() {
  currentEditingAccountId = null;
  document.getElementById('accountFormTitle').textContent = '新建账号';
  document.getElementById('accountSubmitBtn').textContent = '保存账号';
  document.getElementById('accountCancelEditBtn').style.display = 'none';
  document.getElementById('accountForm').reset();
  document.getElementById('accountLoginFields').style.display = 'block';
  document.getElementById('accountStaticFields').style.display = 'none';
}
document.getElementById('accountCancelEditBtn').addEventListener('click', function() {
  exitAccountEditMode();
  loadAccounts();
});
document.getElementById('accountForm').addEventListener('submit', function(e) {
  e.preventDefault();
  var fd = new FormData(this);
  var payload = {
    name: fd.get('name'),
    account_type: fd.get('account_type'),
    login_url: fd.get('login_url') || null,
    username: fd.get('username') || null,
    password: fd.get('password') || null,
    token_response_path: fd.get('token_response_path') || 'access_token',
    token_header_name: fd.get('token_header_name') && fd.get('token_header_name').trim() ? fd.get('token_header_name').trim() : null,
    token_header_prefix: fd.get('token_header_prefix') && fd.get('token_header_prefix').trim() ? fd.get('token_header_prefix').trim() : null,
    login_body: null,
    static_headers: null
  };
  var loginBodyRaw = fd.get('login_body');
  if (loginBodyRaw && loginBodyRaw.trim()) {
    try { payload.login_body = JSON.parse(loginBodyRaw); } catch (err) { alert('自定义登录 Body 必须是合法 JSON'); return; }
  }
  var raw = fd.get('static_headers');
  if (payload.account_type === 'static' && raw && raw.trim()) {
    try { payload.static_headers = JSON.parse(raw); } catch (err) { alert('Header 必须是合法 JSON'); return; }
  }
  if (currentEditingAccountId != null) {
    if (!payload.password || payload.password === '') delete payload.password;
    fetch(API_BASE + '/accounts/' + currentEditingAccountId, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(payload)
    })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .then(function(x) {
        if (x.ok) { exitAccountEditMode(); loadAccounts(); }
        else { alert(x.data.detail || '保存失败'); }
      })
      .catch(function() { alert('网络错误'); });
  } else {
    fetch(API_BASE + '/accounts', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(payload)
    })
      .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
      .then(function(x) {
        if (x.ok) { exitAccountEditMode(); loadAccounts(); }
        else { alert(x.data.detail || '保存失败'); }
      })
      .catch(function() { alert('网络错误'); });
  }
});

// ── FB 投放模块 ──

function renderPager(containerEl, currentPage, totalPages, totalItems, onPageChange) {
  if (!containerEl) return;
  containerEl.innerHTML =
    '<button type="button" class="btn btn-ghost btn-sm" ' + (currentPage <= 1 ? 'disabled' : '') + '>上一页</button>' +
    '<span class="meta">第 ' + currentPage + ' / ' + totalPages + ' 页（共' + totalItems + '条）</span>' +
    '<button type="button" class="btn btn-ghost btn-sm" ' + (currentPage >= totalPages ? 'disabled' : '') + '>下一页</button>';
  var btns = containerEl.querySelectorAll('button');
  btns[0].onclick = function() { if (currentPage > 1) onPageChange(currentPage - 1); };
  btns[1].onclick = function() { if (currentPage < totalPages) onPageChange(currentPage + 1); };
}

var _fbActiveTasks = [];
var _fbTaskToastEl = null;

function _ensureTaskToast() {
  if (_fbTaskToastEl) return _fbTaskToastEl;
  var el = document.createElement('div');
  el.id = 'fbTaskToast';
  el.style.cssText = 'position:fixed;bottom:1.5rem;right:1.5rem;z-index:9999;display:flex;flex-direction:column;gap:0.5rem;max-width:340px;';
  document.body.appendChild(el);
  _fbTaskToastEl = el;
  return el;
}

function _renderTaskToast() {
  var container = _ensureTaskToast();
  container.innerHTML = _fbActiveTasks.map(function(t) {
    var bg = t.status === 'completed' ? 'rgba(16,185,129,0.9)' : t.status === 'failed' ? 'rgba(239,68,68,0.9)' : 'rgba(6,182,212,0.85)';
    var pct = t.progress || 0;
    var bar = t.status === 'completed' || t.status === 'failed' ? '' :
      '<div style="height:3px;background:rgba(255,255,255,0.2);border-radius:2px;margin-top:4px;">' +
      '<div style="height:100%;width:' + pct + '%;background:#fff;border-radius:2px;transition:width 0.3s;"></div></div>';
    var label = t.label || t.task_type;
    var msg = t.status === 'completed' ? '完成' : t.status === 'failed' ? (t.error_message || '失败') : (pct ? pct + '%' : '处理中...');
    return '<div style="background:' + bg + ';color:#fff;padding:0.6rem 0.9rem;border-radius:var(--radius-sm);font-size:0.82rem;backdrop-filter:blur(6px);">'
      + '<div style="display:flex;justify-content:space-between;"><span>' + escapeHtml(label) + '</span><span>' + escapeHtml(msg) + '</span></div>'
      + bar + '</div>';
  }).join('');
}

function submitAsyncTask(taskType, payload, onComplete, label) {
  var taskEntry = { task_type: taskType, label: label || taskType, status: 'pending', progress: 0 };
  _fbActiveTasks.push(taskEntry);
  _renderTaskToast();

  fetch(API_BASE + '/fb-api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
    body: JSON.stringify({ task_type: taskType, payload: payload })
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (!data.task_id) {
      taskEntry.status = 'failed';
      taskEntry.error_message = data.detail || 'Submit failed';
      _renderTaskToast();
      setTimeout(function() { _removeTaskEntry(taskEntry); }, 4000);
      return;
    }
    taskEntry.task_id = data.task_id;
    _pollTask(taskEntry, onComplete);
  })
  .catch(function(err) {
    taskEntry.status = 'failed';
    taskEntry.error_message = err.message;
    _renderTaskToast();
    setTimeout(function() { _removeTaskEntry(taskEntry); }, 4000);
  });
}

function _pollTask(entry, onComplete) {
  var interval = 2000;
  var maxInterval = 10000;
  function poll() {
    fetch(API_BASE + '/fb-api/tasks/' + entry.task_id, {
      headers: { 'Authorization': 'Bearer ' + token }
    })
    .then(function(r) { return r.json(); })
    .then(function(task) {
      entry.status = task.status;
      entry.progress = task.progress || 0;
      entry.error_message = task.error_message;
      _renderTaskToast();

      if (task.status === 'completed') {
        setTimeout(function() { _removeTaskEntry(entry); }, 3000);
        if (onComplete) onComplete(task.result);
      } else if (task.status === 'failed') {
        setTimeout(function() { _removeTaskEntry(entry); }, 5000);
      } else {
        interval = Math.min(interval * 1.5, maxInterval);
        setTimeout(poll, interval);
      }
    })
    .catch(function() {
      interval = Math.min(interval * 2, maxInterval);
      setTimeout(poll, interval);
    });
  }
  setTimeout(poll, interval);
}

function _removeTaskEntry(entry) {
  var idx = _fbActiveTasks.indexOf(entry);
  if (idx >= 0) _fbActiveTasks.splice(idx, 1);
  _renderTaskToast();
}

// ── FB Accounts ──
var fbAccountsPage = 1;

function loadFbAccounts(page) {
  page = page || fbAccountsPage;
  fbAccountsPage = page;
  var search = (document.getElementById('fbAccountSearch') || {}).value || '';
  fetch(API_BASE + '/fb-api/accounts?page=' + page + '&page_size=20&search=' + encodeURIComponent(search), {
    headers: { 'Authorization': 'Bearer ' + token }
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    var tbody = document.getElementById('fbAccountsTbody');
    if (!tbody) return;
    if (!data.items || !data.items.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:2rem;">暂无广告账户，点击「+ 新增账户」添加</td></tr>';
      renderPager(document.getElementById('fbAccountsPager'), 1, 1, 0, function(){});
      return;
    }
    tbody.innerHTML = data.items.map(function(a) {
      var sc = a.status === 'active' ? 'color:#10b981;' : a.status === 'token_invalid' ? 'color:#ef4444;' : 'color:#facc15;';
      var statusText = a.status === 'active' ? '正常' : a.status === 'token_invalid' ? 'Token无效' : a.status;
      return '<tr>'
        + '<td>' + escapeHtml(a.bm_id || '-') + '</td>'
        + '<td style="font-size:0.8rem;">' + escapeHtml(a.ad_account_id) + '</td>'
        + '<td>' + escapeHtml(a.name) + '</td>'
        + '<td><span style="' + sc + '">' + escapeHtml(statusText) + '</span></td>'
        + '<td>' + escapeHtml(a.currency) + '</td>'
        + '<td style="font-size:0.78rem;">' + escapeHtml((a.created_at || '').substring(0, 10)) + '</td>'
        + '<td><button class="btn btn-ghost btn-sm" onclick="fbEditAccount(' + a.id + ')">编辑</button>'
        + ' <button class="btn btn-ghost btn-sm" style="color:var(--error);" onclick="fbDeleteAccount(' + a.id + ',\'' + escapeHtml(a.name) + '\')">删除</button></td>'
        + '</tr>';
    }).join('');
    var totalPages = Math.ceil(data.total / (data.page_size || 20));
    renderPager(document.getElementById('fbAccountsPager'), data.page, totalPages, data.total, loadFbAccounts);
  })
  .catch(function(err) {
    var tbody = document.getElementById('fbAccountsTbody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="color:var(--error);text-align:center;">加载失败：' + escapeHtml(err.message) + '</td></tr>';
  });
}

function fbOpenAccountModal(editId) {
  document.getElementById('fbAccountModal').style.display = 'flex';
  document.getElementById('fbAccountModalTitle').textContent = editId ? '编辑广告账户' : '新增广告账户';
  document.getElementById('fbAccEditId').value = editId || '';
  if (!editId) {
    ['fbAccBmId','fbAccAdAccountId','fbAccName','fbAccAccessToken','fbAccAppId','fbAccAppSecret'].forEach(function(id) {
      document.getElementById(id).value = '';
    });
  }
}

function fbEditAccount(accountId) {
  fetch(API_BASE + '/fb-api/accounts/' + accountId, { headers: { 'Authorization': 'Bearer ' + token } })
  .then(function(r) { return r.json(); })
  .then(function(a) {
    fbOpenAccountModal(a.id);
    document.getElementById('fbAccBmId').value = a.bm_id || '';
    document.getElementById('fbAccAdAccountId').value = a.ad_account_id || '';
    document.getElementById('fbAccName').value = a.name || '';
    document.getElementById('fbAccAccessToken').value = '';
    document.getElementById('fbAccAccessToken').placeholder = '留空则不修改';
  });
}

function fbDeleteAccount(accountId, name) {
  if (!confirm('确认删除账户「' + name + '」？')) return;
  submitAsyncTask('fb.delete_account', { account_id: accountId }, function() {
    loadFbAccounts();
  }, '删除账户: ' + name);
}

var addBtn = document.getElementById('fbAddAccountBtn');
if (addBtn) addBtn.addEventListener('click', function() { fbOpenAccountModal(); });

var cancelBtn = document.getElementById('fbAccModalCancelBtn');
if (cancelBtn) cancelBtn.addEventListener('click', function() { document.getElementById('fbAccountModal').style.display = 'none'; });

var confirmBtn = document.getElementById('fbAccModalConfirmBtn');
if (confirmBtn) confirmBtn.addEventListener('click', function() {
  var editId = document.getElementById('fbAccEditId').value;
  var payload = {
    bm_id: document.getElementById('fbAccBmId').value.trim(),
    ad_account_id: document.getElementById('fbAccAdAccountId').value.trim(),
    name: document.getElementById('fbAccName').value.trim(),
    access_token: document.getElementById('fbAccAccessToken').value.trim(),
    app_id: document.getElementById('fbAccAppId').value.trim(),
    app_secret: document.getElementById('fbAccAppSecret').value.trim()
  };
  if (!payload.ad_account_id) { alert('请输入广告户 ID'); return; }
  if (!editId && !payload.access_token) { alert('请输入 Access Token'); return; }

  var taskType = editId ? 'fb.update_account' : 'fb.create_account';
  if (editId) payload.account_id = Number(editId);
  var label = editId ? '更新账户' : '新增账户';

  document.getElementById('fbAccountModal').style.display = 'none';
  submitAsyncTask(taskType, payload, function() { loadFbAccounts(); }, label);
});

var refreshBtn = document.getElementById('fbRefreshAccountsBtn');
if (refreshBtn) refreshBtn.addEventListener('click', function() { loadFbAccounts(); });

var searchInput = document.getElementById('fbAccountSearch');
if (searchInput) {
  var _fbSearchTimer;
  searchInput.addEventListener('input', function() {
    clearTimeout(_fbSearchTimer);
    _fbSearchTimer = setTimeout(function() { loadFbAccounts(1); }, 400);
  });
}

// ── FB Plans ──
var fbPlansPage = 1;

function loadFbPlans(page) {
  page = page || fbPlansPage;
  fbPlansPage = page;
  fetch(API_BASE + '/fb-api/plans?page=' + page + '&page_size=20', {
    headers: { 'Authorization': 'Bearer ' + token }
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    var tbody = document.getElementById('fbPlansTbody');
    if (!tbody) return;
    if (!data.items || !data.items.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:1.5rem;">暂无投放计划</td></tr>';
      renderPager(document.getElementById('fbPlansPager'), 1, 1, 0, function(){});
      return;
    }
    tbody.innerHTML = data.items.map(function(p) {
      var sc = p.status === 'draft' ? 'color:#facc15;' : p.status === 'active' ? 'color:#10b981;' : p.status === 'failed' ? 'color:#ef4444;' : '';
      var statusMap = { draft: '待确认', executing: '执行中', active: '投放中', cancelled: '已取消', failed: '失败' };
      var countries = p.target_countries ? (Array.isArray(p.target_countries) ? p.target_countries.join(', ') : JSON.stringify(p.target_countries)) : '-';
      var actions = '';
      if (p.status === 'draft') {
        actions = '<button class="btn btn-primary btn-sm" onclick="fbReviewPlan(\'' + escapeHtml(p.plan_uid) + '\')">审核</button>';
      } else {
        actions = '<button class="btn btn-ghost btn-sm" onclick="fbReviewPlan(\'' + escapeHtml(p.plan_uid) + '\')">查看</button>';
      }
      return '<tr>'
        + '<td style="font-size:0.8rem;">' + escapeHtml(p.plan_uid.substring(0, 8)) + '</td>'
        + '<td>' + escapeHtml(p.model_used || '-') + '</td>'
        + '<td>' + escapeHtml(countries) + '</td>'
        + '<td>' + (p.daily_budget ? '$' + p.daily_budget : '-') + '</td>'
        + '<td><span style="' + sc + '">' + escapeHtml(statusMap[p.status] || p.status) + '</span></td>'
        + '<td style="font-size:0.78rem;">' + escapeHtml((p.created_at || '').substring(0, 10)) + '</td>'
        + '<td>' + actions + '</td>'
        + '</tr>';
    }).join('');
    var totalPages = Math.ceil(data.total / (data.page_size || 20));
    renderPager(document.getElementById('fbPlansPager'), data.page, totalPages, data.total, loadFbPlans);
  });
}

function fbReviewPlan(planUid) {
  fetch(API_BASE + '/fb-api/plans/' + planUid, {
    headers: { 'Authorization': 'Bearer ' + token }
  })
  .then(function(r) { return r.json(); })
  .then(function(plan) {
    var content = document.getElementById('fbPlanReviewContent');
    if (!content) return;
    var countries = plan.target_countries ? (Array.isArray(plan.target_countries) ? plan.target_countries.join(', ') : JSON.stringify(plan.target_countries)) : '-';
    var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;font-size:0.88rem;">'
      + '<div><strong>计划 ID:</strong> ' + escapeHtml(plan.plan_uid) + '</div>'
      + '<div><strong>模型:</strong> ' + escapeHtml(plan.model_used || '-') + '</div>'
      + '<div><strong>目标国家:</strong> ' + escapeHtml(countries) + '</div>'
      + '<div><strong>日预算:</strong> $' + (plan.daily_budget || 0) + '</div>'
      + '<div><strong>预扣积分:</strong> ' + plan.credits_pre_deducted + '</div>'
      + '<div><strong>状态:</strong> ' + escapeHtml(plan.status) + '</div>'
      + '</div>';

    if (plan.product_description) {
      html += '<div style="margin-top:1rem;"><strong>产品描述:</strong><p style="color:var(--text-muted);font-size:0.85rem;margin-top:0.25rem;">' + escapeHtml(plan.product_description) + '</p></div>';
    }

    if (plan.plan_json) {
      var pj = plan.plan_json;
      html += '<div style="margin-top:1rem;"><strong>Campaign:</strong> ' + escapeHtml(pj.campaign ? pj.campaign.name || '' : '') + '</div>';
      if (pj.ad_sets && pj.ad_sets.length) {
        html += '<div style="margin-top:0.75rem;">';
        pj.ad_sets.forEach(function(as, i) {
          html += '<div style="background:rgba(255,255,255,0.03);border-radius:var(--radius-sm);padding:0.5rem 0.75rem;margin-bottom:0.5rem;">'
            + '<div style="font-weight:600;">AdSet ' + (i + 1) + ': ' + escapeHtml(as.name || '') + '</div>'
            + '<div style="font-size:0.82rem;color:var(--text-muted);">预算占比: ' + Math.round((as.budget_ratio || 0) * 100) + '%'
            + ' | 出价策略: ' + escapeHtml(as.bid_strategy || '-') + '</div>';
          if (as.ads && as.ads.length) {
            as.ads.forEach(function(ad, j) {
              html += '<div style="margin-left:1rem;font-size:0.82rem;margin-top:0.25rem;">Ad ' + (j + 1) + ': ' + escapeHtml(ad.headline || ad.name || '') + '</div>';
            });
          }
          html += '</div>';
        });
        html += '</div>';
      }
    }

    content.innerHTML = html;
    document.getElementById('fbPlanReviewModal').style.display = 'flex';

    var execBtn = document.getElementById('fbPlanExecuteBtn');
    var cancelPlanBtn = document.getElementById('fbPlanCancelBtn');
    if (plan.status === 'draft') {
      execBtn.style.display = '';
      cancelPlanBtn.style.display = '';
      execBtn.onclick = function() {
        document.getElementById('fbPlanReviewModal').style.display = 'none';
        submitAsyncTask('fb.execute_plan', { plan_id: plan.id }, function() {
          loadFbPlans();
          loadFbCampaigns();
        }, '执行投放计划');
      };
      cancelPlanBtn.onclick = function() {
        document.getElementById('fbPlanReviewModal').style.display = 'none';
      };
    } else {
      execBtn.style.display = 'none';
      cancelPlanBtn.style.display = 'none';
    }
  });
}

var closeBtn = document.getElementById('fbPlanCloseBtn');
if (closeBtn) closeBtn.addEventListener('click', function() {
  document.getElementById('fbPlanReviewModal').style.display = 'none';
});

// ── FB Campaigns ──
var fbCampaignsPage = 1;

function loadFbCampaigns(page) {
  page = page || fbCampaignsPage;
  fbCampaignsPage = page;
  var statusFilter = (document.getElementById('fbCampaignStatusFilter') || {}).value || '';
  var url = API_BASE + '/fb-api/campaigns?page=' + page + '&page_size=20';
  if (statusFilter) url += '&status=' + statusFilter;
  fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    var tbody = document.getElementById('fbCampaignsTbody');
    if (!tbody) return;
    if (!data.items || !data.items.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:1.5rem;">暂无活跃 Campaign</td></tr>';
      renderPager(document.getElementById('fbCampaignsPager'), 1, 1, 0, function(){});
      return;
    }
    tbody.innerHTML = data.items.map(function(c) {
      var sc = c.status === 'active' ? 'color:#10b981;' : c.status === 'paused' ? 'color:#facc15;' : '';
      var statusMap = { active: '投放中', paused: '已暂停', draft: '草稿' };
      var actions = '';
      if (c.status === 'active') {
        actions = '<button class="btn btn-ghost btn-sm" onclick="fbPauseCampaign(' + c.id + ')">暂停</button>';
      } else if (c.status === 'paused') {
        actions = '<button class="btn btn-ghost btn-sm" onclick="fbResumeCampaign(' + c.id + ')">启动</button>';
      }
      return '<tr>'
        + '<td>' + escapeHtml(c.name) + '</td>'
        + '<td>' + escapeHtml(c.objective) + '</td>'
        + '<td>$' + c.daily_budget + '</td>'
        + '<td><span style="' + sc + '">' + escapeHtml(statusMap[c.status] || c.status) + '</span></td>'
        + '<td style="font-size:0.78rem;">' + escapeHtml((c.created_at || '').substring(0, 10)) + '</td>'
        + '<td>' + actions + '</td>'
        + '</tr>';
    }).join('');
    var totalPages = Math.ceil(data.total / (data.page_size || 20));
    renderPager(document.getElementById('fbCampaignsPager'), data.page, totalPages, data.total, loadFbCampaigns);
  });
}

function fbPauseCampaign(cid) {
  submitAsyncTask('fb.pause_campaign', { campaign_id: cid }, function() { loadFbCampaigns(); }, '暂停 Campaign');
}
function fbResumeCampaign(cid) {
  submitAsyncTask('fb.resume_campaign', { campaign_id: cid }, function() { loadFbCampaigns(); }, '启动 Campaign');
}

var refreshCampaignsBtn = document.getElementById('fbRefreshCampaignsBtn');
if (refreshCampaignsBtn) refreshCampaignsBtn.addEventListener('click', function() { loadFbPlans(); loadFbCampaigns(); });
var statusFilter = document.getElementById('fbCampaignStatusFilter');
if (statusFilter) statusFilter.addEventListener('change', function() { loadFbCampaigns(1); });

// ── FB Creatives (placeholder) ──
function loadFbCreatives() {
  var grid = document.getElementById('fbCreativesGrid');
  if (!grid) return;
  grid.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:3rem;">素材库功能将在 Phase 2 完善</div>';
}
var fbRefreshCreativesBtn = document.getElementById('fbRefreshCreativesBtn');
if (fbRefreshCreativesBtn) fbRefreshCreativesBtn.addEventListener('click', function() { loadFbCreatives(); });

// ── FB Analytics (placeholder) ──
function loadFbAnalytics() {
  var cards = document.getElementById('fbAnalyticsCards');
  if (!cards) return;
  var metrics = [
    { label: '总花费', value: '--' },
    { label: '总转化', value: '--' },
    { label: '平均 CPA', value: '--' },
    { label: 'ROAS', value: '--' }
  ];
  cards.innerHTML = metrics.map(function(m) {
    return '<div class="card"><div class="card-label">' + escapeHtml(m.label) + '</div>'
      + '<div class="card-value" style="font-size:1.1rem;">' + escapeHtml(m.value) + '</div></div>';
  }).join('');
  var detail = document.getElementById('fbAnalyticsDetail');
  if (detail) detail.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:2rem;">数据看板将在 Celery 数据同步接入后展示</div>';
}
var fbRefreshAnalyticsBtn = document.getElementById('fbRefreshAnalyticsBtn');
if (fbRefreshAnalyticsBtn) fbRefreshAnalyticsBtn.addEventListener('click', function() { loadFbAnalytics(); });
