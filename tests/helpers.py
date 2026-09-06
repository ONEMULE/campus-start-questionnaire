from backend.engine import QUESTIONS,sequence

def make_answers(route='creative', sample='skip'):
    answers={}
    for _ in range(32):
        qid=sequence(answers)[len(answers)]
        q=QUESTIONS[qid]
        if q['type']=='multi':
            ids=[x['id'] for x in q['options']]
            a=([route]+[x for x in ids if x!=route])[:2] if route in ids else ids[:2]
        elif q['type']=='allocation': a=['study','lecture','sleep']
        elif q['type']=='contact': a={'choice':'none','contact':''}
        elif q['type']=='mbti': a=''
        elif q['type']=='worksample': a={'task':'writing','text':'行李箱停下的地方，新故事开始。'} if sample=='writing' else {'task':'skip'}
        elif qid=='N18': a=next(x['id'] for x in q['options'] if route in x['effects'].get('interests',{}))
        else: a=q['options'][0]['id']
        answers[qid]=a
    return answers
