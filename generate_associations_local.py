#!/usr/bin/env python3
"""
Generate associations using local open-source embeddings (sentence-transformers).
No API calls, completely free, runs locally!

Usage:
    python generate_associations_local.py
"""

import sqlite3
import json
from typing import List, Dict
import numpy as np
from sentence_transformers import SentenceTransformer

DB_PATH = "signals.db"
SIMILARITY_THRESHOLD = 0.5
MODEL_NAME = "all-MiniLM-L6-v2"  # Small, fast model (~80MB)


def get_db_connection():
    """Get database connection."""
    return sqlite3.connect(DB_PATH)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def generate_signal_embeddings(conn: sqlite3.Connection, model: SentenceTransformer):
    """Generate and store embeddings for all signals."""
    print("\n📊 Generating signal embeddings...")

    # Get signals without embeddings
    query = """
    SELECT s.id, s.summary, s.context
    FROM signals s
    LEFT JOIN signal_embeddings se ON s.id = se.signal_id
    WHERE se.signal_id IS NULL
    """
    signals = conn.execute(query).fetchall()

    if not signals:
        print("  ✓ All signals already have embeddings")
        return

    print(f"  Processing {len(signals)} signals...")

    # Combine summary and context for each signal
    texts = [f"{s[1]}\n{s[2]}" for s in signals]

    # Generate embeddings in batch (fast!)
    print("  Encoding with local model...")
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    # Save to database
    print("  Saving to database...")
    for (signal_id, _, _), embedding in zip(signals, embeddings):
        conn.execute(
            "INSERT OR REPLACE INTO signal_embeddings (signal_id, embedding, model) VALUES (?, ?, ?)",
            (signal_id, json.dumps(embedding.tolist()), MODEL_NAME)
        )

    conn.commit()
    print(f"  ✓ Generated {len(signals)} signal embeddings")


def generate_issue_embeddings(conn: sqlite3.Connection, model: SentenceTransformer):
    """Generate and store embeddings for all issues."""
    print("\n📊 Generating issue embeddings...")

    # Get issues without embeddings
    query = """
    SELECT i.identifier, i.title, i.description
    FROM issues i
    LEFT JOIN issue_embeddings ie ON i.identifier = ie.issue_id
    WHERE ie.issue_id IS NULL
    """
    issues = conn.execute(query).fetchall()

    if not issues:
        print("  ✓ All issues already have embeddings")
        return

    print(f"  Processing {len(issues)} issues...")

    # Combine title and description
    texts = [f"{iss[1]}\n{iss[2] or ''}" for iss in issues]

    # Generate embeddings in batch
    print("  Encoding with local model...")
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    # Save to database
    print("  Saving to database...")
    for (issue_id, _, _), embedding in zip(issues, embeddings):
        conn.execute(
            "INSERT OR REPLACE INTO issue_embeddings (issue_id, embedding, model) VALUES (?, ?, ?)",
            (issue_id, json.dumps(embedding.tolist()), MODEL_NAME)
        )

    conn.commit()
    print(f"  ✓ Generated {len(issues)} issue embeddings")


