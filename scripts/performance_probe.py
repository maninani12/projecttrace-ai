import json
import time
import statistics
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import httpx
from app.core.config import settings
from app.parsers.archive import read_archive
from app.parsers.source import chunk_file
from app.retrieval.engine import embedder

def summary(samples):
    values=sorted(x[1] for x in samples)
    return {'requests':len(samples),'status_counts':{str(status):sum(s==status for s,_ in samples) for status in set(s for s,_ in samples)},'median_ms':round(statistics.median(values),2),'p95_ms':round(values[min(len(values)-1,int(len(values)*.95))],2)}

with httpx.Client(base_url='http://127.0.0.1:8000',timeout=45) as client:
    session=client.post('/api/v1/auth/demo').json()
    client.headers['X-CSRF-Token']=session['csrf']
    project=client.post('/api/v1/projects',json={'name':'Validation probe'}).json()
    pid=project['id']
    start=time.perf_counter()
    client.post(f'/api/v1/projects/{pid}/demo').raise_for_status()
    for _ in range(120):
        detail=client.get(f'/api/v1/projects/{pid}').json()
        if detail['job']['state'] in {'COMPLETED','FAILED'}:break
        time.sleep(.5)
    report={'measured_at_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
        'environment':'Windows native, Python 3.11, SQLite, one local worker, offline provider, 7-file fixture',
        'analysis_wall_ms':round((time.perf_counter()-start)*1000,2), 'analysis_state':detail['job']['state']}
    def request(_):
        start=time.perf_counter();response=client.get(f'/api/v1/projects/{pid}/claims');return response.status_code,(time.perf_counter()-start)*1000
    with ThreadPoolExecutor(max_workers=8) as pool:
        report['normal_api_8_threads']=summary(list(pool.map(request,range(40))))
    ai=[]
    for i in range(12):
        start=time.perf_counter();response=client.post(f'/api/v1/projects/{pid}/ask',json={'question':f'Which database does this project use? check {i}'});ai.append((response.status_code,(time.perf_counter()-start)*1000))
    report['offline_ai_sequential']=summary(ai)
    start=time.perf_counter();parsed=list(read_archive(ROOT/'samples/mixed-demo.zip',settings()));report['parsing_ms']=round((time.perf_counter()-start)*1000,2)
    texts=[text for f in parsed for _,_,text in chunk_file(f.content)]
    start=time.perf_counter();embedder('hashing-v1').encode(texts);report['embedding_lexical_ms']=round((time.perf_counter()-start)*1000,2)
    project=client.post('/api/v1/projects',json={'name':'GitHub validation'}).json();github_id=project['id']
    response=client.post(f'/api/v1/projects/{github_id}/github',json={'url':'https://github.com/octocat/Hello-World'})
    if response.status_code==202:
        for _ in range(120):
            state=client.get(f'/api/v1/projects/{github_id}').json()
            if state['job']['state'] in {'COMPLETED','FAILED'}:break
            time.sleep(1)
        report['public_github_import']={'state':state['job']['state'],'error':state['job']['error_summary'],'snapshot':{k:state['snapshot'][k] for k in ['commit_sha','branch','source_type']} if state['snapshot'] else None}
    else:report['public_github_import']={'status':response.status_code}
    report['limits']='Small fixture observations only. No capacity claim. AI measurement is offline retrieval, not provider latency. Docker/PostgreSQL/Redis/semantic models were not exercised.'
    (ROOT/'docs/performance-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
