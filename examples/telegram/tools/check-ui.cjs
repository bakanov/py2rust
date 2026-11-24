/* Exercise delayed responses against the actual browser glue, without a server. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');

async function page() {
  const elements = new Map(), drafts = new Map(), requests = [];
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      value: '', hidden: false, innerHTML: '', style: {}, scrollHeight: 0, scrollTop: 0, clientHeight: 500,
      handlers: {}, classList: {add() {}, remove() {}, toggle() {}},
      addEventListener(name, action) { this.handlers[name] = action; },
      focus() {}, replaceChildren() {}, append() {}, setAttribute() {},
    });
    return elements.get(id);
  };
  const context = vm.createContext({
    document: {getElementById: element, querySelector: element, querySelectorAll: () => [], addEventListener() {}, createElement: () => element(Symbol())},
    window: {innerWidth: 1280, addEventListener() {}},
    localStorage: {getItem: key => drafts.get(key) ?? null, setItem: (key, value) => drafts.set(key, value), removeItem: key => drafts.delete(key)},
    URL, URLSearchParams, console: {info() {}}, setTimeout: () => 1, clearTimeout() {}, setInterval() {},
    fetch: async (address, options) => {
      if (address.startsWith('/api/view?')) {
        const chat = new URL('http://local' + address).searchParams.get('chat') || 'room-a';
        return {ok: true, json: async () => ({chat_id: chat, me: 'Demo', title: chat, subtitle: '', can_rename: true, avatar: '', sidebar: '', search: '', thread: '', revision: 1})};
      }
      return new Promise(resolve => requests.push({address, body: JSON.parse(options.body), resolve: (ok = true) => resolve({ok, status: ok ? 200 : 500, json: async () => ok ? {} : {error: 'test failure'}})}));
    },
  });
  vm.runInContext(source, context);
  await new Promise(resolve => setImmediate(resolve));
  return {element, drafts, requests, run: code => vm.runInContext(code, context), submit: () => element('composer').handlers.submit({preventDefault() {}})};
}

async function check() {
  let p = await page();
  p.element('message-input').value = 'sent'; p.run('saveDraft()');
  let sending = p.submit();
  assert.equal(p.requests[0].body.body, 'sent');
  p.element('message-input').value = 'next draft'; p.run('saveDraft()');
  p.requests[0].resolve(); await sending;
  assert.equal(p.element('message-input').value, 'next draft');
  assert.equal(p.drafts.get('paper-plane-draft:room-a'), 'next draft');
  assert.equal(p.element('send').disabled, false);

  p = await page(); p.element('message-input').value = 'sent'; p.run('saveDraft(); ui.pending = [{name:"old",upload:{id:"old"}}]');
  sending = p.submit();
  p.run('ui.pending.push({name:"new",upload:{id:"new"}})');
  p.requests[0].resolve(); await sending;
  assert.equal(p.element('message-input').value, '');
  assert.equal(p.run('ui.pending.length'), 1); assert.equal(p.run('ui.pending[0].name'), 'new');
  assert.equal(p.drafts.has('paper-plane-draft:room-a'), false);

  p = await page(); p.element('message-input').value = 'room a'; p.run('saveDraft()');
  p.drafts.set('paper-plane-draft:room-b', 'room b draft');
  sending = p.submit(); await p.run('selectChat("room-b")');
  p.run('ui.pending = [{name:"room-b-file",upload:{id:"b"}}]');
  p.requests[0].resolve(); await sending;
  assert.equal(p.element('message-input').value, 'room b draft');
  assert.equal(p.run('ui.pending[0].name'), 'room-b-file');
  assert.equal(p.drafts.get('paper-plane-draft:room-b'), 'room b draft');
  assert.equal(p.drafts.has('paper-plane-draft:room-a'), false);

  p = await page(); p.element('message-input').value = 'edit'; p.run('ui.edit = "message-1"');
  p.drafts.set('paper-plane-draft:room-a', 'ordinary draft');
  sending = p.submit(); p.run('cancelEdit()'); p.element('message-input').value = 'new ordinary draft'; p.run('saveDraft()');
  p.requests[0].resolve(); await sending;
  assert.equal(p.element('message-input').value, 'new ordinary draft');
  assert.equal(p.run('ui.edit'), '');

  p = await page(); p.element('message-input').value = 'first edit'; p.run('ui.edit = "message-1"');
  sending = p.submit(); p.element('message-input').value = 'second edit';
  p.requests[0].resolve(); await sending;
  assert.equal(p.element('message-input').value, 'second edit'); assert.equal(p.run('ui.edit'), 'message-1');

  p = await page(); p.element('message-input').value = 'retry'; p.run('saveDraft(); ui.pending = [{name:"retry-file",upload:{id:"r"}}]');
  sending = p.submit(); await p.submit(); assert.equal(p.requests.length, 1);
  p.requests[0].resolve(false); await sending;
  assert.equal(p.element('message-input').value, 'retry'); assert.equal(p.run('ui.pending.length'), 1);
  assert.equal(p.element('send').disabled, false);

  p = await page(); p.element('message-input').value = 'edit'; p.run('ui.edit = "message-1"');
  p.drafts.set('paper-plane-draft:room-a', 'restored draft');
  sending = p.submit(); p.requests[0].resolve(); await sending;
  assert.equal(p.element('message-input').value, 'restored draft'); assert.equal(p.run('ui.edit'), '');
  console.log('7 composer response-race scenarios passed');
}
check().catch(error => { console.error(error); process.exitCode = 1; });
