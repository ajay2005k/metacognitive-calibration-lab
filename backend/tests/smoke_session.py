"""Explicit full-session verification against running Flask; deletes its test data."""
import json
import math
import sys
import urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.items import load_items

BASE='http://127.0.0.1:5000/api'

def request(path, data=None, method=None):
    req=urllib.request.Request(BASE+path,data=json.dumps(data).encode() if data is not None else None,
        headers={'Content-Type':'application/json'},method=method)
    with urllib.request.urlopen(req,timeout=10) as response:return json.load(response)


def run():
    bank={i['id']:i for i in load_items()}
    # This is explicit synthetic verification, never a real participant observation.
    s=request('/sessions',{'n_trials':36,'group':'SCRIPTED-VERIFICATION','condition':{'feedback':'immediate'}})
    sid=s['session_id']
    try:
        for index in range(36):
            next_item=request(f'/sessions/{sid}/next')
            item=bank[next_item['item']['id']]
            correct=index%2==0
            answer=item['answer'] if correct else (item['answer']+1)%4
            # 18 correct at confidence 80; 18 errors at 60.
            result=request(f'/sessions/{sid}/trials',{'item_id':item['id'],'answer':answer,
                'confidence':80 if correct else 60,'latency_ms':1000 if correct else 3000,'timed_out':False})
            assert result['correct']==correct
        assert request(f'/sessions/{sid}/next')['done']
        metrics=request(f'/sessions/{sid}/complete',{})['metrics']
        for key,value in {'n':36,'accuracy':.5,'mean_confidence':70,'overconfidence':20,'calibration_error':40,'point_biserial_r':1}.items():
            assert math.isclose(metrics[key],value,abs_tol=1e-10),(key,metrics[key],value)
        assert metrics['latency']['overall']==2000
        assert metrics['latency']['correct']==1000 and metrics['latency']['incorrect']==3000
        assert metrics['change_after_feedback']==0
        assert len(request('/export?format=json&group=SCRIPTED-VERIFICATION'))>=36
        print('PASS: full 36-trial HTTP session; analytical accuracy, confidence, bias, calibration error, r, latency, and feedback change match.')
    finally:
        request(f'/sessions/{sid}',method='DELETE')
        # No participant-deletion endpoint is exposed; remove this verification-only orphan locally.
        from backend.db import connect
        db=connect()
        if not db.sessions.find_one({'participant_id':s['participant_id']}):
            db.participants.delete_one({'participant_id':s['participant_id']})

if __name__=='__main__':run()
