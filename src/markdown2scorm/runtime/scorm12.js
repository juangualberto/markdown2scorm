/* markdown2scorm — MIT. SCORM 1.2 only; no scores or LMS-specific navigation. */
(function (win) {
  'use strict';
  if (win.MarkdownSCORM) return;
  var api = null, attempted = false, initialized = false, finished = false;
  var started = 0, errors = [];
  var preview = /(?:^|[?&])preview=1(?:&|$)/.test(win.location.search || '');
  function error(method, detail) {
    errors.push(method + ': ' + detail);
    if (win.console && win.console.warn) win.console.warn('SCORM ' + method + ': ' + detail);
  }
  function findAPI() {
    var queue = [win], seen = [], count = 0;
    while (queue.length && count++ < 500) {
      var frame = queue.shift();
      if (!frame || seen.indexOf(frame) >= 0) continue;
      seen.push(frame);
      try { if (frame.API && typeof frame.API.LMSInitialize === 'function') return frame.API; } catch (_) {}
      try { if (frame.parent !== frame) queue.push(frame.parent); } catch (_) {}
      try { if (frame.opener) queue.push(frame.opener); } catch (_) {}
    }
    return null;
  }
  function call(method, args) {
    try {
      var result = api[method].apply(api, args);
      if (method === 'LMSGetValue') {
        if (api.LMSGetLastError && String(api.LMSGetLastError()) !== '0') {
          error(method, 'lectura rechazada');
          return null;
        }
      } else if (String(result).toLowerCase() !== 'true') {
        error(method, api.LMSGetLastError ? api.LMSGetLastError() : 'false');
        return false;
      }
      return result;
    } catch (e) { error(method, e.message); return method === 'LMSGetValue' ? null : false; }
  }
  function time() {
    var cs = Math.min(3599999999, Math.max(0, Math.floor((Date.now() - started) / 10)));
    var hours = Math.floor(cs / 360000);
    var minutes = Math.floor(cs / 6000) % 60;
    var seconds = Math.floor(cs / 100) % 60;
    function pad(n, size) { return String(n).padStart(size, '0'); }
    return pad(hours, 4) + ':' + pad(minutes, 2) + ':' + pad(seconds, 2) + '.' + pad(cs % 100, 2);
  }
  function commit() {
    if (!initialized || finished) return false;
    call('LMSSetValue', ['cmi.core.session_time', time()]);
    return call('LMSCommit', ['']);
  }
  function init() {
    if (attempted || preview) return initialized;
    attempted = true;
    api = findAPI();
    if (!api) return false; // Standalone preview is an ordinary HTML document.
    if (!call('LMSInitialize', [''])) return false;
    initialized = true;
    started = Date.now();
    var status = call('LMSGetValue', ['cmi.core.lesson_status']);
    var mode = call('LMSGetValue', ['cmi.core.lesson_mode']);
    var loaded = Array.prototype.every.call(win.document.images || [], function (img) {
      return img.complete && img.naturalWidth > 0;
    });
    if (status !== null && mode !== null && mode !== 'review' && mode !== 'browse' && loaded) {
      if (['completed', 'passed', 'failed'].indexOf(status) < 0) {
        call('LMSSetValue', ['cmi.core.lesson_status', 'completed']);
      }
    }
    commit();
    return true;
  }
  function finish() {
    if (!initialized || finished) return false;
    commit();
    call('LMSSetValue', ['cmi.core.exit', '']);
    // Set guard before the call: some LMS implementations synchronously unload.
    finished = true;
    return call('LMSFinish', ['']);
  }
  win.MarkdownSCORM = {init: init, commit: commit, finish: finish, errors: errors};
  if (win.document.readyState === 'complete') init();
  else win.addEventListener('load', init);
  win.document.addEventListener('visibilitychange', function () {
    if (win.document.visibilityState === 'hidden') commit();
  });
  win.addEventListener('pagehide', function (event) {
    // A bfcache restore keeps this session alive; do not permanently finish it.
    if (event.persisted) commit(); else finish();
  });
  // beforeunload can be cancelled; save without closing the active session.
  win.addEventListener('beforeunload', commit);
  win.addEventListener('unload', finish);
})(window);
