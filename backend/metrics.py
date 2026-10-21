"""Original metrics. Confidence uses 0–100; accuracy/correlation use 0–1.

Calibration error is weighted absolute bin confidence minus accuracy, in points.
Undefined values are None. Timeouts are excluded defensively at this boundary.
"""
from math import sqrt
from statistics import mean


def average(values):
    values = list(values)
    return mean(values) if values else None


def calibration_curve(trials, width=10):
    bins = []
    for low in range(0, 100, width):
        rows = [t for t in trials if low <= t['confidence'] < low + width
                or (low + width == 100 and t['confidence'] == 100)]
        if rows:
            bins.append({'low': low, 'high': low + width, 'n': len(rows),
                         'confidence': mean(t['confidence'] for t in rows),
                         'accuracy': mean(int(t['correct']) for t in rows)})
    return bins


def performance(rows):
    n = len(rows)
    return {'n': n, 'accuracy': average(int(t['correct']) for t in rows),
            'mean_confidence': average(t['confidence'] for t in rows), 'thin': n < 3}


def session_report(trials):
    rows = [t for t in trials if not t.get('timed_out') and t.get('confidence') is not None]
    n = len(rows)
    accuracy = average(int(t['correct']) for t in rows)
    confidence = average(t['confidence'] for t in rows)
    bias = confidence - accuracy * 100 if n else None
    curve = calibration_curve(rows)
    r = None
    if n > 1:
        xs, ys = [t['confidence'] for t in rows], [int(t['correct']) for t in rows]
        mx, my = mean(xs), mean(ys)
        denominator = sqrt(sum((x-mx)**2 for x in xs) * sum((y-my)**2 for y in ys))
        if denominator:
            r = sum((x-mx)*(y-my) for x, y in zip(xs, ys)) / denominator
    difficulty = {d: performance([t for t in rows if t['difficulty'] == d])
                  for d in ('easy', 'medium', 'hard')}
    categories = {c: performance([t for t in rows if t['category'] == c])
                  for c in ('logic', 'pattern', 'memory', 'probability', 'numerical', 'perceptual')}
    lat = lambda subset: average(t['latency_ms'] for t in subset if t.get('latency_ms') is not None)
    ordered = sorted(rows, key=lambda t: t['trial_no'])
    feedback_change = None
    if len(ordered) >= 4 and any(t.get('feedback') for t in ordered):
        half = len(ordered) // 2
        early, late = ordered[:half], ordered[half:]
        bias_of = lambda ts: mean(t['confidence'] - int(t['correct'])*100 for t in ts)
        feedback_change = bias_of(late) - bias_of(early)
    return {'n': n, 'accuracy': accuracy, 'mean_confidence': confidence,
            'overconfidence': bias, 'underconfidence': -bias if bias is not None else None,
            'calibration_error': sum(b['n'] * abs(b['confidence']-b['accuracy']*100) for b in curve)/n if n else None,
            'point_biserial_r': r, 'calibration_curve': curve,
            'latency': {'overall': lat(rows), 'correct': lat([t for t in rows if t['correct']]),
                        'incorrect': lat([t for t in rows if not t['correct']]),
                        'by_difficulty': {d: lat([t for t in rows if t['difficulty'] == d]) for d in difficulty}},
            'by_difficulty': difficulty, 'by_category': categories,
            'change_after_feedback': feedback_change}
