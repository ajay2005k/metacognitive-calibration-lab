import copy
import pytest
from collections import Counter
from backend.items import load_items, validate_items, select_items


def test_bank_has_all_cells_and_valid_answers():
    items = load_items()
    assert len(items) == 36
    assert set(Counter((i["category"], i["difficulty"]) for i in items).values()) == {2}
    assert validate_items(items) == items


@pytest.mark.parametrize(
    "mutation",
    [
        lambda b: b.pop(),
        lambda b: b[0].update(answer=4),
        lambda b: b[0].update(options=["x"] * 4),
        lambda b: b[1].update(id=b[0]["id"]),
    ],
)
def test_invalid_banks_refused(mutation):
    bank = copy.deepcopy(load_items())
    mutation(bank)
    with pytest.raises(ValueError):
        validate_items(bank)


@pytest.mark.parametrize(
    "difficulty,category,n,count",
    [
        ("mixed", "all", 18, 18),
        ("mixed", "all", 36, 36),
        ("easy", "all", 36, 12),
        ("hard", "logic", 36, 2),
        ("mixed", "memory", 18, 6),
    ],
)
def test_selection(difficulty, category, n, count):
    bank = load_items()
    ids = select_items(bank, dict(difficulty=difficulty, categories=category), n)
    assert len(ids) == len(set(ids)) == count
    if n == 18 and category == "all":
        assert (
            len({(i["category"], i["difficulty"]) for i in bank if i["id"] in ids})
            == 18
        )
