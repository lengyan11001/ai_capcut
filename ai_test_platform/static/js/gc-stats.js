// gc-stats.js - 群控：统计面板

    function _initStatsModelSelect() {
      var sel = document.getElementById('statsModelSelect');
      if (!sel || sel.dataset.inited) return;
      sel.dataset.inited = '1';
      fetch(API_BASE + '/group-control/nurture/models', { headers: authHeaders() })
        .then(function(r) { return r.ok ? r.json() : { models: [], default_model: 'deepseek-chat' }; })
        .then(function(data) {
          var models = data.models || [];
          var saved = '';
          try { saved = localStorage.getItem('stats_report_model') || ''; } catch(e) {}
          var pick = saved || data.default_model || 'deepseek-chat';
          var found = models.some(function(m) { return m.id === pick; });
          if (!found && models.length) pick = models[0].id;
          sel.innerHTML = models.map(function(m) {
            return '<option value="' + escapeAttr(m.id) + '"' + (m.id === pick ? ' selected' : '') + '>' + escapeHtml(m.name) + (m.tier === 'pro' ? ' [Pro]' : '') + '</option>';
          }).join('');
          sel.value = pick;
        });
      sel.addEventListener('change', function() {
        try { localStorage.setItem('stats_report_model', sel.value); } catch(e) {}
      });
    }
    function _getStatsModel() {
      var sel = document.getElementById('statsModelSelect');
      return sel ? sel.value : '';
    }
    function loadStatsPanel() {
      _initStatsModelSelect();
      loadStatsDaily();
      loadStatsReport();
      loadStatsPolicyIntel();
    }
    function loadStatsDaily() {
      fetch(API_BASE + '/group-control/stats/daily', { headers: authHeaders() })
        .then(function(r) { return r.json(); })
        .then(function(d) { renderStatsCards(d); renderStatsByAction(d.by_action || {}); renderStatsByDevice(d.by_device || []); })
        .catch(function() {});
    }
    function renderStatsCards(d) {
      var el = document.getElementById('statsCards');
      if (!el) return;
      var rate = d.success_rate != null ? Math.round(d.success_rate * 100) : 0;
      var rateColor = rate >= 80 ? '#4ade80' : rate >= 50 ? '#facc15' : '#f87171';
      el.innerHTML = [
        _statCard('总任务', d.total || 0, '#93c5fd'),
        _statCard('成功', d.success || 0, '#4ade80'),
        _statCard('失败', d.failed || 0, '#f87171'),
        _statCard('执行中', d.running || 0, '#facc15'),
        _statCard('成功率', rate + '%', rateColor),
      ].join('');
    }
    function _statCard(label, value, color) {
      return '<div style="background:rgba(255,255,255,0.04);border-radius:var(--radius-sm);padding:0.75rem 1rem;text-align:center;">'
        + '<div style="font-size:1.6rem;font-weight:700;color:' + color + ';">' + value + '</div>'
        + '<div class="meta" style="margin-top:0.15rem;">' + label + '</div></div>';
    }
    function renderStatsByAction(byAction) {
      var el = document.getElementById('statsByAction');
      if (!el) return;
      var keys = Object.keys(byAction);
      if (!keys.length) { el.innerHTML = '<div class="meta">暂无数据</div>'; return; }
      var maxV = Math.max.apply(null, keys.map(function(k) { return byAction[k].total; }));
      el.innerHTML = keys.map(function(k) {
        var o = byAction[k]; var pct = maxV ? Math.round(o.total / maxV * 100) : 0;
        return '<div style="margin-bottom:0.5rem;">'
          + '<div style="display:flex;justify-content:space-between;font-size:0.82rem;margin-bottom:2px;"><span>' + escapeHtml(k) + '</span><span>' + o.total + ' (成功 ' + o.success + ' / 失败 ' + o.failed + ')</span></div>'
          + '<div style="background:rgba(255,255,255,0.06);border-radius:3px;height:10px;overflow:hidden;">'
          + '<div style="width:' + pct + '%;height:100%;background:linear-gradient(90deg,#60a5fa,' + (o.failed > o.success ? '#f87171' : '#4ade80') + ');border-radius:3px;"></div></div></div>';
      }).join('');
    }
    function renderStatsByDevice(list) {
      var el = document.getElementById('statsByDevice');
      if (!el) return;
      if (!list.length) { el.innerHTML = '<div class="meta">暂无数据</div>'; return; }
      el.innerHTML = '<table style="width:100%;font-size:0.82rem;border-collapse:collapse;">'
        + '<tr style="border-bottom:1px solid rgba(255,255,255,0.1);"><th style="text-align:left;padding:4px 6px;">设备</th><th>总数</th><th>成功</th><th>失败</th></tr>'
        + list.map(function(d) {
          return '<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">'
            + '<td style="padding:3px 6px;">' + escapeHtml(d.device_label) + '</td>'
            + '<td style="text-align:center;">' + d.total + '</td>'
            + '<td style="text-align:center;color:#4ade80;">' + d.success + '</td>'
            + '<td style="text-align:center;color:#f87171;">' + d.failed + '</td></tr>';
        }).join('') + '</table>';
    }
    function loadStatsReport() {
      var el = document.getElementById('statsReportContent');
      if (!el) return;
      el.innerHTML = '<span class="meta">加载中…</span>';
      fetch(API_BASE + '/group-control/stats/report', { headers: authHeaders() })
        .then(function(r) { return r.json(); })
        .then(function(d) {
          if (!d.exists) { el.innerHTML = '<div class="meta">暂无报告。点击「刷新报告」生成。</div>'; return; }
          var sevColor = d.severity === 'high' ? '#f87171' : d.severity === 'medium' ? '#facc15' : '#4ade80';
          var scoreColor = d.overall_score >= 80 ? '#4ade80' : d.overall_score >= 50 ? '#facc15' : '#f87171';
          var html = '<div style="display:flex;gap:1rem;align-items:center;margin-bottom:0.75rem;">'
            + '<div style="font-size:2rem;font-weight:700;color:' + scoreColor + ';">' + d.overall_score + '<span style="font-size:0.8rem;color:var(--text-muted);">/100</span></div>'
            + '<div><span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.75rem;color:#fff;background:' + sevColor + ';">风险: ' + escapeHtml(d.severity) + '</span>'
            + '<div class="meta" style="margin-top:2px;">日期: ' + escapeHtml(d.report_date || '') + '</div></div></div>';
          html += '<div style="margin-bottom:0.6rem;"><strong style="font-size:0.85rem;">执行分析</strong><div style="font-size:0.82rem;line-height:1.5;margin-top:2px;">' + escapeHtml(d.execution_analysis) + '</div></div>';
          html += '<div style="margin-bottom:0.6rem;"><strong style="font-size:0.85rem;">政策分析</strong><div style="font-size:0.82rem;line-height:1.5;margin-top:2px;">' + escapeHtml(d.policy_analysis) + '</div></div>';
          if (d.recommendations && d.recommendations.length) {
            html += '<div><strong style="font-size:0.85rem;">建议</strong><ul style="margin:4px 0 0 1.2rem;font-size:0.82rem;">';
            d.recommendations.forEach(function(r) { html += '<li>' + escapeHtml(r) + '</li>'; });
            html += '</ul></div>';
          }
          el.innerHTML = html;
        })
        .catch(function() { el.innerHTML = '<div class="meta" style="color:#f87171;">加载失败</div>'; });
    }
    function loadStatsPolicyIntel() {
      var el = document.getElementById('statsPolicyIntel');
      if (!el) return;
      el.innerHTML = '<span class="meta">加载中…</span>';
      fetch(API_BASE + '/group-control/stats/policy-latest', { headers: authHeaders() })
        .then(function(r) { return r.json(); })
        .then(function(d) {
          if (!d.exists) { el.innerHTML = '<div class="meta">暂无政策情报。刷新报告时将自动采集。</div>'; return; }
          var sevColor = d.severity === 'high' ? '#f87171' : d.severity === 'medium' ? '#facc15' : '#4ade80';
          var html = '<div style="display:flex;gap:0.75rem;align-items:flex-start;margin-bottom:0.5rem;">'
            + '<span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.72rem;color:#fff;background:' + sevColor + ';">风险: ' + escapeHtml(d.severity || 'unknown') + '</span>'
            + '<span class="meta">采集时间: ' + escapeHtml(d.crawled_at || '') + '</span></div>';
          var sources = d.sources || '';
          if (sources) {
            var srcList = typeof sources === 'string' ? sources.split(', ') : (Array.isArray(sources) ? sources : []);
            if (srcList.length) {
              html += '<div style="margin-bottom:0.5rem;"><span style="font-size:0.78rem;font-weight:600;color:var(--accent);">数据来源 (' + srcList.length + ')</span>';
              html += '<div style="display:flex;flex-wrap:wrap;gap:0.3rem;margin-top:0.25rem;">';
              srcList.forEach(function(s) {
                html += '<span style="font-size:0.72rem;padding:2px 6px;background:rgba(96,165,250,0.12);color:#93c5fd;border-radius:3px;">' + escapeHtml(s) + '</span>';
              });
              html += '</div></div>';
            }
          }
          html += '<div style="font-size:0.82rem;line-height:1.5;margin-bottom:0.4rem;">' + escapeHtml(d.ai_summary || '') + '</div>';
          if (d.key_changes && d.key_changes.length) {
            html += '<div style="font-size:0.78rem;"><strong>关键发现:</strong><ul style="margin:3px 0 0 1.2rem;">';
            d.key_changes.forEach(function(c) { html += '<li>' + escapeHtml(c) + '</li>'; });
            html += '</ul></div>';
          }
          el.innerHTML = html;
        })
        .catch(function() { el.innerHTML = '<div class="meta" style="color:#f87171;">加载失败</div>'; });
    }
    (function() {
      var btn = document.getElementById('statsReportRefreshBtn');
      if (btn) btn.addEventListener('click', function() {
        var m = _getStatsModel();
        btn.disabled = true; btn.textContent = '生成中…';
        fetch(API_BASE + '/group-control/stats/report-refresh' + (m ? '?model=' + encodeURIComponent(m) : ''), { method: 'POST', headers: authHeaders() })
          .then(function(r) { return r.json(); })
          .then(function() { loadStatsReport(); loadStatsPolicyIntel(); btn.disabled = false; btn.textContent = '刷新报告'; })
          .catch(function() { btn.disabled = false; btn.textContent = '刷新报告'; });
      });
    })();
