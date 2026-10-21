import json
import random
from collections import Counter
from pathlib import Path

CATEGORIES = ('logic', 'pattern', 'memory', 'probability', 'numerical', 'perceptual')
DIFFICULTIES = ('easy', 'medium', 'hard')


def validate_items(items):
    if len(items) != 36 or len({i['id'] for i in items}) != 36:
        raise ValueError('Item bank must contain 36 unique items')
    expected = Counter({(c, d): 2 for c in CATEGORIES for d in DIFFICULTIES})
    if Counter((i['category'], i['difficulty']) for i in items) != expected:
        raise ValueError('Item bank must have two items per category/difficulty cell')
    for item in items:
        opts = item['options']
        if len(opts) != 4 or len(set(opts)) != 4 or type(item['answer']) is not int or not 0 <= item['answer'] < 4:
            raise ValueError(f"Invalid options or answer: {item['id']}")
        if not item.get('question'):
            raise ValueError('Missing question')
        if item['category'] == 'memory' and (not item.get('study') or item.get('study_seconds', 0) <= 0):
            raise ValueError('Invalid memory study')
        s = item.get('stimulus', {})
        if item['category'] == 'perceptual':
            if s.get('type') == 'circles':
                radii = s.get('radii_px', [])
                if len(radii) != 4 or min(radii) <= 0 or radii.index(max(radii)) != item['answer'] or radii.count(max(radii)) != 1:
                    raise ValueError('Invalid circle stimulus')
            elif s.get('type') == 'dots':
                if not 1 <= s.get('count', 0) <= 100 or opts[item['answer']] != str(s['count']):
                    raise ValueError('Invalid dot stimulus')
            else:
                raise ValueError('Unknown stimulus')
    return items


def load_items(path=None):
    return validate_items(json.loads(Path(path or Path(__file__).with_name('items.json')).read_text()))


def select_items(items, condition, n_trials):
    selected = [i for i in items if (condition['categories'] == 'all' or i['category'] == condition['categories'])
                and (condition['difficulty'] == 'mixed' or i['difficulty'] == condition['difficulty'])]
    if condition['categories'] == 'all' and condition['difficulty'] == 'mixed' and n_trials == 18:
        selected = [random.choice([i for i in selected if i['category'] == c and i['difficulty'] == d])
                    for c in CATEGORIES for d in DIFFICULTIES]
    random.shuffle(selected)
    return [i['id'] for i in selected]
