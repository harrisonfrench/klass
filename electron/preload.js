// Preload script for Electron security
// This script runs before the renderer process loads the web content

const { contextBridge } = require('electron');

// Expose safe APIs to the renderer process if needed
contextBridge.exposeInMainWorld('electronAPI', {
    platform: process.platform,
    isElectron: true
});

// Log when preload runs
console.log('Klass Desktop App - Preload initialized');
