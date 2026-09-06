"""Versioned story engine. Game strategy indicators, not validated psychometrics."""
from __future__ import annotations
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTENT = json.loads((ROOT / 'content/questions.v1.json').read_text('utf-8'))
QUESTIONS = CONTENT['QUESTIONS']
DIMS = CONTENT['DIMS']
INTERESTS = CONTENT['INTERESTS']
ROUTES = CONTENT['ROUTE_CODE']
RULE_VERSION = 'strategy-1.1.0'
CONTENT_VERSION = 'story-1.0.2'

class AnswerError(ValueError):
    pass

def rounded(value: float) -> int:
    return math.floor(max(0.0, min(100.0, value)) + 0.5)

def option(qid: str, answer: str) -> dict:
    for item in QUESTIONS[qid].get('options', []):
        if item['id'] == answer:
            return item
    raise AnswerError(f'{qid}: 无效选项')

def interests_raw(answers: dict, include_winter: bool = True, include_final: bool = False) -> dict:
    raw = {key: 0 for key in INTERESTS}
    ids = ['N00', 'N04'] + (['N18'] if include_winter else []) + (['N24'] if include_final else [])
    for qid in ids:
        answer = answers.get(qid)
        if answer is None:
            continue
        definition = QUESTIONS[qid]
        if definition['type'] == 'multi' and isinstance(answer, list):
            for i, choice in enumerate(answer):
                effect = option(qid, choice)['effects']
                if effect.get('interest') in raw:
                    weights = definition.get('interestWeights', [])
                    raw[effect['interest']] += weights[i] if i < len(weights) else 0
        elif definition['type'] == 'single' and isinstance(answer, str):
            for key, val in option(qid, answer)['effects'].get('interests', {}).items():
                raw[key] += val
    return raw

def top_route(raw: dict, answers: dict) -> str:
    # Ties favor the player's own latest ordered choice, never a forced creative route.
    order = []
    for qid in ['N04', 'N00']:
        for key in answers.get(qid, []):
            if key in ROUTES and key not in order:
                order.append(key)
    order += [key for key in ROUTES if key not in order]
    return max(order, key=lambda key: raw[key])

def sequence(answers: dict) -> list[str]:
    first = (answers.get('N04') or answers.get('N00') or ['creative'])[0]
    first = ROUTES.get(first, 'C')
    failure = ROUTES[top_route(interests_raw(answers, False), answers)]
    spring = ROUTES[top_route(interests_raw(answers, True), answers)]
    return ([f'N{i:02}' for i in range(5)] + [f'N05-{first}'] +
            [f'N{i:02}' for i in range(6, 14)] + [f'N14-{failure}'] +
            [f'N{i:02}' for i in range(15, 20)] + [f'{spring}{i:02}' for i in range(1, 4)] +
            [f'N{i:02}' for i in range(20, 29)])

def _text(value: Any, limit: int, required: bool = False) -> str:
    if not isinstance(value, str):
        raise AnswerError('文字字段格式不正确')
    result = value.strip()
    if len(result) > limit or (required and not result) or any(ord(c) < 32 and c not in '\n\t' for c in result):
        raise AnswerError(f'文字不能为空或超过 {limit} 字')
    return result

