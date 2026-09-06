"""Open Mesh Studio, starting one hidden local server only when needed."""
import argparse
from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent


def status(port):
    try:
        with urlopen(f'http://127.0.0.1:{port}/api/health', timeout=5) as response:
            info = json.load(response)
    except URLError as error:
        reason = error.reason
        if isinstance(reason, ConnectionRefusedError) or getattr(reason, 'errno', None) in (errno.ECONNREFUSED, 10061):
            return None
        raise RuntimeError(f'A porta {port} está ocupada ou não respondeu. Nenhum processo foi encerrado.') from None
    except (ValueError, OSError):
        raise RuntimeError(f'Não foi possível identificar o serviço na porta {port}.') from None
    if not isinstance(info, dict) or info.get('app') != 'mesh-studio' or info.get('lifecycle') != 1:
        raise RuntimeError(f'A porta {port} pertence a outro serviço. Nenhum processo foi encerrado.')
    return info


@contextmanager
def launch_lock(port):
    """Serialize simultaneous shortcut clicks without a stale PID file."""
    directory = ROOT / 'artifacts'
    directory.mkdir(exist_ok=True)
    path = directory / f'launcher-{port}.lock'
    with path.open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        deadline = time.monotonic() + 45
        while True:
            handle.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Outra abertura do app ainda está em andamento.') from None
                time.sleep(.2)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def launch(port=8765, allow_writes=False, open_browser=True):
    with launch_lock(port):
        deadline = time.monotonic() + 30
        info = status(port)
        while info and info.get('stopping'):
            if time.monotonic() >= deadline:
                raise RuntimeError('O servidor ainda está liberando o rádio. Tente novamente em alguns instantes.')
            time.sleep(.25)
            info = status(port)
        started = info is None
        if started:
            logs = ROOT / 'artifacts'
            logs.mkdir(exist_ok=True)
            env = {**os.environ, 'MESH_ALLOW_WRITES': '1' if allow_writes else '0'}
            with (logs / f'launcher-server-{port}.log').open('ab') as output:
                proc = subprocess.Popen([sys.executable, '-m', 'server.run', '--port', str(port)],
                    cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            while True:
                if proc.poll() is not None:
                    raise RuntimeError(f'O servidor não iniciou. Consulte artifacts/launcher-server-{port}.log.')
                info = status(port)
                if info and not info.get('stopping'):
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('O servidor demorou para iniciar. Tente abrir o atalho novamente.')
                time.sleep(.2)
    url = f'http://127.0.0.1:{port}'
    if open_browser:
        webbrowser.open(url)
    return {'started': started, 'url': url}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765, choices=range(1024, 65536), metavar='PORT')
    parser.add_argument('--allow-writes', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    try:
        result = launch(args.port, args.allow_writes, not args.no_browser)
        if sys.stdout:
            print(json.dumps(result))
    except Exception as error:
        if os.name == 'nt' and not args.no_browser:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), 'Mesh Studio', 0x10)
        elif sys.stderr:
            print(str(error), file=sys.stderr)
        raise SystemExit(1)
