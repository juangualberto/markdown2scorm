"""Open every SCO with network isolation and check two viewport sizes."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import threading
from lxml import html


def inspect_pages(build: Path, destination: Path):
    from playwright.sync_api import sync_playwright

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(build)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    pages = sorted(build.glob('pages/*.html'))
    image_page = next(p for p in pages if html.fromstring(p.read_bytes()).xpath('//img'))
    table_page = next((p for p in pages if html.fromstring(p.read_bytes()).xpath('//table')), None)
    screenshots = {'introduccion.html': 'introduccion', image_page.name: 'con-imagen'}
    if table_page:
        screenshots[table_page.name] = 'con-tabla'
    destination.mkdir(parents=True, exist_ok=True)
    errors = []
    checked = 0
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context()
            def route_request(route):
                if route.request.url.startswith(base + '/'):
                    route.continue_()
                else:
                    errors.append('Solicitud externa: ' + route.request.url)
                    route.abort()
            context.route('**/*', route_request)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('requestfailed', lambda request: errors.append('Recurso fallido: ' + request.url))
            page.on('response', lambda response: errors.append(f'HTTP {response.status}: {response.url}') if response.status >= 400 else None)
            page.on('console', lambda message: errors.append('Consola: ' + message.text) if message.type == 'error' else None)
            for width, height in [(1280, 900), (390, 844)]:
                page.set_viewport_size({'width': width, 'height': height})
                for path in pages:
                    page.goto(base + '/pages/' + path.name, wait_until='networkidle')
                    findings = page.evaluate('''() => ({
                        overflow: document.documentElement.scrollWidth > innerWidth + 1,
                        images: [...document.images].every(i => i.complete && i.naturalWidth > 0),
                        sidebar: !!document.querySelector('nav, #siteNav'),
                        runtime: !!window.MarkdownSCORM,
                        scormErrors: window.MarkdownSCORM ? window.MarkdownSCORM.errors : ['missing']
                    })''')
                    if findings['overflow'] or not findings['images'] or findings['sidebar'] or not findings['runtime'] or findings['scormErrors']:
                        errors.append(f'{path.name} ({width}px): {findings}')
                    if path.name in screenshots:
                        page.screenshot(path=str(destination / f'{screenshots[path.name]}-{width}.png'), full_page=True)
                    checked += 1
            version = browser.version
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    result = {'browser': 'Chromium ' + version, 'pages': len(pages), 'page_views': checked,
              'viewports': [1280, 390], 'errors': errors,
              'screenshots': sorted(p.name for p in destination.glob('*.png'))}
    (destination / 'visual-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path)
    parser.add_argument('--output', type=Path, default=Path('dist/screenshots'))
    args = parser.parse_args()
    result = inspect_pages(args.build, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result['errors']))
