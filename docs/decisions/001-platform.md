# ADR 001: Modular monolith with a worker

Accepted. FastAPI/Pydantic provide explicit REST contracts; SQLAlchemy/Alembic provide transactions and portable migrations. PostgreSQL is the deployment database; SQLite is a clearly labeled native demo adapter when Docker is absent. Redis/RQ is the production queue: analysis is Python work and RQ offers job isolation and bounded timeouts with low operational overhead. A separate SQL polling process supports local demos, with no analysis executed in HTTP request handlers. No Kubernetes or microservices.
