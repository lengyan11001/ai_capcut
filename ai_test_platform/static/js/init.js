// init.js - Auth, dashboard initialization, navigation, testAI/skill panels

    document.querySelectorAll('.tabs button').forEach(function(btn) {
      btn.addEventListener('click', function() {
        document.querySelectorAll('.tabs button').forEach(function(b) { b.classList.remove('active'); });
        document.querySelectorAll('#authPanel form').forEach(function(f) { f.classList.remove('visible'); });
        btn.classList.add('active');
        var form = btn.dataset.tab === 'login' ? document.getElementById('loginForm') : document.getElementById('registerForm');
        if (form) form.classList.add('visible');
      });
    });

    var refreshBtn = document.getElementById('refreshLibrariesBtn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', function() {
        loadLibraries();
      });
    }

    document.getElementById('loginForm').addEventListener('submit', function(e) {
      e.preventDefault();
      var fd = new FormData(this);
      var body = new URLSearchParams({ username: fd.get('username'), password: fd.get('password') });
      var msgEl = document.getElementById('loginMsg');
      fetch(API_BASE + '/auth/login', { method: 'POST', body, headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(x) {
          if (x.ok) {
            token = x.data.access_token;
            localStorage.setItem('token', token);
            showMsg(msgEl, '登录成功', false);
            loadDashboard();
          } else { showMsg(msgEl, x.data.detail || '登录失败', true); }
        })
        .catch(function() { showMsg(msgEl, '网络错误', true); });
    });

    document.getElementById('registerForm').addEventListener('submit', function(e) {
      e.preventDefault();
      var fd = new FormData(this);
      var msgEl = document.getElementById('registerMsg');
      fetch(API_BASE + '/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: fd.get('email'), password: fd.get('password') })
      })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(x) {
          if (x.ok) {
            pendingVerifyEmail = fd.get('email');
            showMsg(msgEl, '注册成功，验证码已发送到邮箱，请在下方输入验证码完成验证。', false);
            var sec = document.getElementById('verifyEmailSection');
            document.getElementById('verifyEmailInput').value = pendingVerifyEmail;
            sec.style.display = 'block';
          } else {
            showMsg(msgEl, x.data.detail || '注册失败', true);
          }
        })
        .catch(function() { showMsg(msgEl, '网络错误', true); });
    });

    document.getElementById('verifyEmailBtn').addEventListener('click', function() {
      var email = document.getElementById('verifyEmailInput').value || pendingVerifyEmail;
      var code = (document.getElementById('verifyCodeInput').value || '').trim();
      var msgEl = document.getElementById('verifyEmailMsg');
      if (!email || !code) {
        showMsg(msgEl, '请先填写验证码', true);
        return;
      }
      fetch(API_BASE + '/auth/verify-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, code: code })
      })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(x) {
          if (!x.ok) {
            showMsg(msgEl, x.data.detail || '验证失败', true);
            return;
          }
          token = x.data.access_token;
          localStorage.setItem('token', token);
          showMsg(msgEl, '验证成功，已自动登录。', false);
          loadDashboard();
        })
        .catch(function() { showMsg(msgEl, '网络错误', true); });
    });

    document.getElementById('resendCodeBtn').addEventListener('click', function() {
      var email = document.getElementById('verifyEmailInput').value || pendingVerifyEmail;
      var msgEl = document.getElementById('verifyEmailMsg');
      if (!email) {
        showMsg(msgEl, '请先完成注册', true);
        return;
      }
      fetch(API_BASE + '/auth/resend-verification', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email })
      })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(x) {
          showMsg(msgEl, x.data.detail || (x.ok ? '验证码已发送' : '发送失败'), !x.ok);
        })
        .catch(function() { showMsg(msgEl, '网络错误', true); });
    });

    function loadDashboard() {
      if (!token) {
        document.getElementById('authPanel').style.display = 'block';
        document.getElementById('dashboard').classList.remove('visible');
        document.getElementById('headerActions').style.display = 'none';
        var heroEl = document.getElementById('pageHero');
        if (heroEl) heroEl.style.display = '';
        return;
      }
      fetch(API_BASE + '/auth/me', { headers: { 'Authorization': 'Bearer ' + token } })
        .then(function(r) {
          if (r.status === 401) { token = null; localStorage.removeItem('token'); loadDashboard(); return null; }
          return r.json();
        })
        .then(function(d) {
          if (!d) return;
          currentUserProfile = d;
          document.getElementById('userEmail').textContent = d.email;
          document.getElementById('userCredits').textContent = d.credits;
          document.getElementById('headerCredits').textContent = d.credits + ' 积分';
          document.getElementById('headerActions').style.display = 'flex';
          document.getElementById('authPanel').style.display = 'none';
          document.getElementById('dashboard').classList.add('visible');
          loadAvailableCapabilities();
          var heroEl = document.getElementById('pageHero');
          if (heroEl) heroEl.style.display = 'none';
          var maskEl = document.getElementById('tokenMask');
          if (maskEl) maskEl.textContent = '••••••••••••';
          var headerTokenMask = document.getElementById('headerTokenMask');
          if (headerTokenMask) headerTokenMask.textContent = '••••••••••••';
          var copyTokenBtn = document.getElementById('copyTokenBtn');
          var headerCopyTokenBtn = document.getElementById('headerCopyTokenBtn');
          var copyMcpBtn = document.getElementById('copyMcpConfigBtn');
          if (copyTokenBtn && !copyTokenBtn._bound) {
            copyTokenBtn._bound = true;
            copyTokenBtn.addEventListener('click', function() {
              if (!token) return;
              copyToClipboard(token, function() {
                var t = copyTokenBtn.textContent;
                copyTokenBtn.textContent = '已复制';
                setTimeout(function() { copyTokenBtn.textContent = t; }, 1500);
              });
            });
          }
          if (headerCopyTokenBtn && !headerCopyTokenBtn._bound) {
            headerCopyTokenBtn._bound = true;
            headerCopyTokenBtn.addEventListener('click', function() {
              if (!token) return;
              copyToClipboard(token, function() {
                var t = headerCopyTokenBtn.textContent;
                headerCopyTokenBtn.textContent = '已复制';
                setTimeout(function() { headerCopyTokenBtn.textContent = t; }, 1500);
              });
            });
          }
          if (copyMcpBtn && !copyMcpBtn._bound) {
            copyMcpBtn._bound = true;
            copyMcpBtn.addEventListener('click', function() {
              if (!token) return;
              var baseUrl = window.location.origin || (window.location.protocol + '//' + window.location.host);
              var mcp = {
                mcpServers: {
                  'ai-test-platform': {
                    command: 'python',
                    args: ['-m', 'mcp'],
                    cwd: '请替换为你的 ai_test_platform 目录绝对路径',
                    env: {
                      AI_TEST_PLATFORM_BASE_URL: baseUrl,
                      AI_TEST_PLATFORM_TOKEN: token
                    }
                  }
                }
              };
              var jsonStr = JSON.stringify(mcp, null, 2);
              copyToClipboard(jsonStr, function() {
                var t = copyMcpBtn.textContent;
                copyMcpBtn.textContent = '已复制';
                setTimeout(function() { copyMcpBtn.textContent = t; }, 1500);
              });
            });
          }
          var copyHttpUrlBtn = document.getElementById('copyHttpUrlBtn');
          if (copyHttpUrlBtn && !copyHttpUrlBtn._bound) {
            copyHttpUrlBtn._bound = true;
            copyHttpUrlBtn.addEventListener('click', function() {
              if (!token) return;
              var host = window.location.hostname || 'localhost';
              var protocol = window.location.protocol || 'http:';
              var mcpHttpUrl = protocol + '//' + host + ':8001/mcp?token=' + encodeURIComponent(token);
              copyToClipboard(mcpHttpUrl, function() {
                var t = copyHttpUrlBtn.textContent;
                copyHttpUrlBtn.textContent = '已复制';
                setTimeout(function() { copyHttpUrlBtn.textContent = t; }, 1500);
              });
            });
          }
          loadTemplates();
          loadLlmModels();
          loadGenerateRecords();
          bindCreditFlowsClick();
          initChatSessions();
          toggleAdminOpsSection();
        });
    }

    function openCreditFlowsModal() {
      document.getElementById('modalCreditFlows').classList.add('visible');
      loadCreditFlows();
    }
    function loadCreditFlows() {
      var tbody = document.getElementById('creditFlowsBody');
      if (!tbody) return;
      tbody.innerHTML = '<tr><td colspan="5" class="text-muted">加载中…</td></tr>';
      fetch(API_BASE + '/auth/credit-flows?limit=100', { headers: authHeaders() })
        .then(function(r) {
          if (r.status === 401) { token = null; localStorage.removeItem('token'); loadDashboard(); return null; }
          return r.json();
        })
        .then(function(list) {
          if (!tbody) return;
          if (!Array.isArray(list)) { tbody.innerHTML = '<tr><td colspan="5" class="text-muted">加载失败</td></tr>'; return; }
          var typeLabel = { deduct: '扣费', refund: '退款', recharge: '充值' };
          if (list.length === 0) { tbody.innerHTML = '<tr><td colspan="5" class="text-muted">暂无记录</td></tr>'; return; }
          tbody.innerHTML = list.map(function(row) {
            var type = typeLabel[row.flow_type] || row.flow_type;
            var amountStr = row.flow_type === 'deduct' ? '-' + row.amount : '+' + row.amount;
            var amountCls = row.flow_type === 'deduct' ? 'err' : 'ok';
            var time = row.created_at ? new Date(row.created_at).toLocaleString() : '-';
            return '<tr><td>' + time + '</td><td>' + type + '</td><td class="' + amountCls + '">' + amountStr + '</td><td>' + (row.balance_after != null ? row.balance_after : '-') + '</td><td>' + (row.description || '-') + '</td></tr>';
          }).join('');
        })
        .catch(function() {
          if (tbody) tbody.innerHTML = '<tr><td colspan="5" class="text-muted">加载失败</td></tr>';
        });
    }
    document.getElementById('closeCreditFlows').addEventListener('click', function() {
      document.getElementById('modalCreditFlows').classList.remove('visible');
    });
    document.getElementById('modalCreditFlows').addEventListener('click', function(e) {
      if (e.target === this) document.getElementById('modalCreditFlows').classList.remove('visible');
    });
    function bindCreditFlowsClick() {
      var creditsFlowBtn = document.getElementById('creditsFlowBtn');
      if (creditsFlowBtn && !creditsFlowBtn._flowsBound) {
        creditsFlowBtn._flowsBound = true;
        creditsFlowBtn.addEventListener('click', openCreditFlowsModal);
      }
    }

    document.getElementById('logout').addEventListener('click', function() {
      token = null;
      localStorage.removeItem('token');
      document.getElementById('dashboard').classList.remove('visible');
      document.getElementById('authPanel').style.display = 'block';
      document.getElementById('headerActions').style.display = 'none';
      var heroEl = document.getElementById('pageHero');
      if (heroEl) heroEl.style.display = '';
    });

    (function initDropdown() {
      var dropdown = document.getElementById('headerUserDropdown');
      var btn = document.getElementById('headerDropdownBtn');
      if (dropdown && btn) {
        btn.addEventListener('click', function(e) { e.stopPropagation(); dropdown.classList.toggle('open'); });
        document.addEventListener('click', function() { dropdown.classList.remove('open'); });
      }
      var creditsFlowBtn = document.getElementById('creditsFlowBtn');
      if (creditsFlowBtn) creditsFlowBtn.addEventListener('click', function() { dropdown.classList.remove('open'); openCreditFlowsModal(); });
    })();

    document.querySelectorAll('.nav-left-item').forEach(function(el) {
      el.addEventListener('click', function() {
        var view = el.dataset.view;
        var capabilityId = el.dataset.capabilityId || '';
        if (!view) return;
        var _isFbView = view === 'fb-ads' || view.indexOf('fb-') === 0;
        var _isSkillView = view === 'skill' || view.indexOf('skill-') === 0;
        if (view === 'fb-ads') {
          var fbSub = document.getElementById('navFbSub');
          if (fbSub) fbSub.style.display = 'block';
          document.getElementById('navSkillSub').style.display = 'none';
          document.querySelectorAll('.nav-left-item').forEach(function(b) { b.classList.remove('active'); });
          el.classList.add('active');
          document.querySelectorAll('.content-block').forEach(function(p) { p.classList.remove('visible'); });
          var firstFb = document.getElementById('content-fb-accounts');
          if (firstFb) firstFb.classList.add('visible');
          var firstFbNav = document.querySelector('.nav-left-item[data-view="fb-accounts"]');
          if (firstFbNav) firstFbNav.classList.add('active');
          currentView = 'fb-accounts';
          if (typeof loadFbAccounts === 'function') loadFbAccounts();
          return;
        }
        if (view === 'skill') {
          var sub = document.getElementById('navSkillSub');
          if (sub) sub.style.display = 'block';
          document.getElementById('navFbSub').style.display = 'none';
          document.querySelectorAll('.nav-left-item').forEach(function(b) { b.classList.remove('active'); });
          el.classList.add('active');
          document.querySelectorAll('.content-block').forEach(function(p) { p.classList.remove('visible'); });
          var skillOverview = document.getElementById('content-skill');
          if (skillOverview) skillOverview.classList.add('visible');
          currentView = 'skill';
          if (!capabilityListCache.length) loadAvailableCapabilities();
          return;
        }
        if (currentView === 'chat' && view !== 'chat' && typeof saveCurrentSessionToStore === 'function') saveCurrentSessionToStore();
        document.querySelectorAll('.nav-left-item').forEach(function(b) { b.classList.remove('active'); });
        if (view === 'chat' || view === 'group-control' || view === 'admin-console') {
          document.getElementById('navSkillSub').style.display = 'none';
          document.getElementById('navFbSub').style.display = 'none';
          el.classList.add('active');
        } else if (_isFbView) {
          document.getElementById('navSkillSub').style.display = 'none';
          document.getElementById('navFbSub').style.display = 'block';
          document.querySelectorAll('.nav-left-item[data-view="fb-ads"]').forEach(function(b) { b.classList.add('active'); });
          el.classList.add('active');
        } else {
          document.getElementById('navFbSub').style.display = 'none';
          document.querySelectorAll('.nav-left-item[data-view="skill"]').forEach(function(b) { b.classList.add('active'); });
          document.getElementById('navSkillSub').style.display = 'block';
          el.classList.add('active');
        }
        document.querySelectorAll('.content-block').forEach(function(p) { p.classList.remove('visible'); });
        if (view !== 'group-control' && view.indexOf('gc') !== 0) {
          document.querySelectorAll('.gc-panel').forEach(function(p) { p.classList.remove('visible'); });
        }
        var contentId = view === 'chat' ? 'content-chat' : 'content-' + view;
        var contentEl = document.getElementById(contentId);
        if (contentEl) contentEl.classList.add('visible');
        currentView = view;
        if (view === 'skill-testAI') {
          if (!skillPanelLoaded.templates) { loadTemplates(); loadGenerateRecords(); skillPanelLoaded.templates = true; }
          if (!skillPanelLoaded.libraries) { loadLibraries(); loadLlmModels(); skillPanelLoaded.libraries = true; }
          if (!skillPanelLoaded.accounts) { loadAccounts(); skillPanelLoaded.accounts = true; }
        }
        if (view === 'skill-capability') {
          openCapabilityView(capabilityId);
        }
        if (view === 'group-control') {
          var activeGcTab = document.querySelector('.gc-tabs button.active');
          var activeKey = activeGcTab ? activeGcTab.dataset.gcTab : 'stats';
          var gcPanelMap = { stats: 'gcPanelStats', devices: 'gcPanelDevices', plans: 'gcPanelPlans', running: 'gcPanelRunning', tasks: 'gcPanelTasks' };
          Object.keys(gcPanelMap).forEach(function(k) {
            var p = document.getElementById(gcPanelMap[k]);
            if (p) p.classList.toggle('visible', k === activeKey);
          });
          loadGroupControl();
        }
        if (view === 'admin-console') {
          loadAdminOpsData();
        }
        if (view === 'fb-accounts' && typeof loadFbAccounts === 'function') loadFbAccounts();
        if (view === 'fb-campaigns' && typeof loadFbPlans === 'function') { loadFbPlans(); loadFbCampaigns(); }
        if (view === 'fb-creatives' && typeof loadFbCreatives === 'function') loadFbCreatives();
        if (view === 'fb-analytics' && typeof loadFbAnalytics === 'function') loadFbAnalytics();
      });
    });

    function loadLlmModels() {
      if (!token) return;
      var sels = document.querySelectorAll('select[data-llm-select]');
      if (!sels.length) return;
      if (llmModelsCache) {
        sels.forEach(function(sel) { renderLlmModelOptions(sel, llmModelsCache); });
        return;
      }
      fetch(API_BASE + '/auth/pricing', { headers: authHeaders() })
        .then(function(r) {
          if (!r.ok) return null;
          return r.json();
        })
        .then(function(d) {
          if (!d || !d.llm || !d.llm.models) {
            sels.forEach(function(sel) { renderLlmModelOptions(sel, null); });
            return;
          }
          llmModelsCache = d.llm;
          sels.forEach(function(sel) { renderLlmModelOptions(sel, llmModelsCache); });
        })
        .catch(function() {
          sels.forEach(function(sel) { renderLlmModelOptions(sel, null); });
        });
    }

    function renderLlmModelOptions(sel, llm) {
      var opts = ['<option value="">不使用大模型（免费）</option>'];
      if (llm && llm.enabled && llm.models) {
        Object.keys(llm.models).forEach(function(id) {
          var m = llm.models[id] || {};
          var label = m.display_name || id;
          opts.push('<option value="' + id + '">' + label + '</option>');
        });
      }
      sel.innerHTML = opts.join('');
    }

    function loadTemplates() {
      fetch(API_BASE + '/templates', { headers: authHeaders() })
        .then(function(r) {
          if (r.status === 401) { token = null; localStorage.removeItem('token'); loadDashboard(); return null; }
          return r.json();
        })
        .then(function(list) {
          if (!list) return;
          var el = document.getElementById('templateList');
          if (!list.length) { el.innerHTML = '<p class="meta">暂无模版，请先新建。</p>'; return; }
          el.innerHTML = list.map(function(t) {
            var urls = (t.schema_urls || []).length;
            var src = t.has_file ? '本地文件模版' : (urls + ' 个文档地址');
            return '<div class="list-item" data-id="' + t.id + '">' +
              '<div><div class="title">' + escapeHtml(t.name) + '</div><div class="meta">' + src + '</div></div>' +
              '<div class="acts"><button type="button" class="btn btn-primary btn-generate">生成用例</button></div></div>';
          }).join('');
          el.querySelectorAll('.btn-generate').forEach(function(b) {
            b.addEventListener('click', function() {
              templateIdForGenerate = parseInt(b.closest('.list-item').dataset.id, 10);
              document.getElementById('generateLibraryName').value = '';
              document.getElementById('generateEstimateResult').textContent = '';
              document.getElementById('modalGenerateCases').classList.add('visible');
            });
          });
        })
        .catch(function() { document.getElementById('templateList').innerHTML = '<p class="msg err">加载失败</p>'; });
    }

    function loadGenerateRecords() {
      fetch(API_BASE + '/templates/generate-records', { headers: authHeaders() })
        .then(function(r) {
          if (r.status === 401) { token = null; localStorage.removeItem('token'); loadDashboard(); return null; }
          return r.json();
        })
        .then(function(list) {
          var el = document.getElementById('generateRecordsList');
          if (!el) return;
          if (!list || !list.length) { el.innerHTML = '<p class="meta">暂无生成记录</p>'; return; }
          el.innerHTML = '<div class="table-wrap"><table class="records-table"><thead><tr><th>模版</th><th>用例库名</th><th>大模型</th><th>状态</th><th>原因 / 说明</th><th>时间</th></tr></thead><tbody>' +
            list.map(function(r) {
              var statusCls = r.status === 'success' ? 'ok' : (r.status === 'failed' ? 'err' : '');
              var statusText = r.status === 'success' ? '成功' : (r.status === 'failed' ? '失败' : '生成中');
              var time = (r.finished_at || r.created_at || '').slice(0, 19).replace('T', ' ');
              var msg = (r.message || '-');
              if (msg.length > 80) msg = msg.slice(0, 80) + '…';
              return '<tr><td>' + escapeHtml(r.template_name || '') + '</td><td>' + escapeHtml(r.library_name || '') + '</td><td>' + escapeHtml(r.llm_model_id || '-') + '</td><td class="' + statusCls + '">' + statusText + '</td><td title="' + escapeAttr(r.message || '') + '">' + escapeHtml(msg) + '</td><td>' + escapeHtml(time) + '</td></tr>';
            }).join('') +
            '</tbody></table></div>';
        })
        .catch(function() {
          var el = document.getElementById('generateRecordsList');
          if (el) el.innerHTML = '<p class="msg err">加载失败</p>';
        });
    }

    document.getElementById('templateForm').addEventListener('submit', function(e) {
      e.preventDefault();
      var fd = new FormData(this);
      var urlsText = (fd.get('schema_urls') || '').trim();
      var urls = urlsText.split(/\r?\n/).map(function(s) { return s.trim(); }).filter(Boolean);
      if (!urls.length) { alert('请至少填写一个文档地址'); return; }
      fetch(API_BASE + '/templates', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ name: fd.get('name'), schema_urls: urls, base_url: fd.get('base_url') || null })
      })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(x) {
          if (x.ok) { this.reset(); loadTemplates(); }
          else { alert(x.data.detail || '保存失败'); }
        }.bind(this))
        .catch(function() { alert('网络错误'); });
    });

    document.getElementById('templateUploadForm').addEventListener('submit', function(e) {
      e.preventDefault();
      var fd = new FormData(this);
      var name = fd.get('name');
      var file = fd.get('file');
      if (!name || !file || !file.size) {
        showMsg(document.getElementById('templateUploadMsg'), '请填写模版名称并选择文件', true);
        return;
      }
      var body = new FormData();
      body.append('name', name);
      body.append('file', file);
      var baseUrl = fd.get('base_url');
      if (baseUrl && baseUrl.trim()) body.append('base_url', baseUrl.trim());
      var msgEl = document.getElementById('templateUploadMsg');
      msgEl.style.display = 'none';
      fetch(API_BASE + '/templates/from-upload', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token },
        body: body
      })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(x) {
          if (x.ok) {
            showMsg(msgEl, '已保存模版「' + x.data.name + '」', false);
            msgEl.style.display = 'block';
            document.getElementById('templateUploadForm').reset();
            loadTemplates();
          } else {
            showMsg(msgEl, x.data.detail || '保存失败', true);
            msgEl.style.display = 'block';
          }
        })
        .catch(function() {
          showMsg(msgEl, '网络错误', true);
          msgEl.style.display = 'block';
        });
    });

    document.getElementById('btnEstimateCredits').addEventListener('click', function() {
      if (!templateIdForGenerate) return;
      var llmSel = document.getElementById('templateLlmModelSelect');
      var llmId = llmSel ? (llmSel.value || '') : '';
      if (!llmId) {
        document.getElementById('generateEstimateResult').textContent = '请先选择大模型';
        return;
      }
      var resultEl = document.getElementById('generateEstimateResult');
      resultEl.textContent = '计算中…';
      fetch(API_BASE + '/templates/' + templateIdForGenerate + '/generate-cases', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ llm_model_id: llmId, estimate_only: true })
      })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(x) {
          if (x.ok && x.data.estimate_only) {
            var d = x.data;
            var total = d.total_apis || d.total_cases || 0;
            var est = d.llm_estimate;
            if (est && typeof est.estimated_credits === 'number') {
              var tokens = est.estimated_total_tokens || 0;
              resultEl.textContent = '约 ' + total + ' 个接口，预计消耗约 ' + est.estimated_credits + ' 积分（约 ' + (tokens / 1000).toFixed(1) + 'K tokens）';
            } else {
              resultEl.textContent = '约 ' + total + ' 个接口';
            }
          } else {
            resultEl.textContent = x.data.detail || '预估失败';
          }
        })
        .catch(function() {
          document.getElementById('generateEstimateResult').textContent = '网络错误';
        });
    });

    var isGeneratingCases = false;
    var generateConfirmPending = false;
    document.getElementById('confirmGenerateCases').addEventListener('click', function() {
      if (isGeneratingCases) return;
      var name = document.getElementById('generateLibraryName').value.trim();
      var msgEl = document.getElementById('generateCasesMsg');
      msgEl.style.display = 'none';
      if (!name) {
        showMsg(msgEl, '请输入用例库名称', true);
        return;
      }
      if (!templateIdForGenerate) return;
      var llmSel = document.getElementById('templateLlmModelSelect');
      var llmId = llmSel ? (llmSel.value || '') : '';

      if (!generateConfirmPending) {
        var tip = '将根据当前模版创建用例库「' + name + '」。';
        if (llmId) {
          tip += ' 已选择大模型，生成过程中将按实际用量扣除大模型积分。再次点击「生成」确认。';
        } else {
          tip += ' 不使用大模型，仅规则生成。再次点击「生成」确认。';
        }
        showMsg(msgEl, tip, false);
        generateConfirmPending = true;
        return;
      }

      generateConfirmPending = false;
      var payload = { library_name: name };
      if (llmId) payload.llm_model_id = llmId;
      var btn = document.getElementById('confirmGenerateCases');
      var origText = btn.textContent;
      isGeneratingCases = true;
      btn.disabled = true;
      btn.textContent = '生成中…';
      var controller = new AbortController();
      var timeoutId = setTimeout(function() { controller.abort(); }, 180000);
      fetch(API_BASE + '/templates/' + templateIdForGenerate + '/generate-cases', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(payload),
        signal: controller.signal
      })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(x) {
          clearTimeout(timeoutId);
          isGeneratingCases = false;
          btn.disabled = false;
          btn.textContent = origText;
          if (x.ok) {
            document.getElementById('modalGenerateCases').classList.remove('visible');
            templateIdForGenerate = null;
            loadGenerateRecords();
          } else {
            showMsg(msgEl, x.data.detail || '生成失败', true);
          }
        })
        .catch(function(err) {
          clearTimeout(timeoutId);
          isGeneratingCases = false;
          btn.disabled = false;
          btn.textContent = origText;
          if (err.name === 'AbortError') {
            showMsg(msgEl, '请求超时（3 分钟），大模型可能响应过慢，请稍后重试或减少接口数量。', true);
          } else {
            showMsg(msgEl, '网络错误', true);
          }
        });
    });
    document.getElementById('cancelGenerateCases').addEventListener('click', function() {
      document.getElementById('modalGenerateCases').classList.remove('visible');
      templateIdForGenerate = null;
    });

    function loadLibraries() {
      fetch(API_BASE + '/case-libraries', { headers: authHeaders() })
        .then(function(r) {
          if (r.status === 401) { token = null; localStorage.removeItem('token'); loadDashboard(); return null; }
          return r.json();
        })
        .then(function(list) {
          if (!list) return;
          var listEl = document.getElementById('libraryList');
          var detailEl = document.getElementById('libraryDetail');
          detailEl.style.display = 'none';
          listEl.style.display = 'block';
          if (!list.length) { listEl.innerHTML = '<p class="meta">暂无用例库，请先在「文档模版」中保存模版后点击「生成用例」。</p>'; return; }
          listEl.innerHTML = list.map(function(l) {
            var up = (l.updated_at || '').slice(0, 16);
            return '<div class="list-item" data-id="' + l.id + '">' +
              '<div><div class="title">' + escapeHtml(l.name) + '</div><div class="meta">' + (l.cases_count || 0) + ' 条用例 · ' + up + '</div></div>' +
              '<div class="acts"><button type="button" class="btn btn-primary btn-edit-lib">编辑</button> <button type="button" class="btn btn-primary btn-exec-lib">执行</button> <button type="button" class="btn btn-ghost btn-delete-lib">删除</button></div></div>';
          }).join('');
          listEl.querySelectorAll('.btn-delete-lib').forEach(function(b) {
            b.addEventListener('click', function() {
              var id = parseInt(b.closest('.list-item').dataset.id, 10);
              if (!confirm('确定删除该用例库？其中用例将一并删除。')) return;
              fetch(API_BASE + '/case-libraries/' + id, { method: 'DELETE', headers: { 'Authorization': 'Bearer ' + token } })
                .then(function(r) {
                  if (r.status === 204) loadLibraries();
                  else return r.json().then(function(d) { alert(d.detail || '删除失败'); });
                })
                .catch(function() { alert('网络错误'); });
            });
          });
          listEl.querySelectorAll('.btn-edit-lib').forEach(function(b) {
            b.addEventListener('click', function() {
              var id = parseInt(b.closest('.list-item').dataset.id, 10);
              openLibraryDetail(id);
            });
          });
          listEl.querySelectorAll('.btn-exec-lib').forEach(function(b) {
            b.addEventListener('click', function() {
              var id = parseInt(b.closest('.list-item').dataset.id, 10);
              openExecuteModal(id);
            });
          });
        })
        .catch(function() { document.getElementById('libraryList').innerHTML = '<p class="msg err">加载失败</p>'; });
    }

    var selectedCaseIndices = [];
    function renderCasesTable(cases) {
      currentLibraryCases = cases;
      selectedCaseIndices = [];
      var tbody = document.querySelector('#casesTable tbody');
      tbody.innerHTML = cases.map(function(c, i) {
        var pathShort = truncate(c.path || c.full_url || '', 48);
        var pathTitle = (c.path || c.full_url || '');
        return '<tr data-i="' + i + '">' +
          '<td><input type="checkbox" class="case-row-cb" data-i="' + i + '"></td>' +
          '<td title="' + escapeAttr(c.name || '') + '">' + escapeHtml(truncate(c.name || '', 28)) + '</td>' +
          '<td>' + escapeHtml(c.method || 'GET') + '</td>' +
          '<td title="' + escapeAttr(pathTitle) + '">' + escapeHtml(pathShort) + '</td>' +
          '<td>' + (c.expect_status ?? 200) + '</td>' +
          '<td class="acts">' +
          '<button type="button" class="btn btn-ghost btn-sm btn-move-up" title="上移">↑</button> ' +
          '<button type="button" class="btn btn-ghost btn-sm btn-move-down" title="下移">↓</button> ' +
          '<button type="button" class="btn btn-ghost btn-sm btn-edit-case">编辑</button> ' +
          '<button type="button" class="btn btn-ghost btn-sm btn-copy-case">复制</button> ' +
          '<button type="button" class="btn btn-ghost btn-sm btn-delete-case">删除</button> ' +
          '<button type="button" class="btn btn-primary btn-sm btn-run-one">执行</button></td></tr>';
      }).join('');
      var selectAllCb = document.getElementById('selectAllCases');
      if (selectAllCb) selectAllCb.checked = false;
      tbody.querySelectorAll('.case-row-cb').forEach(function(cb) {
        cb.addEventListener('change', function() {
          var i = parseInt(this.dataset.i, 10);
          if (this.checked) {
            if (selectedCaseIndices.indexOf(i) < 0) selectedCaseIndices.push(i);
          } else {
            selectedCaseIndices = selectedCaseIndices.filter(function(x) { return x !== i; });
          }
          selectAllCb.checked = tbody.querySelectorAll('.case-row-cb').length === selectedCaseIndices.length;
        });
      });
      if (selectAllCb) {
        selectAllCb.onclick = function() {
          var checked = this.checked;
          selectedCaseIndices = checked ? cases.map(function(_, i) { return i; }) : [];
          tbody.querySelectorAll('.case-row-cb').forEach(function(c) { c.checked = checked; });
        };
      }
      tbody.querySelectorAll('.btn-edit-case').forEach(function(btn) {
        btn.addEventListener('click', function() { openEditCaseModal(parseInt(btn.closest('tr').dataset.i, 10)); });
      });
      tbody.querySelectorAll('.btn-delete-case').forEach(function(btn) {
        btn.addEventListener('click', function() {
          var i = parseInt(btn.closest('tr').dataset.i, 10);
          if (!confirm('确定删除这条用例？')) return;
          var next = currentLibraryCases.slice(0, i).concat(currentLibraryCases.slice(i + 1));
          patchCasesAndRender(next);
        });
      });
      tbody.querySelectorAll('.btn-run-one').forEach(function(btn) {
        btn.addEventListener('click', function() {
          openExecuteModal(currentLibraryId, parseInt(btn.closest('tr').dataset.i, 10));
        });
      });
      tbody.querySelectorAll('.btn-move-up').forEach(function(btn) {
        btn.addEventListener('click', function() {
          var i = parseInt(btn.closest('tr').dataset.i, 10);
          if (i <= 0) return;
          var arr = currentLibraryCases.slice();
          arr[i] = arr.splice(i - 1, 1, arr[i])[0];
          patchCasesAndRender(arr);
        });
      });
      tbody.querySelectorAll('.btn-move-down').forEach(function(btn) {
        btn.addEventListener('click', function() {
          var i = parseInt(btn.closest('tr').dataset.i, 10);
          if (i >= currentLibraryCases.length - 1) return;
          var arr = currentLibraryCases.slice();
          var t = arr[i];
          arr[i] = arr[i + 1];
          arr[i + 1] = t;
          patchCasesAndRender(arr);
        });
      });
      tbody.querySelectorAll('.btn-copy-case').forEach(function(btn) {
        btn.addEventListener('click', function() {
          var i = parseInt(btn.closest('tr').dataset.i, 10);
          var copy = JSON.parse(JSON.stringify(currentLibraryCases[i]));
          copy.name = (copy.name || '') + ' (副本)';
          var arr = currentLibraryCases.slice(0, i + 1).concat([copy]).concat(currentLibraryCases.slice(i + 1));
          patchCasesAndRender(arr);
        });
      });
    }

    function patchCasesAndRender(cases) {
      if (!currentLibraryId) return;
      fetch(API_BASE + '/case-libraries/' + currentLibraryId, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({ cases: cases })
      })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(x) {
          if (x.ok) { renderCasesTable(cases); }
          else { alert(x.data.detail || '保存失败'); }
        })
        .catch(function() { alert('网络错误'); });
    }

    function openEditCaseModal(index) {
      var c = currentLibraryCases[index] || {};
      document.getElementById('editCaseIndex').value = index;
      document.getElementById('editCaseName').value = c.name || '';
      document.getElementById('editCaseMethod').value = c.method || 'GET';
      document.getElementById('editCasePath').value = c.path || '';
      document.getElementById('editCaseFullUrl').value = c.full_url || '';
      document.getElementById('editCaseExpect').value = c.expect_status ?? 200;
      document.getElementById('editCaseQuery').value = (c.query && typeof c.query === 'object') ? JSON.stringify(c.query, null, 2) : (c.query || '{}');
      document.getElementById('editCaseBody').value = (c.body && typeof c.body === 'object') ? JSON.stringify(c.body, null, 2) : (c.body || '{}');
      document.getElementById('editCaseHeaders').value = (c.headers && typeof c.headers === 'object') ? JSON.stringify(c.headers, null, 2) : (c.headers || '{}');
      var ext = c.extract;
      if (ext && typeof ext === 'object') {
        document.getElementById('editCaseExtract').value = Object.keys(ext).map(function(k) { return k + '=' + (ext[k] || ''); }).join('\n');
      } else {
        document.getElementById('editCaseExtract').value = '';
      }
      document.getElementById('modalEditCase').classList.add('visible');
    }
    document.getElementById('confirmEditCase').addEventListener('click', function() {
      var i = parseInt(document.getElementById('editCaseIndex').value, 10);
      if (i < 0 || i >= currentLibraryCases.length) return;
      var qStr = document.getElementById('editCaseQuery').value.trim();
      var bStr = document.getElementById('editCaseBody').value.trim();
      var hStr = document.getElementById('editCaseHeaders').value.trim();
      var query = null, body = null, headers = null;
      try { query = qStr ? JSON.parse(qStr) : null; } catch (e) { alert('Query 不是合法 JSON'); return; }
      if (bStr) {
        try { body = JSON.parse(bStr); } catch (e) {
          if (bStr.indexOf('{{') >= 0) { body = bStr; }
          else { alert('Body 不是合法 JSON'); return; }
        }
      }
      try { headers = hStr ? JSON.parse(hStr) : null; if (headers && typeof headers !== 'object') headers = null; } catch (e) { alert('Header 不是合法 JSON'); return; }
      var extractLines = document.getElementById('editCaseExtract').value.split('\n');
      var extract = {};
      extractLines.forEach(function(line) {
        line = line.trim();
        if (!line) return;
        var eq = line.indexOf('=');
        if (eq > 0) {
          var key = line.slice(0, eq).trim();
          var path = line.slice(eq + 1).trim();
          if (key) extract[key] = path || '$.';
        }
      });
      currentLibraryCases[i] = {
        name: document.getElementById('editCaseName').value.trim() || currentLibraryCases[i].name,
        method: (document.getElementById('editCaseMethod').value || 'GET').trim().toUpperCase(),
        path: document.getElementById('editCasePath').value.trim() || currentLibraryCases[i].path,
        full_url: document.getElementById('editCaseFullUrl').value.trim() || currentLibraryCases[i].full_url,
        expect_status: parseInt(document.getElementById('editCaseExpect').value, 10) || 200,
        query: query,
        body: body,
        headers: headers && Object.keys(headers).length ? headers : undefined,
        extract: Object.keys(extract).length ? extract : undefined
      };
      document.getElementById('modalEditCase').classList.remove('visible');
      patchCasesAndRender(currentLibraryCases);
    });
    document.getElementById('cancelEditCase').addEventListener('click', function() {
      document.getElementById('modalEditCase').classList.remove('visible');
    });

    function openLibraryDetail(id, keepResult) {
      currentLibraryId = id;
      fetch(API_BASE + '/case-libraries/' + id, { headers: authHeaders() })
        .then(function(r) { return r.json(); })
        .then(function(lib) {
          document.getElementById('libraryList').style.display = 'none';
          document.getElementById('libraryDetail').style.display = 'block';
          document.getElementById('libraryDetailTitle').textContent = lib.name + ' — 用例列表';
          var cases = lib.cases || [];
          renderCasesTable(cases);
          if (!keepResult) {
            document.getElementById('executeResult').style.display = 'none';
            document.getElementById('executeResultStats').textContent = '';
            document.getElementById('executeResultList').innerHTML = '';
          }
        })
        .catch(function() { alert('加载失败'); });
    }

    document.getElementById('backToListBtn').addEventListener('click', function() {
      document.getElementById('libraryDetail').style.display = 'none';
      document.getElementById('libraryList').style.display = 'block';
      currentLibraryId = null;
      loadLibraries();
    });

    document.getElementById('reloadCasesBtn').addEventListener('click', function() {
      if (!currentLibraryId) return;
      fetch(API_BASE + '/case-libraries/' + currentLibraryId, { headers: authHeaders() })
        .then(function(r) { return r.json(); })
        .then(function(lib) { renderCasesTable(lib.cases || []); })
        .catch(function() { alert('加载失败'); });
    });

    var libraryIdForExecute = null;
    var caseIndexForExecute = null;
    var caseIndicesForExecute = null;
    function openExecuteModal(libraryId, caseIndex, caseIndices) {
      libraryIdForExecute = libraryId;
      caseIndexForExecute = caseIndex != null ? caseIndex : null;
      caseIndicesForExecute = (caseIndices && caseIndices.length) ? caseIndices.slice().sort(function(a, b) { return a - b; }) : null;
      fetch(API_BASE + '/accounts', { headers: authHeaders() })
        .then(function(r) { return r.json(); })
        .then(function(accounts) {
          var sel = document.getElementById('executeAccountSelect');
          sel.innerHTML = '<option value="">请选择账号</option>' + (accounts || []).map(function(a) {
            return '<option value="' + a.id + '">' + escapeHtml(a.name) + ' (' + (a.account_type === 'login' ? '登录' : '固定Token') + ')</option>';
          }).join('');
          document.getElementById('modalSelectAccount').classList.add('visible');
        })
        .catch(function() { alert('加载账号列表失败'); });
    }
    document.getElementById('confirmExecute').addEventListener('click', function() {
      var accountId = document.getElementById('executeAccountSelect').value;
      if (!accountId || !libraryIdForExecute) return;
      accountId = parseInt(accountId, 10);
      document.getElementById('modalSelectAccount').classList.remove('visible');
      var blockEl = document.getElementById('executeResult');
      var statsEl = document.getElementById('executeResultStats');
      var listEl = document.getElementById('executeResultList');
      blockEl.style.display = 'block';
      statsEl.textContent = '执行中…';
      listEl.innerHTML = '';
      var libId = libraryIdForExecute;
      var caseIdx = caseIndexForExecute;
      var caseIndices = caseIndicesForExecute;
      libraryIdForExecute = null;
      caseIndexForExecute = null;
      caseIndicesForExecute = null;
      var body = { account_id: accountId };
      if (caseIndices && caseIndices.length) body.case_indices = caseIndices;
      else if (caseIdx != null) body.case_index = caseIdx;
      fetch(API_BASE + '/case-libraries/' + libId + '/execute', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(body)
      })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, status: r.status, data: d }; }); })
        .then(function(x) {
          if (x.ok) {
            var d = x.data;
            statsEl.textContent = '通过 ' + d.passed + ' / ' + d.total + '，失败 ' + d.failed + '，消耗积分 ' + d.credits_used + '，剩余 ' + d.credits_left;
            var parts = [];
            if (d.login_result) {
              var lr = d.login_result;
              var loginStatus = lr.success ? '✓ 成功' : '✗ 失败';
              var loginCode = lr.status_code != null ? ' (' + lr.status_code + ')' : '';
              var loginPreview = (lr.response_preview || '').trim() ? escapeHtml((lr.response_preview || '').slice(0, 500)) : '(无)';
              parts.push('<div class="execute-result-item execute-result-login">' +
                '<h5>前置登录 — ' + loginStatus + loginCode + '</h5>' +
                '<div class="req"><span>登录响应预览</span><pre>' + loginPreview + '</pre></div></div>');
            }
            parts.push((d.results || []).map(function(r) {
              var name = (r.case && r.case.name) ? escapeHtml(r.case.name) : '';
              var status = r.passed ? '✓ 通过' : '✗ 失败';
              var statusCode = r.status_code != null ? ' → ' + r.status_code : '';
              if (r.error) statusCode += ' ' + escapeHtml(r.error);
              var reqUrl = r.request_url != null ? String(r.request_url) : '';
              var reqParams = r.request_params && Object.keys(r.request_params).length ? JSON.stringify(r.request_params, null, 2) : '';
              var reqBody = r.request_body != null && (typeof r.request_body !== 'object' || Object.keys(r.request_body).length) ? (typeof r.request_body === 'object' ? JSON.stringify(r.request_body, null, 2) : String(r.request_body)) : '';
              var reqHeaders = r.request_headers && typeof r.request_headers === 'object' && Object.keys(r.request_headers).length ? JSON.stringify(r.request_headers, null, 2) : '(无)';
              var resp = (r.response_snippet || '');
              var reqBlock = '';
              if (reqUrl) reqBlock += '<div class="req"><span>请求 URL</span><pre>' + escapeHtml(reqUrl) + '</pre></div>';
              reqBlock += '<div class="req"><span>当前请求 Header</span><pre>' + escapeHtml(reqHeaders) + '</pre></div>';
              if (reqParams) reqBlock += '<div class="req"><span>Query 参数</span><pre>' + escapeHtml(reqParams) + '</pre></div>';
              if (reqBody) reqBlock += '<div class="req"><span>Body 参数</span><pre>' + escapeHtml(reqBody) + '</pre></div>';
              reqBlock += '<div class="req"><span>返回值</span><pre>' + escapeHtml(resp || '(无)') + '</pre></div>';
              return '<div class="execute-result-item">' +
                '<h5>' + (r.passed ? '✓' : '✗') + ' ' + name + ' — ' + status + statusCode + '</h5>' + reqBlock + '</div>';
            }).join(''));
            listEl.innerHTML = parts.join('');
            loadDashboard();
            var listHidden = document.getElementById('libraryList').style.display === 'none';
            if (!listHidden) openLibraryDetail(libId, true);
          } else {
            statsEl.textContent = x.data.detail || x.data.message || '执行失败';
            listEl.innerHTML = '';
          }
        })
        .catch(function(err) {
          statsEl.textContent = '网络错误: ' + (err.message || '');
          listEl.innerHTML = '';
        });
    });
    document.getElementById('cancelExecute').addEventListener('click', function() {
      document.getElementById('modalSelectAccount').classList.remove('visible');
      libraryIdForExecute = null;
      caseIndexForExecute = null;
    });
    document.getElementById('executeLibraryBtn').addEventListener('click', function() {
      if (currentLibraryId) openExecuteModal(currentLibraryId);
    });
    document.getElementById('batchExecuteCasesBtn').addEventListener('click', function() {
      if (!currentLibraryId) return;
      if (selectedCaseIndices.length === 0) { alert('请先勾选要执行的用例'); return; }
      openExecuteModal(currentLibraryId, null, selectedCaseIndices);
    });
    document.getElementById('batchDeleteCasesBtn').addEventListener('click', function() {
      if (selectedCaseIndices.length === 0) { alert('请先勾选要删除的用例'); return; }
      if (!confirm('确定删除选中的 ' + selectedCaseIndices.length + ' 条用例？')) return;
      var indices = selectedCaseIndices.slice().sort(function(a, b) { return b - a; });
      var next = currentLibraryCases.slice();
      indices.forEach(function(i) { next.splice(i, 1); });
      selectedCaseIndices = [];
      patchCasesAndRender(next);
    });

    window.addEventListener('beforeunload', function() {
      if (typeof saveCurrentSessionToStore === 'function') saveCurrentSessionToStore();
    });

    if (token) loadDashboard();
