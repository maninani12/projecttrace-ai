import re
from pathlib import PurePosixPath

from sqlalchemy import select

from app.models import Claim, ClaimEvidence, ConsistencyFinding
from app.parsers.source import RULES


def build_claims(db, snapshot, files, chunks, stack, previous_snapshot_id=None):
    by_path = {}
    for chunk in chunks:
        by_path.setdefault(chunk.path, []).append(chunk)
    old_verified = set()
    if previous_snapshot_id:
        old_verified = set(
            db.scalars(
                select(Claim.text).where(
                    Claim.snapshot_id == previous_snapshot_id, Claim.status == "VERIFIED"
                )
            )
        )
    results = []
    known = {x["name"].lower(): x for x in stack}

    def add(text, status, explanation, paths, source="Repository", line=None, recommendation=""):
        if text in old_verified and status in {"CONTRADICTED", "UNVERIFIED"}:
            status = "STALE"
            explanation = "Previously supported; evidence changed in this snapshot. " + explanation
        claim = Claim(
            snapshot_id=snapshot.id,
            text=text,
            status=status,
            confidence={
                "VERIFIED": 0.95,
                "INFERRED": 0.65,
                "CONTRADICTED": 0.85,
                "UNVERIFIED": 0.2,
                "STALE": 0.7,
            }[status],
            explanation=explanation,
            source_artifact=source,
            source_line=line,
            recommendation=recommendation,
        )
        db.add(claim)
        db.flush()
        for path in dict.fromkeys(paths):
            candidates = by_path.get(path, [])
            if source == path and line:
                candidates = [c for c in candidates if c.start_line <= line <= c.end_line]
            else:
                # Prefer the excerpt containing the actual signal, not the file's first chunk.
                technology_patterns = [
                    pattern
                    for name, (_, patterns, _) in RULES.items()
                    if name.lower() in text.lower()
                    for pattern in patterns
                ]
                if not technology_patterns:
                    technology_patterns = [
                        pattern
                        for tech in stack
                        if path in tech["files"]
                        for pattern in RULES[tech["name"]][1]
                    ]
                matched = [
                    c
                    for c in candidates
                    if any(re.search(p, c.content, re.I) for p in technology_patterns)
                ]
                if matched:
                    candidates = matched
            for chunk in candidates[:1]:
                db.add(ClaimEvidence(claim_id=claim.id, chunk_id=chunk.id))
        if source != "Repository":
            kind = {
                "VERIFIED": "MATCH",
                "INFERRED": "MISSING",
                "UNVERIFIED": "MISSING",
                "CONTRADICTED": "CONFLICT",
                "STALE": "OUTDATED",
            }[status]
            db.add(
                ConsistencyFinding(
                    snapshot_id=snapshot.id,
                    claim_id=claim.id,
                    kind=kind,
                    recommendation=recommendation
                    or "Keep the description scoped to the cited static evidence.",
                )
            )
        results.append(claim)

    for tech in stack:
        text = (
            f"{tech['name']} is present in source/configuration."
            if tech["status"] == "VERIFIED"
            else f"{tech['name']} is declared as a dependency."
        )
        add(
            text,
            tech["status"],
            tech["basis"] + "; this does not prove runtime behavior.",
            tech["files"],
        )
    readmes = [f for f in files if PurePosixPath(f.path).name.lower().startswith("readme")]
    for file in readmes:
        for number, line in enumerate(file.content.splitlines(), 1):
            clean = line.strip().strip("#*- ")
            if len(clean) < 12 or len(clean) > 500 or clean.startswith(("```", "http", "|", "![")):
                continue
            # Recommendations and negatives are never presented as implemented claims.
            if re.search(
                r"\b(?:future|planned|recommend|not implemented|does not|will use|todo|roadmap)\b",
                clean,
                re.I,
            ):
                continue
            mentions = [
                name for name in RULES if re.search(r"\b" + re.escape(name) + r"\b", clean, re.I)
            ]
            technical = bool(mentions) or bool(
                re.search(
                    r"\b(?:authentication|encrypted|deployed|real.time|machine learning|tests? pass|secure|scalable|oauth)\b",
                    clean,
                    re.I,
                )
            )
            if not technical:
                continue
            supported = [known[name.lower()] for name in mentions if name.lower() in known]
            missing = [name for name in mentions if name.lower() not in known]
            status = "UNVERIFIED"
            explanation = "No direct implementation evidence verifies this statement. Static inspection cannot prove operational or security claims."
            paths = [file.path]
            recommendation = (
                "Qualify or remove this statement until implementation evidence is available."
            )
            # Database conflicts are scoped to source configuration, never README alone.
            claimed_databases = [name for name in missing if RULES[name][0] == "Database"]
            actual_databases = [
                t for t in stack if t["category"] == "Database" and t["status"] == "VERIFIED"
            ]
            if (
                claimed_databases
                and actual_databases
                and re.search(r"\b(?:uses?|database|built with|powered by)\b", clean, re.I)
            ):
                status = "CONTRADICTED"
                actual = ", ".join(t["name"] for t in actual_databases)
                explanation = f"The README names {', '.join(claimed_databases)}, while source configuration references {actual}. No matching implementation was found; review whether multiple databases were intended."
                paths += [p for t in actual_databases for p in t["files"]]
                recommendation = f"Update the database description to match the {actual} configuration, or provide evidence for the additional database."
            elif supported and not missing:
                dangerous = re.search(
                    r"\b(?:secure|scalable|deployed|encrypted|production|tests? pass|authentication|real.time)\b",
                    clean,
                    re.I,
                )
                if not dangerous:
                    status = "INFERRED"
                    explanation = "The named technologies are present. This supports the stack description indirectly, but the full sentence has not been semantically verified."
                    recommendation = (
                        "Use the cited source files to confirm the precise behavior described."
                    )
                    technologies = "|".join(re.escape(t["name"].lower()) for t in supported)
                    narrow = rf"(?:the )?(?:frontend|backend|project|application|database) (?:uses|is built with|is configured for) (?:{technologies})(?: as its database)?"
                    clauses = clean.lower().rstrip(".").split(" and ")
                    if all(t["status"] == "VERIFIED" for t in supported) and all(
                        re.fullmatch(narrow, clause) for clause in clauses
                    ):
                        status = "VERIFIED"
                        explanation = "This narrow technology statement matches detected source/configuration. Runtime behavior is not verified."
                        recommendation = (
                            "Keep this statement scoped to the cited source/configuration."
                        )
                paths += [p for t in supported for p in t["files"]]
            add(clean, status, explanation, paths, file.path, number, recommendation)
    for old in old_verified:
        if old not in {c.text for c in results}:
            add(
                old,
                "UNVERIFIED",
                "The supporting technology was not detected in the new snapshot.",
                [],
                "Previous snapshot",
                recommendation="Review this claim against the new implementation.",
            )
    return results
