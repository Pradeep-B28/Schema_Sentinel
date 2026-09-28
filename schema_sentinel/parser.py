"""Migration file parser — extracts structured operations from SQL."""

import re
from typing import List, Optional

import sqlparse
from sqlparse.sql import Identifier
from sqlparse.tokens import Comment, DDL, Keyword, Name, Whitespace

from .models import MigrationOperation, OperationType


def parse_migration_file(file_path: str) -> List[MigrationOperation]:
    """
    Parse a SQL migration file and extract all schema-changing operations.
    
    Returns:
        List of MigrationOperation objects in order of appearance.
    """
    content = None
    for enc in ("utf-8-sig", "utf-8", "utf-16", "latin1"):
        try:
            with open(file_path, "r", encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if content is None:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    
    statements = sqlparse.split(content)
    
    operations = []
    current_line = 1
    
    for stmt_text in statements:
        stmt_text = stmt_text.strip()
        if not stmt_text:
            continue
        
        op = _parse_statement(stmt_text, current_line)
        if op:
            operations.append(op)
        
        current_line += stmt_text.count("\n") + 1
    
    return operations


def _parse_statement(stmt_text: str, line_number: int) -> Optional[MigrationOperation]:
    """Parse a single SQL statement into a MigrationOperation."""
    stmt_text_lower = stmt_text.lower().strip()
    
    parsed = sqlparse.parse(stmt_text)
    if not parsed:
        return None
    
    token_list = parsed[0]
    first_token = None
    
    for token in token_list.flatten():
        if token.is_whitespace:
            continue
        if token.ttype is not None and token.ttype in (Comment, Comment.Single, Comment.Multiline):
            continue
        if token.ttype in (Keyword, DDL, Name):
            first_token = token
            break
    
    if not first_token:
        return None
    
    first_word = first_token.value.lower()
    
    # --- Operation type detection (checking full statement text) ---
    operation_type = OperationType.OTHER
    
    if first_word.startswith("create") and "table" in stmt_text_lower:
        operation_type = OperationType.CREATE_TABLE
    elif first_word.startswith("alter") and "table" in stmt_text_lower:
        operation_type = OperationType.ALTER_TABLE
    elif first_word.startswith("drop") and "table" in stmt_text_lower:
        operation_type = OperationType.DROP_TABLE
    elif first_word.startswith("create") and "index" in stmt_text_lower:
        operation_type = OperationType.CREATE_INDEX
    elif first_word.startswith("drop") and "index" in stmt_text_lower:
        operation_type = OperationType.DROP_INDEX
    elif first_word.startswith("rename") and "table" in stmt_text_lower:
        operation_type = OperationType.RENAME_TABLE
    elif "rename column" in stmt_text_lower:
        operation_type = OperationType.RENAME_COLUMN
    elif "add" in stmt_text_lower and "constraint" in stmt_text_lower:
        operation_type = OperationType.CREATE_CONSTRAINT
    elif "drop" in stmt_text_lower and "constraint" in stmt_text_lower:
        operation_type = OperationType.DROP_CONSTRAINT
    
    # Extract table name
    table_name = None
    if operation_type != OperationType.OTHER:
        if operation_type in (OperationType.CREATE_INDEX, OperationType.DROP_INDEX):
            table_name = _extract_table_name_from_index(stmt_text)
        else:
            table_name = _extract_table_name(stmt_text)
    
    return MigrationOperation(
        operation_type=operation_type,
        table_name=table_name,
        raw_statement=stmt_text,
        line_number=line_number,
    )


def _extract_table_name(stmt_text: str) -> Optional[str]:
    """Extract the table name from a SQL statement."""
    cleaned = re.sub(r'--[^\n]*', '', stmt_text)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'(if exists|if not exists)', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(public|schema)\.', '', cleaned)
    
    match = re.search(r'\b(table|index)\s+([a-zA-Z_][a-zA-Z0-9_$]*)', cleaned, re.IGNORECASE)
    if match:
        return match.group(2)
    
    parsed = sqlparse.parse(stmt_text)
    if parsed:
        for token in parsed[0].flatten():
            if token.ttype == Keyword and token.value.lower() in ('table', 'index'):
                next_token = token.next
                while next_token and (next_token.is_whitespace or 
                                      (next_token.ttype and next_token.ttype in (Comment, Comment.Single, Comment.Multiline))):
                    next_token = next_token.next
                if next_token and isinstance(next_token, Identifier):
                    return next_token.get_real_name()
    
    return None


def _extract_table_name_from_index(stmt_text: str) -> Optional[str]:
    """Extract table name from CREATE INDEX or DROP INDEX statements."""
    cleaned = re.sub(r'--[^\n]*', '', stmt_text)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
    match = re.search(r'\bon\s+([a-zA-Z_][a-zA-Z0-9_$]*)', cleaned, re.IGNORECASE)
    if match:
        return match.group(1)
    return None