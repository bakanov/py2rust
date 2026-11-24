/* Browser glue only: application rules and HTML rendering live in app/*.py. */
'use strict';
const $ = id => document.getElementById(id);
const ui = {chat: '', category: 'all', scope: '', query: '', revision: -1, pending: [], edit: '', busy: false, loading: false, refreshAgain: false, login: false, title: '', deleting: ''};
let toastTimer, searchTimer;
function toast(message) {
  $('toast').textContent = message; $('toast').hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 5000);
}
async function api(path, body, raw = false) {
  const options = body === undefined ? {} : {method: 'POST', body: raw ? body : JSON.stringify(body), headers: raw ? {} : {'Content-Type': 'application/json'}};
  const response = await fetch(path, options);
  const value = await response.json();
  if (!response.ok) {
    if (response.status === 401 && !path.endsWith('/login')) showWelcome();
    throw new Error(value.error || `Request failed (${response.status})`);
  }
  return value;
}
function showWelcome() {
  $('app').hidden = true; $('welcome').hidden = false;
  ui.revision = -1;
}
function draftKey() { return 'paper-plane-draft:' + ui.chat; }
function saveDraft() { if (ui.chat && !ui.edit) localStorage.setItem(draftKey(), $('message-input').value); }
function resizeInput() { const input = $('message-input'); input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 180) + 'px'; }
function updateHTML(id, html) { if ($(id).innerHTML !== html) $(id).innerHTML = html; }
async function refresh(force = false, jump = '') {
  if (ui.loading) { ui.refreshAgain = true; return; }
  ui.loading = true;
  const requestedChat = ui.chat;
  try {
    const query = new URLSearchParams({chat: ui.chat, category: ui.category, q: ui.query, scope: ui.scope});
    const result = await api('/api/view?' + query);
    // A click or search during the request invalidates its rendering.
    if (requestedChat !== ui.chat) { ui.refreshAgain = true; return; }
    $('welcome').hidden = true; $('app').hidden = false;
    $('connection-status').textContent = 'Connected';
    const changedChat = ui.chat !== result.chat_id;
    ui.chat = result.chat_id; ui.title = result.title;
    $('profile-name').textContent = result.me;
    $('chat-title').textContent = result.title;
    $('chat-subtitle').textContent = result.subtitle;
    $('rename-chat').hidden = !result.can_rename;
    updateHTML('chat-avatar', result.avatar);
    updateHTML('chat-list', result.sidebar);
    updateHTML('search-results', result.search);
    const timeline = $('timeline');
    const atBottom = timeline.scrollHeight - timeline.scrollTop - timeline.clientHeight < 100;
    if (force || result.revision !== ui.revision || changedChat) {
      const oldHeight = timeline.scrollHeight, oldTop = timeline.scrollTop;
      updateHTML('messages', result.thread);
      if (force || atBottom || changedChat) timeline.scrollTop = timeline.scrollHeight;
      else timeline.scrollTop = oldTop + (timeline.scrollHeight - oldHeight);
    }
    ui.revision = result.revision;
    if (changedChat) { $('message-input').value = localStorage.getItem(draftKey()) || ''; resizeInput(); }
    if (jump) jumpTo(jump);
  } catch (error) {
    if (!$('app').hidden) $('connection-status').textContent = 'Reconnecting…';
    if (force && !$('app').hidden) toast(error.message);
  } finally {
    ui.loading = false;
    if (ui.refreshAgain) { ui.refreshAgain = false; await refresh(true); }
  }
}
function jumpTo(id) {
  const target = $('message-' + id);
  if (target) { target.scrollIntoView({block: 'center', behavior: 'smooth'}); target.classList.add('highlight'); setTimeout(() => target.classList.remove('highlight'), 2200); }
}
async function selectChat(id, jump = '') {
  saveDraft(); cancelEdit(); clearAttachments(); ui.chat = id; ui.revision = -1;
  $('message-input').value = localStorage.getItem(draftKey()) || ''; resizeInput();
  $('app').classList.add('show-chat');
  await refresh(true, jump);
  if (window.innerWidth > 600) $('message-input').focus();
}
function format(marker) {
  const input = $('message-input'), start = input.selectionStart, end = input.selectionEnd;
  const selected = input.value.slice(start, end) || (marker === '**' ? 'bold text' : 'italic text');
  input.setRangeText(marker + selected + marker, start, end, 'select');
  input.setSelectionRange(start + marker.length, start + marker.length + selected.length);
  input.focus(); saveDraft(); resizeInput();
}
function renderAttachments() {
  $('attachments').replaceChildren();
  for (const entry of ui.pending) {
    const card = document.createElement('div'); card.className = 'pending-file' + (entry.failed ? ' failed' : '');
    if (entry.preview) { const image = document.createElement('img'); image.src = entry.preview; image.alt = ''; card.append(image); }
    const name = document.createElement('span'); name.textContent = entry.name + (entry.upload ? '' : entry.failed ? ' · failed' : ' · uploading…'); card.append(name);
    const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '×'; remove.setAttribute('aria-label', 'Remove ' + entry.name);
    remove.onclick = () => { ui.pending = ui.pending.filter(item => item !== entry); if (entry.preview) URL.revokeObjectURL(entry.preview); renderAttachments(); };
    card.append(remove); $('attachments').append(card);
  }
}
function clearAttachments() { for (const item of ui.pending) if (item.preview) URL.revokeObjectURL(item.preview); ui.pending = []; renderAttachments(); }
async function attachFiles(files) {
  if (ui.edit) { toast('Finish editing before attaching new files.'); return; }
  for (const file of files) {
    if (ui.pending.length >= 10) { toast('Attach at most 10 files per message.'); break; }
    if (!file.size || file.size > 32 * 1024 * 1024) { toast(`${file.name}: choose a nonempty file up to 32 MiB.`); continue; }
    const entry = {name: file.name || 'Screenshot.png', preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : '', upload: null};
    ui.pending.push(entry); renderAttachments();
    try { entry.upload = await api('/api/upload?name=' + encodeURIComponent(entry.name), file, true); }
    catch (error) { entry.failed = true; toast(error.message); }
    renderAttachments();
  }
}
function cancelEdit() { ui.edit = ''; $('edit-banner').hidden = true; $('message-input').value = localStorage.getItem(draftKey()) || ''; resizeInput(); }
$('composer').addEventListener('submit', async event => {
  event.preventDefault(); if (ui.busy) return;
  if (ui.pending.some(file => !file.upload)) { toast('Wait for uploads, or remove failed files.'); return; }
  const content = $('message-input').value;
  if (!content.trim() && !ui.pending.length && !ui.edit) return;
  const sentChat = ui.chat, sentEdit = ui.edit, sentAttachments = [...ui.pending];
  ui.busy = true; $('send').disabled = true;
  try {
    if (sentEdit) await api('/api/edit', {id: sentEdit, body: content});
    else await api('/api/messages', {chat: sentChat, body: content, attachments: sentAttachments.map(item => ({id: item.upload.id}))});
    const sentDraft = 'paper-plane-draft:' + sentChat;
    if (!sentEdit && localStorage.getItem(sentDraft) === content) localStorage.removeItem(sentDraft);
    // A reply belongs to the composer snapshot that was submitted. New typing,
    // attachments, or a different conversation must survive a delayed response.
    if (ui.chat === sentChat) {
      if (ui.edit === sentEdit && $('message-input').value === content) {
        ui.edit = ''; $('edit-banner').hidden = true;
        $('message-input').value = sentEdit ? localStorage.getItem(sentDraft) || '' : '';
      }
      ui.pending = ui.pending.filter(item => {
        if (!sentAttachments.includes(item)) return true;
        if (item.preview) URL.revokeObjectURL(item.preview);
        return false;
      });
      renderAttachments(); resizeInput();
    }
    await refresh(true);
    if (ui.chat === sentChat) $('message-input').focus();
  } catch (error) { toast(error.message); }
  finally { ui.busy = false; $('send').disabled = false; }
});
$('message-input').addEventListener('input', () => { saveDraft(); resizeInput(); });
$('message-input').addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('composer').requestSubmit(); }
  if ((event.ctrlKey || event.metaKey) && ['b', 'i'].includes(event.key.toLowerCase())) { event.preventDefault(); format(event.key.toLowerCase() === 'b' ? '**' : '*'); }
  if (event.key === 'Escape' && ui.edit) cancelEdit();
});
$('message-input').addEventListener('paste', event => {
  const files = [...event.clipboardData.items].filter(item => item.kind === 'file').map(item => item.getAsFile()).filter(Boolean);
  if (files.length) { event.preventDefault(); attachFiles(files); }
});
$('bold').onclick = () => format('**'); $('italic').onclick = () => format('*');
$('attach').onclick = () => $('file-input').click();
$('file-input').onchange = () => { attachFiles([...$('file-input').files]); $('file-input').value = ''; };
$('cancel-edit').onclick = cancelEdit;
let dragDepth = 0;
const pane = document.querySelector('.conversation-pane');
pane.addEventListener('dragenter', event => { if (event.dataTransfer.types.includes('Files')) { event.preventDefault(); dragDepth++; $('drop-overlay').hidden = false; } });
pane.addEventListener('dragover', event => { if (event.dataTransfer.types.includes('Files')) event.preventDefault(); });
pane.addEventListener('dragleave', () => { if (--dragDepth <= 0) { dragDepth = 0; $('drop-overlay').hidden = true; } });
pane.addEventListener('drop', event => { event.preventDefault(); dragDepth = 0; $('drop-overlay').hidden = true; attachFiles([...event.dataTransfer.files]); });
$('search').oninput = () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { ui.query = $('search').value; refresh(); }, 180); };
$('search-chat').onclick = () => { ui.scope = ui.chat; $('search-scope').hidden = false; $('search').focus(); $('app').classList.remove('show-chat'); refresh(); };
$('clear-scope').onclick = () => { ui.scope = ''; $('search-scope').hidden = true; refresh(); };
$('back').onclick = () => $('app').classList.remove('show-chat');
$('new-conversation').onclick = () => { $('create-dialog').showModal(); $('conversation-name').focus(); };
$('create-form').onsubmit = async event => {
  event.preventDefault(); const button = event.submitter; button.disabled = true;
  try { const chat = await api('/api/chats', {title: $('conversation-name').value, kind: document.querySelector('input[name=kind]:checked').value}); $('create-dialog').close(); $('conversation-name').value = ''; await selectChat(chat.id); }
  catch (error) { toast(error.message); } finally { button.disabled = false; }
};
$('rename-chat').onclick = () => { $('rename-input').value = ui.title; $('rename-dialog').showModal(); $('rename-input').focus(); };
$('rename-form').onsubmit = async event => { event.preventDefault(); try { await api('/api/rename', {id: ui.chat, title: $('rename-input').value}); $('rename-dialog').close(); await refresh(); } catch(error) { toast(error.message); } };
async function account() { try { const info = await api('/api/account'); $('account-title').textContent = info.name; $('access-key').value = info.key; $('account-dialog').showModal(); } catch(error) { toast(error.message); } }
$('account').onclick = account; $('profile-name').onclick = account;
$('copy-key').onclick = async () => { try { await navigator.clipboard.writeText($('access-key').value); toast('Access key copied'); } catch { $('access-key').select(); toast('Select and copy the access key with Ctrl+C.'); } };
$('logout').onclick = async () => { try { saveDraft(); await api('/api/logout', {}); $('account-dialog').close(); clearAttachments(); ui.chat = ''; showWelcome(); } catch(error) { toast(error.message); } };
$('switch-login').onclick = () => {
  ui.login = !ui.login; $('welcome-label').textContent = ui.login ? 'Your private access key' : 'What should we call you?';
  $('identity').value = ''; $('identity').maxLength = ui.login ? 64 : 40; $('identity').placeholder = ui.login ? 'Paste your access key' : 'Your name';
  $('join').textContent = ui.login ? 'Sign in' : 'Create profile'; $('switch-login').textContent = ui.login ? 'New here? Create a profile' : 'Already have an access key? Sign in'; $('identity').focus();
};
$('welcome-form').onsubmit = async event => {
  event.preventDefault(); $('join').disabled = true;
  try {
    const info = await api(ui.login ? '/api/login' : '/api/register', ui.login ? {key: $('identity').value} : {name: $('identity').value});
    ui.chat = ''; await refresh(true);
    if (info.key) { $('account-title').textContent = 'Keep your access key'; $('access-key').value = info.key; $('account-dialog').showModal(); }
  } catch(error) { toast(error.message); } finally { $('join').disabled = false; }
};
$('confirm-delete').onclick = async () => { try { await api('/api/delete', {id: ui.deleting}); $('confirm-dialog').close(); await refresh(); } catch(error) { toast(error.message); } };
document.addEventListener('click', async event => {
  const button = event.target.closest('button'); if (!button) return;
  if (button.dataset.close) $(button.dataset.close).close();
  if (button.dataset.chat) await selectChat(button.dataset.chat, button.dataset.message || '');
  if (button.dataset.category) { ui.category = button.dataset.category; document.querySelectorAll('[data-category]').forEach(tab => tab.classList.toggle('selected', tab === button)); await refresh(); }
  if (button.dataset.image) { $('lightbox').src = button.dataset.image; $('image-dialog').showModal(); }
  if (button.dataset.delete) { ui.deleting = button.dataset.delete; $('confirm-dialog').showModal(); }
  if (button.dataset.edit) {
    try { const message = await api('/api/message?id=' + button.dataset.edit); saveDraft(); clearAttachments(); ui.edit = message.id; $('edit-banner').hidden = false; $('message-input').value = message.body; resizeInput(); $('message-input').focus(); }
    catch(error) { toast(error.message); }
  }
});
$('messages').addEventListener('load', () => { if ($('timeline').scrollHeight - $('timeline').scrollTop - $('timeline').clientHeight < 450) $('timeline').scrollTop = $('timeline').scrollHeight; }, true);
window.addEventListener('beforeunload', saveDraft);
setInterval(() => { if (!$('app').hidden && !document.hidden) refresh(); }, 1500);
refresh(true).then(() => console.info('Paper Plane ready'));
