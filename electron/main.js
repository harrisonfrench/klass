const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

let mainWindow = null;
let flaskProcess = null;
const FLASK_PORT = 5000;
const FLASK_URL = `http://127.0.0.1:${FLASK_PORT}`;

// Determine if we're running in development or production
const isDev = !app.isPackaged;

function getFlaskPath() {
    if (isDev) {
        // Development: Flask app is in parent directory
        return path.join(__dirname, '..');
    } else {
        // Production: Flask app is in resources
        return path.join(process.resourcesPath, 'flask-app');
    }
}

function getPythonPath() {
    const fs = require('fs');
    const isWindows = process.platform === 'win32';

    if (isDev) {
        // Development: use venv if available, otherwise system python
        const venvPython = isWindows
            ? path.join(__dirname, '..', 'venv', 'Scripts', 'python.exe')
            : path.join(__dirname, '..', 'venv', 'bin', 'python');

        if (fs.existsSync(venvPython)) {
            return venvPython;
        }
        return isWindows ? 'python' : 'python3';
    } else {
        // Production: use bundled python or system python
        return isWindows ? 'python' : 'python3';
    }
}

function startFlask() {
    return new Promise((resolve, reject) => {
        const flaskPath = getFlaskPath();
        const pythonPath = getPythonPath();

        console.log(`Starting Flask from: ${flaskPath}`);
        console.log(`Using Python: ${pythonPath}`);

        // Set environment variables
        const env = {
            ...process.env,
            FLASK_APP: 'app.py',
            FLASK_ENV: 'development',
            FLASK_DEBUG: '0',
            PYTHONUNBUFFERED: '1'
        };

        // Load .env file if it exists
        const dotenvPath = path.join(flaskPath, '.env');
        const fs = require('fs');
        if (fs.existsSync(dotenvPath)) {
            const dotenv = require('dotenv');
            const envConfig = dotenv.parse(fs.readFileSync(dotenvPath));
            Object.assign(env, envConfig);
        }

        // Spawn Flask process
        flaskProcess = spawn(pythonPath, ['app.py'], {
            cwd: flaskPath,
            env: env,
            stdio: ['pipe', 'pipe', 'pipe']
        });

        flaskProcess.stdout.on('data', (data) => {
            console.log(`Flask: ${data}`);
        });

        flaskProcess.stderr.on('data', (data) => {
            console.error(`Flask Error: ${data}`);
        });

        flaskProcess.on('error', (error) => {
            console.error('Failed to start Flask:', error);
            reject(error);
        });

        flaskProcess.on('exit', (code, signal) => {
            console.log(`Flask exited with code ${code}, signal ${signal}`);
            flaskProcess = null;
        });

        // Wait for Flask to be ready
        waitForFlask(resolve, reject, 30); // 30 second timeout
    });
}

function waitForFlask(resolve, reject, remainingAttempts) {
    if (remainingAttempts <= 0) {
        reject(new Error('Flask failed to start within timeout'));
        return;
    }

    http.get(FLASK_URL, (res) => {
        console.log('Flask is ready!');
        resolve();
    }).on('error', (err) => {
        console.log(`Waiting for Flask... (${remainingAttempts} attempts remaining)`);
        setTimeout(() => {
            waitForFlask(resolve, reject, remainingAttempts - 1);
        }, 1000);
    });
}

function stopFlask() {
    if (flaskProcess) {
        console.log('Stopping Flask...');
        flaskProcess.kill('SIGTERM');

        // Force kill after 5 seconds if still running
        setTimeout(() => {
            if (flaskProcess) {
                console.log('Force killing Flask...');
                flaskProcess.kill('SIGKILL');
            }
        }, 5000);
    }
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 800,
        minHeight: 600,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true
        },
        titleBarStyle: 'default',
        show: false,
        backgroundColor: '#18181b'  // Match app dark background
    });

    // Wait for page to fully load before showing
    mainWindow.webContents.on('did-finish-load', () => {
        mainWindow.show();
    });

    // Handle load failures
    mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
        console.error('Page failed to load:', errorDescription);
    });

    mainWindow.loadURL(FLASK_URL);

    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    // Open DevTools in development to debug
    if (isDev) {
        mainWindow.webContents.openDevTools();
    }
}

// App lifecycle
app.whenReady().then(async () => {
    try {
        await startFlask();
        createWindow();
    } catch (error) {
        dialog.showErrorBox('Failed to Start',
            `Could not start the application.\n\nError: ${error.message}\n\nPlease make sure Python and all dependencies are installed.`
        );
        app.quit();
    }
});

app.on('window-all-closed', () => {
    stopFlask();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (mainWindow === null && flaskProcess) {
        createWindow();
    }
});

app.on('before-quit', () => {
    stopFlask();
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
    stopFlask();
});
