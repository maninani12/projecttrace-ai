import hashlib

from sqlalchemy import select

from app.ai.providers import OpenAIProvider
from app.models import (
    AnswerCache,
    Claim,
    ClaimEvidence,
    EvidenceChunk,
    GeneratedDocument,
    VivaQuestion,
    VivaSession,
    iso_time,
)
from app.retrieval.engine import evidence_dict, retrieve
from app.security.redaction import redact


def claim_dict(db, claim, snapshot, chunks=None):
    chunks = (
        chunks
        if chunks is not None
        else db.scalars(
            select(EvidenceChunk)
            .join(ClaimEvidence, ClaimEvidence.chunk_id == EvidenceChunk.id)
            .where(ClaimEvidence.claim_id == claim.id)
        )
    )
    return {
        "id": claim.id,
        "text": claim.text,
        "status": claim.status,
        "confidence": claim.confidence,
        "explanation": claim.explanation,
        "source_artifact": claim.source_artifact,
        "source_line": claim.source_line,
        "recommendation": claim.recommendation,
        "created_at": iso_time(claim.created_at),
        "snapshot_id": snapshot.id,
        "commit_sha": snapshot.commit_sha,
        "evidence": [evidence_dict(c, snapshot) for c in chunks],
    }


def claim_page(db, claims, snapshot):
    """Resolve a whole page of claim citations in one query."""
    by_claim = {c.id: [] for c in claims}
    if by_claim:
        links = db.execute(
            select(ClaimEvidence.claim_id, EvidenceChunk)
            .join(EvidenceChunk, ClaimEvidence.chunk_id == EvidenceChunk.id)
            .where(ClaimEvidence.claim_id.in_(by_claim))
        )
        for claim_id, chunk in links:
            by_claim[claim_id].append(chunk)
    return [claim_dict(db, claim, snapshot, by_claim[claim.id]) for claim in claims]


def ask(db, snapshot, question, config):
    safe_question = redact(question)[0]
    query_hash = hashlib.sha256(
        (config.llm_provider + config.llm_model + safe_question.lower().strip()).encode()
    ).hexdigest()
    cached = db.scalar(
        select(AnswerCache).where(
            AnswerCache.snapshot_id == snapshot.id, AnswerCache.query_hash == query_hash
        )
    )
    if cached:
        return cached.response
    chunks = retrieve(db, snapshot, safe_question, config)
    evidence = [evidence_dict(c, snapshot) for c in chunks]
    if config.llm_provider == "openai":
        # Re-scan the trimmed payload just before external transmission.
        context = [{**item, "content": redact(item["content"])[0][:5000]} for item in evidence[:6]]
        result = OpenAIProvider(config).answer(safe_question, context)
        response = {
            "answer": result.answer,
            "status": result.status,
            "confidence": result.confidence,
            "evidence": [x for x in context if x["id"] in result.citation_ids],
            "limitations": result.limitations
            + ["AI summary; citations are validated but semantic entailment is not proven."],
            "provider": "openai",
        }
    else:
        stack = snapshot.summary.get("stack", [])
        category = next(
            (
                v
                for k, v in [
                    ("database", "Database"),
                    ("backend", "Backend"),
                    ("frontend", "Frontend"),
                    ("authentication", "Authentication"),
                    ("styling", "Styling"),
                ]
                if k in safe_question.lower()
            ),
            None,
        )
        selected = [t for t in stack if t["category"] == category]
        if selected:
            names = ", ".join(t["name"] for t in selected)
            direct = all(t["status"] == "VERIFIED" for t in selected)
            paths = {p for t in selected for p in t["files"]}
            direct_chunks = list(
                db.scalars(
                    select(EvidenceChunk)
                    .where(EvidenceChunk.snapshot_id == snapshot.id, EvidenceChunk.path.in_(paths))
                    .limit(8)
                )
            )
            response = {
                "answer": f"The project references {names} in its source or configuration."
                if direct
                else f"The manifests declare {names}. Implementation usage is not confirmed.",
                "status": "VERIFIED" if direct else "INFERRED",
                "confidence": 0.95 if direct else 0.65,
                "evidence": [evidence_dict(c, snapshot) for c in direct_chunks],
                "limitations": [
                    "Static evidence confirms presence or configuration, not successful execution."
                ],
                "provider": "offline",
            }
        else:
            response = {
                "answer": "The static index cannot verify this behavior. Review the retrieved excerpts below. Configure an AI provider for a cited explanation.",
                "status": "UNVERIFIED",
                "confidence": 0.2 if evidence else 0,
                "evidence": evidence,
                "limitations": [
                    "Offline mode retrieves relevant evidence; it does not infer arbitrary application workflows."
                ],
                "provider": "offline",
            }
    db.add(AnswerCache(snapshot_id=snapshot.id, query_hash=query_hash, response=response))
    try:
        db.commit()
    except __import__("sqlalchemy").exc.IntegrityError:
        db.rollback()  # A concurrent identical query populated the cache.
    return response


