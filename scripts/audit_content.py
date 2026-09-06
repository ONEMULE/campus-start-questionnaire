#!/usr/bin/env python3
"""Generate human-readable questions and deterministic branch-coverage evidence."""
import csv,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.engine import CONTENT,QUESTIONS,DIMS,INTERESTS,calculate,sequence
from tests.helpers import make_answers
ROOT=Path(__file__).resolve().parents[1]

def main():
 reports=ROOT/'reports';reports.mkdir(exist_ok=True)
 paths={};rows=[]
 for route in INTERESTS:
  a=make_answers(route);r=calculate(a)
  paths[route]={'nodes':sequence(a),'count':len(a),'indicator_opportunities':r['evidenceCounts']}
  rows.append({'route':route,**r['evidenceCounts']})
 report={'expanded_nodes':len(QUESTIONS),'story_nodes_per_path':32,'registration_outside_story':True,'optional_story_slots':['N19','N28'],'coverage_meaning':'Related scenario opportunities in five same-interest paths; NOT reliability, validity, or all possible mixed-interest paths','paths':paths,'open_issues':['Self-reported hypothetical preferences are not demonstrated skill','Many choices mix multiple constructs','Alternative routes have unequal observation opportunities','No local cohort norms or validated hiring thresholds']}
 (reports/'content-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 with (reports/'indicator-coverage.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['route',*DIMS]);w.writeheader();w.writerows(rows)
 lines=['# 题库全文与选项配置','',f'展开节点：{len(QUESTIONS)}。此文件由JSON生成，仅供校对；编辑应回到content/questions.v1.json。','', '剧情节点之外另有姓名、学号与同意登记，不在本表编号。','']
 for k,q in QUESTIONS.items():
  lines += ['## '+k+' · '+q.get('title',''),'','阶段：'+q.get('chapter','')+'；类型：`'+q['type']+'`','',q.get('scene',''),'', '**'+q.get('prompt','')+'**','']
  for o in q.get('options',[]):
   lines += ['### '+o['id']+' / '+o.get('text',''),'',o.get('sub',''),'','配置：`'+json.dumps(o.get('effects',{}),ensure_ascii=False,separators=(',',':'))+'`','']
  extra={k:v for k,v in q.items() if k not in ('id','chapter','title','scene','prompt','options','type')}
  if extra:lines += ['补充配置：','```json',json.dumps(extra,ensure_ascii=False,indent=2),'```','']
 (ROOT/'docs/QUESTION_BANK.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print(json.dumps({'nodes':len(QUESTIONS),'paths':{k:v['count'] for k,v in paths.items()}},ensure_ascii=False))
if __name__=='__main__':main()