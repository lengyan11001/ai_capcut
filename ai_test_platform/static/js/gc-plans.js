// gc-plans.js - 群控：计划列表 + 养号进度 + 执行明细

    var nurtureBindingsCache = [];
    var nurturePlansCache = [];
    var nurtureProgressCache = [];
    var nurtureProgressPage = 1;
    var nurtureProgressPageSize = 10;
    var selectedNurtureBindingId = null;
    var selectedNurturePlanId = null;
    var _nurtureAutoRefreshTimer = null;
    var _expandedEvalPlanIds = {};

    function loadNurtureBindings() {
      return fetch(API_BASE + '/group-control/nurture/bindings', { headers: authHeaders() })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(x) {
          var list = x.ok && Array.isArray(x.data) ? x.data : [];
          nurtureBindingsCache = list;
          return list;
        });
    }

    function loadNurturePlans(bindingId) {
      var qs = bindingId ? ('?binding_id=' + encodeURIComponent(bindingId)) : '';
      return fetch(API_BASE + '/group-control/nurture/plans' + qs, { headers: authHeaders() })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(x) {
          var list = x.ok && Array.isArray(x.data) ? x.data : [];
          nurturePlansCache = list;
          return list;
        });
    }

    function loadNurtureProgress() {
      return fetch(API_BASE + '/group-control/nurture/progress', { headers: authHeaders() })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(x) {
          var list = x.ok && Array.isArray(x.data) ? x.data : [];
          list.sort(function(a, b) {
            return String(b.created_at || '').localeCompare(String(a.created_at || ''));
          });
          nurtureProgressCache = list;
          renderNurtureProgressPage();
          return list;
        });
    }

    function renderNurtureProgressPage() {
      var list = nurtureProgressCache || [];
      var q = (document.getElementById('plansSearchInput') || {}).value || '';
      q = q.toLowerCase().trim();
      if (q) list = list.filter(function(r) {
        return (r.device_label || '').toLowerCase().indexOf(q) >= 0 || (r.plan_name || '').toLowerCase().indexOf(q) >= 0 || (r.objective || '').toLowerCase().indexOf(q) >= 0 || String(r.plan_id || '').indexOf(q) >= 0;
      });
      var el = document.getElementById('nurtureProgressList');
      var scrollParent = el ? el.closest('.card-body') || el.parentElement : null;
      var savedScroll = scrollParent ? scrollParent.scrollTop : 0;
      var pagerEl = document.getElementById('nurtureProgressPager');
      if (!el) return;
      if (!list.length) {
        el.innerHTML = '<p class="meta">' + (q ? '未找到匹配计划' : '暂无养号计划，请在手机列表点击"创建养号计划"') + '</p>';
        if (pagerEl) pagerEl.innerHTML = '';
        return;
      }
      var total = list.length;
      var pageCount = Math.max(1, Math.ceil(total / nurtureProgressPageSize));
      if (nurtureProgressPage > pageCount) nurtureProgressPage = pageCount;
      if (nurtureProgressPage < 1) nurtureProgressPage = 1;
      var start = (nurtureProgressPage - 1) * nurtureProgressPageSize;
      var rows = list.slice(start, start + nurtureProgressPageSize);

      var hasGenerating = false;
      el.innerHTML = rows.map(function(r, localIdx) {
        var globalIdx = total - (start + localIdx);
        var statusMap = { draft: '草稿', approved: '已批准', active: '执行中', paused: '已暂停', completed: '已完成', generating: 'AI 生成中…', gen_failed: '生成失败' };
        var statusText = statusMap[r.plan_status] || r.plan_status || '-';
        var statusColor = r.plan_status === 'generating' ? '#f59e0b'
          : r.plan_status === 'gen_failed' ? '#ef4444'
          : (r.plan_status === 'active' || r.plan_status === 'approved') ? '#16a34a'
          : (r.plan_status === 'paused' ? '#d97706' : '');
        if (r.plan_status === 'generating') hasGenerating = true;
        var title = '计划#' + (r.plan_id || '-') + ' ' + (r.device_label || ('设备#' + (r.device_id || '-')));
        var createdStr = r.plan_created_at ? new Date(r.plan_created_at).toLocaleString() : (r.created_at ? new Date(r.created_at).toLocaleString() : '-');
        var m = r.metrics || {};
        var sourceTag = '';
        if (r.plan_status === 'generating') {
          var stageLabel = r.plan_gen_stage || '准备中';
          var roundLabel = r.plan_gen_round ? ('第' + r.plan_gen_round + '轮') : '';
          sourceTag = '<span style="background:#f59e0b;color:#000;padding:1px 6px;border-radius:3px;font-size:11px;animation:pulse 1.5s infinite;">&#9889; ' + escapeHtml(stageLabel) + ' ' + roundLabel + '</span>';
        } else if (r.plan_status === 'gen_failed') {
          sourceTag = '<span style="background:#ef4444;color:#fff;padding:1px 6px;border-radius:3px;font-size:11px;">&#10060; 生成失败</span>';
        } else {
          var sourceLabel = r.plan_source === 'direct_llm' ? ('AI:' + (r.plan_model || '?'))
            : r.plan_source === 'openclaw' ? ('OpenClaw:' + (r.plan_model || '?'))
            : r.plan_source === 'fallback' ? '静态兜底' : '未知';
          var srcClr = r.plan_source === 'direct_llm' ? '#7c3aed'
            : r.plan_source === 'openclaw' ? '#2563eb'
            : r.plan_source === 'fallback' ? '#9ca3af' : '#6b7280';
          sourceTag = '<span style="background:' + srcClr + ';color:#fff;padding:1px 6px;border-radius:3px;font-size:11px;">' + escapeHtml(sourceLabel) + '</span>';
        }
        var objTag = r.plan_objective ? ' <span style="background:rgba(139,92,246,0.15);color:#c4b5fd;padding:1px 6px;border-radius:3px;font-size:11px;border:1px solid rgba(139,92,246,0.25);">' + escapeHtml(r.plan_objective) + '</span>' : '';
        var evalRounds = r.plan_eval_rounds || [];
        var evalTag = '';
        if (evalRounds.length && r.plan_status !== 'generating') {
          var lastR = evalRounds[evalRounds.length - 1];
          var sc = lastR.score;
          if (typeof sc === 'number') {
            var scClr = sc >= 80 ? '#10b981' : sc >= 60 ? '#f59e0b' : '#ef4444';
            evalTag = ' <span style="background:' + scClr + ';color:#fff;padding:1px 6px;border-radius:3px;font-size:11px;cursor:pointer;" class="eval-score-tag" data-plan-id="' + r.plan_id + '">AI评分:' + Math.round(sc) + ' (' + evalRounds.length + '轮)</span>';
          }
        }
        var meta = sourceTag + objTag + evalTag + ' ' +
          '创建:' + createdStr + ' · 状态:<b style="color:' + (statusColor || 'inherit') + ';">' + statusText + '</b>' +
          (r.plan_requires_reconfirm ? ' (待重确认)' : '');
        if (r.plan_status === 'gen_failed') {
          meta += ' · <span style="color:#f87171;font-size:0.8rem;">' + escapeHtml(r.plan_summary || '') + '</span>';
        } else if (r.plan_status === 'generating') {
          var genRounds = r.plan_eval_rounds || [];
          if (genRounds.length) {
            meta += '<div class="eval-timeline" style="margin-top:6px;">';
            genRounds.forEach(function(er) {
              var badge = typeof er.score === 'number' ? ('<b>' + Math.round(er.score) + '分</b>') : (er.verdict || '?');
              meta += '<div class="eval-step" style="font-size:0.78rem;color:#a1a1aa;padding:2px 0;">第' + er.round + '轮 → ' + badge;
              if (er.issues && er.issues.length) meta += ' · 问题:' + er.issues.length + '个';
              meta += '</div>';
            });
            meta += '</div>';
          }
        } else if (r.plan_status !== 'generating') {
          meta += ' · ' + (m.total || 0) + '项(成功' + (m.success || 0) + '/失败' + (m.failed || 0) + '/执行中' + (m.running || 0) + '/待执行' + (m.scheduled || 0) + ')' +
            ' · phase:' + (r.phase || '-') +
            ' · karma:' + (r.current_karma || 0) + '/' + (r.target_karma || 0);
        }
        var evalPanel = '';
        if (evalRounds.length && r.plan_status !== 'generating') {
          evalPanel = '<div class="eval-panel" id="evalPanel_' + r.plan_id + '" style="display:none;margin-top:8px;padding:10px;background:rgba(0,0,0,0.25);border-radius:8px;border:1px solid rgba(255,255,255,0.06);font-size:0.82rem;">';
          evalRounds.forEach(function(er) {
            var scColor = typeof er.score === 'number' ? (er.score >= 80 ? '#10b981' : er.score >= 60 ? '#f59e0b' : '#ef4444') : '#6b7280';
            evalPanel += '<div style="margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid rgba(255,255,255,0.06);">';
            evalPanel += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">';
            evalPanel += '<span style="font-weight:700;color:var(--accent);">第' + er.round + '轮</span>';
            if (typeof er.score === 'number') {
              evalPanel += '<span style="background:' + scColor + ';color:#fff;padding:1px 8px;border-radius:4px;font-weight:700;font-size:0.9rem;">' + Math.round(er.score) + '分</span>';
              evalPanel += '<span style="color:' + (er.verdict === 'pass' ? '#10b981' : '#f59e0b') + ';">' + (er.verdict === 'pass' ? '✓ 通过' : '⚠ 需改进') + '</span>';
            } else {
              evalPanel += '<span style="color:#f87171;">' + escapeHtml(er.verdict || er.detail || '失败') + '</span>';
            }
            evalPanel += '</div>';
            if (er.scores) {
              var dimNames = { keyword_relevance:'关键词贴合', subreddit_relevance:'社区匹配', stage_compliance:'阶段合规', rhythm_naturalness:'节奏自然', risk_control:'风险控制', content_diversity:'内容丰富' };
              evalPanel += '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:4px;">';
              Object.keys(er.scores).forEach(function(k) {
                var v = er.scores[k];
                var bc = v >= 80 ? 'rgba(16,185,129,0.15)' : v >= 60 ? 'rgba(245,158,11,0.15)' : 'rgba(239,68,68,0.15)';
                var fc = v >= 80 ? '#6ee7b7' : v >= 60 ? '#fcd34d' : '#fca5a5';
                evalPanel += '<span style="background:' + bc + ';color:' + fc + ';padding:2px 6px;border-radius:4px;font-size:0.75rem;">' + (dimNames[k] || k) + ':' + v + '</span>';
              });
              evalPanel += '</div>';
            }
            if (er.issues && er.issues.length) {
              evalPanel += '<div style="color:#fca5a5;margin-top:3px;">问题: ' + er.issues.map(function(i) { return escapeHtml(i); }).join(' · ') + '</div>';
            }
            if (er.suggestions && er.suggestions.length) {
              evalPanel += '<div style="color:#93c5fd;margin-top:2px;">建议: ' + er.suggestions.map(function(s) { return escapeHtml(s); }).join(' · ') + '</div>';
            }
            evalPanel += '</div>';
          });
          evalPanel += '</div>';
        }
        var selected = (selectedNurturePlanId && selectedNurturePlanId === r.plan_id) ? ' style="border-color:var(--accent);"' : '';
        var actions = '';
        if (r.plan_status === 'generating') {
          actions += '<span class="meta" style="color:#f59e0b;">等待中…</span>';
        } else if (r.plan_status === 'gen_failed') {
          actions += '<button type="button" class="btn btn-ghost btn-sm btn-nurture-retry" data-plan-id="' + r.plan_id + '" data-device-id="' + (r.device_id || '') + '" data-binding-id="' + (r.binding_id || '') + '" style="color:#f59e0b;">重试</button> ';
        } else if (r.plan_status === 'draft') {
          actions += '<button type="button" class="btn btn-ghost btn-sm btn-nurture-start" data-plan-id="' + r.plan_id + '" data-device-id="' + (r.device_id || '') + '" data-binding-id="' + (r.binding_id || '') + '">开始执行</button> ';
        }
        if (r.plan_status === 'approved' || r.plan_status === 'active') {
          actions += '<button type="button" class="btn btn-ghost btn-sm btn-nurture-pause" data-plan-id="' + r.plan_id + '" data-binding-id="' + (r.binding_id || '') + '">暂停</button> ';
        }
        if (r.plan_status === 'paused') {
          actions += '<button type="button" class="btn btn-ghost btn-sm btn-nurture-start" data-plan-id="' + r.plan_id + '" data-device-id="' + (r.device_id || '') + '" data-binding-id="' + (r.binding_id || '') + '">恢复执行</button> ';
        }
        if (r.plan_status !== 'generating') {
          actions += '<button type="button" class="btn btn-ghost btn-sm btn-nurture-delete-plan" data-plan-id="' + r.plan_id + '" style="color:#b91c1c;">删除</button>';
        }
        var titleStyle = statusColor ? ' style="color:' + statusColor + ';"' : '';
        return '<div class="list-item nurture-progress-item" data-binding-id="' + (r.binding_id || '') + '" data-plan-id="' + (r.plan_id || '') + '"' + selected + '><div><div class="title"' + titleStyle + '>' + escapeHtml(title) + '</div><div class="meta">' + meta + '</div>' + evalPanel + '</div><div class="acts">' + actions + '</div></div>';
      }).join('');
      if (_nurtureAutoRefreshTimer) { clearTimeout(_nurtureAutoRefreshTimer); _nurtureAutoRefreshTimer = null; }
      if (hasGenerating) {
        _nurtureAutoRefreshTimer = setTimeout(function() { _nurtureAutoRefreshTimer = null; loadNurtureProgress(); }, 5000);
      }
      Object.keys(_expandedEvalPlanIds).forEach(function(pid) {
        if (_expandedEvalPlanIds[pid]) {
          var panel = document.getElementById('evalPanel_' + pid);
          if (panel) panel.style.display = 'block';
        }
      });
      el.querySelectorAll('.eval-score-tag').forEach(function(tag) {
        tag.addEventListener('click', function(e) {
          e.stopPropagation();
          var pid = tag.getAttribute('data-plan-id');
          var panel = document.getElementById('evalPanel_' + pid);
          if (panel) {
            var show = panel.style.display === 'none';
            panel.style.display = show ? 'block' : 'none';
            _expandedEvalPlanIds[pid] = show;
          }
        });
      });

      if (pagerEl) {
        pagerEl.innerHTML = '<button type="button" class="btn btn-ghost btn-sm" id="nurtureProgressPrevBtn">上一页</button>' +
          '<span class="meta">第 ' + nurtureProgressPage + ' / ' + pageCount + ' 页（共' + total + '条）</span>' +
          '<button type="button" class="btn btn-ghost btn-sm" id="nurtureProgressNextBtn">下一页</button>';
        var prev = document.getElementById('nurtureProgressPrevBtn');
        var next = document.getElementById('nurtureProgressNextBtn');
        if (prev) prev.disabled = nurtureProgressPage <= 1;
        if (next) next.disabled = nurtureProgressPage >= pageCount;
        if (prev) prev.addEventListener('click', function() { nurtureProgressPage -= 1; renderNurtureProgressPage(); });
        if (next) next.addEventListener('click', function() { nurtureProgressPage += 1; renderNurtureProgressPage(); });
      }

      el.querySelectorAll('.nurture-progress-item').forEach(function(itemEl) {
        itemEl.addEventListener('click', function(e) {
          if (e.target && (e.target.classList.contains('btn-nurture-start') || e.target.classList.contains('btn-nurture-pause') || e.target.classList.contains('btn-nurture-delete-plan'))) return;
          var bid = parseInt(String(itemEl.getAttribute('data-binding-id') || '').trim(), 10);
          var pid = parseInt(String(itemEl.getAttribute('data-plan-id') || '').trim(), 10);
          if (!isNaN(pid) && pid > 0) {
            selectedNurturePlanId = pid;
            selectedNurtureBindingId = isNaN(bid) ? selectedNurtureBindingId : bid;
            renderNurtureProgressPage();
            loadNurtureSchedule(bid);
          }
        });
      });
      el.querySelectorAll('.btn-nurture-start').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.stopPropagation();
          var msgEl = document.getElementById('nurtureMsg');
          var planId = parseInt(String(btn.getAttribute('data-plan-id') || '').trim(), 10);
          var deviceId = parseInt(String(btn.getAttribute('data-device-id') || '').trim(), 10);
          var bindingId = parseInt(String(btn.getAttribute('data-binding-id') || '').trim(), 10);
          selectedNurtureBindingId = isNaN(bindingId) ? selectedNurtureBindingId : bindingId;
          var req = planId ? fetch(API_BASE + '/group-control/nurture/plans/' + planId + '/approve', { method: 'POST', headers: authHeaders() })
                           : fetch(API_BASE + '/group-control/nurture/plans/generate-by-device', { method: 'POST', headers: authHeaders(), body: JSON.stringify({ device_id: deviceId, auto_approve: true }) });
          req.then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
            .then(function(x2) {
              if (!msgEl) return;
              if (x2.ok) {
                msgEl.className = 'msg ok';
                var startInfo = (x2.data && x2.data.start_date) ? '，将从 ' + x2.data.start_date + ' 开始' : '';
                msgEl.textContent = planId ? '计划已开始执行' + startInfo : '已自动创建并开始执行计划' + startInfo;
                loadNurturePanel();
                loadControlTasks();
              } else {
                msgEl.className = 'msg err';
                msgEl.textContent = (x2.data && x2.data.detail) || '开始执行失败';
              }
            })
            .catch(function(err) {
              if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '网络错误: ' + (err.message || ''); }
            });
        });
      });
      el.querySelectorAll('.btn-nurture-pause').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.stopPropagation();
          var msgEl = document.getElementById('nurtureMsg');
          var planId = parseInt(String(btn.getAttribute('data-plan-id') || '').trim(), 10);
          var bindingId = parseInt(String(btn.getAttribute('data-binding-id') || '').trim(), 10);
          selectedNurtureBindingId = isNaN(bindingId) ? selectedNurtureBindingId : bindingId;
          if (!planId) {
            if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '当前记录没有可暂停的计划'; }
            return;
          }
          fetch(API_BASE + '/group-control/nurture/plans/' + planId + '/pause', { method: 'POST', headers: authHeaders() })
            .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
            .then(function(x3) {
              if (!msgEl) return;
              if (x3.ok) {
                msgEl.className = 'msg ok';
                msgEl.textContent = '计划已暂停';
                loadNurturePanel();
              } else {
                msgEl.className = 'msg err';
                msgEl.textContent = (x3.data && x3.data.detail) || '暂停失败';
              }
            })
            .catch(function(err) {
              if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '网络错误: ' + (err.message || ''); }
            });
        });
      });
      el.querySelectorAll('.btn-nurture-delete-plan').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.stopPropagation();
          var planId = parseInt(String(btn.getAttribute('data-plan-id') || '').trim(), 10);
          if (!planId || !confirm('确定删除计划 #' + planId + ' 及其所有执行明细？此操作不可恢复。')) return;
          var msgEl = document.getElementById('nurtureMsg');
          fetch(API_BASE + '/group-control/nurture/plans/' + planId, { method: 'DELETE', headers: authHeaders() })
            .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
            .then(function(x4) {
              if (!msgEl) return;
              if (x4.ok) {
                msgEl.className = 'msg ok';
                msgEl.textContent = '计划已删除';
                loadNurturePanel();
                loadControlTasks();
              } else {
                msgEl.className = 'msg err';
                msgEl.textContent = (x4.data && x4.data.detail) || '删除失败';
              }
            })
            .catch(function(err) {
              if (msgEl) { msgEl.className = 'msg err'; msgEl.textContent = '网络错误: ' + (err.message || ''); }
            });
        });
      });
      el.querySelectorAll('.btn-nurture-retry').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.stopPropagation();
          var deviceId = parseInt(String(btn.getAttribute('data-device-id') || '').trim(), 10);
          if (!deviceId) return;
          openCreatePlanModal(deviceId, null);
        });
      });
      if (scrollParent && savedScroll) scrollParent.scrollTop = savedScroll;
    }

    function loadNurtureSchedule(bindingId) {
      if (bindingId) selectedNurtureBindingId = bindingId;
      var qs = '?limit=120';
      if (selectedNurtureBindingId) qs += '&binding_id=' + encodeURIComponent(selectedNurtureBindingId);
      return fetch(API_BASE + '/group-control/nurture/schedule' + qs, { headers: authHeaders() })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(x) {
          var el = document.getElementById('nurtureScheduleList');
          var list = x.ok && Array.isArray(x.data) ? x.data : [];
          if (!el) return list;
          if (!list.length) { el.innerHTML = '<p class="meta">暂无执行明细</p>'; return list; }
          list = list.slice().sort(function(a, b) {
            var da = parseInt(a.day_no || 0, 10), db = parseInt(b.day_no || 0, 10);
            if (da !== db) return da - db;
            var sa = parseInt(a.seq_no || 0, 10), sb = parseInt(b.seq_no || 0, 10);
            if (sa !== sb) return sa - sb;
            return String(a.scheduled_at || '').localeCompare(String(b.scheduled_at || ''));
          });
          var dayMap = {};
          list.forEach(function(item) {
            var day = parseInt(item.day_no || 0, 10) || 0;
            if (!dayMap[day]) dayMap[day] = [];
            dayMap[day].push(item);
          });
          var days = Object.keys(dayMap).map(function(k){ return parseInt(k, 10); }).sort(function(a,b){ return a-b; });
          el.innerHTML = days.map(function(day) {
            var rows = dayMap[day] || [];
            var stat = { total: rows.length, success: 0, failed: 0, running: 0, pending: 0 };
            rows.forEach(function(r) {
              var st = String(r.task_status || r.status || '');
              if (st === 'success') stat.success += 1;
              else if (st === 'failed' || st === 'cancelled') stat.failed += 1;
              else if (st === 'running' || st === 'dispatched') stat.running += 1;
              else stat.pending += 1;
            });
            var head = '<div class="list-item" style="display:block;background:rgba(255,255,255,0.02);"><div class="title">Day ' + day + '</div><div class="meta">总' + stat.total + ' · 成功' + stat.success + ' · 失败' + stat.failed + ' · 执行中' + stat.running + ' · 待执行' + stat.pending + '</div></div>';
            var body = rows.map(function(r) {
              var when = r.scheduled_at ? new Date(r.scheduled_at).toLocaleString() : '-';
              var started = r.task_started_at ? new Date(r.task_started_at).toLocaleString() : '-';
              var finished = r.task_finished_at ? new Date(r.task_finished_at).toLocaleString() : '-';
              var meta = '计划:' + when + ' · 状态:' + (r.status || '-') + ' · 任务:' + (r.task_status || '-') + ' · 开始:' + started + ' · 结束:' + finished;
              var err = r.execution_error_code || r.last_error_code;
              var payloadText = JSON.stringify(r.payload || {}, null, 2);
              return '<div class="list-item" style="display:block;"><div><div class="title">' + escapeHtml((r.title || '-') + ' [S' + (r.seq_no || '-') + ']') + '</div><div class="meta">' + escapeHtml(meta) + '</div>' + (err ? ('<div class="meta" style="margin-top:0.2rem;color:#b91c1c;">错误: ' + escapeHtml(err) + '</div>') : '') + '<details style="margin-top:0.25rem;"><summary class="meta" style="cursor:pointer;">查看 payload</summary><pre style="white-space:pre-wrap;margin-top:0.25rem;">' + escapeHtml(payloadText) + '</pre></details></div></div>';
            }).join('');
            return head + body;
          }).join('');
          return list;
        });
    }

    function loadNurtureStrategy() {
      return fetch(API_BASE + '/group-control/nurture/strategy/latest', { headers: authHeaders() })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(x) {
          var el = document.getElementById('nurtureStrategySummary');
          var snap = x.ok && x.data && x.data.snapshot ? x.data.snapshot : null;
          if (!el) return snap;
          if (!snap) { el.textContent = ''; return snap; }
          var txt = '今日策略复审: ' + (snap.severity || '-') + ' · ' + (snap.summary || '');
          if (snap.requires_reconfirm) txt += ' · 需要重新确认计划';
          el.textContent = txt;
          return snap;
        });
    }

    function loadNurturePanel() {
      return loadNurtureBindings().then(function() {
        return Promise.all([
          loadNurturePlans(),
          loadNurtureProgress(),
          loadNurtureSchedule(),
          loadNurtureStrategy()
        ]);
      });
    }

    var nurtureRefreshBtn = document.getElementById('nurtureRefreshBtn');
    if (nurtureRefreshBtn) {
      nurtureRefreshBtn.addEventListener('click', function() { loadNurturePanel(); });
    }
