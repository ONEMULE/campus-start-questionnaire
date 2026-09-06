"""Small synthetic load probe; refuses sites with demo disabled. Not a capacity certificate."""
import argparse,concurrent.futures,json,statistics,sys,time,secrets
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.helpers import make_answers

def run(url,workers,sessions,output):
 if not 1<=workers<=50 or not 1<=sessions<=150:raise SystemExit('Use 1..50 workers and 1..150 sessions')
 cfg=httpx.get(url+'/api/config').json()
 if not cfg.get('demo_enabled'):raise SystemExit('Refusing production data: use an isolated demo-enabled staging site')
 stamp=str(int(time.time()))[-7:]+str(secrets.randbelow(100)).zfill(2)
 def one(n):
  start=time.perf_counter();done=0
  try:
   with httpx.Client(base_url=url,timeout=30,headers={'Origin':url}) as c:
    reg=c.post('/api/sessions',json={'name':'压测虚构','student_id':'9'+stamp+str(n).zfill(3),'consent_core':True,'privacy_version':cfg['privacy_version']});reg.raise_for_status();done+=1
    headers={'Authorization':'Bearer '+reg.json()['access_token']}
    a=make_answers(['creative','research','academic','org','explore'][n%5])
    partial=dict(list(a.items())[:10]);r=c.put('/api/sessions/me/progress',json={'answers':partial,'revision':1},headers=headers);r.raise_for_status();done+=1
    r=c.post('/api/sessions/me/submit',json={'answers':a},headers=headers);r.raise_for_status();done+=1
    assert r.json().get('receipt')
   return {'seconds':time.perf_counter()-start,'ok':True,'requests':done}
  except Exception as e:return {'seconds':time.perf_counter()-start,'ok':False,'requests':done,'error_type':type(e).__name__}
 start=time.perf_counter()
 with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:rows=list(pool.map(one,range(sessions)))
 elapsed=time.perf_counter()-start;times=sorted(x['seconds'] for x in rows)
 result={'synthetic_sessions':sessions,'workers':workers,'requests_completed':sum(x['requests'] for x in rows),'failed_sessions':sum(not x['ok'] for x in rows),'wall_seconds':round(elapsed,3),'session_p50_seconds':round(statistics.median(times),3),'session_p95_seconds':round(times[int((len(times)-1)*.95)],3),'workload':'One registration, one 10-node progress save, one 32-node final submit per session','scope':'Local single-instance development probe; NOT Hangzhou, campus network, WeChat, or production capacity','errors':[x for x in rows if not x['ok']]}
 output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
 if result['failed_sessions']:raise SystemExit(1)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--workers',type=int,default=10);p.add_argument('--sessions',type=int,default=20);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.url.rstrip('/'),a.workers,a.sessions,a.output)