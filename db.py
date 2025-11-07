"""
Database query functions for the associations pipeline.
"""

import sqlite3
from typing import List, Dict, Optional, Tuple

DB_PATH = "signals.db"


def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn


# ==================== ISSUES ====================

def get_all_issues_with_counts() -> List[Dict]:
    """Get all issues with their signal association counts."""
    conn = get_db_connection()
    query = """
    SELECT
        i.identifier,
        i.title,
        i.description,
        i.state_name,
        i.team_name,
        i.assignee_name,
        i.created_at,
        i.priority,
        COUNT(a.signal_id) as signal_count
    FROM issues i
    LEFT JOIN associations a ON a.issue_id = i.identifier
    GROUP BY i.identifier
    ORDER BY signal_count DESC, i.created_at DESC
    """
    results = conn.execute(query).fetchall()
    conn.close()
    return [dict(row) for row in results]


def get_issue_by_id(issue_id: str) -> Optional[Dict]:
    """Get a single issue by identifier."""
    conn = get_db_connection()
    query = """
    SELECT *
    FROM issues
    WHERE identifier = ?
    """
    result = conn.execute(query, (issue_id,)).fetchone()
    conn.close()
    return dict(result) if result else None


def get_signals_for_issue(issue_id: str, min_score: float = 0.0) -> List[Dict]:
    """Get all signals associated with an issue, ordered by score."""
    conn = get_db_connection()
    query = """
    SELECT
        s.*,
        a.score,
        a.reason,
        a.method
    FROM associations a
    JOIN signals s ON a.signal_id = s.id
    WHERE a.issue_id = ?
      AND a.score >= ?
    ORDER BY a.score DESC
    """
    results = conn.execute(query, (issue_id, min_score)).fetchall()
    conn.close()
    return [dict(row) for row in results]


# ==================== SIGNALS ====================

def get_all_signals_with_counts() -> List[Dict]:
    """Get all signals with their issue association counts."""
    conn = get_db_connection()
    query = """
    SELECT
        s.id,
        s.summary,
        s.context,
        s.sentiment,
        s.severity,
        s.date,
        COUNT(a.issue_id) as issue_count
    FROM signals s
    LEFT JOIN associations a ON a.signal_id = s.id
    GROUP BY s.id
    ORDER BY issue_count DESC, s.date DESC
    """
    results = conn.execute(query).fetchall()
    conn.close()
    return [dict(row) for row in results]


def get_signal_by_id(signal_id: int) -> Optional[Dict]:
    """Get a single signal by ID."""
    conn = get_db_connection()
    query = """
    SELECT *
    FROM signals
    WHERE id = ?
    """
    result = conn.execute(query, (signal_id,)).fetchone()
    conn.close()
    return dict(result) if result else None


def get_issues_for_signal(signal_id: int, min_score: float = 0.0) -> List[Dict]:
    """Get all issues associated with a signal, ordered by score."""
    conn = get_db_connection()
    query = """
    SELECT
        i.*,
        a.score,
        a.reason,
        a.method
    FROM associations a
    JOIN issues i ON a.issue_id = i.identifier
    WHERE a.signal_id = ?
      AND a.score >= ?
    ORDER BY a.score DESC
    """
    results = conn.execute(query, (signal_id, min_score)).fetchall()
    conn.close()
    return [dict(row) for row in results]


# ==================== ASSOCIATIONS ====================

def get_association(signal_id: int, issue_id: str) -> Optional[Dict]:
    """Get association details between a signal and issue."""
    conn = get_db_connection()
    query = """
    SELECT *
    FROM associations
    WHERE signal_id = ? AND issue_id = ?
    """
    result = conn.execute(query, (signal_id, issue_id)).fetchone()
    conn.close()
    return dict(result) if result else None


def get_associations_count() -> int:
    """Get total number of associations."""
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) FROM associations").fetchone()[0]
    conn.close()
    return count


def get_embeddings_status() -> Dict[str, int]:
    """Get status of embeddings generation."""
    conn = get_db_connection()

    signal_total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    signal_embedded = conn.execute("SELECT COUNT(*) FROM signal_embeddings").fetchone()[0]

    issue_total = conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
    issue_embedded = conn.execute("SELECT COUNT(*) FROM issue_embeddings").fetchone()[0]

    associations_count = conn.execute("SELECT COUNT(*) FROM associations").fetchone()[0]

    conn.close()

    return {
        "signal_total": signal_total,
        "signal_embedded": signal_embedded,
        "issue_total": issue_total,
        "issue_embedded": issue_embedded,
        "associations_count": associations_count
    }


# ==================== ADMIN ====================

def delete_all_data() -> Dict[str, int]:
    """Delete all data from the database (preserves schema).

    Returns counts of deleted records.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get counts before deletion
    signal_count = cursor.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    issue_count = cursor.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
    association_count = cursor.execute("SELECT COUNT(*) FROM associations").fetchone()[0]
    signal_embedding_count = cursor.execute("SELECT COUNT(*) FROM signal_embeddings").fetchone()[0]
    issue_embedding_count = cursor.execute("SELECT COUNT(*) FROM issue_embeddings").fetchone()[0]

    # Delete all data (cascade handled by foreign keys)
    cursor.execute("DELETE FROM associations")
    cursor.execute("DELETE FROM signal_embeddings")
    cursor.execute("DELETE FROM issue_embeddings")
    cursor.execute("DELETE FROM signals")
    cursor.execute("DELETE FROM issues")

    conn.commit()
    conn.close()

    # Vacuum to reclaim space (must be done after commit, outside transaction)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("VACUUM")
    conn.close()

    return {
        "signals": signal_count,
        "issues": issue_count,
        "associations": association_count,
        "signal_embeddings": signal_embedding_count,
        "issue_embeddings": issue_embedding_count
    }
