import copy
import pytest
from backend.engine import QUESTIONS,sequence,calculate,validate_answers,gate_snapshots,AnswerError
from .helpers import make_answers

@pytest.mark.parametrize('route,code',[('academic','A'),('research','R'),('creative','C'),('org','O'),('explore','E')])
def test_all_routes(route,code):
    a=make_answers(route)
    clean=validate_answers(a,complete=True)
    path=sequence(a)
    assert len(path)==32 and len(set(path))==32
    assert path[5]=='N05-'+code and path[14]=='N14-'+code and path[20]==code+'01'
    r=calculate(clean)
    assert all(0<=v<=100 for v in r['scores'].values())
    assert len(gate_snapshots(a))==8

def test_content_count(): assert len(QUESTIONS)==52

def test_mbti_does_not_change_scores():
    a=make_answers();r=calculate(a);a['N28']='INTJ';s=calculate(a)
    for k in ['scores','ending','roleFits','interests']: assert r[k]==s[k]

def test_sample_not_faked_scored():
    a=make_answers(sample='writing');r=calculate(a)
    assert r['sampleStatus']=='待人工评阅' and 'sample_score' not in r

def test_illegal_branch_and_gap():
    a=make_answers();a['R01']='A'
    with pytest.raises(AnswerError): validate_answers(a,complete=True)
    a=make_answers();del a['N02']
    with pytest.raises(AnswerError): validate_answers(a,complete=False)

def test_foreign_contact_is_erased():
    a=make_answers();a['N27']={'choice':'none','contact':'secret contact'}
    assert validate_answers(a,complete=True)['N27']['contact']==''

def test_alloc_not_six_observations():
    a=make_answers();r=calculate(a);a['N10']=list(QUESTIONS['N10']['costs']);s=calculate(a)
    assert r['scores']==s['scores'] and r['evidenceCounts']==s['evidenceCounts']
    assert s['flags']['OVERCOMMIT']>=1

def test_gate_no_future_leak():
    a=make_answers();g=gate_snapshots(a);a['N28']='ENFP';a['N24']=['research','org'];h=gate_snapshots(a)
    for key in list(g)[:-1]: assert g[key]==h[key]

def test_photo_disabled():
    a=make_answers();a['N19']={'task':'photos','selected':[0,1,2],'reasons':{'0':'a','1':'b','2':'c'}}
    with pytest.raises(AnswerError): validate_answers(a,complete=True)

def test_writing_limit_and_order_unique():
    a=make_answers();a['N19']={'task':'writing','text':'字'*81}
    with pytest.raises(AnswerError): validate_answers(a,complete=True)
    a['N19']={'task':'clips','order':[0,1,1,3]}
    with pytest.raises(AnswerError): validate_answers(a,complete=True)
