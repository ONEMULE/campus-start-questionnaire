"""Real browser smoke test. Use only a dedicated development/staging database."""
import argparse,json,os,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.helpers import make_answers
from backend.engine import QUESTIONS


def run(base,out):
    out.mkdir(parents=True,exist_ok=True)
    errors=[];results=[]
    password=os.environ.get('UI_TEST_ADMIN_PASSWORD')
    if not password:raise SystemExit('Set UI_TEST_ADMIN_PASSWORD privately for a synthetic staging database')
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
        probe=browser.new_context()
        cfg=probe.request.get(base+'/api/config').json()
        if not cfg.get('demo_enabled'):raise SystemExit('Refusing to seed a non-test site; staging must enable demo')
        probe.close()
        stamp=str(int(time.time()))[-5:]
        for idx,route in enumerate(['creative','research','academic','org','explore']):
            ctx=browser.new_context(viewport={'width':390 if idx==0 else 1280,'height':844 if idx==0 else 900},is_mobile=idx==0,has_touch=idx==0)
            page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base);page.locator('#name').wait_for()
            if idx==0:
                for width in [320,390,768]:
                    page.set_viewport_size({'width':width,'height':844})
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),f'Landing overflow {width}'
                page.set_viewport_size({'width':390,'height':844})
                page.screenshot(path=str(out/'01-mobile-landing.png'),full_page=True)
            sid='90'+stamp+str(idx)
            page.locator('#name').fill('测试同学'+str(idx));page.locator('#studentId').fill(sid);page.locator('#consent').check();page.locator('#joinBtn').click()
            page.locator('#closeModal').wait_for();page.locator('#closeModal').click()
            answers=make_answers(route,sample='writing' if idx==0 else 'skip')
            for n,(qid,answer) in enumerate(answers.items()):
                page.locator('#app .eyebrow').filter(has_text=qid).wait_for()
                q=QUESTIONS[qid]
                if idx==0 and n==2:
                    page.reload();page.locator('#app .eyebrow').filter(has_text=qid).wait_for()
                if idx==0 and n==10:
                    page.screenshot(path=str(out/'02-mobile-question.png'),full_page=True)
                if q['type'] in ['single','multi','allocation','contact']:
                    ids=answer if isinstance(answer,list) else [answer['choice']] if isinstance(answer,dict) else [answer]
                    for val in ids:page.locator('[data-choice="'+val+'"]').click()
                elif q['type']=='worksample':
                    if answer['task']=='writing':
                        page.locator('[data-task="writing"]').click();page.locator('#workText').fill(answer['text']);page.screenshot(path=str(out/'03-mobile-work-sample.png'),full_page=True)
                elif q['type']=='mbti':page.locator('#mbti').select_option('')
                if idx==0 and n==12:ctx.set_offline(True)
                page.locator('#nextBtn').click()
                if idx==0 and n==13:
                    ctx.set_offline(False)
                    page.evaluate('window.dispatchEvent(new Event("online"))')
            page.locator('.result-title').wait_for(timeout=20000)
            assert page.locator('#network').inner_text().find('已保存')>=0
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            assert '测试同学' not in page.locator('#shareText').input_value()
            assert sid not in page.locator('#shareText').input_value()
            if idx==0:page.screenshot(path=str(out/'04-mobile-result.png'),full_page=True)
            results.append({'route':route,'story_nodes':32,'registered':True,'submitted':True,'student_id':sid})
            ctx.close()
        # Backtracking changes the route, never leaves old answers counted.
        ctx=browser.new_context(viewport={'width':390,'height':844});page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base);page.locator('summary').filter(has_text='开发测试入口').click();page.locator('#demoBtn').click()
        answers=make_answers('creative')
        for qid,a in list(answers.items())[:6]:
            q=QUESTIONS[qid]
            for val in a if isinstance(a,list) else [a]:page.locator('[data-choice="'+val+'"]').click()
            page.locator('#nextBtn').click()
        page.locator('#backBtn').click();page.locator('#backBtn').click()
        for val in ['creative','academic','research','org']:page.locator('[data-choice="'+val+'"]').click()
        page.locator('#nextBtn').click()
        assert page.locator('#app .eyebrow').inner_text()=='N05-R'
        stored=page.evaluate('JSON.parse(sessionStorage.getItem("campusStartV11"))')
        assert 'N05-C' not in stored['answers']
        ctx.close()
        # Staff flow includes actual form posting and download.
        ctx=browser.new_context(viewport={'width':1280,'height':900});page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base+'/admin');page.locator('#username').fill('admin');page.locator('#password').fill(password);page.locator('#loginBtn').click()
        page.locator('#searchId').wait_for();page.screenshot(path=str(out/'05-admin-list.png'),full_page=True)
        page.locator('#searchId').fill(results[0]['student_id']);page.locator('#searchForm').evaluate('(e)=>e.requestSubmit()')
        page.locator('[data-record]').first.click();page.locator('#reviewForm').wait_for()
        for i in range(4):page.locator('#score'+str(i)).select_option('3')
        page.locator('#note').fill('自动化测试的虚构作品，仅验证保存流程。');page.locator('#reviewForm').evaluate('(e)=>e.requestSubmit()')
        page.get_by_text('已评阅：',exact=False).wait_for();page.screenshot(path=str(out/'06-admin-review.png'),full_page=True)
        page.locator('#backList').click()
        with page.expect_download() as download:page.locator('a[href="/api/admin/export.csv"]').click()
        assert download.value.suggested_filename.endswith('.csv')
        page.locator('#logoutBtn').click();page.locator('#loginBtn').wait_for()
        page.goto(base+'/qr');page.locator('#qrImage').wait_for() if page.locator('#qrImage').count() else page.locator('img').wait_for()
        assert page.locator('img').evaluate('(el)=>el.complete && el.naturalWidth>0')
        ctx.close();browser.close()
    assert not errors,errors
    report={'browser':'Chromium / Playwright','routes':results,'story_submissions':5,'screenshots':6,'backtracking':True,'reload_resume':True,'offline_resume':True,'admin_review_export_logout':True,'landing_widths':[320,390,768],'javascript_errors':errors,'real_wechat_devices_tested':False}
    (out/'ui-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.url.rstrip('/'),a.output)