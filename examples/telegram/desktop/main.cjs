'use strict';
const {app, BrowserWindow, dialog, session} = require('electron');
const {spawn, spawnSync} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const root = path.resolve(__dirname, '..');
let server, window;
// Tests can isolate their data; normal launches use the standard app directory.
if (process.env.PAPER_PLANE_PROFILE) app.setPath('userData', process.env.PAPER_PLANE_PROFILE);
app.setName('Paper Plane');
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => { if (window) { window.restore(); window.focus(); } });
  app.whenReady().then(start).catch(error => { console.error(error); if (!process.env.PAPER_PLANE_SMOKE) dialog.showErrorBox('Paper Plane could not start', error.message); app.exit(1); });
}
async function start() {
  let address = process.env.PAPER_PLANE_URL;
  if (address) {
    const parsed = new URL(address);
    if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('PAPER_PLANE_URL must be an HTTP(S) address.');
  } else {
    const packagedBinary = path.join(root, 'server', 'paper-plane-server');
    let binary = packagedBinary;
    if (!fs.existsSync(binary)) {
      const python = process.env.PAPER_PLANE_PYTHON || 'python';
      const result = spawnSync(python, [path.join(root, 'tools/build.py')], {cwd: root, stdio: 'inherit'});
      if (result.error || result.status !== 0) throw new Error('Building the Python project failed. See terminal output.');
      binary = path.join(root, '.py2rust/bin/paper-plane-server');
    }
    address = await new Promise((resolve, reject) => {
      server = spawn(binary, [], {cwd: root, env: {...process.env, PAPER_PLANE_PORT: '0', PAPER_PLANE_HOST: '127.0.0.1', PAPER_PLANE_DATA: process.env.PAPER_PLANE_DATA || path.join(app.getPath('userData'), 'data'), PAPER_PLANE_WEB: path.join(root, 'web')}, stdio: ['ignore', 'pipe', 'pipe']});
      const timer = setTimeout(() => reject(new Error('Server startup timed out')), 15000);
      let output = '';
      server.stdout.on('data', chunk => { output += chunk; const found = output.match(/LISTENING (http:\/\/[^\s]+)/); if (found) { clearTimeout(timer); resolve(found[1]); } });
      server.stderr.on('data', chunk => process.stderr.write(chunk));
      server.on('error', error => { clearTimeout(timer); reject(error); });
      server.on('exit', code => { clearTimeout(timer); if (window && !app.isQuitting) dialog.showErrorBox('Server stopped', `The chat server stopped (${code}). Restart Paper Plane to reconnect.`); reject(new Error(`Server exited (${code})`)); });
    });
  }
  const origin = new URL(address).origin;
  session.defaultSession.setPermissionRequestHandler((contents, permission, callback) => callback(contents.getURL().startsWith(origin + '/') && ['clipboard-sanitized-write'].includes(permission)));
  window = new BrowserWindow({width: 1280, height: 840, minWidth: 420, minHeight: 520, title: 'Paper Plane', icon: path.join(root, 'web/icon.svg'), backgroundColor: '#edf3ef', webPreferences: {nodeIntegration: false, contextIsolation: true, sandbox: true}});
  window.setMenuBarVisibility(false);
  window.webContents.setWindowOpenHandler(() => ({action: 'deny'}));
  window.webContents.on('will-navigate', (event, target) => { if (new URL(target).origin !== origin) event.preventDefault(); });
  let ready;
  if (process.env.PAPER_PLANE_SMOKE) {
    ready = new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Interface did not become ready')), 15000);
      window.webContents.on('console-message', details => {
        if (details.message === 'Paper Plane ready') { clearTimeout(timer); resolve(); }
      });
    });
  }
  await window.loadURL(address);
  if (process.env.PAPER_PLANE_SMOKE) {
    await ready;
    await new Promise(resolve => setTimeout(resolve, 150)); // Allow the rendered frame to reach the compositor.
    const screenshot = await window.webContents.capturePage();
    fs.writeFileSync(process.env.PAPER_PLANE_SMOKE, screenshot.toPNG());
    console.log('DESKTOP_READY ' + address);
    app.quit();
  }
}
app.on('window-all-closed', () => app.quit());
app.on('before-quit', () => { app.isQuitting = true; if (server) server.kill(); });
