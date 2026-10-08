"""Optional browser acceptance test. Requires Playwright and a Chromium install.

Run after installation: python scripts/browser_smoke.py --chromium /usr/bin/chromium
Artifacts are written outside the repository by default; no user captures used.
"""
import argparse
import json
from pathlib import Path
import threading
import time
from playwright.sync_api import sync_playwright
from recontrail.demo import make_demo
from recontrail.server import JobStore, WorkbenchServer
from recontrail.storage import atomic_json


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,default=Path('../recontrail-browser-validation'))
    p.add_argument('--chromium',default=None)
    args=p.parse_args()
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=True)
    capture=root/'capture';make_demo(capture)
    store=JobStore(root/'jobs')
    server=WorkbenchServer(('127.0.0.1',0),store)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    errors=[];external=[]
    base=f'http://{server.expected_host}'
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=args.chromium,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':1050},device_scale_factor=1)
            page.on('pageerror',lambda exc:errors.append(str(exc)))
            page.on('request',lambda request:external.append(request.url) if not request.url.startswith((base,'file:','blob:','data:')) else None)
            page.goto(f'{base}/#token={store.token}')
            page.wait_for_timeout(250)
            assert '#token=' not in page.url
            page.screenshot(path=str(root/'recontrail-workbench-empty.png'),full_page=True)
            page.locator('#files').set_input_files([str(p) for p in sorted((capture/'images').glob('*.png'))])
            page.locator('#intrinsics').set_input_files(str(capture/'intrinsics.json'))
            page.locator('#preset').select_option('quick')
            page.locator('#start').click()
            page.wait_for_function("document.getElementById('state').textContent === '处理完成'",timeout=120000)
            assert page.locator('#result').is_visible()
            assert page.locator('#error').is_hidden()
            page.screenshot(path=str(root/'recontrail-workbench-complete.png'),full_page=True)
            with page.expect_download() as download_info:
                page.get_by_role('button',name='保存离线报告',exact=True).click()
            download=download_info.value
            report=root/'report.html';download.save_as(str(report))
            page.goto(report.as_uri());page.wait_for_timeout(300)
            assert page.locator('#registered').inner_text()=='8 / 8'
            before=page.locator('#cloud').screenshot()
            box=page.locator('#cloud').bounding_box()
            page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
            page.mouse.down();page.mouse.move(box['x']+box['width']/2+160,box['y']+box['height']/2+30,steps=8);page.mouse.up()
            page.wait_for_timeout(100)
            assert page.locator('#cloud').screenshot()!=before
            page.locator('#reset').click();page.wait_for_timeout(100)
            page.screenshot(path=str(root/'recontrail-report-preview.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(100)
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
            page.screenshot(path=str(root/'recontrail-report-mobile.png'),full_page=True)
            browser.close()
        assert not errors,errors
        assert not external,external
        atomic_json(root/'browser-result.json',{'passed':True,'javascript_errors':errors,'external_requests':external,
            'checks':['upload through UI','actual worker reconstruction','8/8 registration','HTML download',
                      'offline viewer orbit/reset','390px responsive layout','token removed from address bar'],
            'fixture':'original synthetic multi-depth capture'})
        print(json.dumps({'passed':True,'artifacts':str(root)}))
    finally:
        server.shutdown();server.server_close();store.close();thread.join(timeout=2)


if __name__=='__main__':
    main()
