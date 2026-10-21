"""Original analytical checks; the unavailable reference suite is not reproduced."""
import pytest
from backend.metrics import session_report, calibration_curve

def trial(no, confidence, correct, latency=1000, **extra):
    return dict(trial_no=no, confidence=confidence, correct=correct, latency_ms=latency,
                category='logic', difficulty='easy', feedback=True, **extra)

def test_hand_computed_metrics():
    report = session_report([trial(1,100,True,1000),trial(2,80,False,2000),trial(3,60,True,3000),trial(4,20,False,4000)])
    assert report['n'] == 4
    assert report['accuracy'] == .5
    assert report['mean_confidence'] == 65
    assert report['overconfidence'] == 15
    assert report['underconfidence'] == -15
    assert report['calibration_error'] == 35
    assert report['point_biserial_r'] == pytest.approx(30 / (3500**.5))
    assert report['latency']['overall'] == 2500
    assert report['latency']['correct'] == 2000
    assert report['latency']['incorrect'] == 3000
    assert report['change_after_feedback'] == -50

def test_empty_and_constant_values_are_null():
    empty = session_report([])
    for field in ('accuracy','mean_confidence','overconfidence','calibration_error','point_biserial_r','change_after_feedback'):
        assert empty[field] is None
    assert empty['n'] == 0
    assert session_report([trial(1,50,True),trial(2,50,False)])['point_biserial_r'] is None
    assert session_report([trial(1,10,True),trial(2,90,True)])['point_biserial_r'] is None

def test_bins_edges_and_timeouts():
    rows = [trial(1,0,False),trial(2,10,True),trial(3,99,True),trial(4,100,True)]
    curve = calibration_curve(rows)
    assert [(b['low'],b['n']) for b in curve] == [(0,1),(10,1),(90,2)]
    assert calibration_curve(rows,20)[-1]['n'] == 2
    assert session_report(rows+[trial(5,None,False,timed_out=True)])['n'] == 4
    assert session_report(rows[:2])['by_category']['logic']['thin'] is True
