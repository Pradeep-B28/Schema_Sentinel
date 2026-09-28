"""Command-line interface for Schema Sentinel."""

import sys
from pathlib import Path

# Ensure UTF-8 output encoding across platforms (e.g. Windows consoles)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import click

from .parser import parse_migration_file
from .models import OperationType
from .profiler import DatabaseProfiler
from .risk_analyzer import RiskAnalyzer, RiskLevel
from .ci_analyzer import CIAnalyzer


@click.group()
def main():
    """Schema Sentinel — Pre-migration risk analysis for database schema changes."""
    pass


@main.command()
@click.argument("migration_file", type=click.Path(exists=True))
@click.option("--connection", "-c", help="Database connection string (overrides DATABASE_URL)")
@click.option("--no-db", is_flag=True, help="Run without database connection (heuristic-only analysis)")
@click.option("--format", "-f", type=click.Choice(['human', 'github', 'json']), default='human',
              help="Output format (human, github-markdown, json)")
@click.option("--fail-on-high", is_flag=True,
              help="Exit with non-zero code if any high-risk operations are detected")
def analyze(migration_file, connection, no_db, format, fail_on_high):
    """
    Analyze a migration file for production risks.

    MIGRATION_FILE: Path to the SQL migration file to analyze.
    """
    click.echo(f"📄 Analyzing migration: {migration_file}")
    click.echo()

    # Parse migration file
    try:
        operations = parse_migration_file(migration_file)
    except Exception as e:
        click.echo(f"❌ Error parsing migration file: {e}", err=True)
        sys.exit(1)

    if not operations:
        click.echo("⚠️  No schema-changing operations found in this migration file.")
        return

    # Connect to database if requested
    profiler = None
    if not no_db:
        try:
            profiler = DatabaseProfiler(connection_string=connection)
            click.echo("✅ Connected to production database (read-only)")
            click.echo()
        except Exception as e:
            click.echo(f"⚠️  Could not connect to database: {e}")
            click.echo("   Running with heuristic-only analysis (no production stats)")
            click.echo()
            profiler = None

    # Create risk analyzer
    analyzer = RiskAnalyzer(profiler=profiler)

    # Analyze each operation and collect assessments
    assessments = []
    for op in operations:
        assessment = analyzer.analyze_operation(op)
        assessments.append(assessment)

    # Close profiler
    if profiler:
        profiler.close()

    # --- Output based on format ---
    if format == 'json':
        # JSON output
        ci = CIAnalyzer()
        json_output = ci.generate_json_output(assessments)
        click.echo(json_output)
    elif format == 'github':
        # GitHub Markdown output (for PR comments)
        ci = CIAnalyzer()
        github_comment = ci.generate_github_comment(assessments)
        click.echo(github_comment)
    else:
        # Human-readable output (default)
        click.echo(f"🔍 Found {len(operations)} schema-changing operation(s):")
        click.echo()

        high_risk_count = 0

        for i, assessment in enumerate(assessments, 1):
            click.echo(f"  {'='*50}")
            click.echo(f"  Operation {i}:")
            click.echo(assessment.get_summary())
            click.echo()

            if assessment.overall_level == RiskLevel.HIGH:
                high_risk_count += 1

        # Summary
        click.echo("  " + "=" * 50)
        click.echo()
        click.echo(f"📊 Summary: {len(operations)} operations analyzed")

        if high_risk_count > 0:
            click.echo(f"   🔴 {high_risk_count} operation(s) have HIGH risk")
            click.echo("   ⚠️  Review high-risk operations before deploying!")
        else:
            click.echo("   ✅ No high-risk operations detected")

        click.echo()
        click.echo("✅ Analysis complete!")

    # --- Fail on high risk ---
    if fail_on_high:
        high_risk_count = sum(1 for a in assessments if a.overall_level == RiskLevel.HIGH)
        if high_risk_count > 0:
            click.echo(f"❌ Failing build due to {high_risk_count} high-risk operation(s).", err=True)
            sys.exit(1)


@main.command()
@click.argument("table_name")
@click.option("--connection", "-c", help="Database connection string (overrides DATABASE_URL)")
def profile(table_name, connection):
    """
    Profile a table in the production database.

    TABLE_NAME: Name of the table to profile.
    """
    click.echo(f"📊 Profiling table: {table_name}")
    click.echo()

    try:
        profiler = DatabaseProfiler(connection_string=connection)
        summary = profiler.get_table_summary(table_name)

        if "error" in summary:
            click.echo(f"❌ {summary['error']}")
            profiler.close()
            return

        click.echo("📋 Table Statistics:")
        click.echo("  " + "-" * 50)
        click.echo(f"  Table Name:      {summary['table_name']}")
        click.echo(f"  Row Count:       {summary['row_count']}")
        click.echo(f"  Total Size:      {summary['total_size_mb']} MB")
        click.echo(f"  Table Size:      {summary['table_size_mb']} MB")
        click.echo(f"  Index Size:      {summary['index_size_mb']} MB")
        click.echo(f"  Columns:         {summary['column_count']}")
        click.echo(f"  Indexes:         {summary['index_count']}")
        click.echo(f"  Has Primary Key: {summary['has_primary_key']}")

        if summary['foreign_keys']:
            click.echo(f"  Foreign Keys:    {', '.join(summary['foreign_keys'])}")

        click.echo()
        click.echo("✅ Profiling complete!")

        profiler.close()

    except Exception as e:
        click.echo(f"❌ Error connecting to database: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()