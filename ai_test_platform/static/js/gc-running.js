// gc-running.js - 群控：执行列表

    var runningCache = [];
    var runningPage = 1;
    var runningPageSize = 10;
    var runningExpandedPlanIds = {};
    function loadRunningPanel() {
      var statusSel = document.getElementById('runningStatusFilter');
      var sv = statusSel ? statusSel.value : '';
      var qs = sv ? '?status=' + encodeURIComponent(sv) : '';
      fetch(API_BASE + '/group-control/nurture/running' + qs, { headers: authHeaders() })
        .then(function(r) { return r.json(); })
        .then(function(d) { runningCache = Array.isArray(d) ? d : []; renderRunningList(); })
        .catch(function() {});
    }
    function renderRunningList() {
      var el = document.getElementById('runningList');
      if (!el) return;
      var q = (document.getElementById('runningSearchInput') || {}).value || '';
      q = q.toLowerCase().trim();
      var list = runningCache;
      if (q) list = list.filter(function(p) {
        return (p.device_label || '').toLowerCase().indexOf(q) >= 0 || (p.plan_name || '').toLowerCase().indexOf(q) >= 0 || (p.objective || '').toLowerCase().indexOf(q) >= 0 || String(p.plan_id).indexOf(q) >= 0;
      });
      if (!list.length) { el.innerHTML = '<div class="meta">暂无匹配的计划记录</div>'; return; }
      var total = list.length;
      var pageCount = Math.max(1, Math.ceil(total / runningPageSize));
      if (runningPage > pageCount) runningPage = pageCount;
      if (runningPage < 1) runningPage = 1;
      var start = (runningPage - 1) * runningPageSize;
      var pageList = list.slice(start, start + runningPageSize);

      var html = pageList.map(function(p) {
        var statusColor = p.plan_status === 'active' ? '#4ade80' : p.plan_status === 'paused' ? '#d97706' : p.plan_status === 'completed' ? '#6b7280' : '#facc15';
        var items = p.items || [];
        var activeItems = items.filter(function(i) { return i.status !== 'cancelled'; });
        var cancelledCnt = items.length - activeItems.length;
        var succCnt = activeItems.filter(function(i) { return i.status === 'success'; }).length;
        var failCnt = activeItems.filter(function(i) { return i.status === 'failed'; }).length;
        var runCnt = activeItems.filter(function(i) { return i.status === 'running' || i.status === 'dispatched'; }).length;
        var skipCnt = activeItems.filter(function(i) { return i.status === 'skipped'; }).length;
        var summary = '<span class="meta" style="margin-left:0.5rem;">' + activeItems.length + '项';
        if (succCnt) summary += ' <span style="color:#4ade80;">' + succCnt + '成功</span>';
        if (failCnt) summary += ' <span style="color:#f87171;">' + failCnt + '失败</span>';
        if (runCnt) summary += ' <span style="color:#facc15;">' + runCnt + '运行</span>';
        if (skipCnt) summary += ' <span style="color:#f97316;">' + skipCnt + '跳过</span>';
        summary += '</span>';
        var expanded = !!runningExpandedPlanIds[p.plan_id];
        var arrow = expanded ? '&#9660;' : '&#9654;';
        var header = '<div class="running-plan-header" data-plan-id="' + p.plan_id + '" style="display:flex;justify-content:space-between;align-items:center;cursor:pointer;user-select:none;">'
          + '<div><span style="margin-right:0.3rem;font-size:0.7rem;color:var(--text-muted);">' + arrow + '</span>'
          + '<span style="font-weight:600;">' + escapeHtml(p.device_label || '?') + '</span> <span class="meta">计划#' + p.plan_id + '</span>'
          + (p.objective ? ' <span style="font-size:0.75rem;color:#93c5fd;">(' + escapeHtml(p.objective) + ')</span>' : '')
          + summary + '</div>'
          + '<span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.72rem;color:#fff;background:' + statusColor + ';">' + escapeHtml(p.plan_status) + '</span></div>';
        var detail = '';
        if (expanded && items.length) {
          var currentRound = items.filter(function(i) { return i.status !== 'cancelled'; });
          var historyRound = items.filter(function(i) { return i.status === 'cancelled'; });
          function _sortItems(arr) {
            return arr.slice().sort(function(a, b) {
              var da = parseInt(a.day_no || 0, 10), db2 = parseInt(b.day_no || 0, 10);
              if (da !== db2) return da - db2;
              return parseInt(a.seq_no || 0, 10) - parseInt(b.seq_no || 0, 10);
            });
          }
          function _buildRows(arr) {
            return arr.map(function(i) {
              var ic = i.status === 'success' ? '#4ade80' : i.status === 'failed' ? '#f87171' : i.status === 'running' || i.status === 'dispatched' ? '#facc15' : i.status === 'skipped' ? '#f97316' : i.status === 'cancelled' ? '#6b7280' : '#888';
              var timeStr = '';
              if (i.scheduled_at) { var d = new Date(i.scheduled_at); timeStr = (d.getMonth()+1) + '/' + d.getDate() + ' ' + String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0'); }
              return '<tr style="border-bottom:1px solid rgba(255,255,255,0.03);font-size:0.78rem;' + (i.status === 'cancelled' ? 'opacity:0.5;' : '') + '">'
                + '<td style="padding:2px 4px;">' + i.day_no + '-' + i.seq_no + '</td>'
                + '<td>' + escapeHtml(i.action) + '</td>'
                + '<td>' + escapeHtml(i.title || '') + '</td>'
                + '<td><span style="color:' + ic + ';">' + escapeHtml(i.status) + '</span></td>'
                + '<td style="white-space:nowrap;">' + escapeHtml(timeStr) + '</td>'
                + '<td style="color:#f87171;font-size:0.72rem;">' + escapeHtml(truncate(i.error,40)) + '</td></tr>';
            }).join('');
          }
          var thRow = '<tr style="border-bottom:1px solid rgba(255,255,255,0.08);font-size:0.75rem;color:var(--text-muted);"><th style="text-align:left;padding:2px 4px;">D-S</th><th style="text-align:left;">动作</th><th style="text-align:left;">标题</th><th>状态</th><th>日期时间</th><th>错误</th></tr>';
          detail = '<div style="margin-top:0.4rem;">';
          if (currentRound.length) {
            detail += '<div style="font-size:0.75rem;font-weight:600;color:var(--accent);margin-bottom:0.2rem;">当前轮次 (' + currentRound.length + '项)</div>';
            detail += '<table style="width:100%;border-collapse:collapse;">' + thRow + _buildRows(_sortItems(currentRound)) + '</table>';
          }
          if (historyRound.length) {
            detail += '<details style="margin-top:0.5rem;"><summary style="cursor:pointer;font-size:0.75rem;color:var(--text-muted);">历史轮次 (' + historyRound.length + '项)</summary>';
            detail += '<table style="width:100%;border-collapse:collapse;margin-top:0.2rem;">' + thRow + _buildRows(_sortItems(historyRound)) + '</table></details>';
          }
          detail += '</div>';
        } else if (expanded) {
          detail = '<div class="meta" style="margin-top:0.3rem;">暂无调度项</div>';
        }
        return '<div style="background:rgba(255,255,255,0.03);border-radius:var(--radius-sm);padding:0.6rem 0.75rem;margin-bottom:0.5rem;">' + header + detail + '</div>';
      }).join('');

      if (pageCount > 1) {
        html += '<div style="display:flex;gap:0.4rem;align-items:center;justify-content:flex-end;margin-top:0.5rem;">'
          + '<button type="button" class="btn btn-ghost btn-sm" id="runningPrevBtn"' + (runningPage <= 1 ? ' disabled' : '') + '>上一页</button>'
          + '<span class="meta">第 ' + runningPage + ' / ' + pageCount + ' 页（共' + total + '个计划）</span>'
          + '<button type="button" class="btn btn-ghost btn-sm" id="runningNextBtn"' + (runningPage >= pageCount ? ' disabled' : '') + '>下一页</button></div>';
      }
      el.innerHTML = html;

      el.querySelectorAll('.running-plan-header').forEach(function(hdr) {
        hdr.addEventListener('click', function() {
          var pid = parseInt(hdr.getAttribute('data-plan-id'), 10);
          if (runningExpandedPlanIds[pid]) { delete runningExpandedPlanIds[pid]; }
          else { runningExpandedPlanIds[pid] = true; }
          renderRunningList();
        });
      });
      var prevBtn = document.getElementById('runningPrevBtn');
      var nextBtn = document.getElementById('runningNextBtn');
      if (prevBtn) prevBtn.addEventListener('click', function() { runningPage -= 1; renderRunningList(); });
      if (nextBtn) nextBtn.addEventListener('click', function() { runningPage += 1; renderRunningList(); });
    }
    (function() {
      var si = document.getElementById('runningSearchInput');
      if (si) si.addEventListener('input', function() { runningPage = 1; renderRunningList(); });
      var rb = document.getElementById('runningRefreshBtn');
      if (rb) rb.addEventListener('click', function() { loadRunningPanel(); });
      var sf = document.getElementById('runningStatusFilter');
      if (sf) sf.addEventListener('change', function() { runningPage = 1; loadRunningPanel(); });
    })();
