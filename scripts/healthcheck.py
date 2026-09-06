#!/usr/bin/env python3
"""Non-mutating checks. Secrets are read from a file, not CLI arguments."""
import argparse,json,sys,urllib.request,urllib.parse
from dotenv import dotenv_values
p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--env-file');a=p.parse_args()
headers={}
if a.env_file:
    env=dotenv_values(a.env_file)
    headers={'X-Edge-Token':env.get('EDGE_TOKEN',''),'Host':urllib.parse.urlsplit(env.get('PUBLIC_URL','')).netloc}
results=[]
for path in ['/healthz','/readyz','/api/config','/qr.png']:
    try:
        req=urllib.request.Request(a.url.rstrip('/')+path,headers=headers)
        with urllib.request.urlopen(req,timeout=12) as r:
            body=r.read();ok=r.status==200 and (body.startswith(b'\x89PNG') if path.endswith('.png') else isinstance(json.loads(body),dict))
        results.append({'path':path,'ok':ok})
    except Exception as e:results.append({'path':path,'ok':False,'error':type(e).__name__})
print(json.dumps(results,indent=2));sys.exit(0 if all(r['ok'] for r in results) else 1)