import secrets
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.settings import Settings
from backend.security import password_hash

PASSWORD='unit-test-password-123456789'
@pytest.fixture
def config(tmp_path):
    return Settings(environment='development',public_url='http://testserver',db_path=tmp_path/'test.sqlite3',encryption_key=Fernet.generate_key().decode(),hmac_key=secrets.token_hex(32),admin_password_hash=password_hash(PASSWORD),demo_enabled=True)
@pytest.fixture
def app(config): return create_app(config)
@pytest.fixture
def client(app):
    with TestClient(app) as c: yield c

def register(client,sid='00001234',name='测试同学'):
    response=client.post('/api/sessions',json={'name':name,'student_id':sid,'consent_core':True,'privacy_version':'2026-09-v1.2'})
    assert response.status_code==201,response.text
    data=response.json()
    return data,{'Authorization':'Bearer '+data['access_token']}

def login(client):
    r=client.post('/api/admin/login',json={'username':'admin','password':PASSWORD})
    assert r.status_code==200,r.text
    return {'X-CSRF-Token':r.json()['csrf_token']}
