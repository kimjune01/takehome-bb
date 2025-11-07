#!/usr/bin/env python3
"""
Load signals and Linear issues into a simple SQLite database
Just 2 tables - signals and issues
"""

import json
import sqlite3


def create_tables(conn):
    """Create simple database schema"""
    cursor = conn.cursor()

    # Signals table - store everything as-is from JSON
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY,
            summary TEXT NOT NULL,
            context TEXT NOT NULL,
            sentiment INTEGER NOT NULL,
            severity INTEGER NOT NULL,
            bias INTEGER NOT NULL,
            date TEXT NOT NULL,
            boundary TEXT NOT NULL,
            method TEXT NOT NULL,
            topics TEXT,
            keywords TEXT,
            impacts TEXT,
            emotions TEXT
        )
    """)

    # Linear issues table - store everything as-is from JSON
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id TEXT PRIMARY KEY,
            identifier TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            state_name TEXT,
            state_type TEXT,
            team_name TEXT,
            team_key TEXT,
            assignee_name TEXT,
            assignee_email TEXT,
            creator_name TEXT,
            creator_email TEXT,
            priority INTEGER,
            estimate INTEGER,
            labels TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        )
    """)

    # Create indexes for common queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_date ON signals(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_team ON issues(team_key)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_state ON issues(state_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_identifier ON issues(identifier)")

    conn.commit()


def load_signals(conn, json_file='signals.json'):
    """Load signals from JSON into database"""
    print(f"Loading signals from {json_file}...")

    with open(json_file, 'r') as f:
        signals = json.load(f)

    print(f"Found {len(signals)} signals")

    cursor = conn.cursor()

    for signal in signals:
        # Convert arrays to JSON strings for storage
        topics_json = json.dumps([t['name'] for t in signal.get('topics', [])])
        keywords_json = json.dumps([k['name'] for k in signal.get('keywords', [])])
        impacts_json = json.dumps([i['name'] for i in signal.get('impacts', [])])
        emotions_json = json.dumps([e['name'] for e in signal.get('emotions', [])])

        cursor.execute("""
            INSERT INTO signals
            (id, summary, context, sentiment, severity, bias, date, boundary, method,
             topics, keywords, impacts, emotions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal['id'],
            signal['summary'],
            signal['context'],
            signal['sentiment'],
            signal['severity'],
            signal['bias'],
            signal['date'],
            signal['boundary'],
            signal['method'],
            topics_json,
            keywords_json,
            impacts_json,
            emotions_json
        ))

    conn.commit()
    print(f"✓ Loaded {len(signals)} signals")


def load_issues(conn, json_file='linear_issues.json'):
    """Load Linear issues from JSON into database"""
    print(f"Loading issues from {json_file}...")

    with open(json_file, 'r') as f:
        issues = json.load(f)

    print(f"Found {len(issues)} issues")

    cursor = conn.cursor()

    for issue in issues:
        # Extract nested data
        state = issue.get('state') or {}
        team = issue.get('team') or {}
        assignee = issue.get('assignee') or {}
        creator = issue.get('creator') or {}

        # Convert labels to JSON string
        labels = [l['name'] for l in issue.get('labels', {}).get('nodes', [])]
        labels_json = json.dumps(labels)

        cursor.execute("""
            INSERT INTO issues
            (id, identifier, title, description, state_name, state_type,
             team_name, team_key, assignee_name, assignee_email,
             creator_name, creator_email, priority, estimate, labels,
             created_at, updated_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            issue['id'],
            issue['identifier'],
            issue['title'],
            issue.get('description', ''),
            state.get('name'),
            state.get('type'),
            team.get('name'),
            team.get('key'),
            assignee.get('name'),
            assignee.get('email'),
            creator.get('name'),
            creator.get('email'),
            issue.get('priority'),
            issue.get('estimate'),
            labels_json,
            issue['createdAt'],
            issue['updatedAt'],
            issue.get('completedAt')
        ))

    conn.commit()
    print(f"✓ Loaded {len(issues)} issues")


def main():
    """Load all data into database"""
    db_file = 'signals.db'

    print(f"Creating database: {db_file}")
    print()

    conn = sqlite3.connect(db_file)

    try:
        # Create tables
        print("Creating tables...")
        create_tables(conn)
        print()

        # Load data
        load_signals(conn)
        load_issues(conn)

        # Print statistics
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM signals")
        signal_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM issues")
        issue_count = cursor.fetchone()[0]

        print()
        print("=" * 50)
        print("Database created successfully!")
        print("=" * 50)
        print(f"Tables: 2 (signals, issues)")
        print(f"Signals: {signal_count}")
        print(f"Issues: {issue_count}")
        print()

        # Sample queries
        print("Sample signal:")
        cursor.execute("SELECT id, summary, topics FROM signals LIMIT 1")
        row = cursor.fetchone()
        print(f"  ID: {row[0]}")
        print(f"  Summary: {row[1][:80]}...")
        print(f"  Topics: {row[2]}")

        print()
        print("Sample issue:")
        cursor.execute("SELECT identifier, title, team_name, state_name FROM issues LIMIT 1")
        row = cursor.fetchone()
        print(f"  ID: {row[0]}")
        print(f"  Title: {row[1][:80]}...")
        print(f"  Team: {row[2]}")
        print(f"  State: {row[3]}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
