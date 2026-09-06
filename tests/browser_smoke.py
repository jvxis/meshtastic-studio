"""Standalone browser acceptance test. Starts its own server; uses ONLY the simulator."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import httpx
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"


def run():
    ARTIFACTS.mkdir(exist_ok=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    env = {**os.environ, "MESH_ALLOW_WRITES": "0"}
    proc = subprocess.Popen([sys.executable, "-m", "server.run", "--port", str(port)],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    try:
        for _ in range(100):
            try:
                if httpx.get(url + "/api/state").status_code == 200:
                    break
            except httpx.TransportError:
                pass
            time.sleep(.1)
        else:
            raise RuntimeError("Test server did not start")
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1050}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            # A session response must advertise the server permission even
            # before selecting hardware. These are HTTP mocks, never radio I/O.
            def enabled_session(route):
                result = route.fetch().json()
                result['state']['server_writes_enabled'] = True
                assert result['state']['writes_enabled'] is False
                route.fulfill(status=200, json=result)
            page.route('**/api/session', enabled_session)
            page.goto(url)
            expect(page.locator('.top-status')).to_contain_text('Gravação habilitada')
            expect(page.locator('#app .status-strip')).to_contain_text('Gravação habilitada')
            expect(page.locator('#connection-mode')).to_have_count(0)
            page.unroute('**/api/session', enabled_session)
            page.reload()
            expect(page.locator('.top-status')).to_contain_text('Somente leitura')

            # Finish an old poll after our own connect changes the epoch.
            held = []
            old_messages = httpx.get(url+'/api/messages').json()
            page.route('**/api/messages', lambda route: held.append(route))
            for _ in range(30):
                if held: break
                page.wait_for_timeout(100)
            assert held
            page.locator('[data-action="demo"]').click()
            expect(page.locator('.device-name')).to_have_text('Estação de demonstração')
            held[0].fulfill(status=200, json=old_messages)
            page.unroute('**/api/messages')
            expect(page.locator('#toast')).not_to_contain_text('A sessão mudou')

            # Another client changes the selected session: refresh state and
            # token automatically, preserving the typed message without sending.
            page.locator('nav [data-page="messages"]').click()
            page.locator('#chat-text').fill('Rascunho preservado após atualização de sessão')
            token = httpx.get(url+'/api/session').json()['token']
            headers = {'x-mesh-token': token}
            httpx.post(url+'/api/disconnect', json={}, headers=headers).raise_for_status()
            httpx.post(url+'/api/demo', json={}, headers=headers).raise_for_status()
            # Observing a second session fetch proves the epoch was reconciled.
            refreshed = []
            def capture_session(route):
                refreshed.append(True)
                route.continue_()
            page.route('**/api/session', capture_session)
            for _ in range(40):
                if refreshed: break
                page.wait_for_timeout(100)
            assert refreshed
            expect(page.locator('#chat-text')).to_have_value('Rascunho preservado após atualização de sessão')
            expect(page.locator('#toast')).not_to_contain_text('A sessão mudou')
            assert not httpx.get(url+'/api/messages').json()['messages']
            page.unroute('**/api/session', capture_session)
            page.locator('#chat-text').fill('')
            page.locator('nav [data-page="overview"]').click()
            page.locator('[data-action="disconnect"]').click()
            expect(page.locator('#port-select')).to_be_visible()
            expect(page.locator('#port-select')).to_be_visible()
            page.locator('#connection-type').select_option('tcp')
            expect(page.locator('#tcp-host')).to_be_visible()
            expect(page.locator('#tcp-port')).to_have_value('4403')
            expect(page.locator('#port-select')).to_have_count(0)
            page.locator('#tcp-host').fill('192.0.2.10')
            page.locator('#tcp-port').fill('4404')
            page.locator('#connection-type').select_option('serial')
            expect(page.locator('#tcp-host')).to_have_count(0)
            page.locator('#connection-type').select_option('tcp')
            expect(page.locator('#tcp-host')).to_have_value('192.0.2.10')
            expect(page.locator('#tcp-port')).to_have_value('4404')
            page.set_viewport_size({'width': 390, 'height': 844})
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            expect(page.locator('.sidebar')).not_to_be_in_viewport()
            page.screenshot(path=str(ARTIFACTS / 'tcp-connect-mobile.png'), full_page=True)
            page.set_viewport_size({'width': 1440, 'height': 1050})
            page.screenshot(path=str(ARTIFACTS / 'tcp-connect-desktop.png'), full_page=True)
            submitted = []
            empty_state = httpx.get(url + '/api/state').json()
            def capture_connect(route):
                submitted.append(route.request.post_data_json)
                route.fulfill(status=200, json=empty_state)
            page.route('**/api/connect', capture_connect)
            page.locator('[data-action="connect"]').click()
            expect(page.locator('#toast')).to_contain_text('Rádio conectado')
            assert submitted == [{'transport': 'tcp', 'host': '192.0.2.10', 'tcp_port': 4404, 'mode': 'desktop'}]
            expect(page.locator('#connection-mode')).to_have_count(0)
            page.unroute('**/api/connect', capture_connect)
            page.locator('[data-action="demo"]').click()
            expect(page.locator('[data-action="disconnect"]')).to_be_visible()
            expect(page.locator('.device-name')).to_have_text("Estação de demonstração")
            page.screenshot(path=str(ARTIFACTS / "demo-desktop.png"), full_page=True)
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")

            page.locator('nav [data-page="radio"]').click()
            field = page.locator('[data-field="hop_limit"]')
            field.fill("4")
            page.locator('[data-action="review"]').click()
            expect(page.locator('#review-dialog')).to_be_visible()
            expect(page.locator('.diff-row code')).to_have_text("hop_limit")
            expect(page.locator('#apply-review')).to_be_disabled()
            page.locator('#confirm-input').fill("APLICAR !de000001")
            expect(page.locator('#apply-review')).to_be_enabled()
            page.screenshot(path=str(ARTIFACTS / "demo-review.png"), animations="disabled")
            page.locator('#apply-review').click()
            expect(page.locator('#review-dialog')).not_to_be_visible()
            expect(page.locator('[data-field="hop_limit"]')).to_have_value("4")

            # An invalid list must remain invalid when another field is edited.
            page.locator('[data-field="ignore_incoming"]').fill("[not json")
            page.locator('[data-field="hop_limit"]').fill("5")
            expect(page.locator('[data-action="review"]')).to_be_disabled()
            page.locator('[data-field="ignore_incoming"]').fill("[]")
            expect(page.locator('[data-action="review"]')).to_be_enabled()
            page.locator('[data-action="discard"]').click()
            expect(page.locator('[data-field="hop_limit"]')).to_have_value("4")

            page.locator('nav [data-page="connections"]').click()
            expect(page.locator('[data-field="wifi_psk"]')).to_have_value("")
            page.locator('[data-field="wifi_ssid"]').fill("Rede alterada no simulador")
            page.locator('[data-action="review"]').click()
            expect(page.locator('.diff-row code')).to_have_text("wifi_ssid")
            assert "demo-password" not in page.locator('body').inner_text()
            page.locator('#cancel-review').click()
            page.locator('[data-action="discard"]').click()

            page.locator('nav [data-page="device"]').click()
            page.locator('[data-section="config.position"]').click()
            expect(page.locator('[data-field="gps_enabled"]')).to_have_count(0)
            expect(page.locator('[data-field="gps_mode"]')).to_be_enabled()
            page.locator('.legacy-fields summary').first.click()
            expect(page.locator('.legacy-fields')).to_contain_text('use gps_mode')
            page.locator('[data-action="json"]').click()
            values = json.loads(page.locator('#json-editor').input_value())
            values['gps_enabled'] = not values['gps_enabled']
            page.locator('#json-editor').fill(json.dumps(values))
            page.locator('[data-action="review"]').click()
            expect(page.locator('#toast')).to_contain_text('somente leitura')
            # This deliberately rejected preview produces one expected Chrome console error.
            assert errors == ['Failed to load resource: the server responded with a status of 400 (Bad Request)']
            errors.clear()
            page.locator('[data-action="discard"]').click()

            page.locator('nav [data-page="modules"]').click()
            page.locator('[data-section="module.tak"]').click()
            expect(page.locator('.editor-head h2')).to_have_text("TAK")
            page.locator('[data-action="json"]').click()
            expect(page.locator('#json-editor')).to_be_visible()
            page.locator('#json-editor').fill('{"broken":')
            expect(page.locator('#form-error')).to_be_visible()
            page.locator('[data-action="discard"]').click()

            page.locator('nav [data-page="channels"]').click()
            expect(page.locator('.channel-card')).to_have_count(8)
            page.locator('[data-section="channel.1"]').click()
            expect(page.locator('[data-field="settings.name"]')).to_have_value("Equipe")
            page.locator('[data-field="settings.name"]').fill("Trilha")
            page.locator('[data-action="review"]').click()
            expect(page.locator('.diff-row code')).to_have_text("settings.name")
            page.locator('#cancel-review').click()
            page.locator('[data-action="discard"]').click()

            page.locator('nav [data-page="nodes"]').click()
            expect(page.locator('tbody tr')).to_have_count(6)
            page.locator('#node-search').fill("serra")
            expect(page.locator('tbody tr')).to_have_count(1)

            page.locator('nav [data-page="screen"]').click()
            page.locator('[data-section="canned_text"]').click()
            expect(page.locator('[data-field="text"]')).to_contain_text("Olá!")

            page.locator('nav [data-page="messages"]').click()
            page.locator('.chat-help > summary').last.click()
            page.locator('#chat-receive').click()
            expect(page.locator('#chat-feed')).to_contain_text('Mensagem de canal simulada')
            held=[]
            page.route('**/api/messages/send', lambda route: held.append(route))
            page.locator('#chat-text').fill('Olá canal! <script>window.chatInjected=true</script>')
            page.locator('#chat-send').click()
            expect(page.locator('#review-dialog')).not_to_be_visible()
            expect(page.locator('#chat-text')).to_have_value('')
            expect(page.locator('#chat-send')).to_be_disabled()
            page.locator('#chat-text').fill('Próxima mensagem em rascunho')
            page.locator('#chat-text').press('Enter')
            expect(page.locator('#chat-text')).to_have_value('Próxima mensagem em rascunho')
            assert len(held)==1  # Repeated Enter while sending never submits twice.
            page.locator('#chat-target').select_option('direct:!de000003')
            page.locator('#chat-text').fill('Rascunho de outra conversa')
            held[0].fulfill(response=held[0].fetch())
            page.unroute('**/api/messages/send')
            expect(page.locator('#chat-send-status')).to_be_empty()
            expect(page.locator('#chat-text')).to_have_value('Rascunho de outra conversa')
            page.locator('#chat-target').select_option('channel:0')
            expect(page.locator('#chat-feed')).to_contain_text('Envio simulado')
            expect(page.locator('#chat-feed')).to_contain_text('<script>')
            assert not page.evaluate('Boolean(window.chatInjected)')
            expect(page.locator('#chat-text')).to_have_value('Próxima mensagem em rascunho')
            page.locator('#chat-text').fill('')
            page.locator('#chat-target').select_option('direct:!de000003')
            expect(page.locator('#chat-feed')).to_contain_text('Mensagem direta de demonstração')
            expect(page.locator('#chat-channel')).to_have_count(0)
            page.locator('#chat-text').fill('Olá, mensagem direta!')
            page.locator('#chat-text').press('Shift+Enter')
            page.locator('#chat-text').press_sequentially('Segunda linha')
            expect(page.locator('#chat-text')).to_have_value('Olá, mensagem direta!\nSegunda linha')
            page.locator('#chat-text').press('Enter')
            expect(page.locator('#review-dialog')).not_to_be_visible()
            expect(page.locator('#chat-feed')).to_contain_text('Olá, mensagem direta!')
            sent = httpx.get(url+'/api/messages').json()['messages']
            direct = next(m for m in sent if m['text'].startswith('Olá, mensagem direta!'))
            assert direct['destination'] == '!de000003' and direct['channel'] == 0
            assert direct['conversation'] == 'direct:!de000003'
            page.screenshot(path=str(ARTIFACTS / 'demo-messages.png'), full_page=True, animations='disabled')
            page.set_viewport_size({'width': 390, 'height': 844})
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            page.screenshot(path=str(ARTIFACTS / 'demo-messages-mobile.png'), full_page=True, animations='disabled')
            assert page.evaluate("Array.from(document.querySelectorAll('.chat-panel,.chat-panel h2,.chat-panel p,.chat-feed')).every(e=>e.scrollWidth<=e.clientWidth+1)")
            page.set_viewport_size({'width': 1440, 'height': 1050})

            expect(page.locator('#app .status-strip')).to_have_count(0)
            page.locator('#chat-active').click()
            expect(page.locator('#chat-receive-status')).to_contain_text('Conectado · recebendo mensagens')
            expect(page.locator('#chat-stop')).to_be_enabled()
            expect(page.locator('#chat-active')).to_be_hidden()
            expect(page.locator('#chat-receive')).to_be_disabled()
            page.locator('#chat-text').fill('Mensagem durante escuta ativa')
            page.locator('#chat-send').click()
            expect(page.locator('#review-dialog')).not_to_be_visible()
            expect(page.locator('#chat-feed')).to_contain_text('Mensagem durante escuta ativa')
            expect(page.locator('#chat-receive-status')).to_contain_text('Conectado · recebendo mensagens')
            page.locator('nav [data-page="radio"]').click()
            expect(page.locator('.status-strip').first).to_contain_text('Escuta ativa.')
            page.locator('[data-action="read-section"]').click()
            expect(page.locator('[data-field="hop_limit"]')).to_have_value('4')
            page.locator('nav [data-page="messages"]').click()
            expect(page.locator('#chat-receive-status')).to_contain_text('Conectado · recebendo mensagens')
            page.screenshot(path=str(ARTIFACTS / 'active-desktop.png'), full_page=True, animations='disabled')
            page.set_viewport_size({'width': 390, 'height': 844})
            page.screenshot(path=str(ARTIFACTS / 'active-mobile.png'), full_page=True, animations='disabled')
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            page.locator('#chat-stop').click()
            expect(page.locator('#chat-receive-status')).to_contain_text('Rádio desconectado')
            expect(page.locator('#chat-active')).to_be_enabled()
            expect(page.locator('#chat-stop')).to_be_hidden()
            page.set_viewport_size({'width': 1440, 'height': 1050})

            expect(page.locator('#chat-send')).to_be_disabled()
            page.locator('#chat-text').fill('😀'*59)
            expect(page.locator('#chat-send')).to_be_disabled()
            expect(page.locator('#chat-bytes')).to_contain_text('236 / 233')
            page.locator('#chat-text').fill('')
            rejected=[]
            page.route('**/api/messages/preview',lambda route: rejected.append(route))
            page.locator('#chat-text').fill('Texto que precisa ser preservado')
            page.locator('#chat-send').click()
            expect(page.locator('#chat-text')).to_have_value('')
            page.locator('#chat-text').fill('Novo rascunho durante a validação')
            assert len(rejected)==1
            rejected[0].fulfill(status=409,json={'detail':'Falha de validação simulada'})
            page.unroute('**/api/messages/preview')
            expect(page.locator('#chat-send-status')).to_be_empty()
            expect(page.locator('#chat-text')).to_have_value('Novo rascunho durante a validação')
            page.locator('#chat-recovery summary').click()
            expect(page.locator('#chat-recovery')).to_contain_text('Texto que precisa ser preservado')
            page.locator('#chat-text').fill('')
            page.locator('#chat-restore').click()
            expect(page.locator('#chat-text')).to_have_value('Texto que precisa ser preservado')
            page.locator('#chat-text').fill('')
            assert len(errors)==1 and '409' in errors[0],errors
            errors.clear()

            interrupted=[]
            page.route('**/api/messages/send',lambda route: interrupted.append(route))
            page.locator('#chat-text').fill('Resposta perdida após envio simulado')
            with page.expect_request('**/api/messages/send'):
                page.locator('#chat-send').click()
            expect(page.locator('#chat-text')).to_have_value('')
            page.locator('#chat-text').fill('Rascunho após falha de rede')
            assert len(interrupted)==1
            response=interrupted[0].fetch()  # Simulator receives it; browser loses the response.
            assert response.ok
            interrupted[0].abort('failed')
            page.unroute('**/api/messages/send')
            expect(page.locator('#toast')).to_contain_text('Resultado desconhecido')
            expect(page.locator('#chat-text')).to_have_value('Rascunho após falha de rede')
            expect(page.locator('#chat-feed .chat-message').filter(has_text='Resposta perdida após envio simulado')).to_have_count(1)
            page.locator('#chat-recovery summary').click()
            expect(page.locator('#chat-recovery')).to_contain_text('Resultado desconhecido')
            page.locator('#chat-text').fill('')
            page.locator('#chat-restore').click()
            page.locator('#chat-text').fill('')
            assert len(errors)==1 and 'ERR_FAILED' in errors[0],errors
            errors.clear()

            page.locator('nav [data-page="overview"]').click()
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(ARTIFACTS / "demo-mobile.png"), full_page=True, animations="disabled")
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
            page.locator('[data-action="menu"]').click()
            page.locator('nav [data-page="radio"]').click()
            expect(page.locator('[data-field="hop_limit"]')).to_have_value("4")
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
            page.screenshot(path=str(ARTIFACTS / "demo-mobile-editor.png"), full_page=True, animations="disabled")
            # Exercise shutdown through the mobile UI, including cancel with
            # an unsent draft. The managed test server must actually exit.
            state = httpx.get(url + '/api/state').json()
            messages = httpx.get(url + '/api/messages').json()['messages']
            page.locator('[data-action="menu"]').click()
            page.locator('nav [data-page="messages"]').click()
            page.locator('#chat-text').fill('Rascunho antes de encerrar')
            page.locator('[data-action="menu"]').click()
            dialogs = []
            def cancel_close(dialog):
                dialogs.append(dialog.message)
                dialog.dismiss()
            page.on('dialog', cancel_close)
            page.locator('[data-action="shutdown"]').click()
            assert dialogs
            expect(page.locator('#chat-text')).to_have_value('Rascunho antes de encerrar')
            assert httpx.get(url+'/api/health').json()['stopping'] is False
            page.remove_listener('dialog', cancel_close)
            page.on('dialog', lambda dialog: dialog.accept())
            page.locator('[data-action="shutdown"]').click()
            expect(page.locator('h1')).to_have_text('App encerrado')
            page.screenshot(path=str(ARTIFACTS/'app-closed-mobile.png'), full_page=True)
            proc.wait(timeout=10)
            assert proc.returncode == 0
            browser.close()
            assert not errors, errors
        assert state["demo"] and not state["server_writes_enabled"]
        assert state["device"]["write_packets"] == 0
        assert state["device"]["simulated_writes"] == 1
        assert len(messages) == 8
        assert messages[-1]['destination'] == '!de000003' and messages[-1]['channel'] == 0
        print(json.dumps({"passed": True, "checks": ["TCP and serial selector", "TCP form payload", "desktop", "mobile", "schema forms", "draft review", "simulated write and readback", "secret preservation", "invalid JSON", "channels", "node search", "extra settings", "channel and direct messages", "message XSS escaping", "direct send without modal", "Enter and Shift+Enter", "draft preservation during pending send", "duplicate submission prevention", "failed send text recovery", "lost response without automatic retry", "active listening with send, navigation and stop"], "browser_errors": errors, "serial_writes": 0}, indent=2))
    finally:
        if proc.poll() is None:
            proc.terminate()
        proc.wait(timeout=10)


if __name__ == "__main__":
    run()
