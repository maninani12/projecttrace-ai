import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

import numpy as np
from sqlalchemy import select

from app.models import EvidenceChunk

STOP = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "does",
    "do",
    "what",
    "which",
    "this",
    "project",
    "use",
    "uses",
    "how",
    "it",
    "in",
    "of",
    "to",
    "and",
}
SYNONYMS = {
    "database": "postgresql postgres mongodb sqlite database_url create_engine database",
    "backend": "fastapi flask django express backend",
    "frontend": "react vue frontend",
    "authentication": "jwt login password auth token",
    "model": "model predict load checkpoint",
    "workflow": "route post submit create update",
    "tests": "test pytest vitest",
}


def tokens(text):
    return [x for x in re.findall(r"[a-z][a-z0-9_]+", text.lower()) if x not in STOP]


class EmbeddingProvider(Protocol):
    name: str

    def encode(self, texts: list[str]) -> np.ndarray: ...


class HashEmbedding:
    """Deterministic lexical vectors for offline mode; not semantic/transformer embeddings."""

    name = "hashing-v1"

    def encode(self, texts):
        matrix = np.zeros((len(texts), 384), dtype="float32")
        for i, text in enumerate(texts):
            for token in tokens(text):
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "little") % 384
                matrix[i, index] += 1 if digest[4] & 1 else -1
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.maximum(norms, 1e-9)


class SentenceEmbedding:
    def __init__(self, name):
        from sentence_transformers import SentenceTransformer

        self.name = name
        self.model = SentenceTransformer(name, trust_remote_code=False)
        if self.model.get_sentence_embedding_dimension() != 384:
            raise ValueError("The configured model must have 384 dimensions.")

    def encode(self, texts):
        return self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)


@lru_cache(maxsize=2)
def embedder(name):
    return HashEmbedding() if name == "hashing-v1" else SentenceEmbedding(name)


class VectorStore(Protocol):
    def search(self, db, snapshot_id: str, query: np.ndarray, limit: int): ...


class FaissStore:
    def search(self, db, snapshot_id, query, limit):
        import faiss

        rows = list(
            db.scalars(select(EvidenceChunk).where(EvidenceChunk.snapshot_id == snapshot_id))
        )
        if not rows:
            return {}
        index = faiss.IndexFlatIP(384)
        index.add(np.asarray([x.embedding for x in rows], dtype="float32"))
        scores, indices = index.search(np.asarray([query], dtype="float32"), min(limit, len(rows)))
        return {rows[int(i)].id: float(s) for i, s in zip(indices[0], scores[0], strict=True)}


class PgVectorStore:
    def search(self, db, snapshot_id, query, limit):
        # SQLite uses JSON. PostgreSQL uses the native vector type.
        from pgvector.sqlalchemy import Vector
        from sqlalchemy import cast

        distance = cast(EvidenceChunk.embedding, Vector(384)).cosine_distance(query.tolist())
        rows = db.execute(
            select(EvidenceChunk.id, distance.label("distance"))
            .where(EvidenceChunk.snapshot_id == snapshot_id)
            .order_by(distance)
            .limit(limit)
        )
        return {row.id: 1 - row.distance for row in rows}


def retrieve(db, snapshot, question, config, limit=8):
    chunks = list(db.scalars(select(EvidenceChunk).where(EvidenceChunk.snapshot_id == snapshot.id)))
    if not chunks:
        return []
    expanded = question + " " + " ".join(v for k, v in SYNONYMS.items() if k in question.lower())
    query_tokens = set(tokens(expanded))
    original_tokens = set(tokens(question))
    provider = embedder(chunks[0].embedding_model)
    query_vector = provider.encode([expanded])[0]
    store = PgVectorStore() if config.vector_store == "pgvector" else FaissStore()
    vector = store.search(db, snapshot.id, query_vector, min(50, len(chunks)))
    documents = [tokens(x.content) for x in chunks]
    avg = sum(map(len, documents)) / max(len(documents), 1)
    frequency = {term: sum(term in d for d in documents) for term in query_tokens}
    scored = []
    for chunk, words in zip(chunks, documents, strict=True):
        bm25 = 0
        for term in query_tokens:
            tf = words.count(term)
            if tf:
                idf = math.log(1 + (len(chunks) - frequency[term] + 0.5) / (frequency[term] + 0.5))
                bm25 += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(words) / max(avg, 1)))
        path_signal = sum(t in chunk.path.lower() for t in original_tokens)
        implementation = 0.4 if chunk.chunk_type == "code" else 0
        score = bm25 + max(vector.get(chunk.id, 0), 0) * 2 + path_signal + implementation
        if bm25 > 0 or path_signal > 0:
            scored.append((score, chunk))
    return [chunk for _, chunk in sorted(scored, key=lambda x: x[0], reverse=True)[:limit]]


def evidence_dict(chunk, snapshot):
    return {
        "id": chunk.id,
        "file_id": chunk.file_id,
        "project_id": snapshot.project_id,
        "snapshot_id": snapshot.id,
        "commit_sha": snapshot.commit_sha,
        "path": chunk.path,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "chunk_type": chunk.chunk_type,
        "content": chunk.content[:8000],
    }
