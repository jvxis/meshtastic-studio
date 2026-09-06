"""Managed local server: graceful shutdown requested by the authenticated UI."""
import argparse
import uvicorn
from .app import create_app


def run(port=8765, manager=None):
    server = None

    def stop():
        server.should_exit = True

    app = create_app(manager, shutdown_callback=stop)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port,
                                          access_log=False))
    server.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765, choices=range(1024, 65536), metavar='PORT')
    args = parser.parse_args()
    run(args.port)
