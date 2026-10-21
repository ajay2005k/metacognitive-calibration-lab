"""JSON API for the local Metacognitive Calibration Laboratory."""

import csv
import io
import math
import os
import random
import re
import string
import uuid
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from pymongo.errors import DuplicateKeyError, PyMongoError
from werkzeug.exceptions import BadRequest, HTTPException

try:
    from .db import connect, create_indexes
    from .items import CATEGORIES, load_items, select_items
    from .metrics import calibration_curve, session_report
except ImportError:
    from db import connect, create_indexes
    from items import CATEGORIES, load_items, select_items
    from metrics import calibration_curve, session_report


def now():
    return datetime.now(timezone.utc).isoformat()


def clean(document):
    return {k: v for k, v in document.items() if k != "_id"}


def create_app(database=None):
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
    CORS(app, origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")])
    bank = {i["id"]: i for i in load_items()}
    db = database if database is not None else connect()
    create_indexes(db)
    app.extensions["db"] = db
    app.extensions["items"] = bank

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(message=error.description), error.code

    @app.errorhandler(PyMongoError)
    def database_error(error):
        app.logger.error("Database error: %s", error)
        return jsonify(
            message="Database unavailable or write conflict. Please retry."
        ), 503

    def body():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise BadRequest("Expected a JSON object")
        return data

    def fail(message, code=400):
        from werkzeug.exceptions import NotFound

        raise (NotFound(message) if code == 404 else BadRequest(message))

    def session(sid):
        s = db.sessions.find_one({"session_id": sid})
        if not s:
            fail("Session not found", 404)
        return s

    def filters():
        query = {}
        for field in ("group", "feedback", "is_synthetic"):
            if field not in request.args:
                continue
            value = request.args[field]
            if field == "feedback":
                if value not in ("immediate", "delayed", "none"):
                    fail("Invalid feedback filter")
                query["condition.feedback"] = value
            elif field == "is_synthetic":
                if value not in ("true", "false"):
                    fail("is_synthetic must be true or false")
                query[field] = value == "true"
            else:
                query[field] = value
        return query

    @app.get("/api/health")
    def health():
        db.command("ping")
        return jsonify(status="ok")

    @app.post("/api/sessions")
    def create_session():
        data = body()
        condition = data.get("condition", {})
        if not isinstance(condition, dict):
            fail("condition must be an object")
        defaults = dict(
            difficulty="mixed",
            feedback="none",
            time_limit="none",
            categories="all",
            interface="slider",
        )
        if set(condition) - set(defaults):
            fail("Unknown condition setting")
        cond = defaults | condition
        choices = dict(
            difficulty=("easy", "hard", "mixed"),
            feedback=("immediate", "delayed", "none"),
            time_limit=("none", "20"),
            categories=("all", *CATEGORIES),
            interface=("slider", "buttons"),
        )
        for key, allowed in choices.items():
            if cond[key] not in allowed:
                fail(f"Invalid {key}")
        n = data.get("n_trials", 36)
        if type(n) is not int:
            fail("n_trials must be an integer")
        if (
            cond["difficulty"] == "mixed"
            and cond["categories"] == "all"
            and n not in (18, 36)
        ):
            fail("n_trials must be 18 or 36 for mixed, all-category sessions")
        age, year = data.get("age_range") or None, data.get("academic_year")
        if age not in (None, "18-20", "21-23", "24+"):
            fail("Invalid age_range")
        if year is not None and (type(year) is not int or year not in range(1, 5)):
            fail("academic_year must be 1–4")
        group = data.get("group", "")
        if not isinstance(group, str) or len(group) > 80:
            fail("group must be text, at most 80 characters")
        pid = data.get("participant_id")
        if pid is not None and (
            not isinstance(pid, str) or not re.fullmatch(r"P-[A-Z0-9]{5}", pid)
        ):
            fail("participant_id must be P- plus five uppercase letters or digits")
        if pid is None:
            while True:
                pid = "P-" + "".join(
                    random.choices(string.ascii_uppercase + string.digits, k=5)
                )
                try:
                    db.participants.insert_one(
                        dict(
                            participant_id=pid,
                            age_range=age,
                            academic_year=year,
                            created_at=now(),
                        )
                    )
                    break
                except DuplicateKeyError:
                    continue
        else:
            db.participants.update_one(
                {"participant_id": pid},
                {
                    "$setOnInsert": dict(
                        participant_id=pid,
                        age_range=age,
                        academic_year=year,
                        created_at=now(),
                    )
                },
                upsert=True,
            )
        order = select_items(list(bank.values()), cond, n)
        sid = str(uuid.uuid4())
        s = dict(
            session_id=sid,
            participant_id=pid,
            group=group.strip(),
            condition=cond,
            n_trials=len(order),
            item_order=order,
            started_at=now(),
            ended_at=None,
            status="in_progress",
            is_synthetic=False,
        )
        db.sessions.insert_one(s)
        return jsonify(session_id=sid, participant_id=pid, n_trials=len(order)), 201

    @app.get("/api/sessions/<sid>/next")
    def next_item(sid):
        s = session(sid)
        count = db.trials.count_documents({"session_id": sid})
        if count == s["n_trials"] or s["status"] == "complete":
            return jsonify(done=True)
        item = {k: v for k, v in bank[s["item_order"][count]].items() if k != "answer"}
        return jsonify(
            item=item,
            trial_no=count + 1,
            n_trials=s["n_trials"],
            condition=s["condition"],
        )

    @app.post("/api/sessions/<sid>/trials")
    def store_trial(sid):
        s, data = session(sid), body()
        if s["status"] != "in_progress":
            fail("Session is already complete")
        item_id = data.get("item_id")
        if (
            not isinstance(item_id, str)
            or item_id not in bank
            or item_id not in s["item_order"]
        ):
            fail("Unknown item for this session")
        if db.trials.find_one({"session_id": sid, "item_id": item_id}):
            fail("Item already answered in this session")
        count = db.trials.count_documents({"session_id": sid})
        if count >= s["n_trials"] or item_id != s["item_order"][count]:
            fail("Please answer the next item in session order")
        timeout = data.get("timed_out", False)
        if type(timeout) is not bool:
            fail("timed_out must be a boolean")
        if timeout and s["condition"]["time_limit"] != "20":
            fail("This session has no time limit")
        answer, confidence, latency = (
            data.get("answer"),
            data.get("confidence"),
            data.get("latency_ms"),
        )
        if timeout:
            if answer is not None or confidence is not None:
                fail("Timed-out trials must have null answer and confidence")
            latency = None
        else:
            if type(answer) is not int or answer not in range(4):
                fail("answer must be an original option index, 0–3")
            if (
                type(confidence) not in (int, float)
                or not math.isfinite(confidence)
                or not 0 <= confidence <= 100
            ):
                fail("confidence must be between 0 and 100")
            if (
                type(latency) not in (int, float)
                or not math.isfinite(latency)
                or latency < 0
            ):
                fail("latency_ms must be a nonnegative finite number")
        item = bank[item_id]
        correct = not timeout and answer == item["answer"]
        trial = dict(
            session_id=sid,
            trial_no=count + 1,
            item_id=item_id,
            category=item["category"],
            difficulty=item["difficulty"],
            answer=answer,
            correct=correct,
            confidence=confidence,
            latency_ms=latency,
            timed_out=timeout,
            timestamp=now(),
        )
        try:
            db.trials.insert_one(trial)
        except DuplicateKeyError:
            fail("Trial already submitted; reload the session")
        return jsonify(
            stored=True, correct=correct, right_option=item["options"][item["answer"]]
        ), 201

    @app.post("/api/sessions/<sid>/complete")
    def complete(sid):
        s = session(sid)
        if s["status"] != "in_progress":
            fail("Session is already complete")
        trials = list(db.trials.find({"session_id": sid}).sort("trial_no", 1))
        if len(trials) != s["n_trials"]:
            fail("All scheduled trials must be submitted before completion")
        usable = [
            dict(t, feedback=s["condition"]["feedback"] != "none")
            for t in trials
            if not t["timed_out"]
        ]
        metrics = session_report(usable)
        metrics["timed_out_count"] = sum(t["timed_out"] for t in trials)
        report = dict(session_id=sid, metrics=metrics, generated_at=now())
        # Unique report key is the completion claim; parallel completion cannot win twice.
        try:
            db.reports.insert_one(report)
        except DuplicateKeyError:
            fail("Session is already complete")
        db.sessions.update_one(
            {"session_id": sid}, {"$set": {"status": "complete", "ended_at": now()}}
        )
        return jsonify(clean(report))

    @app.get("/api/sessions")
    def list_sessions():
        rows = []
        for s in db.sessions.find(filters()).sort("started_at", -1):
            row = clean(s)
            row.pop("item_order", None)
            report = db.reports.find_one({"session_id": s["session_id"]})
            row["metrics"] = report["metrics"] if report else None
            row["answered"] = db.trials.count_documents({"session_id": s["session_id"]})
            rows.append(row)
        return jsonify(rows)

    @app.get("/api/sessions/<sid>")
    def get_session(sid):
        s = clean(session(sid))
        s["trials"] = [
            clean(t) for t in db.trials.find({"session_id": sid}).sort("trial_no", 1)
        ]
        return jsonify(s)

    @app.delete("/api/sessions/<sid>")
    def delete_session(sid):
        session(sid)
        db.trials.delete_many({"session_id": sid})
        db.reports.delete_many({"session_id": sid})
        db.sessions.delete_one({"session_id": sid})
        return jsonify(deleted=True)

    @app.get("/api/reports/<sid>")
    def get_report(sid):
        s = session(sid)
        report = db.reports.find_one({"session_id": sid})
        if not report:
            fail("Report not found; complete the session first", 404)
        return jsonify(dict(clean(report), session=clean(s)))

    @app.get("/api/dashboard")
    def dashboard():
        sessions = list(db.sessions.find(filters()))
        reports = {
            r["session_id"]: r["metrics"]
            for r in db.reports.find(
                {"session_id": {"$in": [s["session_id"] for s in sessions]}}
            )
        }
        completed = [s for s in sessions if s["session_id"] in reports]

        def aggregates(key):
            out = []
            for label in sorted({key(s) for s in completed}):
                members = [s for s in completed if key(s) == label]
                ms = [reports[s["session_id"]] for s in members]
                result = {
                    "label": label,
                    "n_sessions": len(members),
                    "synthetic_sessions": sum(s["is_synthetic"] for s in members),
                }
                for metric in (
                    "accuracy",
                    "mean_confidence",
                    "overconfidence",
                    "calibration_error",
                ):
                    vals = [m[metric] for m in ms if m[metric] is not None]
                    result[metric] = mean(vals) if vals else None
                out.append(result)
            return out

        curves = {}
        for feedback in ("immediate", "delayed", "none"):
            ids = [
                s["session_id"]
                for s in completed
                if s["condition"]["feedback"] == feedback
            ]
            ts = list(db.trials.find({"session_id": {"$in": ids}, "timed_out": False}))
            curves[feedback] = calibration_curve(ts, 20)
        ids = [s["session_id"] for s in completed]
        latency = {}
        for difficulty in ("easy", "medium", "hard"):
            ts = list(
                db.trials.find(
                    {
                        "session_id": {"$in": ids},
                        "difficulty": difficulty,
                        "timed_out": False,
                    }
                )
            )
            vals = [t["latency_ms"] for t in ts if t["latency_ms"] is not None]
            latency[difficulty] = mean(vals) if vals else None
        return jsonify(
            n_sessions=len(sessions),
            n_complete=len(completed),
            synthetic_sessions=sum(s["is_synthetic"] for s in sessions),
            by_feedback=aggregates(lambda s: s["condition"]["feedback"]),
            by_group=aggregates(lambda s: s["group"]),
            calibration_curves=curves,
            latency_by_difficulty=latency,
        )

    @app.get("/api/export")
    def export():
        fmt = request.args.get("format", "json")
        if fmt not in ("json", "csv"):
            fail("format must be csv or json")
        rows = []
        for s in db.sessions.find(filters()).sort("started_at", 1):
            participant = (
                db.participants.find_one({"participant_id": s["participant_id"]}) or {}
            )
            for trial in db.trials.find({"session_id": s["session_id"]}).sort(
                "trial_no", 1
            ):
                rows.append(
                    clean(trial)
                    | dict(
                        participant_id=s["participant_id"],
                        age_range=participant.get("age_range"),
                        academic_year=participant.get("academic_year"),
                        group=s["group"],
                        is_synthetic=s["is_synthetic"],
                    )
                    | {f"condition_{k}": v for k, v in s["condition"].items()}
                )
        if fmt == "json":
            return jsonify(rows)
        fields = [
            "session_id",
            "trial_no",
            "item_id",
            "category",
            "difficulty",
            "answer",
            "correct",
            "confidence",
            "latency_ms",
            "timed_out",
            "timestamp",
            "participant_id",
            "age_range",
            "academic_year",
            "group",
            "is_synthetic",
            "condition_difficulty",
            "condition_feedback",
            "condition_time_limit",
            "condition_categories",
            "condition_interface",
        ]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            # Prevent spreadsheet formula execution in instructor-entered group labels.
            row["group"] = (
                "'" + row["group"]
                if row["group"].lstrip().startswith(("=", "+", "-", "@"))
                else row["group"]
            )
            writer.writerow(row)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=mclab-trials.csv"},
        )

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000)
