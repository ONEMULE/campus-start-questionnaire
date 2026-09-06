#!/usr/bin/env python3
"""Create development-only secrets. Never overwrites an existing environment."""
from pathlib import Path
import sys, secrets, argparse, os
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.security import password_hash
from cryptography.fernet import Fernet
p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8000);args=p.parse_args()
path=ROOT/'.env'
if path.exists():
    raise SystemExit('.env already exists; no secrets were changed.')
password=secrets.token_urlsafe(24)
values={'APP_ENV':'development','PUBLIC_URL':f'http://127.0.0.1:{args.port}','DATABASE_PATH':str(ROOT/'var/campus.sqlite3'),'DATA_ENCRYPTION_KEY':Fernet.generate_key().decode(),'INDEX_HMAC_KEY':secrets.token_hex(32),'EDGE_TOKEN':secrets.token_urlsafe(48),'ADMIN_USERNAME':'admin','ADMIN_PASSWORD_HASH':password_hash(password),'OPERATOR_NAME':'Local development only','PRIVACY_CONTACT':'Use fictitious records only','COHORT':'2026','ENABLE_DEMO':'true','PHOTO_TASK_ENABLED':'false','RETENTION_DAYS':'90','DRAFT_RETENTION_DAYS':'7','PRIVACY_VERSION':'2026-09-v1.2'}
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w',encoding='utf-8') as f:
    for k,v in values.items(): f.write(k+"='"+v+"'\n")
print('Development environment written. DO NOT use real student data.')
print('Admin username: admin')
print('Admin password (shown once): '+password)
print('Run: python -m uvicorn backend.main:create_app --factory --host 127.0.0.1 --port '+str(args.port)+' --no-access-log')
