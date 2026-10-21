"""Explicit, deterministic simulation. Never runs on application startup."""

import argparse
import random
from datetime import datetime, timedelta, timezone

try:
    from .app import create_app
    from .metrics import session_report
except ImportError:
    from app import create_app
    from metrics import session_report


def clear_demo(db):
    ids = [s["session_id"] for s in db.sessions.find({"is_synthetic": True})]
    db.trials.delete_many({"session_id": {"$in": ids}})
    db.reports.delete_many({"session_id": {"$in": ids}})
    db.sessions.delete_many({"session_id": {"$in": ids}})
    db.participants.delete_many({"participant_id": {"$regex": "^DEMO-"}})


def seed(db, bank):
    if db.sessions.count_documents({"is_synthetic": True}):
        raise ValueError("Synthetic sessions already exist. Use --clear first.")
    rng = random.Random(20261021)
    anchor = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
    for person in range(24):
        feedback = "immediate" if person < 12 else "none"
        pid, sid = f"DEMO-{person + 1:03}", f"demo-session-{person + 1:03}"
        cond = dict(
            difficulty="mixed",
            feedback=feedback,
            time_limit="none",
            categories="all",
            interface="slider",
        )
        items = list(bank.values())
        rng.shuffle(items)
        started = (anchor + timedelta(hours=person)).isoformat()
        db.participants.insert_one(
            dict(
                participant_id=pid,
                age_range=None,
                academic_year=None,
                created_at=started,
            )
        )
        db.sessions.insert_one(
            dict(
                session_id=sid,
                participant_id=pid,
                group="Demo feedback"
                if feedback == "immediate"
                else "Demo no feedback",
                condition=cond,
                n_trials=36,
                item_order=[i["id"] for i in items],
                started_at=started,
                ended_at=(anchor + timedelta(hours=person, minutes=15)).isoformat(),
                status="complete",
                is_synthetic=True,
            )
        )
        bias = rng.uniform(5, 17)
        trials = []
        for index, item in enumerate(items):
            base = {"easy": 0.86, "medium": 0.66, "hard": 0.43}[item["difficulty"]]
            correct = rng.random() < base
            shrink = 1 - 0.7 * index / 35 if feedback == "immediate" else 1
            confidence = round(
                max(
                    0,
                    min(
                        100,
                        base * 100
                        + (
                            bias
                            + {"easy": 0, "medium": 5, "hard": 12}[item["difficulty"]]
                        )
                        * shrink
                        + rng.gauss(0, 10),
                    ),
                )
            )
            answer = (
                item["answer"]
                if correct
                else rng.choice([i for i in range(4) if i != item["answer"]])
            )
            t = dict(
                session_id=sid,
                trial_no=index + 1,
                item_id=item["id"],
                category=item["category"],
                difficulty=item["difficulty"],
                answer=answer,
                correct=correct,
                confidence=confidence,
                latency_ms=round(rng.uniform(2200, 6500) + (0 if correct else 1800)),
                timed_out=False,
                timestamp=started,
            )
            trials.append(t)
        db.trials.insert_many([dict(t) for t in trials])
        metrics = session_report([dict(t, feedback=feedback != "none") for t in trials])
        metrics["timed_out_count"] = 0
        db.reports.insert_one(
            dict(session_id=sid, metrics=metrics, generated_at=started)
        )
    return 24


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete synthetic sessions and demo participants only, then exit",
    )
    args = parser.parse_args()
    app = create_app()
    if args.clear:
        clear_demo(app.extensions["db"])
        print("Synthetic sessions cleared. Real participant data preserved.")
    else:
        print(
            f"Created {seed(app.extensions['db'], app.extensions['items'])} clearly marked synthetic sessions."
        )