def validate_answers(answers: Any, *, complete: bool, allow_photo: bool = False) -> dict:
    if not isinstance(answers, dict) or len(answers) > 52:
        raise AnswerError('答案格式不正确')
    if set(answers) - set(QUESTIONS):
        raise AnswerError('包含未知题目')
    clean = {}
    # Validate route-defining inputs before determining the path.
    def validate_one(qid: str, value: Any) -> Any:
        d = QUESTIONS[qid]
        kind = d['type']
        if kind == 'single':
            if not isinstance(value, str): raise AnswerError(f'{qid}: 请选择一个选项')
            option(qid, value)
            return value
        if kind in ('multi', 'allocation'):
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value) or len(set(value)) != len(value):
                raise AnswerError(f'{qid}: 选项不可重复')
            if kind == 'multi' and (len(value) > d.get('limit', 2) or (d.get('exact') and len(value) != d['limit'])):
                raise AnswerError(f'{qid}: 请选择 {d["limit"]} 项')
            if kind == 'allocation' and not 1 <= len(value) <= len(d['options']):
                raise AnswerError(f'{qid}: 请选择行动')
            for x in value: option(qid, x)
            return value
        if kind == 'mbti':
            if value not in CONTENT['MBTIS'] + ['', 'skip']:
                raise AnswerError('无效 MBTI 选项')
            return '' if value == 'skip' else value
        if kind == 'contact':
            if not isinstance(value, dict) or set(value) - {'choice', 'contact'}:
                raise AnswerError('联系意向格式不正确')
            choice = value.get('choice')
            option(qid, choice)
            contact = _text(value.get('contact', ''), 100)
            # Store no contact if no invitation permission; no extra name copy in answers.
            return {'choice': choice, 'contact': '' if choice == 'none' else contact}
        if kind == 'worksample':
            if not isinstance(value, dict): raise AnswerError('作品任务格式不正确')
            task = value.get('task')
            if task == 'skip': return {'task': 'skip'}
            if task == 'writing': return {'task': task, 'text': _text(value.get('text', ''), 80, True)}
            if task == 'clips':
                order = value.get('order')
                if not isinstance(order, list) or len(order) != 4 or not all(type(x) is int and 0 <= x < 6 for x in order) or len(set(order)) != 4:
                    raise AnswerError('请选择并排序四段素材')
                return {'task': task, 'order': order, 'note': _text(value.get('note', ''), 120)}
            if task == 'photos' and allow_photo:
                selected = value.get('selected')
                if not isinstance(selected, list) or len(selected) != 3 or not all(type(x) is int and 0 <= x < 8 for x in selected) or len(set(selected)) != 3:
                    raise AnswerError('请选择三张照片')
                reasons = value.get('reasons', {})
                if not isinstance(reasons,dict):raise AnswerError('Invalid photo reasons')
                return {'task': task, 'selected': selected, 'reasons': {str(x): _text(reasons.get(str(x), ''), 80, True) for x in selected}}
            raise AnswerError('该作品任务尚未开放')
        raise AnswerError('未知题目类型')

    for qid in ('N00', 'N04', 'N18', 'N24'):
        if qid in answers: clean[qid] = validate_one(qid, answers[qid])
    path = sequence(clean)
    if set(answers) - set(path): raise AnswerError('答案包含不属于当前路线的题目；请返回变更处继续')
    seen_gap = False
    for qid in path:
        if qid not in answers:
            seen_gap = True
            if complete: raise AnswerError(f'尚未完成 {qid}')
        else:
            if seen_gap: raise AnswerError('进度必须从开头连续作答')
            clean[qid] = validate_one(qid, answers[qid])
    return {qid: clean[qid] for qid in path if qid in clean}

