"""Inspect the real standalone canvas and sentence interactions before author review."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.local/browser-qa'))
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'reports/氯硫框架具体化/paper-maps-20261104'
file=folder/'Qin论文_关键论证画布试读.html'
report={'mode':'same_product_canvas_with_source_bound_pivotal_judgments','scope':'Selected pivotal argument of Qin; complete paragraph map remains separate','author_acceptance':'pending','errors':[],'checks':{},'screenshots':{}}
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1150});page.on('pageerror',lambda e:report['errors'].append(str(e)))
    page.goto(file.as_uri());page.get_by_role('navigation',name='图谱视图').get_by_role('button',name='关键论证',exact=True).wait_for(timeout=15000)
    page.wait_for_timeout(550)
    out=ROOT/'reports/screenshots';out.mkdir(exist_ok=True)
    image=out/'paper-map-canvas-overview.png';page.screenshot(path=str(image));report['screenshots']['overview']=str(image)
    page.get_by_role('button',name='搜索图谱',exact=True).click()
    page.get_by_role('textbox',name='搜索图谱内容',exact=True).fill('仅忽略溶解')
    page.locator('.content-map-search-results').get_by_role('button',name='仅忽略溶解引起的孔隙变化会高估膨胀，完全忽略钙溶出会低估膨胀',exact=False).click()
    expected='The model would overestimate the expansion of specimens under external sulfate attack if it did not consider changes in porosity caused by calcium leaching.'
    evidence=page.locator('.content-map-evidence');evidence.locator('blockquote').filter(has_text=expected).wait_for()
    report['checks']['click_opens_original_sentence']=True
    report['checks']['context_contains_exact_sentence']=expected in page.locator('.content-map-source-context mark').all_text_contents()
    canvas=page.get_by_role('region',name='论文关键论证画布');scale=float(canvas.get_attribute('data-scale'))
    page.get_by_role('button',name='放大画布',exact=True).click();report['checks']['zoom_button_changes_scale']=float(canvas.get_attribute('data-scale'))>scale
    page.get_by_role('button',name='重置画布',exact=True).click();canvas.focus();before=float(canvas.get_attribute('data-pan-x'));page.keyboard.press('ArrowRight');report['checks']['keyboard_pans_canvas']=float(canvas.get_attribute('data-pan-x'))!=before
    page.get_by_role('button',name='重置画布',exact=True).click();page.wait_for_timeout(200)
    image=out/'paper-map-canvas-trial.png';page.screenshot(path=str(image));report['screenshots']['mind_map']=str(image)
    page.get_by_role('navigation',name='图谱视图').get_by_role('button',name='内容关系',exact=True).click();page.wait_for_timeout(200)
    image=out/'paper-map-relations-trial.png';page.screenshot(path=str(image));report['screenshots']['content_relations']=str(image)
    report['checks']['selected_relation_canvas_visible']=page.get_by_role('region',name='论文内容关系画布').is_visible()
    report['checks']['desktop_has_no_page_overflow']=not page.evaluate('document.documentElement.scrollWidth>innerWidth')
    page.get_by_role('navigation',name='图谱视图').get_by_role('button',name='完整摘要',exact=True).click()
    source=json.loads((folder/'qin2020/automatic-source.json').read_text(encoding='utf8'))
    report['checks']['abstract_matches_full_source']=page.locator('.content-map-original-abstract').inner_text()==source['abstract']['text']
    page.get_by_role('navigation',name='图谱视图').get_by_role('button',name='思维导图',exact=True).click();page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(250)
    report['checks']['mobile_has_no_page_overflow']=not page.evaluate('document.documentElement.scrollWidth>innerWidth')
    image=out/'paper-map-mobile-trial.png';page.screenshot(path=str(image));report['screenshots']['mobile']=str(image)
    browser.close()
report['software_checks_passed']=not report['errors'] and all(report['checks'].values())
(ROOT/'reports/paper-map-canvas-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False));assert report['software_checks_passed']
