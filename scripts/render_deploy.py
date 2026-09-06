#!/usr/bin/env python3
"""Validate deployment inputs and render candidate files. Never installs/reloads anything."""
from __future__ import annotations
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cryptography.fernet import Fernet
from dotenv import dotenv_values
from backend.security import password_hash
from backend.settings import Settings


def validate(c: dict) -> None:
    needed=['site_id','domain','node_tailscale_ip','edge_tailscale_ip','run_user','run_group','app_root','environment_file','nginx_include_dir','edge_static_dir','acme_webroot','tls_fullchain','tls_private_key','operator_name','privacy_contact']
    missing=[x for x in needed if not isinstance(c.get(x),str) or not c[x].strip()]
    if missing: raise ValueError('Missing required inputs: '+', '.join(missing))
    if c.get('environment') not in ('production','staging'): raise ValueError('environment must be production or staging')
    for key in ['site_id','run_user','run_group']:
        if not re.fullmatch(r'[a-z_][a-z0-9_-]{1,40}',c[key]): raise ValueError('Invalid '+key)
    if c['run_user']=='root' or c['run_group']=='root': raise ValueError('Never run this service as root')
    if not re.fullmatch(r'(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?',c['domain']) or '.' not in c['domain'] or '..' in c['domain']:
        raise ValueError('Use a real, lowercase FQDN')
    if any(x in c['domain'] for x in ['example.com','example.org','replace','localhost']): raise ValueError('Placeholder domain is not deployable')
    for key in ['node_tailscale_ip','edge_tailscale_ip']:
        if ipaddress.ip_address(c[key]) not in ipaddress.ip_network('100.64.0.0/10'): raise ValueError('Use verified Tailscale IPv4 for '+key)
    if c['node_tailscale_ip']==c['edge_tailscale_ip']: raise ValueError('This template is for two different hosts')
    if not isinstance(c.get('app_port'),int) or not 1024<=c['app_port']<=65535: raise ValueError('Invalid app_port')
    for key in ['approved_uid','approved_gid']:
        if type(c.get(key)) is not int or c[key]<=0: raise ValueError('Must record approved non-root '+key)
    for key in ['app_root','environment_file','nginx_include_dir','edge_static_dir','acme_webroot','tls_fullchain','tls_private_key']:
        if not re.fullmatch(r'/[A-Za-z0-9_./-]+',c[key]) or '..' in Path(c[key]).parts: raise ValueError('Unsafe absolute path: '+key)
    if c['app_root'] in ('/data/lx','/data','/opt','/srv','/'): raise ValueError('Use a dedicated application subdirectory')
    if c.get('environment')=='staging' and c['app_root'].rstrip('/').endswith('/prod'): raise ValueError('Staging must not use the prod directory')
    for net in c.get('admin_allowlist',[]): ipaddress.ip_network(net,strict=False)
    if not c.get('admin_allowlist') and not c.get('allow_public_admin',False):
        raise ValueError('Set admin_allowlist or explicitly approve allow_public_admin=true with strong HTTPS authentication')
    for key,value in c.items():
        if isinstance(value,str) and any(ch in value for ch in ['\n','\r','\x00',"'"]): raise ValueError('Unsafe configuration value: '+key)


