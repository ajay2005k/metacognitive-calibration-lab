import csv
import io
import pytest
from backend.metrics import session_report
from backend.seed_demo import seed, clear_demo

def create(client, **options):
    data = {'condition':dict(difficulty='hard',categories='logic',feedback='immediate',time_limit='20',interface='slider')}
    data.update(options)
    response = client.post('/api/sessions',json=data)
    assert response.status_code == 201, response.json
    return response.json['session_id']

def answer(client,app,sid,timeout=False,confidence=80):
    nxt=client.get(f'/api/sessions/{sid}/next').json
    item=nxt['item']
    index=app.extensions['items'][item['id']]['answer']
    return client.post(f'/api/sessions/{sid}/trials',json=dict(item_id=item['id'],answer=None if timeout else index,
        confidence=None if timeout else confidence,latency_ms=None if timeout else 1234,timed_out=timeout))

def test_create_and_next_order_no_answer(client,app):
    sid=create(client)
    s=client.get(f'/api/sessions/{sid}').json
    assert s['participant_id'].startswith('P-') and len(s['participant_id'])==7
    assert s['n_trials']==2 and s['is_synthetic'] is False
    nxt=client.get(f'/api/sessions/{sid}/next').json
    assert nxt['item']['id']==s['item_order'][0]
    assert 'answer' not in nxt['item']
    assert answer(client,app,sid).json['correct'] is True
    assert client.get(f'/api/sessions/{sid}/next').json['item']['id']==s['item_order'][1]

def test_reject_bad_trials_duplicates_unknown_order(client,app):
    sid=create(client)
    session=client.get(f'/api/sessions/{sid}').json
    payload=dict(item_id=session['item_order'][0],answer=0,confidence=80,latency_ms=1000)
    for patch in ({'confidence':-1},{'confidence':101},{'confidence':True},{'answer':4},{'answer':True},{'latency_ms':-1},{'item_id':'unknown'},{'item_id':session['item_order'][1]}):
        assert client.post(f'/api/sessions/{sid}/trials',json=payload|patch).status_code==400
    assert client.post(f'/api/sessions/{sid}/trials',json=payload).status_code==201
    assert client.post(f'/api/sessions/{sid}/trials',json=payload).status_code==400

def test_completion_timeouts_exports_and_delete(client,app):
    sid=create(client,group='Group A',age_range='21-23',academic_year=2)
    assert client.post(f'/api/sessions/{sid}/complete').status_code==400
    assert answer(client,app,sid,timeout=True).status_code==201
    assert answer(client,app,sid).status_code==201
    assert client.get(f'/api/sessions/{sid}/next').json=={'done':True}
    response=client.post(f'/api/sessions/{sid}/complete')
    assert response.status_code==200
    m=response.json['metrics']
    assert m['n']==1 and m['timed_out_count']==1
    assert m['accuracy']==1 and m['mean_confidence']==80 and m['overconfidence']==-20
    assert m['latency']['overall']==1234 and m['point_biserial_r'] is None
    assert client.post(f'/api/sessions/{sid}/complete').status_code==400
    assert client.get(f'/api/reports/{sid}').json['session']['status']=='complete'
    exported=client.get('/api/export?format=json').json
    assert len(exported)==2
    assert exported[0]['answer'] is None and exported[0]['confidence'] is None
    assert exported[0]['age_range']=='21-23'
    assert len(list(csv.DictReader(io.StringIO(client.get('/api/export?format=csv').text))))==2
    assert client.get('/api/export?format=xml').status_code==400
    assert client.delete(f'/api/sessions/{sid}').status_code==200
    db=app.extensions['db']
    assert db.trials.count_documents({})==db.reports.count_documents({})==db.sessions.count_documents({})==0
    assert db.participants.count_documents({})==1
    assert client.get(f'/api/sessions/{sid}').status_code==404

@pytest.mark.parametrize('data',[{'n_trials':19},{'condition':{'difficulty':'medium'}},{'condition':{'feedback':'bad'}},{'condition':[]},{'age_range':'12'},{'academic_year':True},{'participant_id':'John'},{'group':123}])
def test_invalid_session(client,data):
    assert client.post('/api/sessions',json=data).status_code==400

def test_default_and_18_trial_cells(client,app):
    sid=create(client,condition={},n_trials=18)
    s=client.get(f'/api/sessions/{sid}').json
    bank=app.extensions['items']
    assert len(s['item_order'])==18
    assert len({(bank[i]['category'],bank[i]['difficulty']) for i in s['item_order']})==18

def test_filters_and_dashboard(client,app):
    sid=create(client,group='A')
    answer(client,app,sid);answer(client,app,sid)
    client.post(f'/api/sessions/{sid}/complete')
    assert len(client.get('/api/sessions?group=A&feedback=immediate&is_synthetic=false').json)==1
    assert client.get('/api/sessions?group=B').json==[]
    d=client.get('/api/dashboard?group=A').json
    assert d['n_complete']==1 and d['by_feedback'][0]['accuracy']==1
    assert d['by_group'][0]['label']=='A'
    assert sum(b['n'] for b in d['calibration_curves']['immediate'])==2
    assert d['latency_by_difficulty']['hard']==1234
    assert d['latency_by_difficulty']['easy'] is None

def test_all_timeout_report(client,app):
    sid=create(client)
    answer(client,app,sid,timeout=True);answer(client,app,sid,timeout=True)
    m=client.post(f'/api/sessions/{sid}/complete').json['metrics']
    assert m['n']==0 and m['timed_out_count']==2 and m['accuracy'] is None

def test_seed_is_explicit_deterministic_and_clears_only_demo(app,client):
    real_sid=create(client)
    db=app.extensions['db']
    assert seed(db,app.extensions['items'])==24
    assert db.sessions.count_documents({'is_synthetic':True})==24
    assert db.trials.count_documents({})==24*36
    demo=client.get('/api/sessions?is_synthetic=true').json
    assert all(s['participant_id'].startswith('DEMO-') for s in demo)
    before=list(db.trials.find({'session_id':'demo-session-001'},{'_id':0}))
    with pytest.raises(ValueError):seed(db,app.extensions['items'])
    clear_demo(db)
    assert db.sessions.count_documents({})==1
    assert db.sessions.find_one({'session_id':real_sid})
    seed(db,app.extensions['items'])
    assert list(db.trials.find({'session_id':'demo-session-001'},{'_id':0}))==before

def test_json_errors_and_cors(client):
    response=client.post('/api/sessions',data='invalid',content_type='application/json')
    assert response.status_code==400 and response.json['message']
    assert client.get('/api/sessions/not-found').status_code==404
    response=client.get('/api/sessions',headers={'Origin':'http://localhost:5173'})
    assert response.headers['Access-Control-Allow-Origin']=='http://localhost:5173'
