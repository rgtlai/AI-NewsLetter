#!/usr/bin/env node
// Railway start script - explicit Node.js
const { spawn } = require('child_process');

const port = process.env.PORT || 3000;
console.log(`Starting Next.js application on port ${port}`);

const child = spawn('npx', ['next', 'start', '-p', port], {
  stdio: 'inherit',
  shell: true
});

child.on('error', (error) => {
  console.error('Failed to start Next.js:', error);
  process.exit(1);
});

child.on('close', (code) => {
  console.log(`Next.js process exited with code ${code}`);
  process.exit(code);
});
