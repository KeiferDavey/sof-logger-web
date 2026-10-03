"""Browser bridge to the unmodified SoF logger. Linux amd64 only."""
import asyncio, base64, fcntl, hashlib, hmac, os, pty, secrets, signal, struct, termios, time
from pathlib import Path
from aiohttp import web, WSMsgType

ROOT = Path(__file__).resolve().parent
os.environ['PYTHONPATH'] = str(ROOT / 'vendor/python')
USER = os.getenv('WEB_USER', 'admin')
PASSWORD = os.getenv('WEB_PASSWORD', '')
PORT = int(os.getenv('SERVER_PORT', '8080'))
ORIGIN = os.getenv('PUBLIC_URL', '').rstrip('/')
SESSIONS = {}
ATTEMPTS = {}
CLIENTS = set()
REPLAY = bytearray()
MASTER = None
PROC = None
STOPPING = False
SALT = secrets.token_bytes(32)
HASH = hashlib.scrypt(PASSWORD.encode(), salt=SALT, n=16384, r=8, p=1)


def authorized(request):
    token = request.cookies.get('sof_session', '')
    return SESSIONS.get(token, 0) > time.time()


def same_origin(request):
    expected = ORIGIN or f'{request.scheme}://{request.host}'
    return request.headers.get('Origin') == expected


@web.middleware
async def protect(request, handler):
    if request.path not in ('/', '/login') and not authorized(request):
        raise web.HTTPUnauthorized(text='Sign in first')
    result = await handler(request)
    result.headers['Cache-Control'] = 'no-store'
    result.headers['X-Content-Type-Options'] = 'nosniff'
    result.headers['X-Frame-Options'] = 'DENY'
    result.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return result


async def index(request):
    return web.FileResponse(ROOT / 'public' / ('index.html' if authorized(request) else 'login.html'))


async def login(request):
    if not same_origin(request):
        raise web.HTTPForbidden(text='Origin mismatch. Set PUBLIC_URL to your browser URL.')
    # Global limit prevents spoofed forwarded addresses from bypassing the limit.
    now = time.time()
    recent = [t for t in ATTEMPTS.get('login', []) if t > now - 60]
    if len(recent) >= 10:
        raise web.HTTPTooManyRequests(text='Wait one minute before trying again.')
    recent.append(now)
    ATTEMPTS['login'] = recent
    form = await request.post()
    supplied = hashlib.scrypt(str(form.get('password', '')).encode(), salt=SALT, n=16384, r=8, p=1)
    if not (hmac.compare_digest(str(form.get('username', '')), USER) and hmac.compare_digest(supplied, HASH)):
        raise web.HTTPUnauthorized(text='Incorrect login. Go back and try again.')
    token = secrets.token_urlsafe(32)
    for old in list(SESSIONS):
        if SESSIONS[old] < now:
            del SESSIONS[old]
    SESSIONS[token] = now + 8 * 3600
    response = web.HTTPSeeOther('/')
    response.set_cookie('sof_session', token, httponly=True, samesite='Strict', secure=ORIGIN.startswith('https://'), max_age=8*3600)
    return response


async def logout(request):
    if not same_origin(request):
        raise web.HTTPForbidden()
    token = request.cookies.get('sof_session', '')
    SESSIONS.pop(token, None)
    for ws, session in list(CLIENTS):
        if session == token:
            await ws.close()
    response = web.HTTPSeeOther('/')
    response.del_cookie('sof_session')
    return response


def validate(value, name):
    if not value or any(c in value for c in '\r\n\x00"'):
        raise RuntimeError(f'Invalid or missing {name}')
    return value


def configure():
    folder = ROOT / 'logger'
    cfg = folder / 'sof-logger.cfg'
    text = cfg.read_text()
    settings = {
        'net_server_ip': validate(os.getenv('SOF_SERVER_IP', ''), 'SOF_SERVER_IP'),
        'net_server_port': str(int(os.getenv('SOF_SERVER_PORT', '28910'))),
        'net_server_rcon': '"' + validate(os.getenv('SOF_RCON_PASSWORD', ''), 'SOF_RCON_PASSWORD') + '"',
        'net_client_port': '0',
    }
    lines = []
    for line in text.splitlines():
        key = line.split('=', 1)[0].strip()
        lines.append(key + '=' + settings.pop(key) if key in settings else line)
    lines.extend(k + '=' + v for k, v in settings.items())
    cfg.write_text('\n'.join(lines) + '\n')
    cfg.chmod(0o600)
    return folder