ROLE_WEIGHTS = {
    '摄影摄像': {'AI': .20, 'AD': .20, 'CE': .15, 'CO': .10, 'PQ': .10, 'RR': .10},
    '编导策划': {'CE': .25, 'CO': .20, 'PQ': .15, 'FA': .10, 'AI': .10, 'CW': .05},
    '剪辑后期': {'PQ': .25, 'PE': .20, 'RA': .15, 'CE': .10, 'RR': .10, 'TR': .05},
    '统筹制片': {'OC': .25, 'TR': .20, 'CW': .15, 'RA': .15, 'SS': .10},
    '运营联络': {'SS': .25, 'CW': .20, 'FA': .15, 'AI': .15, 'TR': .10},
}
ENDING_COPIES = {
    '光影造浪者':'普通的活动到了你手里，总会慢慢长出一个故事。',
    '故事建筑师':'别人在想拍什么，你先想：为什么要这样拍？',
    '幕后工匠':'你不一定最显眼，但很多成品都经过了你的手。',
    '现场捕手':'事情发生的时候，你通常已经在现场了。',
    '潮汐调度员':'十个人开始乱的时候，你已经把时间表建好了。',
    '岸线连接者':'你让原本不认识的人，开始一起把事情做好。',
    '深海钻探者':'别人看到的是任务，你先看到的是问题。',
    'DDL 驯兽师':'Deadline 不会消失，但你找到了和它相处的方法。',
    '慢热观测员':'你不急着抢话，但往往先看见关键细节。',
    '全栈潜水员':'很多位置你都愿意试，也能把不同的人和事接起来。',
    '野生探索者':'没有现成攻略，所以你决定自己开地图。',
    '起潮新芽':'不急着给自己定型。地图已经亮起来，下一站由你选。'
}

def calculate(answers: dict) -> dict:
    evidence = {d: 0.0 for d in DIMS}
    maximum = {d: 0.0 for d in DIMS}
    events = {d: [] for d in DIMS}
    flags: dict[str, int] = {}
    positions: dict[str, int] = {}
    meta = {}
    sample = None
    def merge(target: dict, incoming: dict):
        for key, value in incoming.items(): target[key] = target.get(key, 0) + value
    for qid in sequence(answers):
        if qid not in answers: continue
        d, a = QUESTIONS[qid], answers[qid]
        if d['type'] == 'single':
            effect = option(qid, a)['effects']
            possible = {}
            for opt in d['options']:
                for dim, val in opt['effects'].get('dims', {}).items(): possible[dim] = max(possible.get(dim, 0), val)
            for dim, val in possible.items():
                actual = effect.get('dims', {}).get(dim, 0)
                maximum[dim] += val; evidence[dim] += actual
                events[dim].append(actual / val if val else 0)
            existed = flags.get('OVERCOMMIT', 0)
            merge(flags, {k:v for k,v in effect.get('flags', {}).items() if k != 'OVERCOMMIT_IF_EXISTING'})
            if existed and effect.get('flags', {}).get('OVERCOMMIT_IF_EXISTING'): flags['OVERCOMMIT'] = flags.get('OVERCOMMIT', 0) + 1
            merge(positions, effect.get('positions', {})); meta.update(effect.get('meta', {}))
        elif d['type'] == 'allocation':
            # A time-budget choice is preference/context, NOT six independent trait tests.
            cost = sum(d['costs'][x] for x in a)
            meta['actionCost'] = cost
            if cost > 10: flags['OVERCOMMIT'] = flags.get('OVERCOMMIT', 0) + 1
        elif d['type'] == 'multi' and qid == 'N17': meta['growthGoals'] = a
        elif d['type'] == 'worksample': sample = None if a['task'] == 'skip' else a
        elif d['type'] == 'contact': meta['consent'] = option(qid, a['choice'])['effects']['meta']['consent']
        elif d['type'] == 'mbti': meta['mbti'] = a
    scores, counts, coverage = {}, {}, {}
    for dim in DIMS:
        n = len(events[dim]); counts[dim] = n
        ratio = evidence[dim] / maximum[dim] if maximum[dim] else .5
        scores[dim] = rounded(50 + (100 * ratio - 50) * n / (n + 2))
        coverage[dim] = '未观察' if n == 0 else '较少' if n < 3 else '已多次呈现'
    raw = interests_raw(answers, True, True)
    interests = {key: rounded(value / 8 * 100) for key, value in raw.items()}
    s, i = scores, interests
    reliability = .40*s['TR']+.35*s['PE']+.25*s['RA']
    recovery = .40*s['RR']+.30*s['LA']+.30*s['FA']
    def avg(*values): return sum(values)/len(values)
    candidates = [
        ('光影造浪者',i['creative']>=60 and s['CE']>=72 and s['PE']>=60,avg(s['CE'],s['PE'],i['creative'])),
        ('故事建筑师',s['CE']>=70 and s['CO']>=68 and s['PQ']>=58,avg(s['CE'],s['CO'],s['PQ'])),
        ('幕后工匠',s['PQ']>=74 and s['PE']>=70 and s['RA']>=60,avg(s['PQ'],s['PE'],s['RA'])),
        ('现场捕手',s['AI']>=68 and s['AD']>=68 and s['CE']>=58,avg(s['AI'],s['AD'],s['CE'])),
        ('潮汐调度员',s['OC']>=72 and s['TR']>=68 and s['CW']>=62,avg(s['OC'],s['TR'],s['CW'])),
        ('岸线连接者',s['SS']>=74 and s['CW']>=68 and s['FA']>=58,avg(s['SS'],s['CW'],s['FA'])),
        ('深海钻探者',s['CO']>=72 and s['LA']>=70 and s['RR']>=58 and i['research']>=60,avg(s['CO'],s['LA'],s['RR'],i['research'])),
        ('DDL 驯兽师',s['TR']>=78 and s['PE']>=72 and s['RA']>=65,avg(s['TR'],s['PE'],s['RA'])),
        ('慢热观测员',s['SS']<=48 and s['PQ']>=65 and s['LA']>=62 and reliability>=60,avg(100-s['SS'],s['PQ'],s['LA'])),
        ('全栈潜水员',sum(60<=v<=74 for v in s.values())>=8 and min(s.values())>=45,avg(*s.values())),
        ('野生探索者',s['UT']>=72 and s['CO']>=70 and s['AI']>=55 and i['explore']>=60,avg(s['UT'],s['CO'],s['AI'],i['explore']))
    ]
    eligible = sorted([x for x in candidates if x[1]], key=lambda x:x[2], reverse=True)
    ending = eligible[0][0] if eligible else '起潮新芽'
    secondary = eligible[1][0] if len(eligible)>1 else ''
