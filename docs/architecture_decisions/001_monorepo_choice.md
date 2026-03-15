# ADR 001: Monolithic Repository (Monorepo) Architecture

## Status
Accepted

## Context
PARWA is an autonomous AI customer support platform consisting of multiple logical components: a Node.js/Next.js frontend dashboard, a Python/FastAPI backend, background Celery workers for heavy LLM processing, and various shared configuration/security modules. As a team of parallel AI agents building this system, we need a repository structure that maximizes code sharing, simplifies integration testing, and provides a single source of truth for deployments.

## Decision
We will use a Monolithic Repository (Monorepo) structure (`parwa code/`) containing all project components. 
- Shared utilities (e.g., `config.py`, `logger.py`, `security.py`) will live in a top-level `shared/` directory.
- The backend, worker, and frontend will each have discrete directories but share dependencies where appropriate.
- Docker Compose will be used from the root to orchestrate the entire development environment.

## Consequences
### Positive
- **Unified Versioning**: A single git commit represents the state of the entire system (frontend + backend + infrastructure).
- **Simplified Agent Coordination**: "Builder" agents can easily cross-reference configuration files and data contracts without needing to clone multiple repositories.
- **Easier Refactoring**: Changes to the core `shared/` directory instantly apply to all consuming services.

### Negative
- As the project grows beyond Week 60, CI/CD pipeline times may increase if not properly optimized to only test changed modules.
- Python and Node.js environments must be managed carefully within the same overarching directory structure.
