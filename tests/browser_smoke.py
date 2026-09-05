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
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.app:app", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
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
            page.goto(url)
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
            page.locator('#chat-receive').click()
            expect(page.locator('#chat-feed')).to_contain_text('Mensagem de canal simulada')
            page.locator('#chat-text').fill('Olá canal! <script>window.chatInjected=true</script>')
            page.locator('#chat-review').click()
            expect(page.locator('#chat-send')).to_be_visible()
            expect(page.locator('.chat-review-text')).to_contain_text('<script>')
            page.locator('#chat-send').click()
            expect(page.locator('#review-dialog')).not_to_be_visible()
            expect(page.locator('#chat-feed')).to_contain_text('Envio simulado')
            assert not page.evaluate('Boolean(window.chatInjected)')
            expect(page.locator('#chat-text')).to_have_value('')
            page.locator('#chat-target').select_option('direct:!de000003')
            expect(page.locator('#chat-feed')).to_contain_text('Mensagem direta de demonstração')
            page.locator('#chat-channel').select_option('1')
            page.locator('#chat-text').fill('Olá, mensagem direta!')
            page.locator('#chat-review').click()
            expect(page.locator('.dialog-body')).to_contain_text('canal 1')
            page.locator('#chat-send').click()
            expect(page.locator('#review-dialog')).not_to_be_visible()
            expect(page.locator('#chat-feed')).to_contain_text('Olá, mensagem direta!')
            expect(page.locator('#chat-channel')).to_have_value('1')
            page.screenshot(path=str(ARTIFACTS / 'demo-messages.png'), full_page=True, animations='disabled')
            page.set_viewport_size({'width': 390, 'height': 844})
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
            page.screenshot(path=str(ARTIFACTS / 'demo-messages-mobile.png'), full_page=True, animations='disabled')
            assert page.evaluate("Array.from(document.querySelectorAll('.chat-panel,.chat-panel h2,.chat-panel p,.chat-feed')).every(e=>e.scrollWidth<=e.clientWidth+1)")
            page.set_viewport_size({'width': 1440, 'height': 1050})

            page.locator('nav [data-page="overview"]').click()
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(ARTIFACTS / "demo-mobile.png"), full_page=True, animations="disabled")
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
            page.locator('[data-action="menu"]').click()
            page.locator('nav [data-page="radio"]').click()
            expect(page.locator('[data-field="hop_limit"]')).to_have_value("4")
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
            page.screenshot(path=str(ARTIFACTS / "demo-mobile-editor.png"), full_page=True, animations="disabled")
            browser.close()
            assert not errors, errors
        state = httpx.get(url + "/api/state").json()
        assert state["demo"] and not state["server_writes_enabled"]
        assert state["device"]["write_packets"] == 0
        assert state["device"]["simulated_writes"] == 1
        messages = httpx.get(url + '/api/messages').json()['messages']
        assert len(messages) == 4
        assert messages[-1]['destination'] == '!de000003' and messages[-1]['channel'] == 1
        print(json.dumps({"passed": True, "checks": ["desktop", "mobile", "schema forms", "draft review", "simulated write and readback", "secret preservation", "invalid JSON", "channels", "node search", "extra settings", "channel and direct messages", "message XSS escaping"], "browser_errors": errors, "serial_writes": 0}, indent=2))
    finally:
        proc.terminate()
        proc.wait(timeout=10)


if __name__ == "__main__":
    run()