def render(config: Path, out: Path, new_install: bool, reuse_env: Path | None):
    c=json.loads(config.read_text('utf-8'));validate(c)
    if out.exists() and any(out.iterdir()): raise ValueError('Output directory is not empty; use a new private candidate directory')
    out.mkdir(parents=True,exist_ok=True,mode=0o700)
    if os.name=='posix':os.chmod(out,0o700)
    if new_install:
        admin_password=secrets.token_urlsafe(28)
        keys={'DATA_ENCRYPTION_KEY':Fernet.generate_key().decode(),'INDEX_HMAC_KEY':secrets.token_hex(32),'EDGE_TOKEN':secrets.token_urlsafe(48),'ADMIN_PASSWORD_HASH':password_hash(admin_password),'ENROLLMENT_CODE':secrets.token_urlsafe(8) if c.get('require_enrollment_code') else ''}
    else:
        prior=dotenv_values(reuse_env)
        keys={key:prior.get(key,'') for key in ['DATA_ENCRYPTION_KEY','INDEX_HMAC_KEY','EDGE_TOKEN','ADMIN_PASSWORD_HASH','ENROLLMENT_CODE']}
        if any(not keys[key] for key in ['DATA_ENCRYPTION_KEY','INDEX_HMAC_KEY','EDGE_TOKEN','ADMIN_PASSWORD_HASH']): raise ValueError('Existing env has missing secrets; stop rather than rotate data keys')
        admin_password=None
    env={
        'APP_ENV':c['environment'],'PUBLIC_URL':'https://'+c['domain'],
        'DATABASE_PATH':c['app_root']+'/data/campus.sqlite3','DATABASE_JOURNAL_MODE':'DELETE',**keys,
        'ADMIN_USERNAME':'admin','OPERATOR_NAME':c['operator_name'],'PRIVACY_CONTACT':c['privacy_contact'],
        'COHORT':str(c.get('cohort','2026')),'STUDENT_ID_PATTERN':c.get('student_id_pattern',r'^[0-9]{6,16}$'),
        'ROSTER_REQUIRED':str(c.get('roster_required',False)).lower(),'PHOTO_TASK_ENABLED':'false',
        'ENABLE_DEMO':'true' if c['environment']=='staging' else 'false',
        'RETENTION_DAYS':str(c.get('retention_days',90)),'DRAFT_RETENTION_DAYS':str(c.get('draft_retention_days',7)),
        'PRIVACY_VERSION':'2026-09-v1.2','ICP_NUMBER':c.get('icp_number',''),'POLICE_NUMBER':c.get('police_number',''),'POLICE_URL':c.get('police_url','')}
    Settings(environment=env['APP_ENV'],public_url=env['PUBLIC_URL'],db_path=Path(env['DATABASE_PATH']),encryption_key=keys['DATA_ENCRYPTION_KEY'],hmac_key=keys['INDEX_HMAC_KEY'],admin_password_hash=keys['ADMIN_PASSWORD_HASH'],edge_token=keys['EDGE_TOKEN'],operator_name=c['operator_name'],privacy_contact=c['privacy_contact'],retention_days=int(env['RETENTION_DAYS']),draft_days=int(env['DRAFT_RETENTION_DAYS']),demo_enabled=c['environment']=='staging')
    values={'SITE_ID':c['site_id'],'DOMAIN':c['domain'],'NODE_IP':c['node_tailscale_ip'],'EDGE_IP':c['edge_tailscale_ip'],'PORT':str(c['app_port']),'RUN_USER':c['run_user'],'RUN_GROUP':c['run_group'],'APP_ROOT':c['app_root'],'ENV_FILE':c['environment_file'],'NGINX_DIR':c['nginx_include_dir'],'EDGE_STATIC':c['edge_static_dir'],'ACME_ROOT':c['acme_webroot'],'TLS_FULLCHAIN':c['tls_fullchain'],'TLS_KEY':c['tls_private_key'],'ZONE':c['site_id'].replace('-','_'),'EDGE_TOKEN':keys['EDGE_TOKEN'],'ADMIN_ALLOW':'\n        '.join(['allow '+n+';' for n in c.get('admin_allowlist',[])]+(['deny all;'] if c.get('admin_allowlist') else ['# Public admin explicitly approved; application authentication remains mandatory.']))}
    def write(name,text):
        target=out/name
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(text)
    write('app.env',''.join(k+"='"+str(v)+"'\n" for k,v in env.items()))
    mapping={'app.service':c['site_id']+'.service','proxy.conf':c['site_id']+'.proxy.conf','nginx.conf':c['site_id']+'.nginx.conf','bootstrap-http.conf':c['site_id']+'.bootstrap.conf','backup.service':c['site_id']+'-backup.service','backup.timer':c['site_id']+'-backup.timer','tailnet-grant.json':c['site_id']+'.grant.json','logrotate.conf':c['site_id']+'.logrotate'}
    for template,name in mapping.items():
        text=(ROOT/'deploy/templates'/template).read_text('utf-8')
        for key,val in values.items():text=text.replace('@@'+key+'@@',val)
        if re.search(r'@@[A-Z_]+@@',text):raise ValueError('Unresolved template marker in '+template)
        write(name,text)
    write('maintenance.html',(ROOT/'deploy/maintenance.html').read_text('utf-8'))
    if admin_password:
        write('INITIAL_CREDENTIALS_PRIVATE.txt','Admin username: admin\nAdmin password: '+admin_password+'\nEnrollment code: '+(keys['ENROLLMENT_CODE'] or '(disabled)')+'\nStore in a password manager. Do not commit, paste into agent chat, or distribute this file.\n')
    write('deployment-summary.json',json.dumps({k:v for k,v in c.items()},ensure_ascii=False,indent=2)+'\n')
    print('Candidate files generated in '+str(out)+'. No server files were installed or changed.')
    print('Keep app.env, proxy.conf and INITIAL_CREDENTIALS_PRIVATE.txt private. Preserve data keys across upgrades.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    g=p.add_mutually_exclusive_group(required=True);g.add_argument('--new-install',action='store_true');g.add_argument('--reuse-env',type=Path)
    a=p.parse_args()
    try:render(a.config,a.output,a.new_install,a.reuse_env)
    except (ValueError,KeyError,OSError) as e:raise SystemExit('STOP: '+str(e))