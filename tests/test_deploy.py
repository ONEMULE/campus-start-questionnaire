import json
from pathlib import Path
import pytest
from scripts.render_deploy import validate,render
ROOT=Path(__file__).resolve().parents[1]


def deployment():
    c=json.loads((ROOT/'config/deployment.example.json').read_text())
    c.update(domain='freshman.test.invalid',node_tailscale_ip='100.100.10.2',edge_tailscale_ip='100.100.10.3',run_user='campus_test',run_group='campus_test',approved_uid=3100,approved_gid=3100,tls_fullchain='/tmp/qa/fullchain.pem',tls_private_key='/tmp/qa/privkey.pem',operator_name='QA activity',privacy_contact='privacy@qa.invalid',allow_public_admin=True)
    return c


def test_missing_config_fails_closed():
    with pytest.raises(ValueError):validate(json.loads((ROOT/'config/deployment.example.json').read_text()))


def test_root_or_global_path_rejected():
    c=deployment();c['run_user']='root'
    with pytest.raises(ValueError):validate(c)
    c=deployment();c['app_root']='/data/lx'
    with pytest.raises(ValueError):validate(c)


def test_render_and_reuse_keys(tmp_path):
    c=deployment();inp=tmp_path/'deployment.json';inp.write_text(json.dumps(c))
    out=tmp_path/'first';render(inp,out,True,None)
    assert (out/'app.env').exists() and '@@' not in (out/'campus-start-prod.nginx.conf').read_text()
    second=tmp_path/'second';render(inp,second,False,out/'app.env')
    from dotenv import dotenv_values
    a,b=dotenv_values(out/'app.env'),dotenv_values(second/'app.env')
    for key in ['DATA_ENCRYPTION_KEY','INDEX_HMAC_KEY','EDGE_TOKEN']:assert a[key]==b[key]
    assert not (second/'INITIAL_CREDENTIALS_PRIVATE.txt').exists()


def test_admin_requires_explicit_policy():
    c=deployment();c['allow_public_admin']=False
    with pytest.raises(ValueError):validate(c)