def viva(db, snapshot, difficulty):
    session = VivaSession(snapshot_id=snapshot.id, difficulty=difficulty)
    db.add(session)
    db.flush()
    claims = list(db.scalars(select(Claim).where(Claim.snapshot_id == snapshot.id).limit(30)))
    if difficulty == "ADVERSARIAL EXAMINER":
        claims.sort(key=lambda c: c.status not in {"CONTRADICTED", "STALE", "UNVERIFIED"})
    questions = []
    for claim in claims[:10]:
        detail = claim_dict(db, claim, snapshot)
        if claim.status in {"CONTRADICTED", "STALE"}:
            question = f"Your documentation says “{claim.text}”. How would you explain the discrepancy with the implementation?"
        elif claim.status == "UNVERIFIED":
            question = f"What evidence would you need to defend this claim: “{claim.text}”?"
        else:
            verbs = {
                "BEGINNER": "Identify",
                "FACULTY": "Explain the evidence for",
                "TECHNICAL REVIEWER": "Trace the source and configuration behind",
                "RECRUITER": "Describe the implementation tradeoffs and evidence behind",
                "ADVERSARIAL EXAMINER": "Defend with exact source evidence",
            }
            question = f"{verbs[difficulty]}: {claim.text}"
        answer = f"{claim.status}: {claim.explanation}"
        if claim.recommendation:
            answer += " Recommended correction: " + claim.recommendation
        row = VivaQuestion(
            session_id=session.id,
            question=question,
            answer=answer,
            topic="Documentation consistency"
            if claim.source_artifact != "Repository"
            else "Technology evidence",
            follow_up="Which cited file and line supports your explanation? What would require runtime verification?",
            evidence=detail["evidence"],
        )
        db.add(row)
        db.flush()
        questions.append(
            {
                "id": row.id,
                "question": row.question,
                "answer": row.answer,
                "topic": row.topic,
                "follow_up": row.follow_up,
                "evidence": row.evidence,
                "difficulty": difficulty,
                "revision": False,
            }
        )
    db.commit()
    return {"id": session.id, "difficulty": difficulty, "questions": questions}


def document(db, snapshot, kind, project):
    claims = list(db.scalars(select(Claim).where(Claim.snapshot_id == snapshot.id)))
    verified = [claim_dict(db, c, snapshot) for c in claims if c.status == "VERIFIED"]
    facts = (
        "\n".join(
            "- "
            + c["text"]
            + " ["
            + ", ".join(f"{e['path']}:{e['start_line']}-{e['end_line']}" for e in c["evidence"])
            + "]"
            for c in verified
        )
        or "- No verified technology facts are available."
    )
    limitations = "\n".join("- " + x for x in snapshot.summary.get("limitations", []))
    corrections = (
        "\n".join(
            "- " + c.recommendation
            for c in claims
            if c.status in {"CONTRADICTED", "UNVERIFIED", "STALE"}
        )
        or "- No correction candidates detected."
    )
    missing = "Not established by static repository evidence. Add an author-supplied statement and verify it separately."
    sections = [
        ("Introduction", f"Implementation evidence summary for {project.name}."),
        ("Problem Statement", missing),
        ("Objectives", missing),
        ("Scope", "This document describes only the analyzed snapshot."),
        (
            "Modules",
            "\n".join(
                f"- {r['method']} {r['path']} [{r['file']}:{r['line']}]"
                for r in snapshot.summary.get("routes", [])
            )
            or missing,
        ),
        (
            "Methodology",
            missing,
        ),
        (
            "Architecture Explanation",
            "Detected source facts do not establish a complete runtime architecture.\n" + facts,
        ),
        ("Technology Stack", facts),
        ("Features", "Confirmed source/configuration facts:\n" + facts),
        ("Challenges & Limitations", limitations),
        (
            "Conclusion",
            "Use the cited evidence to defend implementation claims. Runtime success is unverified.",
        ),
        ("Future Scope — recommendations, not implemented", corrections),
        ("References", "\n".join("- " + e["path"] for c in verified for e in c["evidence"])),
    ]
    if kind == "presentation":
        by_name = dict(sections)
        sections = [
            ("Project Title", project.name),
            ("Introduction", by_name["Introduction"]),
            ("Problem Statement", missing),
            ("Objectives", missing),
            ("Scope", by_name["Scope"]),
            ("Proposed System / Methodology", missing),
            ("Architecture", by_name["Architecture Explanation"]),
            ("Implementation / Technology Stack", facts),
            (
                "UI / Application Screens",
                "Add screenshots captured from the running analyzed application. None are verified by this static inspection.",
            ),
            ("Challenges & Limitations", limitations),
            ("Conclusion", by_name["Conclusion"]),
            ("Future Scope — recommendations, not implemented", corrections),
            ("References", by_name["References"]),
        ]
        sections = [(name, "\n".join(text.splitlines()[:6])) for name, text in sections]
    elif kind in {"resume", "linkedin"}:
        sections = [
            ("Verified information", facts),
            (
                "Description guidance",
                "Describe your personal contribution separately; ownership, performance and deployment are not inferred.",
            ),
            ("Recommended / future functionality", corrections),
        ]
    elif kind == "readme":
        sections = [
            ("Verified information", facts),
            ("README improvement suggestions", corrections),
            ("Limitations", limitations),
        ]
    elif kind == "viva-notes":
        sections = [
            ("Evidence to defend", facts),
            ("Claims requiring revision", corrections),
            ("Limitations", limitations),
        ]
    content = (
        f"# {project.name} — {kind}\n\nSnapshot: {snapshot.commit_sha}\n\nGenerated from static evidence.\n\n"
        + "\n\n".join("## " + name + "\n\n" + text for name, text in sections)
    )
    content = content.replace("\n", "\n")
    row = GeneratedDocument(snapshot_id=snapshot.id, kind=kind, content=redact(content)[0])
    db.add(row)
    db.commit()
    return {
        "id": row.id,
        "kind": kind,
        "content": row.content,
        "snapshot_id": snapshot.id,
        "created_at": iso_time(row.created_at),
    }
