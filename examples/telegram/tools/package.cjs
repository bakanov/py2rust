/* Assemble a portable Linux x64 app from the locked Electron distribution. */
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
require('electron'); // Downloads the locked runtime if this is the first launch.
if (process.platform !== 'linux' || process.arch !== 'x64') throw new Error('Package on Linux x64.');
const python = process.env.PAPER_PLANE_PYTHON || 'python';
const result = spawnSync(python, [path.join(__dirname, 'build.py')], {stdio: 'inherit'});
if (result.status !== 0) process.exit(result.status || 1);
const destination = path.join(root, 'dist/paper-plane-linux-x64');
fs.mkdirSync(destination, {recursive: true});
fs.cpSync(path.join(root, 'node_modules/electron/dist'), destination, {recursive: true});
fs.renameSync(path.join(destination, 'electron'), path.join(destination, 'paper-plane'));
const resources = path.join(destination, 'resources/app');
fs.mkdirSync(path.join(resources, 'server'), {recursive: true});
fs.copyFileSync(path.join(root, '.py2rust/bin/paper-plane-server'), path.join(resources, 'server/paper-plane-server'));
for (const directory of ['desktop', 'web']) fs.cpSync(path.join(root, directory), path.join(resources, directory), {recursive: true});
fs.writeFileSync(path.join(resources, 'package.json'), JSON.stringify({name: 'paper-plane', version: '0.1.0', main: 'desktop/main.cjs'}));
fs.writeFileSync(path.join(destination, 'README.txt'), 'Run ./paper-plane to start. No Python, Cargo, or Node installation is required. Data is stored in your standard user app directory. To connect to a shared server: PAPER_PLANE_URL=http://host:8765 ./paper-plane\n');
const archive = path.join(root, 'dist/paper-plane-linux-x64.tar.gz');
const packed = spawnSync('tar', ['-czf', archive, '-C', path.dirname(destination), path.basename(destination)], {stdio: 'inherit'});
if (packed.status !== 0) process.exit(packed.status || 1);
console.log(archive);
