const http = require('http');

const SERVER_PORT = process.env.PORT || 3000;
const MAX_EXECUTION_TIME = 6000;

const requestManager = (req, res) => {
    const watchdog = setTimeout(() => {
        if (!res.writableEnded) {
            res.writeHead(503, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Resource limit exceeded' }));
        }
    }, MAX_EXECUTION_TIME);

    if (req.url === '/health' || req.url === '/ping') {
        clearTimeout(watchdog);
        res.writeHead(200, { 'Content-Type': 'text/plain' });
        return res.end('OK');
    }

    if (req.url === '/run-task' && req.method === 'POST') {
        let payload = '';
        
        req.on('data', chunk => {
            payload += chunk;
        });

        req.on('end', () => {
            clearTimeout(watchdog);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'completed' }));
        });
    } else {
        clearTimeout(watchdog);
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('Not Found');
    }
};

const server = http.createServer(requestManager);

server.listen(SERVER_PORT, () => {
    console.log(`Core runtime online on port ${SERVER_PORT}`);
});
