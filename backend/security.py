from __future__ import annotations
import base64
import hashlib
import hmac
import secrets

def password_hash(password: str) -> str:
    if len(password) < 16: raise ValueError('管理员口令至少16字符')
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)
    return 'scrypt$16384$8$1$'+base64.urlsafe_b64encode(salt).decode()+'$'+base64.urlsafe_b64encode(digest).decode()

def password_verify(password: str, encoded: str) -> bool:
    try:
        kind,n,r,p,salt,digest = encoded.split('$')
        if kind != 'scrypt' or (int(n),int(r),int(p)) != (16384,8,1): return False
        computed = hashlib.scrypt(password.encode(),salt=base64.urlsafe_b64decode(salt),n=int(n),r=int(r),p=int(p),dklen=32)
        return hmac.compare_digest(computed,base64.urlsafe_b64decode(digest))
    except (ValueError,TypeError): return False

def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def keyed_hash(key: str, namespace: str, value: str) -> str:
    return hmac.new(key.encode(),(namespace+':'+value).encode(),hashlib.sha256).hexdigest()

def csv_safe(value: object, *, force_text: bool=False) -> str:
    text = str(value if value is not None else '')
    if force_text or text.lstrip().startswith(('=','+','-','@','\t','\r','\n')):
        return "'"+text
    return text
