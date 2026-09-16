const http = require('http');
const GuacamoleLite = require('guacamole-lite');

const GUACD_HOST = process.env.GUACD_HOST || 'guacd';
const GUACD_PORT = parseInt(process.env.GUACD_PORT || '4822', 10);
const PORT = parseInt(process.env.PORT || '8080', 10);

const rawSecret = process.env.GUAC_KEY || process.env.SECRET_KEY || 'nscc-lab-portal-secret-key-39281';
const key = rawSecret.substring(0, 32).padEnd(32, '0');

console.log(`[guac-bridge] Starting WebSocket server on port ${PORT}...`);
console.log(`[guac-bridge] Connecting to guacd at ${GUACD_HOST}:${GUACD_PORT}`);

const server = http.createServer((req, res) => {
    if (req.url === '/health' || req.url === '/healthz') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok', guacd: `${GUACD_HOST}:${GUACD_PORT}` }));
    } else {
        res.writeHead(404);
        res.end();
    }
});

const websocketOptions = {
    server: server,
    path: '/guacws'
};

const guacdOptions = {
    host: GUACD_HOST,
    port: GUACD_PORT
};

const clientOptions = {
    crypt: {
        cypher: 'AES-256-CBC',
        key: key
    },
    allowedUnencryptedConnectionSettings: {
        rdp: ['width', 'height', 'dpi']
    },
    log: {
        level: process.env.LOG_LEVEL || 'NORMAL'
    }
};

const guacServer = new GuacamoleLite(websocketOptions, guacdOptions, clientOptions);

server.listen(PORT, '0.0.0.0', () => {
    console.log(`[guac-bridge] Guacamole WebSocket bridge listening on port ${PORT} at /guacws`);
});
