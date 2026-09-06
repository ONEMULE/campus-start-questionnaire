from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
from cryptography.fernet import Fernet
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

def truth(value: str) -> bool:
    return value.lower() in ('1', 'true', 'yes')

@dataclass
class Settings:
    environment: str
    public_url: str
    db_path: Path
    encryption_key: str
    hmac_key: str
    admin_password_hash: str
    edge_token: str = ''
    journal_mode: str = 'DELETE'
    operator_name: str = '本地开发测试'
    privacy_contact: str = '仅使用虚构测试数据'
    cohort: str = '2026'
    admin_username: str = 'admin'
    student_id_pattern: str = r'^[0-9]{6,16}$'
    enrollment_code: str = ''
    roster_required: bool = False
    photo_enabled: bool = False
    demo_enabled: bool = False
    retention_days: int = 90
    draft_days: int = 7
    privacy_version: str = '2026-09-v1.2'
    icp_number: str = ''
    police_number: str = ''
    police_url: str = ''
    secure_cookies: bool = field(init=False)

    def __post_init__(self):
        self.public_url = self.public_url.rstrip('/')
        parsed = urlsplit(self.public_url)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.path not in ('','/') or parsed.query or parsed.fragment:
            raise ValueError('PUBLIC_URL 必须为不带路径的完整站点源地址')
        self.secure_cookies = parsed.scheme == 'https'
        Fernet(self.encryption_key.encode())
        if len(self.hmac_key) < 32 or not self.admin_password_hash.startswith('scrypt$'):
            raise ValueError('必须提供独立 HMAC 密钥与 scrypt 管理员口令哈希')
        if self.journal_mode not in ('DELETE','WAL'):
            raise ValueError('DATABASE_JOURNAL_MODE must be DELETE or WAL')
        re.compile(self.student_id_pattern)
        if not 1 <= self.retention_days <= 365 or not 1 <= self.draft_days <= 30:
            raise ValueError('保存期限超出允许范围')
        if self.environment in ('production', 'staging'):
            if parsed.scheme != 'https' or len(self.edge_token) < 32:
                raise ValueError('生产环境要求 HTTPS PUBLIC_URL 和至少32字符 EDGE_TOKEN')
            if not self.operator_name.strip() or not self.privacy_contact.strip() or any(x in (self.operator_name+self.privacy_contact) for x in ['待填写','本地开发','REPLACE','CHANGE_ME']):
                raise ValueError('生产环境必须填写实际数据负责人和隐私联系渠道')
            if self.environment == 'production' and self.demo_enabled:
                raise ValueError('生产环境默认不开放匿名预览，请在独立 staging 环境体验')
        if self.photo_enabled:
            assets = ROOT / 'web/assets/photos'
            if not all((assets / f'{i}.jpg').is_file() for i in range(8)):
                raise ValueError('启用照片任务前必须提供获授权的 0.jpg 至 7.jpg')

    @classmethod
    def from_env(cls):
        load_dotenv(os.environ.get('APP_ENV_FILE', str(ROOT / '.env')), override=False)
        e = os.environ
        return cls(environment=e.get('APP_ENV','development'), public_url=e.get('PUBLIC_URL','http://127.0.0.1:8000'), db_path=Path(e.get('DATABASE_PATH',str(ROOT/'var/campus.sqlite3'))), encryption_key=e['DATA_ENCRYPTION_KEY'], hmac_key=e['INDEX_HMAC_KEY'], admin_password_hash=e['ADMIN_PASSWORD_HASH'], edge_token=e.get('EDGE_TOKEN',''), journal_mode=e.get('DATABASE_JOURNAL_MODE','DELETE').upper(), operator_name=e.get('OPERATOR_NAME','本地开发测试'), privacy_contact=e.get('PRIVACY_CONTACT','仅使用虚构测试数据'), cohort=e.get('COHORT','2026'), admin_username=e.get('ADMIN_USERNAME','admin'), student_id_pattern=e.get('STUDENT_ID_PATTERN',r'^[0-9]{6,16}$'), enrollment_code=e.get('ENROLLMENT_CODE',''), roster_required=truth(e.get('ROSTER_REQUIRED','false')), photo_enabled=truth(e.get('PHOTO_TASK_ENABLED','false')), demo_enabled=truth(e.get('ENABLE_DEMO','false')), retention_days=int(e.get('RETENTION_DAYS','90')), draft_days=int(e.get('DRAFT_RETENTION_DAYS','7')), privacy_version=e.get('PRIVACY_VERSION','2026-09-v1.2'), icp_number=e.get('ICP_NUMBER',''), police_number=e.get('POLICE_NUMBER',''), police_url=e.get('POLICE_URL',''))