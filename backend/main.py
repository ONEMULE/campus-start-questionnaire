from __future__ import annotations
import csv
import hmac
import io
import re
import secrets
import sqlite3
import time
import unicodedata
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any

import qrcode
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .engine import (CONTENT, CONTENT_VERSION, RULE_VERSION, AnswerError,
                     calculate, gate_snapshots, sequence, validate_answers)
from .security import csv_safe, keyed_hash, password_verify, token_hash
from .settings import ROOT, Settings
from .store import Store

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

class Registration(StrictModel):
    name: str = Field(min_length=1,max_length=80)
    student_id: str = Field(min_length=1,max_length=32)
    consent_core: bool
    privacy_version: str
    enrollment_code: str = Field(default='',max_length=200)

class Progress(StrictModel):
    answers: dict[str, Any]
    revision: int = Field(ge=1, le=1000000)

class Submission(StrictModel):
    answers: dict[str, Any]

class Login(StrictModel):
    username: str = Field(max_length=80)
    password: str = Field(max_length=256)

class Review(StrictModel):
    role: str
    scores: list[int] = Field(min_length=4,max_length=4)
    note: str = Field(default='',max_length=1000)

class BodyLimit:
    """Bound streamed bodies before FastAPI parses JSON, including chunked requests."""
    def __init__(self, app, limit=131072): self.app,self.limit=app,limit
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in ('POST','PUT','PATCH'):
            return await self.app(scope,receive,send)
        body=bytearray()
        while True:
            message=await receive()
            if message['type']=='http.disconnect': return
            body.extend(message.get('body',b''))
            if len(body)>self.limit:
                return await JSONResponse({'detail':'请求过大'},status_code=413)(scope,receive,send)
            if not message.get('more_body',False): break
        sent=False
        async def replay():
            nonlocal sent
            if not sent:
                sent=True
                return {'type':'http.request','body':bytes(body),'more_body':False}
            return await receive()
        return await self.app(scope,replay,send)


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg=settings or Settings.from_env()
    store=Store(cfg)
    app=FastAPI(title='大一，启动！',version='1.1.0',docs_url=None,redoc_url=None,openapi_url=None)
    app.state.settings=cfg
    app.state.store=store
    app.add_middleware(BodyLimit)
    app.mount('/static',StaticFiles(directory=ROOT/'web'),name='static')

    @app.middleware('http')
    async def protect(request: Request, call_next):
        path=request.url.path
        if cfg.environment in ('production','staging') and path != '/healthz':
            if not hmac.compare_digest(request.headers.get('x-edge-token',''),cfg.edge_token):
                return JSONResponse({'detail':'入口不可用'},status_code=403)
        hostname=request.url.hostname
        allowed={urlsplit(cfg.public_url).hostname}
        if cfg.environment=='development': allowed|={'localhost','127.0.0.1','testserver'}
        if path!='/healthz' and hostname not in allowed:
            return JSONResponse({'detail':'无效主机名'},status_code=400)
        if request.method in ('POST','PUT','PATCH','DELETE'):
            origin=request.headers.get('origin')
            if origin and origin.rstrip('/') != cfg.public_url:
                return JSONResponse({'detail':'来源校验失败'},status_code=403)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; object-src 'none'"
        if not path.startswith('/static/'):
            response.headers['Cache-Control']='no-store'
        if cfg.environment=='production': response.headers['Strict-Transport-Security']='max-age=31536000'
        return response

    @app.exception_handler(RequestValidationError)
    async def bad_input(request, exc):
        # Never echo a student's input or a password back in validation diagnostics.
        return JSONResponse({'detail':'请求字段或数据格式不正确','fields':[list(e['loc']) for e in exc.errors()]},status_code=422)

    @app.exception_handler(AnswerError)
    async def bad_answer(request, exc):
        return JSONResponse({'detail':str(exc)},status_code=422)

    def check_rate(request: Request, namespace: str, maximum: int, seconds: int):
        ip=request.client.host if request.client else 'unknown'
        key=keyed_hash(cfg.hmac_key,'rate:'+namespace,ip)
        if not store.limit(key,maximum,seconds):
            raise HTTPException(429,'请求过于频繁，请稍后重试',headers={'Retry-After':str(seconds)})

    def participant(request: Request):
        auth=request.headers.get('authorization','')
        if not auth.startswith('Bearer ') or len(auth)>200: raise HTTPException(401,'请使用原设备继续，或输入恢复码')
        with store.connect() as c:
            row=c.execute('SELECT * FROM participants WHERE token_hash=?',(token_hash(auth[7:]),)).fetchone()
        if row is None: raise HTTPException(401,'恢复码无效或记录已删除')
        return row

    def admin(request: Request):
        token=request.cookies.get('campus_admin','')
        with store.connect() as c:
            row=c.execute('SELECT * FROM admin_sessions WHERE token_hash=? AND expires_at>?',(token_hash(token),int(time.time()))).fetchone()
        if row is None: raise HTTPException(401,'请先登录管理后台')
        if request.method in ('POST','PUT','PATCH','DELETE'):
            if not hmac.compare_digest(request.headers.get('x-csrf-token',''),row['csrf']):
                raise HTTPException(403,'操作校验失败，请刷新后重试')
        return row

    def name_clean(name: str) -> str:
        name=unicodedata.normalize('NFKC',name).strip()
        if len(name)<2 or len(name)>40 or any(unicodedata.category(ch).startswith('C') for ch in name) or any(ch in '<>/\\={}[]' for ch in name):
            raise HTTPException(422,'请填写真实姓名（2至40字符）')
        return name

    def sid_clean(sid: str) -> str:
        sid=unicodedata.normalize('NFKC',sid).strip()
        if re.fullmatch(cfg.student_id_pattern,sid) is None:
            raise HTTPException(422,'学号格式不正确，请核对完整学号')
        return sid

    @app.get('/')
    def index(): return FileResponse(ROOT/'web/index.html')

    @app.get('/admin')
    def admin_page(): return FileResponse(ROOT/'web/admin.html')

    @app.get('/privacy')
    def privacy_page(): return FileResponse(ROOT/'web/privacy.html')

    @app.get('/qr')
    def qr_page(): return FileResponse(ROOT/'web/qr.html')

    @app.get('/qr.png')
    def qr_image():
        qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=12,border=4)
        qr.add_data(cfg.public_url+'/');qr.make(fit=True)
        image=qr.make_image(fill_color='black',back_color='white')
        out=io.BytesIO();image.save(out,format='PNG')
        return Response(out.getvalue(),media_type='image/png',headers={'Content-Disposition':'inline; filename=campus-start-qr.png'})

    @app.get('/healthz')
    def health(): return {'status':'ok','version':'1.1.0'}

    @app.get('/readyz')
    def ready():
        with store.connect() as c: c.execute('SELECT 1').fetchone()
        return {'status':'ready','content_version':CONTENT_VERSION,'rule_version':RULE_VERSION}

    @app.get('/api/config')
    def public_config():
        return {'name':'大一，启动！','subtitle':'海洋学院新生模拟器','version':'1.1.0','public_url':cfg.public_url,'cohort':cfg.cohort,'operator':cfg.operator_name,'privacy_contact':cfg.privacy_contact,'privacy_version':cfg.privacy_version,'retention_days':cfg.retention_days,'draft_days':cfg.draft_days,'enrollment_required':bool(cfg.enrollment_code),'roster_required':cfg.roster_required,'photo_enabled':cfg.photo_enabled,'demo_enabled':cfg.demo_enabled,'student_id_pattern':cfg.student_id_pattern,'icp_number':cfg.icp_number,'police_number':cfg.police_number,'police_url':cfg.police_url,'content_version':CONTENT_VERSION,'rule_version':RULE_VERSION}

    @app.get('/api/content')
    def content(): return CONTENT

    @app.post('/api/sessions',status_code=201)
    def register(payload: Registration, request: Request):
        check_rate(request,'register',400,300)
        if not payload.consent_core or payload.privacy_version!=cfg.privacy_version:
            raise HTTPException(422,'请先阅读并同意当前版本的数据使用说明')
        if cfg.enrollment_code and not hmac.compare_digest(payload.enrollment_code,cfg.enrollment_code):
            raise HTTPException(403,'参与口令不正确，请联系活动负责人')
        sid=sid_clean(payload.student_id);name=name_clean(payload.name)
        sidkey=keyed_hash(cfg.hmac_key,'sid:'+cfg.cohort,sid)
        if cfg.roster_required:
            with store.connect() as c: r=c.execute('SELECT name_key FROM roster WHERE cohort=? AND sid_key=?',(cfg.cohort,sidkey)).fetchone()
            if r is None or not hmac.compare_digest(r['name_key'],keyed_hash(cfg.hmac_key,'name',name)):
                raise HTTPException(403,'登记信息未通过，请核对姓名与学号或联系负责人')
        uid=str(uuid.uuid4());token=secrets.token_urlsafe(32);now=int(time.time())
        try:
            with store.connect() as c:
                c.execute('INSERT INTO participants(id,cohort,sid_key,identity_enc,token_hash,privacy_version,created_at,updated_at,answers_enc) VALUES(?,?,?,?,?,?,?,?,?)',(uid,cfg.cohort,sidkey,store.seal({'name':name,'student_id':sid}),token_hash(token),cfg.privacy_version,now,now,store.seal({})))
        except sqlite3.IntegrityError:
            raise HTTPException(409,'该登记已有记录。请使用原设备或恢复码继续；不要重复登记。')
        return {'id':uid,'access_token':token,'privacy_version':cfg.privacy_version,'note':'恢复码具有个人记录访问权限，请私下保存，不要发到群里。'}

    @app.get('/api/sessions/me')
    def me(row=Depends(participant)):
        return {'id':row['id'],'identity':store.open(row['identity_enc']),'answers':store.open(row['answers_enc']),'revision':row['revision'],'status':row['status'],'receipt':row['receipt'],'result':store.open(row['result_enc'])}

    @app.put('/api/sessions/me/progress')
    def progress(payload: Progress,row=Depends(participant)):
        clean=validate_answers(payload.answers,complete=False,allow_photo=cfg.photo_enabled)
        with store.connect() as c:
            c.execute("UPDATE participants SET answers_enc=?,revision=?,updated_at=? WHERE id=? AND status='draft' AND revision<?",(store.seal(clean),payload.revision,int(time.time()),row['id'],payload.revision))
            fresh=c.execute('SELECT status,revision FROM participants WHERE id=?',(row['id'],)).fetchone()
        if fresh['status']!='draft': raise HTTPException(409,'结果已提交，不能继续改写')
        return {'ok':True,'revision':fresh['revision'],'count':len(clean)}

    @app.post('/api/sessions/me/submit')
    def submit(payload: Submission,row=Depends(participant)):
        if row['status']=='submitted':
            return {'ok':True,'receipt':row['receipt'],'result':store.open(row['result_enc']),'already':True}
        clean=validate_answers(payload.answers,complete=True,allow_photo=cfg.photo_enabled)
        result=calculate(clean)
        result['gateSnapshots']=gate_snapshots(clean)
        receipt='DY-'+secrets.token_hex(5).upper();now=int(time.time())
        with store.connect() as c:
            c.execute("UPDATE participants SET answers_enc=?,result_enc=?,status='submitted',receipt=?,submitted_at=?,updated_at=? WHERE id=? AND status='draft'",(store.seal(clean),store.seal(result),receipt,now,now,row['id']))
            current=c.execute('SELECT result_enc,receipt FROM participants WHERE id=?',(row['id'],)).fetchone()
        return {'ok':True,'receipt':current['receipt'],'result':store.open(current['result_enc'])}

    @app.delete('/api/sessions/me')
    def withdraw(row=Depends(participant)):
        with store.connect() as c:
            c.execute('DELETE FROM participants WHERE id=?',(row['id'],))
            c.execute('INSERT INTO audit(at,actor,action,record_id) VALUES(?,?,?,?)',(int(time.time()),'participant','participant_withdraw',row['id']))
        return {'ok':True,'note':'活动库记录已删除。到期备份清理与工作人员已导出副本按隐私说明处理。'}

    @app.post('/api/preview')
    def preview(payload: Submission,request: Request):
        if not cfg.demo_enabled: raise HTTPException(404)
        check_rate(request,'preview',120,60)
        clean=validate_answers(payload.answers,complete=True,allow_photo=cfg.photo_enabled)
        return {'result':calculate(clean),'saved':False}

    @app.post('/api/admin/login')
    def login(payload: Login,request: Request,response: Response):
        check_rate(request,'login',10,60)
        valid_user=hmac.compare_digest(payload.username,cfg.admin_username)
        valid_password=password_verify(payload.password,cfg.admin_password_hash)
        if not (valid_user and valid_password): raise HTTPException(401,'账号或口令不正确')
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32);now=int(time.time())
        with store.connect() as c:
            c.execute('DELETE FROM admin_sessions WHERE expires_at<=?',(now,))
            c.execute('INSERT INTO admin_sessions VALUES(?,?,?)',(token_hash(token),csrf,now+8*3600))
        response.set_cookie('campus_admin',token,httponly=True,secure=cfg.secure_cookies,samesite='strict',max_age=8*3600,path='/')
        store.audit('login')
        return {'ok':True,'csrf_token':csrf}

    @app.get('/api/admin/me')
    def admin_me(row=Depends(admin)): return {'username':cfg.admin_username,'csrf_token':row['csrf']}

    @app.post('/api/admin/logout')
    def logout(response: Response,row=Depends(admin)):
        with store.connect() as c: c.execute('DELETE FROM admin_sessions WHERE token_hash=?',(row['token_hash'],))
        response.delete_cookie('campus_admin',path='/');return {'ok':True}

    def public_record(row,detail=False):
        identity=store.open(row['identity_enc'])
        result=store.open(row['result_enc']) or {}
        answers=store.open(row['answers_enc']) or {}
        contact=answers.get('N27',{})
        value={'id':row['id'],'cohort':row['cohort'],**identity,'status':row['status'],'created_at':row['created_at'],'submitted_at':row['submitted_at'],'receipt':row['receipt'],'ending':result.get('ending',''),'availability':result.get('availability',''),'consent':result.get('consent','NO_CONTACT'),'contact':contact.get('contact','') if contact.get('choice')!='none' else '', 'review':store.open(row['review_enc']),'progress':len(answers),'identity_verification':'名册字段匹配（非本人认证）' if cfg.roster_required else '本人填写（未核验）'}
        if detail: value.update({'answers':answers,'result':result,'privacy_version':row['privacy_version']})
        return value

    @app.get('/api/admin/participants')
    def list_participants(page:int=1,limit:int=30,student_id:str='',status:str='',_row=Depends(admin)):
        if page<1 or not 1<=limit<=100 or status not in ('','draft','submitted'): raise HTTPException(422,'查询参数无效')
        conditions=['cohort=?'];values:list[Any]=[cfg.cohort]
        if student_id:
            conditions.append('sid_key=?');values.append(keyed_hash(cfg.hmac_key,'sid:'+cfg.cohort,sid_clean(student_id)))
        if status: conditions.append('status=?');values.append(status)
        where=' AND '.join(conditions)
        with store.connect() as c:
            count=c.execute('SELECT count(*) FROM participants WHERE '+where,values).fetchone()[0]
            rows=c.execute('SELECT * FROM participants WHERE '+where+' ORDER BY created_at DESC,id LIMIT ? OFFSET ?',values+[limit,(page-1)*limit]).fetchall()
            stats=dict(c.execute('SELECT status,count(*) FROM participants WHERE cohort=? GROUP BY status',(cfg.cohort,)).fetchall())
        return {'total':count,'page':page,'limit':limit,'stats':stats,'items':[public_record(r) for r in rows]}

    @app.get('/api/admin/participants/{record_id}')
    def detail(record_id:str,_row=Depends(admin)):
        with store.connect() as c: row=c.execute('SELECT * FROM participants WHERE id=? AND cohort=?',(record_id,cfg.cohort)).fetchone()
        if row is None: raise HTTPException(404)
        store.audit('read_detail',record_id)
        return public_record(row,True)

    @app.post('/api/admin/participants/{record_id}/review')
    def review(record_id:str,payload:Review,_row=Depends(admin)):
        if any(type(x) is not int or x<0 or x>4 for x in payload.scores): raise HTTPException(422,'每项评分须为0至4整数')
        with store.connect() as c:
            row=c.execute('SELECT * FROM participants WHERE id=? AND cohort=?',(record_id,cfg.cohort)).fetchone()
            if row is None: raise HTTPException(404)
            result=store.open(row['result_enc']) or {}
            sample=result.get('workSample') or {}
            valid_roles={'writing':['编导策划','运营联络'],'clips':['剪辑后期'],'photos':['摄影摄像']}
            if payload.role not in valid_roles.get(sample.get('task'),[]): raise HTTPException(422,'该作品未覆盖所选岗位，不能跨任务评分')
            score=sum(payload.scores)/16*100
            final=.65*result['behaviorFits'][payload.role]+.20*result['interests']['creative']+.15*score
            entry={'role':payload.role,'scores':payload.scores,'score':score,'reviewed_fit':round(final,2),'note':payload.note,'at':int(time.time()),'reviewer':cfg.admin_username,'rubric_version':'sample-1.0','warning':'单份作品评阅；不作自动录取依据'}
            c.execute('UPDATE participants SET review_enc=? WHERE id=?',(store.seal(entry),record_id))
        store.audit('review',record_id)
        return entry

    @app.post('/api/admin/participants/{record_id}/rotate-access')
    def rotate_access(record_id:str,_row=Depends(admin)):
        token=secrets.token_urlsafe(32)
        with store.connect() as c:
            cursor=c.execute('UPDATE participants SET token_hash=? WHERE id=? AND cohort=?',(token_hash(token),record_id,cfg.cohort))
            if not cursor.rowcount: raise HTTPException(404)
        store.audit('rotate_access',record_id)
        return {'access_token':token,'note':'原恢复码立即失效；请核验本人后单独发送新码。'}

    @app.delete('/api/admin/participants/{record_id}')
    def delete_record(record_id:str,_row=Depends(admin)):
        with store.connect() as c:
            cursor=c.execute('DELETE FROM participants WHERE id=? AND cohort=?',(record_id,cfg.cohort))
            if not cursor.rowcount: raise HTTPException(404)
            c.execute('INSERT INTO audit(at,actor,action,record_id) VALUES(?,?,?,?)',(int(time.time()),'admin','delete',record_id))
        return {'ok':True}

    @app.get('/api/admin/export.csv')
    def export(_row=Depends(admin)):
        with store.connect() as c: rows=c.execute('SELECT * FROM participants WHERE cohort=? ORDER BY created_at',(cfg.cohort,)).fetchall()
        out=io.StringIO(newline='');writer=csv.writer(out)
        writer.writerow(['记录ID','姓名','学号','状态','提交时间(UTC秒)','回执编号','主结局','联系意向','联系方式','每周时间','作品评阅岗位','作品得分','评阅后参考分']+list(CONTENT['DIMS']))
        for row in rows:
            r=public_record(row,True);v=r.get('review') or {};result=r['result']
            values=[r['id'],r['name'],csv_safe(r['student_id'],force_text=True),r['status'],r['submitted_at'],r['receipt'],r['ending'],r['consent'],r['contact'],r['availability'],v.get('role',''),v.get('score',''),v.get('reviewed_fit','')]+[result.get('scores',{}).get(d,'') for d in CONTENT['DIMS']]
            writer.writerow([csv_safe(x) for x in values])
        store.audit('export_csv')
        return Response(('\ufeff'+out.getvalue()).encode('utf-8'),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=campus-start-export.csv'})

    @app.get('/api/admin/audit')
    def audit(_row=Depends(admin)):
        with store.connect() as c: rows=c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 200').fetchall()
        return {'items':[dict(r) for r in rows]}

    return app