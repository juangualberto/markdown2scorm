const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const scenario = process.argv[2];
const source = fs.readFileSync(process.argv[3], 'utf8');
let calls = [], handlers = {}, docHandlers = {}, now = 1000;
let state = { 'cmi.core.lesson_status': 'not attempted', 'cmi.core.lesson_mode': 'normal' };
let api = {
  LMSInitialize: x => { calls.push(['init', x]); return scenario === 'initfail' ? 'false' : 'true'; },
  LMSGetValue: k => { calls.push(['get', k]); if (scenario === 'throwget') throw Error('read'); return state[k] || ''; },
  LMSGetLastError: () => scenario === 'geterror' ? '401' : '0',
  LMSSetValue: (k, v) => { calls.push(['set', k, v]); state[k] = v; return 'true'; },
  LMSCommit: x => { calls.push(['commit', x]); return scenario === 'commitfail' ? 'false' : 'true'; },
  LMSFinish: x => { calls.push(['finish', x]); if (scenario === 'reentrant') window.MarkdownSCORM.finish(); return 'true'; }
};
let window = {
  location: {search: scenario === 'preview' ? '?preview=1' : ''},
  console: {warn: () => {}},
  document: {readyState: 'loading', images: [], visibilityState: 'visible', addEventListener: (n, f) => docHandlers[n] = f},
  addEventListener: (n, f) => handlers[n] = f
};
window.parent = window;
if (scenario === 'parent') window.parent = { API: api };
else if (scenario === 'opener') window.opener = {parent: {API: api}};
else if (scenario === 'crossorigin') {
  Object.defineProperty(window, 'parent', {get: () => {throw Error('SecurityError');}});
  window.opener = {API: api};
} else if (scenario !== 'standalone') window.API = api;
if (['completed', 'passed', 'failed'].includes(scenario)) state['cmi.core.lesson_status'] = scenario;
if (['review', 'browse'].includes(scenario)) state['cmi.core.lesson_mode'] = scenario;
if (scenario === 'brokenimage') window.document.images = [{complete: true, naturalWidth: 0}];
if (scenario === 'ready') window.document.readyState = 'complete';
const context = {window, Date: {now: () => now}};
vm.runInNewContext(source, context);
if (handlers.load) handlers.load();
window.MarkdownSCORM.init();
vm.runInNewContext(source, context); // guard against script included twice
now = 3662230;
if (scenario === 'hidden') {
  window.document.visibilityState = 'hidden';
  docHandlers.visibilitychange();
}
if (scenario === 'bfcache') {
  handlers.pagehide({persisted: true});
  assert.equal(calls.filter(c => c[0] === 'finish').length, 0);
}
handlers.pagehide({persisted: false});
handlers.beforeunload(); handlers.unload(); window.MarkdownSCORM.finish();
let count = kind => calls.filter(c => c[0] === kind).length;
if (['standalone', 'preview'].includes(scenario)) {
  assert.equal(calls.length, 0);
} else if (scenario === 'initfail') {
  assert.equal(count('init'), 1); assert.equal(count('set'), 0); assert.equal(count('finish'), 0);
  assert.ok(window.MarkdownSCORM.errors.length);
} else {
  assert.equal(count('init'), 1); assert.equal(count('finish'), 1);
  assert.equal(state['cmi.core.session_time'], '0001:01:01.23');
  assert.ok(count('commit') >= 2);
  if (['completed', 'passed', 'failed'].includes(scenario)) assert.equal(state['cmi.core.lesson_status'], scenario);
  else if (['review', 'browse', 'brokenimage', 'throwget', 'geterror'].includes(scenario)) assert.equal(state['cmi.core.lesson_status'], 'not attempted');
  else assert.equal(state['cmi.core.lesson_status'], 'completed');
  assert.ok(!calls.some(c => c[1] && c[1].includes('score')));
  let final = calls.findIndex(c => c[0] === 'finish');
  assert.equal(final, calls.length - 1);
  assert.equal(calls[final - 1][1], 'cmi.core.exit');
  if (['throwget', 'geterror', 'commitfail'].includes(scenario)) assert.ok(window.MarkdownSCORM.errors.length);
}
console.log('OK ' + scenario);
