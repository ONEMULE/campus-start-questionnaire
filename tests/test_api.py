import json
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.security import keyed_hash,token_hash,csv_safe
from .conftest import register,login,PASSWORD
from .helpers import make_answers

def test_registration_identity_and_encryption(client,app,config):
    data,headers=register(client)
    me=client.get('/api/sessions/me',headers=headers).json()
    assert me['identity']=={'name':'测试同学','student_id':'00001234'}
    for p in config.db_path.parent.glob('test.sqlite3*'):
        raw=p.read_bytes()
        assert '测试同学'.encode() not in raw and b'00001234' not in raw and data['access_token'].encode() not in raw

def test_required_identity_and_consent(client):
    for payload in [{'name':'测试同学','student_id':'00001234','consent_core':False,'privacy_version':'2026-09-v1.2'}, {'name':'测试同学','student_id':12345678,'consent_core':True,'privacy_version':'2026-09-v1.2'}, {'name':'','student_id':'00001234','consent_core':True,'privacy_version':'2026-09-v1.2'}]:
        r=client.post('/api/sessions',json=payload);assert r.status_code==422

def test_validation_error_does_not_echo_input(client):
    r=client.post('/api/sessions',json={'name':'PrivatePersonNoEcho','student_id':12345678})
    assert 'PrivatePersonNoEcho' not in r.text and '12345678' not in r.text

def test_duplicate_no_overwrite(client):
    d,h=register(client)
    r=client.post('/api/sessions',json={'name':'另一个人','student_id':'00001234','consent_core':True,'privacy_version':'2026-09-v1.2'})
    assert r.status_code==409
    assert client.get('/api/sessions/me',headers=h).json()['identity']['name']=='测试同学'

def test_unauthenticated_access(client):
    assert client.get('/api/sessions/me').status_code==401
    assert client.get('/api/admin/participants').status_code==401
    assert client.get('/api/admin/export.csv').status_code==401

def test_progress_versions_and_restore(client):
    d,h=register(client);a=make_answers();partial=dict(list(a.items())[:5])
    r=client.put('/api/sessions/me/progress',headers=h,json={'answers':partial,'revision':2});assert r.status_code==200
    client.put('/api/sessions/me/progress',headers=h,json={'answers':{'N00':a['N00']},'revision':1})
    restored=client.get('/api/sessions/me',headers=h).json();assert restored['revision']==2 and len(restored['answers'])==5

@pytest.mark.parametrize('route',['academic','research','creative','org','explore'])
def test_finish_all_routes(client,route):
    d,h=register(client);a=make_answers(route)
    r=client.post('/api/sessions/me/submit',headers=h,json={'answers':a})
    assert r.status_code==200,r.text
    data=r.json();assert data['ok'] and len(data['result']['gateSnapshots'])==8
    again=client.post('/api/sessions/me/submit',headers=h,json={'answers':a})
    assert again.json()['receipt']==data['receipt'] and again.json()['already']

def test_do_not_trust_browser_result(client):
    d,h=register(client)
    r=client.post('/api/sessions/me/submit',headers=h,json={'answers':make_answers(),'result':{'scores':{'AI':100}}})
    assert r.status_code==422

def test_final_cannot_be_overwritten(client):
    d,h=register(client);a=make_answers()
    r=client.post('/api/sessions/me/submit',headers=h,json={'answers':a}).json()
    a['N01']='D'
    assert client.post('/api/sessions/me/submit',headers=h,json={'answers':a}).json()['result']==r['result']
    assert client.put('/api/sessions/me/progress',headers=h,json={'answers':a,'revision':99}).status_code==409

def test_contact_opt_out_and_manual_review(client):
    d,h=register(client);a=make_answers(sample='writing');a['N27']={'choice':'none','contact':'must not store'}
    client.post('/api/sessions/me/submit',headers=h,json={'answers':a})
    auth=login(client)
    detail=client.get('/api/admin/participants/'+d['id']).json()
    assert detail['contact']=='' and detail['answers']['N27']['contact']==''
    r=client.post('/api/admin/participants/'+d['id']+'/review',headers=auth,json={'role':'编导策划','scores':[3,4,3,2],'note':'测试评阅'})
    assert r.status_code==200 and r.json()['score']==75
    wrong=client.post('/api/admin/participants/'+d['id']+'/review',headers=auth,json={'role':'摄影摄像','scores':[4,4,4,4]})
    assert wrong.status_code==422

