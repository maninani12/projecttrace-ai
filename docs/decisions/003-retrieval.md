# ADR 003: Replaceable hybrid retrieval

Accepted. Use BM25 + vector similarity + path/structure weighting. PostgreSQL pgvector is the deployment adapter and FAISS supports native demos. Sentence Transformers is optional to avoid a mandatory model/torch download for a small student demo. Hashing lexical vectors make offline execution reproducible and are labeled honestly. The first baseline uses flat search and bounded chunk counts; persistence, ANN indexing and reranking require measured improvements before introduction.
