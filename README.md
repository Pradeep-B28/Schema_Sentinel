<div align="center">

# 🔍 Schema Sentinel — PostgreSQL Pre-Migration Lock & Risk Analyzer

### *Detect Dangerous ALTER TABLE Commands, Exclusive Table Locks, and Schema Breaking Changes Before Production*

[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-12%20%7C%2014%20%7C%2016-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub_Actions_Gatekeeper-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)](action.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

<p align="center">
  <a href="#-overview">Overview</a> •
  <a href="#-detected-anti-patterns--risk-scoring">Risk Scoring</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-installation--cli-usage">CLI Usage</a> •
  <a href="#-github-action-cicd-integration">GitHub Action</a> •
  <a href="#-license--copyright">License & Copyright</a>
</p>

</div>

---

## 💡 Overview

Deploying schema migrations in high-throughput PostgreSQL production environments carries severe risks. Adding unindexed foreign keys, altering column types in-place, or executing non-concurrent index creations can acquire an `ACCESS EXCLUSIVE` lock—stalling active transactions and triggering catastrophic connection pool exhaustion.

**Schema Sentinel** is an automated static and live-profiling gatekeeper. It parses migration SQL statements, calculates multi-axis risk scores, optionally queries live table metadata for row counts and active locks, and blocks high-risk deployments before they impact production.

---

## 🛑 Detected Anti-Patterns & Risk Scoring

Schema Sentinel evaluates operations across a 4-axis risk matrix (scored 1 to 10):
- **Lock Risk**: Severity of the acquired lock (`ACCESS EXCLUSIVE` vs `SHARE UPDATE EXCLUSIVE`).
- **Data Integrity Risk**: Risk of irreversible data loss or truncation.
- **Compatibility Risk**: Probability of breaking downstream API contracts and queries.
- **Performance Risk**: Expected query degradation, table rewrites, or CPU stalls.

| Risk Level | Anti-Pattern SQL Operation | Technical Impact & Lock Mode | Safe Alternative |
| :--- | :--- | :--- | :--- |
| 🔴 **HIGH** | `DROP TABLE` / `DROP COLUMN` | Irreversible data destruction; breaks active queries immediately. | Mark column deprecated, remove code references, backup before drop. |
| 🔴 **HIGH** | `ALTER COLUMN TYPE` | Full table rewrite under `ACCESS EXCLUSIVE` lock. | Add new column with new type, dual-write & backfill, swap columns. |
| 🔴 **HIGH** | `RENAME TABLE` / `RENAME COLUMN` | Breaks active microservices and running transactions. | Create backwards-compatible view alias prior to renaming. |
| 🔴 **HIGH** | `ADD CONSTRAINT FOREIGN KEY` | Locks referenced and referencing tables to validate all rows. | Add with `NOT VALID`, then run `VALIDATE CONSTRAINT` asynchronously. |
| 🟡 **MEDIUM** | `CREATE INDEX` (without `CONCURRENTLY`) | Acquires `SHARE` lock, blocking all concurrent `INSERT`/`UPDATE`/`DELETE`. | Always use `CREATE INDEX CONCURRENTLY`. |
| 🟢 **LOW** | `CREATE TABLE` / Adding Nullable Column | Minimal metadata lock; non-blocking operation. | Standard safe deployment. |

---

## 🏗️ Architecture

```
                                  +-----------------------------+
                                  |     SQL MIGRATION FILE      |
                                  +--------------+--------------+
                                                 |
                                                 v
                                  +-----------------------------+
                                  |    Multi-Encoding Parser    |
                                  |  - sqlparse token traverse  |
                                  |  - Comment stripping & AST  |
                                  +--------------+--------------+
                                                 |
                         +-----------------------+-----------------------+
                         |                                               |
                         v (Static / Offline)                            v (Live Database)
          +-----------------------------+                 +-----------------------------+
          |     Heuristic Analyzer      |                 |      Database Profiler      |
          |  - Operation categorization |                 |  - Live Table Row Counts    |
          |  - Anti-pattern detection   |                 |  - Active pg_locks & bloat  |
          +--------------+--------------+                 +--------------+--------------+
                         |                                               |
                         +-----------------------+-----------------------+
                                                 |
                                                 v
                                  +-----------------------------+
                                  |     4-Axis Risk Scorer      |
                                  |  (Lock, Integrity, Compat,  |
                                  |         Performance)        |
                                  +--------------+--------------+
                                                 |
                 +-------------------------------+-------------------------------+
                 |                               |                               |
                 v                               v                               v
    +-------------------------+     +-------------------------+     +-------------------------+
    |  Human Console Output   |     |   GitHub PR Markdown    |     |    Structured JSON      |
    +-------------------------+     +-------------------------+     +-------------------------+
```

---

## 🚀 Installation & CLI Usage

### Prerequisites
- Python 3.10+
- `pip` or virtualenv

### 1. Installation
```powershell
# Clone the repository
git clone https://github.com/Pradeep-B28/Schema-Sentinel.git
cd Schema-Sentinel

# Setup virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

### 2. Analyzing Migration Files

```powershell
# Run heuristic-only analysis (no database required)
schema-sentinel analyze sample_migration.sql --no-db

# Run with connection to production/staging database
schema-sentinel analyze sample_migration.sql -c "postgresql://user:pass@localhost:5432/mydb"

# Fail CI build if any high-risk operations are detected
schema-sentinel analyze migration.sql --no-db --fail-on-high

# Generate GitHub PR comment format
schema-sentinel analyze migration.sql --no-db -f github

# Export machine-readable JSON report
schema-sentinel analyze migration.sql --no-db -f json > risk_report.json
```

### 3. Profiling Tables

```powershell
# Profile a specific production table's size, bloat, and active locks
schema-sentinel profile users -c "postgresql://user:pass@localhost:5432/mydb"
```

---

## 🐙 GitHub Action CI/CD Integration

Add Schema Sentinel to `.github/workflows/schema-sentinel.yml` to automatically review pull requests containing database migrations:

```yaml
name: Schema Sentinel Migration Audit

on:
  pull_request:
    paths:
      - '**/*.sql'

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Run Schema Sentinel Audit
        uses: Pradeep-B28/Schema-Sentinel@v1
        with:
          migration_file: 'sample_migration.sql'
          fail_on_high: 'true'
```

---

## 📄 License & Copyright

```
Copyright (c) 2026 Pradeep Basha (Pradeep-B28). All Rights Reserved.

Licensed under the MIT License. You may freely use, modify, and distribute
this project under the terms of the MIT license. See the LICENSE file for details.
```

Built with 🛡️ by **[Pradeep Basha](https://github.com/Pradeep-B28)**.