# Legacy absolute thresholds almost always produced the same fallback for
    # forced-choice items. Below is explicitly an entertainment story matcher,
    # not a recalibration of ability or a population norm.
    ending_basis = '旧剧情组合条件命中（非能力门槛）' if eligible else '兴趣路线与本局相对选择匹配（娱乐叙事）'
    if not eligible:
        center = avg(*s.values())
        relative = {d: (v-center)/20 for d,v in s.items()}
        profiles = [
          ('光影造浪者', {'CE':.35,'PE':.30,'AD':.20,'PQ':.15}, 'creative'),
          ('故事建筑师', {'CE':.35,'CO':.30,'PQ':.20,'FA':.15}, 'creative'),
          ('幕后工匠', {'PQ':.40,'PE':.30,'RA':.20,'TR':.10}, 'creative'),
          ('现场捕手', {'AI':.35,'AD':.35,'CE':.20,'CO':.10}, 'creative'),
          ('潮汐调度员', {'OC':.40,'TR':.25,'CW':.25,'RA':.10}, 'org'),
          ('岸线连接者', {'SS':.45,'CW':.35,'FA':.20}, 'org'),
          ('深海钻探者', {'CO':.35,'LA':.35,'RR':.20,'PQ':.10}, 'research'),
          ('DDL 驯兽师', {'TR':.40,'PE':.35,'RA':.25}, 'academic'),
          ('慢热观测员', {'PQ':.35,'LA':.30,'SS':-.35}, 'creative'),
          ('野生探索者', {'UT':.40,'CO':.40,'AI':.20}, 'explore')]
        narrative = [(name, sum(relative[d]*w for d,w in weights.items())+1.25*i[theme]/100)
                     for name,weights,theme in profiles]
        ranked_interests = sorted(i.values(), reverse=True)
        spread = math.sqrt(avg(*[(v-center)**2 for v in s.values()]))
        if ranked_interests[0]-ranked_interests[1] <= 15 and sum(v>=25 for v in i.values())>=3 and spread<=18:
            narrative.append(('全栈潜水员',1.35+(18-spread)/18))
        narrative.sort(key=lambda x:x[1],reverse=True)
        undecided = (ranked_interests[0]<60 and spread<15) or (len(narrative)>1 and narrative[0][1]-narrative[1][1]<.06)
        ending = '起潮新芽' if undecided else narrative[0][0]
        secondary = narrative[0][0] if undecided else narrative[1][0]
    behavior = {name: sum(s[d]*weight for d,weight in weights.items())/sum(weights.values()) for name,weights in ROLE_WEIGHTS.items()}
    fits = {name: rounded((.65*val+.20*i['creative'])/.85) for name,val in behavior.items()}
    badges = []
    for name, condition in [('我来吧',flags.get('VOLUNTEER',0)>=2),('先做个 Demo',flags.get('DEMO_FIRST',0)>=2),('Plan B 还有 Plan C',s['AD']>=75),('细节扫描仪',s['PQ']>=80),('DDL 战神',s['TR']>=80),('群聊发动机',s['SS']>=80),('冷静拆任务',s['OC']>=75),('什么都想学',s['CO']>=80),('慢热但靠谱',s['SS']<50 and reliability>=70)]:
        if condition: badges.append(name)
    if not badges: badges=['校园随机事件收集者']
    if flags.get('OVERCOMMIT',0)>=2: badges.append('时间管理谈判家')
    team = {'统筹型':.4*s['OC']+.3*s['CW']+.3*s['AI'], '创作者':.45*s['CE']+.3*s['CO']+.25*s['PQ'], '稳定执行':.4*s['PE']+.3*s['RA']+.3*s['PQ'], '连接者':.4*s['SS']+.35*s['CW']+.25*s['FA'], '灵活补位':.4*s['AD']+.3*s['FA']+.3*s['CW']}
    return {'rule_version':RULE_VERSION,'content_version':CONTENT_VERSION,'scores':s,'evidenceCounts':counts,'coverage':coverage,'interests':i,'rawInterests':raw,'flags':flags,'positions':positions,'reliability':rounded(reliability),'recovery':rounded(recovery),'teamRoles':{k:rounded(v) for k,v in team.items()},'ending':ending,'endingBasis':ending_basis,'strictCandidates':[x[0] for x in eligible],'endingCopy':ENDING_COPIES[ending],'secondary':secondary,'behaviorFits':{k:round(v,4) for k,v in behavior.items()},'roleFits':fits,'badges':badges,'availability':meta.get('availability','未填写'),'consent':meta.get('consent','NO_CONTACT'),'mbti':meta.get('mbti',''),'workSample':sample,'sampleStatus':'待人工评阅' if sample else '未提交','route':sequence(answers),'completedCount':len(answers),'disclaimer':'本局数值仅表示预设情境中的选择分布，不是人格百分位、心理诊断或录取结论。'}

def gate_snapshots(answers: dict) -> dict:
    """Only use answers already encountered at each gate; never use future evidence."""
    path = sequence(answers)
    result = {}
    checkpoints = [('G1','N03'),('G2','N05-'),('G3','N09'),('G4','N13'),('G5','N16'),('G6','N19'),('G7','N23'),('G8','N28')]
    for gate, marker in checkpoints:
        end = next((k for k in path if k == marker or (marker.endswith('-') and k.startswith(marker))), None)
        if end not in answers: continue
        prefix = {k:answers[k] for k in path[:path.index(end)+1] if k in answers}
        r = calculate(prefix)
        result[gate] = {'after':end,'scores':r['scores'],'counts':r['evidenceCounts'],'flags':r['flags'],'reliability':r['reliability'],'recovery':r['recovery'],'route_hint':sequence(prefix)[20]}
    return result
