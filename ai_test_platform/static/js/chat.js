// chat.js - 智能对话模块

    var CHAT_SESSIONS_KEY = 'ai_test_platform_chat_sessions';
    var CHAT_SESSIONS_BY_LANE_KEY = 'ai_test_platform_chat_sessions_by_lane';
    var CHAT_LANE_PREF_KEY = 'ai_test_platform_chat_lane';
    var chatSessions = [];
    var currentSessionId = null;
    var chatHistory = [];
    var chatPendingBySession = {};

    function getSessionById(id) {
      var sid = id != null ? String(id) : '';
      return chatSessions.find(function(s) { return String(s.id) === sid; }) || null;
    }
    function isSessionPending(id) {
      return !!chatPendingBySession[String(id)];
    }
    function setSessionPending(id, pending) {
      var sid = String(id || '');
      if (!sid) return;
      if (pending) chatPendingBySession[sid] = true;
      else delete chatPendingBySession[sid];
      var s = getSessionById(sid);
      if (s) s.pending = !!pending;
      refreshChatInputState();
      renderChatSessionList();
    }
    function refreshChatInputState() {
      var input = document.getElementById('chatInput');
      var btn = document.getElementById('chatSendBtn');
      if (!btn) return;
      // 不锁输入框，避免切新会话无法输入；仅在当前会话请求进行中禁用发送按钮
      btn.disabled = !!(currentSessionId && isSessionPending(currentSessionId));
      if (input) input.disabled = false;
    }
    function renderCurrentSessionMessages() {
      var container = document.getElementById('chatMessages');
      if (!container) return;
      container.innerHTML = '';
      var sid = currentSessionId ? String(currentSessionId) : '';
      var session = getSessionById(sid);
      var messages = session && Array.isArray(session.messages) ? session.messages : [];
      chatHistory = messages.slice();
      messages.forEach(function(m) { appendChatMessage(m.role, m.content); });
      if (sid && isSessionPending(sid)) showChatTypingIndicator();
      container.scrollTop = container.scrollHeight;
      refreshChatInputState();
    }

    function normalizeSessionList(arr) {
      if (!Array.isArray(arr)) return [];
      arr.forEach(function(s) {
        if (s.id != null) s.id = String(s.id);
        var m = s.messages || s.history;
        s.messages = Array.isArray(m) ? m : [];
      });
      return arr;
    }
    /** 曾启用「双轨会话」时，把学习轨列表迁回单一 key，避免丢管理员侧历史 */
    function migrateDualStorageToSingle() {
      try {
        var dualRaw = localStorage.getItem(CHAT_SESSIONS_BY_LANE_KEY);
        if (!dualRaw) return;
        if (localStorage.getItem(CHAT_SESSIONS_KEY)) {
          localStorage.removeItem(CHAT_SESSIONS_BY_LANE_KEY);
          localStorage.removeItem(CHAT_LANE_PREF_KEY);
          return;
        }
        var o = JSON.parse(dualRaw);
        var learn = normalizeSessionList(Array.isArray(o.learn) ? o.learn : []);
        localStorage.setItem(CHAT_SESSIONS_KEY, JSON.stringify(learn));
        localStorage.removeItem(CHAT_SESSIONS_BY_LANE_KEY);
        localStorage.removeItem(CHAT_LANE_PREF_KEY);
      } catch (e) {}
    }
    function loadChatSessionsFromStorage() {
      migrateDualStorageToSingle();
      try {
        var raw = localStorage.getItem(CHAT_SESSIONS_KEY);
        if (!raw) return;
        var parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          chatSessions = normalizeSessionList(parsed);
        }
      } catch (e) {}
    }
    function saveChatSessionsToStorage() {
      try {
        localStorage.setItem(CHAT_SESSIONS_KEY, JSON.stringify(chatSessions));
      } catch (e) {}
    }
    function getSessionTitle(session) {
      var msg = (session.messages || []).find(function(m) { return m.role === 'user' && (m.content || '').trim(); });
      if (msg) {
        var t = (msg.content || '').trim();
        return t.length > 24 ? t.slice(0, 24) + '…' : t;
      }
      return session.title || '新对话';
    }
    function getSessionPreview(session) {
      var messages = session.messages || [];
      for (var i = messages.length - 1; i >= 0; i--) {
        var m = messages[i];
        if (m && (m.content || '').trim()) {
          var t = (m.content || '').trim();
          return t.length > 32 ? t.slice(0, 32) + '…' : t;
        }
      }
      return '暂无消息';
    }
    function formatSessionTime(ts) {
      if (!ts) return '';
      var d = new Date(ts);
      var now = new Date();
      var diff = (now - d) / 60000;
      if (diff < 1) return '刚刚';
      if (diff < 60) return Math.floor(diff) + ' 分钟前';
      if (diff < 1440) return Math.floor(diff / 60) + ' 小时前';
      if (diff < 43200) return Math.floor(diff / 1440) + ' 天前';
      return d.toLocaleDateString();
    }
    function createNewSession() {
      var id = 's' + Date.now();
      var session = { id: id, title: '新对话', messages: [], updatedAt: Date.now(), pending: false };
      chatSessions.unshift(session);
      saveChatSessionsToStorage();
      switchChatSession(id);
      renderChatSessionList();
    }
    function switchChatSession(id) {
      var sid = id != null ? String(id) : '';
      if (currentSessionId === sid) return;
      saveCurrentSessionToStore();
      currentSessionId = sid;
      renderCurrentSessionMessages();
      renderChatSessionList();
    }
    function saveCurrentSessionToStore() {
      if (!currentSessionId) return;
      var session = chatSessions.find(function(s) { return String(s.id) === String(currentSessionId); });
      if (session) {
        session.messages = Array.isArray(chatHistory) ? chatHistory.slice() : [];
        session.updatedAt = Date.now();
        if (session.messages.length) {
          var firstUser = session.messages.find(function(m) { return m && m.role === 'user'; });
          if (firstUser && (firstUser.content || '').trim()) session.title = getSessionTitle(session);
        }
        saveChatSessionsToStorage();
      }
    }
    window.addEventListener('beforeunload', function() { if (typeof saveCurrentSessionToStore === 'function') saveCurrentSessionToStore(); });
    function renderChatSessionList() {
      var listEl = document.getElementById('chatSessionList');
      var searchVal = (document.getElementById('chatSessionSearch') && document.getElementById('chatSessionSearch').value || '').trim().toLowerCase();
      if (!listEl) return;
      var filtered = searchVal
        ? chatSessions.filter(function(s) {
            var title = getSessionTitle(s); var preview = getSessionPreview(s);
            return title.toLowerCase().indexOf(searchVal) >= 0 || preview.toLowerCase().indexOf(searchVal) >= 0;
          })
        : chatSessions.slice();
      if (filtered.length === 0) {
        listEl.innerHTML = '<p class="meta" style="padding:0.5rem;font-size:0.8rem;color:var(--text-muted);">暂无对话</p>';
        return;
      }
      listEl.innerHTML = filtered.map(function(s) {
        var title = getSessionTitle(s);
        var preview = getSessionPreview(s);
        var time = formatSessionTime(s.updatedAt);
        var active = s.id === currentSessionId ? ' active' : '';
        return '<div class="chat-session-item' + active + '" data-session-id="' + escapeAttr(s.id) + '">' +
          '<div class="session-title">' + escapeHtml(title) + '</div>' +
          '<div class="session-preview">' + escapeHtml(preview) + '</div>' +
          '<div class="session-time">' + escapeHtml(time) + '</div></div>';
      }).join('');
      listEl.querySelectorAll('.chat-session-item').forEach(function(el) {
        el.addEventListener('click', function() { switchChatSession(el.getAttribute('data-session-id')); });
      });
    }
    function initChatSessions() {
      loadChatSessionsFromStorage();
      if (chatSessions.length === 0) {
        createNewSession();
        return;
      }
      if (!currentSessionId || !chatSessions.find(function(s) { return s.id === currentSessionId; })) {
        currentSessionId = chatSessions[0].id;
      }
      var sid = currentSessionId;
      setTimeout(function() {
        if (document.getElementById('chatMessages')) switchChatSession(sid);
        renderChatSessionList();
      }, 0);
    }

    function linkifyText(text) {
      var escaped = (text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
      return escaped.replace(/https?:\/\/[^\s<>"]+/g, function(raw) {
        var url = raw;
        var suffix = '';
        while (/[)\]}\u3002\uff0c\uff01\uff1f,.]$/.test(url)) {
          if (url.endsWith(')')) {
            var opens = (url.match(/\(/g) || []).length;
            var closes = (url.match(/\)/g) || []).length;
            if (closes <= opens) break;
          }
          suffix = url.slice(-1) + suffix;
          url = url.slice(0, -1);
        }
        return '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + url + '</a>' + suffix;
      });
    }
    function appendChatMessage(role, content) {
      var container = document.getElementById('chatMessages');
      if (!container) return;
      var div = document.createElement('div');
      div.className = 'chat-msg ' + role;
      var text = (content || '').trim() || '（无内容）';
      var html = linkifyText(text);
      div.innerHTML = '<div class="role">' + (role === 'user' ? '我' : '助手') + '</div>' + html;
      container.appendChild(div);
      container.scrollTop = container.scrollHeight;
    }
    function showChatTypingIndicator() {
      var container = document.getElementById('chatMessages');
      if (!container) return;
      var div = document.createElement('div');
      div.id = 'chatTypingIndicator';
      div.className = 'chat-msg assistant typing';
      div.innerHTML = '<div class="role">助手</div><div class="typing-dots"><span></span><span></span><span></span></div> <span class="typing-text">正在思考...</span>';
      container.appendChild(div);
      container.scrollTop = container.scrollHeight;
    }
    function removeChatTypingIndicator() {
      var el = document.getElementById('chatTypingIndicator');
      if (el && el.parentNode) el.parentNode.removeChild(el);
    }
    function appendAssistantMessageReveal(fullText) {
      var container = document.getElementById('chatMessages');
      if (!container) return;
      var text = (fullText || '').trim() || '（无内容）';
      var lines = text.split('\n');
      var div = document.createElement('div');
      div.className = 'chat-msg assistant';
      var roleDiv = document.createElement('div');
      roleDiv.className = 'role';
      roleDiv.textContent = '助手';
      var bodyDiv = document.createElement('div');
      bodyDiv.className = 'chat-msg-body';
      div.appendChild(roleDiv);
      div.appendChild(bodyDiv);
      container.appendChild(div);
      var lineDelay = 150;
      var i = 0;
      function showNext() {
        if (i >= lines.length) {
          container.scrollTop = container.scrollHeight;
          return;
        }
        var line = lines[i];
        var lineEl = document.createElement('div');
        lineEl.className = 'chat-msg-line';
        lineEl.innerHTML = linkifyText(line);
        bodyDiv.appendChild(lineEl);
        i++;
        container.scrollTop = container.scrollHeight;
        if (i < lines.length) setTimeout(showNext, lineDelay);
      }
      if (lines.length) setTimeout(showNext, lineDelay); else container.scrollTop = container.scrollHeight;
    }
    function sendChatMessage() {
      var input = document.getElementById('chatInput');
      var btn = document.getElementById('chatSendBtn');
      if (!input || !btn) return;
      var message = (input.value || '').trim();
      if (!message) return;
      if (!currentSessionId) {
        if (chatSessions.length) switchChatSession(chatSessions[0].id);
        else createNewSession();
      }
      var sid = String(currentSessionId);
      var session = getSessionById(sid);
      if (!session) return;
      if (isSessionPending(sid)) return;

      input.value = '';
      session.messages = Array.isArray(session.messages) ? session.messages : [];
      session.messages.push({ role: 'user', content: message });
      session.updatedAt = Date.now();
      if (String(currentSessionId) === sid) {
        appendChatMessage('user', message);
        chatHistory = session.messages.slice();
      }
      saveCurrentSessionToStore();
      renderChatSessionList();
      setSessionPending(sid, true);
      showChatTypingIndicator();
      var historyForRequest = session.messages.slice(0, -1);
      fetch(API_BASE + '/chat', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          message: message,
          history: historyForRequest,
          session_id: sid,
          context_id: getCurrentCapabilityContextId()
        })
      })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, status: r.status, data: d }; }); })
        .then(function(x) {
          var targetSession = getSessionById(sid);
          if (!targetSession) return;
          if (String(currentSessionId) === sid) removeChatTypingIndicator();
          if (x.ok) {
            var reply = (x.data && x.data.reply) ? x.data.reply : '';
            targetSession.messages = Array.isArray(targetSession.messages) ? targetSession.messages : [];
            targetSession.messages.push({ role: 'assistant', content: reply });
            targetSession.updatedAt = Date.now();
            if (String(currentSessionId) === sid) {
              appendAssistantMessageReveal(reply);
              chatHistory = targetSession.messages.slice();
            }
            fetch(API_BASE + '/auth/me', { headers: authHeaders() }).then(function(r) { return r.json(); }).then(function(d) {
              if (d && d.credits != null) {
                var el = document.getElementById('userCredits'); if (el) el.textContent = d.credits;
                var h = document.getElementById('headerCredits'); if (h) h.textContent = d.credits + ' 积分';
              }
            }).catch(function() {});
          } else {
            var errMsg = (x.data && x.data.detail) ? x.data.detail : ('请求失败 ' + (x.status || ''));
            targetSession.messages = Array.isArray(targetSession.messages) ? targetSession.messages : [];
            targetSession.messages.push({ role: 'assistant', content: '错误：' + errMsg });
            targetSession.updatedAt = Date.now();
            if (String(currentSessionId) === sid) {
              appendChatMessage('assistant', '错误：' + errMsg);
              chatHistory = targetSession.messages.slice();
            }
          }
          saveChatSessionsToStorage();
        })
        .catch(function(e) {
          var targetSession = getSessionById(sid);
          var msg = '网络错误：' + (e && e.message ? e.message : '请稍后重试');
          if (targetSession) {
            targetSession.messages = Array.isArray(targetSession.messages) ? targetSession.messages : [];
            targetSession.messages.push({ role: 'assistant', content: msg });
            targetSession.updatedAt = Date.now();
          }
          if (String(currentSessionId) === sid) {
            removeChatTypingIndicator();
            appendChatMessage('assistant', msg);
            if (targetSession) chatHistory = targetSession.messages.slice();
          }
          saveChatSessionsToStorage();
        })
        .finally(function() {
          setSessionPending(sid, false);
          if (String(currentSessionId) === sid) removeChatTypingIndicator();
        });
    }
    var chatSendBtn = document.getElementById('chatSendBtn');
    var chatInput = document.getElementById('chatInput');
    if (chatSendBtn) chatSendBtn.addEventListener('click', sendChatMessage);
    if (chatInput) {
      var chatInputComposing = false;
      chatInput.addEventListener('compositionstart', function() { chatInputComposing = true; });
      chatInput.addEventListener('compositionend', function() { chatInputComposing = false; });
      chatInput.addEventListener('keydown', function(e) {
        // 中文输入法组合态下回车用于上屏，不应触发发送
        if (chatInputComposing || e.isComposing || e.keyCode === 229) return;
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); }
      });
    }
    var chatNewSessionBtn = document.getElementById('chatNewSessionBtn');
    if (chatNewSessionBtn) chatNewSessionBtn.addEventListener('click', createNewSession);
    var chatSessionSearch = document.getElementById('chatSessionSearch');
    if (chatSessionSearch) chatSessionSearch.addEventListener('input', renderChatSessionList);
