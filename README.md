# Schema Sentinel — PostgreSQL Pre-Migration Lock & Risk Analyzer

> **Source Repository:** [github.com/Pradeep-B28/Schema_Sentinel](https://github.com/Pradeep-B28/Schema_Sentinel)  
> **Author:** [B Pradeep](https://github.com/Pradeep-B28) · [Portfolio](https://pradeep-b28.github.io/Pradeep-B28/)

---

## Overview

Deploying schema migrations in high-concurrency PostgreSQL environments carries severe operational risks. Unindexed foreign keys, in-place column type mutations, or non-concurrent index creations acquire `ACCESS EXCLUSIVE` locks—halting concurrent reads and writes, backing up connection pools, and causing production outages.

**Schema Sentinel** is an automated static migration analyzer and live-database lock profiler. It tokenizes SQL migration statements, detects transactional anti-patterns, evaluates lock severity across a 4-axis risk matrix, and acts as a CI/CD gatekeeper before migrations reach production databases.

```mermaid
flowchart TD
    SQL["SQL Migration Script\n(Flyway, Liquibase, Django, Prisma)"] --> Parser["Multi-Encoding SQL Parser\n(AST Tokenizer & Comment Stripper)"]
    
    Parser --> Heuristic["Static Heuristic Engine\n(Anti-pattern match & lock classification)"]
    Parser -.->|Optional Connection| LiveProfiler["Live PostgreSQL Profiler\n(Table row count, bloat, pg_locks)"]
    
    Heuristic --> Scorer["4-Axis Risk Scorer\n(Lock · Integrity · Compatibility · Performance)"]
    LiveProfiler -.-> Scorer
    
    Scorer --> CLI["Terminal Table / Diff"]
    Scorer --> Action["GitHub Action CI Check\n(--fail-on-high gatekeeper)"]
    Scorer --> JSON["Machine-Readable JSON Report"]
```

---

## 4-Axis Risk Scoring Matrix

Every detected migration operation is scored against four orthogonal operational dimensions:

| Risk Dimension | What It Measures | Example High-Risk Operation | Safe Alternative |
| :--- | :--- | :--- | :--- |
| **Lock Risk** | Severity and duration of PostgreSQL table lock | `ALTER TABLE ... ADD CONSTRAINT FOREIGN KEY` | Add constraint `NOT VALID`, then `VALIDATE CONSTRAINT` asynchronously |
| **Data Integrity Risk** | Potential for irreversible truncation or data loss | `ALTER TABLE ... ALTER COLUMN TYPE ...` | Create new column, dual-write & backfill, swap columns |
| **Compatibility Risk** | Probability of breaking active microservices | `ALTER TABLE ... RENAME COLUMN ...` | Add view alias / expand-contract deployment pattern |
| **Performance Risk** | Risk of sequential table scan or blocking reads | `CREATE INDEX ...` (without `CONCURRENTLY`) | Always specify `CREATE INDEX CONCURRENTLY` |

---

## Anti-Pattern Detection Matrix

| Severity | Anti-Pattern | Operational Lock Acquired | Recommended Mitigation |
| :--- | :--- | :--- | :--- |
| 🔴 **CRITICAL** | `DROP TABLE` / `DROP COLUMN` | `ACCESS EXCLUSIVE` | Deprecate in application code first; verify zero access via pg_stat_user_tables; take snapshot. |
| 🔴 **CRITICAL** | `ALTER COLUMN TYPE` | `ACCESS EXCLUSIVE` (Full table rewrite) | Dual-write pattern: add new column, backfill in batches, switch application reads. |
| 🔴 **CRITICAL** | `ADD CONSTRAINT ... FOREIGN KEY` | `SHARE ROW EXCLUSIVE` (Blocks writes) | Use `ADD CONSTRAINT ... NOT VALID`, validate in subsequent non-blocking transaction. |
| 🟡 **WARNING** | `CREATE INDEX` without `CONCURRENTLY` | `SHARE` (Blocks concurrent writes) | Use `CREATE INDEX CONCURRENTLY` outside transactional blocks. |
| 🟢 **SAFE** | `CREATE TABLE` / Add Nullable Column | `ROW EXCLUSIVE` / Minimal metadata lock | Safe for continuous deployment. |

---

## Installation & CLI Usage

### Prerequisites
- Python 3.10+
- `pip` or virtualenv

### 1. Installation

```powershell
# Clone the repository
git clone https://github.com/Pradeep-B28/Schema_Sentinel.git
cd Schema_Sentinel

# Setup virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

### 2. Static Analysis (Offline / CI-Friendly)

Analyze migration scripts without connecting to a database:
```powershell
# Run heuristic analysis
schema-sentinel analyze sample_migration.sql --no-db

# Enforce CI failure on critical / high-risk operations
schema-sentinel analyze sample_migration.sql --no-db --fail-on-high

# Output GitHub PR Markdown format
schema-sentinel analyze sample_migration.sql --no-db -f github

# Export machine-readable JSON
schema-sentinel analyze sample_migration.sql --no-db -f json > migration_report.json
```

### 3. Live Database Profiling

Query actual production/staging table size, row counts, and active lock contention before executing:
```powershell
# Analyze migration script with live database context
schema-sentinel analyze sample_migration.sql -c "postgresql://user:pass@localhost:5432/production_db"

# Profile an individual table's current bloat and active lock queue
schema-sentinel profile users -c "postgresql://user:pass@localhost:5432/production_db"
```

---

## GitHub Actions CI/CD Integration

Integrate Schema Sentinel into `.github/workflows/migration-check.yml` to prevent unsafe migrations from merging:

```yaml
name: Schema Migration Safety Gate

on:
  pull_request:
    paths:
      - '**/*.sql'
      - 'migrations/**'

jobs:
  schema-sentinel:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Schema Sentinel
        run: pip install schema-sentinel

      - name: Audit Migration Scripts
        run: |
          schema-sentinel analyze migrations/ --no-db --fail-on-high -f github >> $GITHUB_STEP_SUMMARY
```

---

## License

This project is licensed under the [MIT License](LICENSE).
