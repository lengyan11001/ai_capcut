// app.js - Global variables, auth helpers, and utility functions

var API_BASE = '';
var token = localStorage.getItem('token');
var pendingVerifyEmail = null;
var llmModelsCache = null;

function showMsg(el, text, isErr) {
  el.textContent = text;
  el.className = 'msg ' + (isErr ? 'err' : 'ok');
  el.style.display = 'block';
}

function copyToClipboard(text, doneCb) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function() { if (doneCb) doneCb(); }).catch(function() {
      fallbackCopy(text, doneCb);
    });
  } else {
    fallbackCopy(text, doneCb);
  }
}
function fallbackCopy(text, doneCb) {
  var ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed'; ta.style.left = '-9999px';
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); if (doneCb) doneCb(); } catch (e) {}
  document.body.removeChild(ta);
}

function authHeaders() {
  return { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token };
}

var templateIdForGenerate = null;
var currentLibraryId = null;
var currentLibraryCases = [];
var currentEditingAccountId = null;
var currentUserProfile = null;
var capabilityListCache = [];
var capabilityViewEntries = [];
var currentCapabilityId = '';
var currentCapabilityEntry = null;
var currentCapabilityCallLogs = [];
var currentCapabilityChatLogs = [];
var adminCapabilityRegistry = [];
var adminAssignedCapabilityIds = [];
var adminDevicePool = [];
var adminAccountPool = [];
var adminAssignedDeviceIds = [];
var adminAssignedAccountIds = [];

var currentView = 'chat';
var skillPanelLoaded = { templates: false, libraries: false, accounts: false };

function escapeHtml(s) { return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function escapeAttr(s) { return (s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function truncate(s, len) { s = (s || '').trim(); return s.length <= len ? s : s.slice(0, len) + '…'; }
