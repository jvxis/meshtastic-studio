import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from server.app import Manager, create_app
from server.demo import DemoDevice


def test_shutdown_is_authenticated_and_closes_before_stopping():
    manager = Manager(allow_writes=True)
    manager.connect(demo=True)
    device = manager.device
    stopped = []

    def stop():
        assert not device.connected() and manager.device is None
        stopped.append(True)

    with TestClient(create_app(manager, shutdown_callback=stop), base_url='http://127.0.0.1') as c:
        assert c.get('/api/health').json()['shutdown_available']
        assert c.get('/api/shutdown').status_code == 405
        assert c.post('/api/shutdown', json={}).status_code == 403
        c.headers['x-mesh-token'] = c.get('/api/session').json()['token']
        assert c.post('/api/shutdown', json={}, headers={'origin': 'http://evil.invalid'}).status_code == 403
        c.post('/api/messages/active', json={}).raise_for_status()
        c.post('/api/shutdown', json={}).raise_for_status()
        assert stopped == [True] and manager.active_thread is None
        assert c.post('/api/demo', json={}).status_code == 503
        c.post('/api/shutdown', json={}).raise_for_status()
        assert stopped == [True]


def test_unmanaged_or_failed_shutdown_does_not_report_success(monkeypatch):
    manager = Manager()
    manager.connect(demo=True)
    stop = Mock()
    for callback in (None, stop):
        with TestClient(create_app(manager, shutdown_callback=callback), base_url='http://127.0.0.1') as c:
            c.headers['x-mesh-token'] = c.get('/api/session').json()['token']
            with monkeypatch.context() as patch:
                patch.setattr(manager, 'disconnect', Mock(side_effect=RuntimeError('Cannot release')))
                assert c.post('/api/shutdown', json={}).status_code in (409, 503)
                assert not manager.shutting_down
                stop.assert_not_called()


def test_shutdown_waits_for_existing_operation():
    manager = Manager()
    manager.connect(demo=True)
    callback = Mock()
    held, release = threading.Event(), threading.Event()

    def operation():
        with manager.lock:
            held.set()
            assert release.wait(5)

    with TestClient(create_app(manager, shutdown_callback=callback), base_url='http://127.0.0.1') as c:
        c.headers['x-mesh-token'] = c.get('/api/session').json()['token']
        worker = threading.Thread(target=operation)
        worker.start()
        assert held.wait(5)
        results = []
        closing = threading.Thread(target=lambda: results.append(c.post('/api/shutdown', json={})))
        closing.start()
        try:
            deadline = time.monotonic() + 3
            while not manager.shutting_down:
                assert time.monotonic() < deadline
                time.sleep(.01)
            callback.assert_not_called()
            assert manager.device.connected()
        finally:
            release.set()
            worker.join(5)
            closing.join(5)
        assert results[0].status_code == 200
        callback.assert_called_once()


def test_launcher_reuses_server_and_shutdown_exits_process():
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    url = f'http://127.0.0.1:{port}'
    command = [sys.executable, 'launcher.py', '--port', str(port), '--allow-writes', '--no-browser']
    options = dict(cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    processes = [subprocess.Popen(command, **options) for _ in range(2)]
    try:
        results = []
        for proc in processes:
            stdout, stderr = proc.communicate(timeout=45)
            assert proc.returncode == 0, stderr
            results.append(json.loads(stdout))
        assert sum(result['started'] for result in results) == 1
        session = httpx.get(url+'/api/session').raise_for_status().json()
        assert session['state']['server_writes_enabled'] and not session['state']['session_active']
        headers = {'x-mesh-token': session['token']}
        httpx.post(url+'/api/demo', json={}, headers=headers).raise_for_status()
        httpx.post(url+'/api/messages/active', json={}, headers=headers).raise_for_status()
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.kill()  # Only our test launcher; never a radio/server process.
        try:
            session = httpx.get(url+'/api/session').raise_for_status().json()
            httpx.post(url+'/api/shutdown', json={}, headers={'x-mesh-token': session['token']}).raise_for_status()
        except httpx.ConnectError:
            pass
    deadline = time.monotonic() + 10
    while True:
        try:
            httpx.get(url+'/api/health')
        except httpx.ConnectError:
            break
        assert time.monotonic() < deadline, 'Managed server did not exit'
        time.sleep(.1)


@pytest.mark.skipif(os.name != 'nt', reason='Windows desktop shortcut uses pythonw')
def test_windowless_launcher_can_start_server():
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    url = f'http://127.0.0.1:{port}'
    try:
        result = subprocess.run([str(pythonw), 'launcher.py', '--port', str(port),
            '--allow-writes', '--no-browser'], cwd=root, timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0
        assert httpx.get(url+'/api/health').json()['shutdown_available']
        assert httpx.get(url+'/api/state').json()['server_writes_enabled']
    finally:
        try:
            token = httpx.get(url+'/api/session').raise_for_status().json()['token']
            httpx.post(url+'/api/shutdown', json={}, headers={'x-mesh-token': token}).raise_for_status()
        except httpx.ConnectError:
            pass
    deadline = time.monotonic() + 10
    while True:
        try:
            httpx.get(url+'/api/health')
        except httpx.ConnectError:
            break
        assert time.monotonic() < deadline
        time.sleep(.1)
