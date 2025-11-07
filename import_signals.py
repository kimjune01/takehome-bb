#!/usr/bin/env python3
"""
Import signals from a JSON file into the database.
"""

import json
import sqlite3
import sys


def import_signals(json_file_path, db_path='signals.db'):
    """Import signals from JSON file into database"""

    print(f"Loading signals from {json_file_path}...")

    try:
        with open(json_file_path, 'r') as f:
            signals = json.load(f)
    except FileNotFoundError:
        print(f"✗ Error: File not found: {json_file_path}")
        return False
    except json.JSONDecodeError as e:
        print(f"✗ Error: Invalid JSON format: {e}")
        return False

    if not isinstance(signals, list):
        print(f"✗ Error: JSON must be an array of signal objects")
        return False

    print(f"Found {len(signals)} signals")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    inserted = 0
    updated = 0
    errors = 0

    for signal in signals:
        try:
            # Validate required fields
            required_fields = ['id', 'summary', 'context', 'sentiment', 'severity',
                             'bias', 'date', 'boundary', 'method']
            for field in required_fields:
                if field not in signal:
                    print(f"⚠ Warning: Signal missing required field '{field}', skipping")
                    errors += 1
                    continue

            # Convert arrays to JSON strings for storage
            topics_json = json.dumps([t['name'] for t in signal.get('topics', [])])
            keywords_json = json.dumps([k['name'] for k in signal.get('keywords', [])])
            impacts_json = json.dumps([i['name'] for i in signal.get('impacts', [])])
            emotions_json = json.dumps([e['name'] for e in signal.get('emotions', [])])

            # Check if signal already exists
            cursor.execute("SELECT id FROM signals WHERE id = ?", (signal['id'],))
            exists = cursor.fetchone()

            # Insert or replace
            cursor.execute("""
                INSERT OR REPLACE INTO signals
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

            if exists:
                updated += 1
            else:
                inserted += 1

        except Exception as e:
            print(f"⚠ Warning: Error processing signal {signal.get('id', 'unknown')}: {e}")
            errors += 1
            continue

    conn.commit()
    conn.close()

    print()
    print(f"✓ Import complete!")
    print(f"  Inserted: {inserted} new signals")
    print(f"  Updated: {updated} existing signals")
    if errors > 0:
        print(f"  Errors: {errors} signals skipped")

    return True


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python import_signals.py <json_file_path>")
        sys.exit(1)

    json_file = sys.argv[1]
    success = import_signals(json_file)

    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