def test_review_needs_csrf(client):
    d,h=register(client);client.post('/api/sessions/me/submit',headers=h,json={'answers':make_answers(sample='writing')});login(client)
    assert client.post('/api/admin/participants/'+d['id']+'/review',json={'role':'编导策划','scores':[1,1,1,1]}).status_code==403

def test_csv_bom_and_text_id(client):
    register(client);login(client);r=client.get('/api/admin/export.csv')
    assert r.content.startswith(b'\xef\xbb\xbf') and "'00001234" in r.text
    assert csv_safe('=HYPERLINK("bad")').startswith("'")
    assert csv_safe('   @SUM(1)').startswith("'")

def test_withdraw_and_access_rotation(client):
    d,h=register(client);auth=login(client)
    r=client.post('/api/admin/participants/'+d['id']+'/rotate-access',headers=auth)
    assert r.status_code==200 and client.get('/api/sessions/me',headers=h).status_code==401
    new={'Authorization':'Bearer '+r.json()['access_token']}
    assert client.delete('/api/sessions/me',headers=new).status_code==200
    assert client.get('/api/sessions/me',headers=new).status_code==401

def test_csrf_origin_and_admin_cookie(client):
    r=client.post('/api/admin/login',headers={'Origin':'https://evil.example'},json={'username':'admin','password':PASSWORD})
    assert r.status_code==403
    r=client.post('/api/admin/login',json={'username':'admin','password':PASSWORD})
    assert 'httponly' in r.headers['set-cookie'].lower() and 'samesite=strict' in r.headers['set-cookie'].lower()

def test_login_throttle(client):
    for _ in range(10): assert client.post('/api/admin/login',json={'username':'admin','password':'wrong'}).status_code==401
    assert client.post('/api/admin/login',json={'username':'admin','password':'wrong'}).status_code==429

def test_big_body(client):
    r=client.post('/api/sessions',content=b'x'*140000,headers={'Content-Type':'application/json'})
    assert r.status_code==413

def test_qr_fixed_target(client):
    a=client.get('/qr.png');b=client.get('/qr.png?target=https://evil.example')
    assert a.status_code==200 and a.content==b.content and a.headers['content-type']=='image/png'

def test_production_requires_edge_and_secure_cookie(config):
    config.environment='production';config.public_url='https://testserver';config.edge_token='E'*48;config.operator_name='Authorized activity operator';config.privacy_contact='privacy@example.org';config.demo_enabled=False;config.__post_init__()
    with TestClient(create_app(config),base_url='https://testserver') as c:
        assert c.get('/api/config').status_code==403
        headers={'X-Edge-Token':config.edge_token}
        assert c.get('/api/config',headers=headers).status_code==200
        r=c.post('/api/admin/login',headers=headers,json={'username':'admin','password':PASSWORD})
        assert r.status_code==200 and 'secure' in r.headers['set-cookie'].lower()

def test_roster_enforcement(config):
    config.roster_required=True
    app=create_app(config)
    with app.state.store.connect() as c:
        c.execute('INSERT INTO roster VALUES(?,?,?)',(config.cohort,keyed_hash(config.hmac_key,'sid:'+config.cohort,'00001234'),keyed_hash(config.hmac_key,'name','测试同学')))
    with TestClient(app) as client:
        register(client)
        r=client.post('/api/sessions',json={'name':'别的同学','student_id':'99999999','consent_core':True,'privacy_version':'2026-09-v1.2'})
        assert r.status_code==403

def test_no_contact_name_affects_score(client):
    d,h=register(client);a=make_answers();x=client.post('/api/sessions/me/submit',headers=h,json={'answers':a}).json()['result']
    d,h=register(client,'00005678','另一同学');y=client.post('/api/sessions/me/submit',headers=h,json={'answers':a}).json()['result']
    assert x==y