async def broadcast(data):
    for ws, token in list(CLIENTS):
        if SESSIONS.get(token, 0) <= time.time():
            await ws.close()
            continue
        try:
            if ws._writer.transport.get_write_buffer_size() > 1024*1024:
                await ws.close()
            else:
                await ws.send_bytes(data)
        except Exception:
            CLIENTS.discard((ws, token))


async def pump():
    while not STOPPING:
        await asyncio.sleep(.02)
        try:
            data = os.read(MASTER, 65536)
        except BlockingIOError:
            continue
        except OSError:
            return
        if not data:
            return
        REPLAY.extend(data)
        if len(REPLAY) > 2*1024*1024:
            del REPLAY[:len(REPLAY)-1024*1024]
        await broadcast(data)


async def start_logger(app):
    global MASTER, PROC
    folder = configure()
    MASTER, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 40, 140, 0, 0))
    os.set_blocking(MASTER, False)
    env = dict(os.environ, TERM='xterm', LANG='C.UTF-8', LD_LIBRARY_PATH=str(ROOT / 'vendor/lib'))
    PROC = await asyncio.create_subprocess_exec(str(folder / 'sof-logger.amd64'), cwd=folder, env=env,
                                               stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    os.close(slave)
    app['pump'] = asyncio.create_task(pump())
    app['monitor'] = asyncio.create_task(monitor())
    print(f'SOF logger web ready on port {PORT}', flush=True)


async def monitor():
    code = await PROC.wait()
    if not STOPPING:
        await broadcast(f'\r\n[Logger exited with code {code}. Restart this server in Pterodactyl.]\r\n'.encode())
        print(f'Logger exited with code {code}', flush=True)


async def socket(request):
    if not same_origin(request):
        raise web.HTTPForbidden()
    ws = web.WebSocketResponse(heartbeat=25, max_msg_size=8192)
    await ws.prepare(request)
    pair = (ws, request.cookies['sof_session'])
    if REPLAY:
        await ws.send_bytes(bytes(REPLAY))
    CLIENTS.add(pair)
    await ws.send_bytes(b'\r\nConnected to original SoF logger. Screen refreshes on its next poll.\r\n')
    # Force a redraw on attach. All browsers share a fixed 140 x 40 terminal.
    if PROC.returncode is None:
        os.kill(PROC.pid, signal.SIGWINCH)
    try:
        async for message in ws:
            if not authorized(request):
                await ws.close()
                break
            if message.type == WSMsgType.TEXT and PROC.returncode is None:
                try:
                    os.write(MASTER, message.data.encode())
                except BlockingIOError:
                    pass
    finally:
        CLIENTS.discard(pair)
    return ws


async def cleanup(app):
    global STOPPING
    STOPPING = True
    for ws, token in list(CLIENTS):
        await ws.close()
    if PROC and PROC.returncode is None:
        # Original release has a signal handler for clean shutdown.
        PROC.send_signal(signal.SIGTERM)
        try:
            await asyncio.wait_for(PROC.wait(), 5)
        except asyncio.TimeoutError:
            PROC.kill()
            await PROC.wait()
    for key in ('pump', 'monitor'):
        app[key].cancel()
    if MASTER is not None:
        os.close(MASTER)


if __name__ == '__main__':
    if len(PASSWORD) < 12:
        raise SystemExit('Set WEB_PASSWORD to at least 12 characters.')
    app = web.Application(middlewares=[protect], client_max_size=8192)
    app.router.add_get('/', index)
    app.router.add_post('/login', login)
    app.router.add_post('/logout', logout)
    app.router.add_get('/ws', socket)
    for name in ('xterm.js', 'xterm.css', 'app.js'):
        app.router.add_get('/' + name, lambda request, n=name: web.FileResponse(ROOT / 'public' / n))
    app.on_startup.append(start_logger)
    app.on_cleanup.append(cleanup)
    web.run_app(app, host='0.0.0.0', port=PORT, access_log=None)