def compute_associations(conn: sqlite3.Connection):
    """Compute similarities and create associations (incremental)."""
    print(f"\n🔗 Computing associations (threshold: {SIMILARITY_THRESHOLD})...")

    # Get only pairs that don't have associations yet (INCREMENTAL)
    print("  Finding pairs without associations...")
    pairs_to_process = conn.execute("""
        SELECT se.signal_id, se.embedding as signal_embedding,
               ie.issue_id, ie.embedding as issue_embedding
        FROM signal_embeddings se
        CROSS JOIN issue_embeddings ie
        LEFT JOIN associations a ON a.signal_id = se.signal_id AND a.issue_id = ie.issue_id
        WHERE a.id IS NULL  -- Only pairs without existing associations
    """).fetchall()

    if not pairs_to_process:
        print("  ✓ All pairs already have associations computed")
        return

    print(f"  Processing {len(pairs_to_process):,} new pairs...")

    associations = []
    comparisons_done = 0
    total_comparisons = len(pairs_to_process)

    for signal_id, signal_emb_json, issue_id, issue_emb_json in pairs_to_process:
        signal_emb = np.array(json.loads(signal_emb_json))
        issue_emb = np.array(json.loads(issue_emb_json))

        score = cosine_similarity(signal_emb, issue_emb)

        if score >= SIMILARITY_THRESHOLD:
            associations.append({
                "signal_id": signal_id,
                "issue_id": issue_id,
                "score": score,
                "reason": f"Semantic similarity: {score:.2f}",
                "method": f"local-{MODEL_NAME}"
            })

        comparisons_done += 1

        # Progress update every 10,000 pairs
        if comparisons_done % 10000 == 0:
            pct = (comparisons_done / total_comparisons) * 100
            print(f"  Progress: {comparisons_done:,}/{total_comparisons:,} comparisons ({pct:.1f}%)")

    # Save associations to database
    print(f"\n  Saving {len(associations):,} associations...")
    for assoc in associations:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO associations
                (signal_id, issue_id, score, reason, method)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    assoc["signal_id"],
                    assoc["issue_id"],
                    assoc["score"],
                    assoc["reason"],
                    assoc["method"]
                )
            )
        except Exception as e:
            print(f"  ⚠️  Error saving association: {e}")

    conn.commit()
    print(f"  ✓ Saved {len(associations):,} associations")

    # Print statistics
    if associations:
        scores = [a["score"] for a in associations]
        print(f"\n📈 Statistics:")
        print(f"  Total associations: {len(associations):,}")
        print(f"  Average score: {np.mean(scores):.3f}")
        print(f"  Min score: {np.min(scores):.3f}")
        print(f"  Max score: {np.max(scores):.3f}")
        print(f"  Median score: {np.median(scores):.3f}")

        # Score distribution
        high = len([s for s in scores if s >= 0.8])
        medium = len([s for s in scores if 0.5 <= s < 0.8])
        print(f"\n  Score distribution:")
        print(f"    High (≥0.8): {high:,} ({high/len(scores)*100:.1f}%)")
        print(f"    Medium (0.5-0.8): {medium:,} ({medium/len(scores)*100:.1f}%)")


def print_sample_associations(conn: sqlite3.Connection, limit: int = 5):
    """Print sample associations for verification."""
    print(f"\n🔍 Sample associations (top {limit}):")

    results = conn.execute("""
        SELECT
            a.score,
            s.summary,
            i.identifier,
            i.title
        FROM associations a
        JOIN signals s ON a.signal_id = s.id
        JOIN issues i ON a.issue_id = i.identifier
        ORDER BY a.score DESC
        LIMIT ?
    """, (limit,)).fetchall()

    for score, signal_summary, issue_id, issue_title in results:
        print(f"\n  Score: {score:.3f}")
        print(f"  Signal: {signal_summary[:80]}...")
        print(f"  Issue: {issue_id} - {issue_title[:60]}...")


def main():
    """Main execution."""
    print("=" * 70)
    print("🚀 Associations Pipeline - Local Embedding Generator (FREE!)")
    print("=" * 70)
    print(f"Using model: {MODEL_NAME}")

    # Load the model (downloads on first run, ~80MB)
    print("\n📥 Loading sentence-transformers model...")
    print("   (First run will download ~80MB model)")
    model = SentenceTransformer(MODEL_NAME)
    print("   ✓ Model loaded!")

    conn = get_db_connection()

    try:
        # Step 1: Generate signal embeddings
        generate_signal_embeddings(conn, model)

        # Step 2: Generate issue embeddings
        generate_issue_embeddings(conn, model)

        # Step 3: Compute associations
        compute_associations(conn)

        # Step 4: Show samples
        print_sample_associations(conn, limit=5)

        print("\n" + "=" * 70)
        print("✅ All done! (100% free, no API calls!)")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
