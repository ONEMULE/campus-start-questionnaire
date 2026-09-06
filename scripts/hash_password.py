#!/usr/bin/env python3
from pathlib import Path
import sys,getpass
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.security import password_hash
p=getpass.getpass('New admin password (at least 16 characters): ')
if p!=getpass.getpass('Repeat: '): raise SystemExit('Passwords differ')
print(password_hash(p))
