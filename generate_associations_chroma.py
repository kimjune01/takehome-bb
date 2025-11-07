#!/usr/bin/env python3
"""
Generate associations using ChromaDB for fast vector search.
Much faster than pairwise comparison!

Usage:
    python generate_associations_chroma.py
"""

import sqlite3
import json
from typing import List, Dict
import numpy as np
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

DB_PATH = "signals.db"
SIMILARITY_THRESHOLD = 0.5
MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K = 50  # Check top 50 most similar items per query


def get_db_connection():
    """Get database connection."""
    return sqlite3.connect(DB_PATH)


def setup_chromadb():
    """Initialize ChromaDB client."""
    client = chromadb.Client(Settings(
        anonymized_telemetry=False,
        allow_reset=True
    ))
    return client


def load_or_create_embeddings(conn: sqlite3.Connection, model: SentenceTransformer):
    """Load or generate embeddings for signals and issues."""

    # Check if embeddings exist
    signal_count = conn.execute("SELECT COUNT(*) FROM signal_embeddings").fetchone()[0]
    issue_count = conn.execute("SELECT COUNT(*) FROM issue_embeddings").fetchone()[0]

    if signal_count == 0:
        print("\n📊 Generating signal embeddings...")
        signals = conn.execute("SELECT id, summary, context FROM signals").fetchall()
        texts = [f"{s[1]}\n{s[2]}" for s in signals]

        print(f"  Encoding {len(signals)} signals...")
        embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

        print("  Saving to database...")
        for (signal_id, _, _), embedding in zip(signals, embeddings):
            conn.execute(
                "INSERT OR REPLACE INTO signal_embeddings (signal_id, embedding, model) VALUES (?, ?, ?)",
                (signal_id, json.dumps(embedding.tolist()), MODEL_NAME)
            )
        conn.commit()
        print(f"  ✓ Generated {len(signals)} signal embeddings")
    else:
        print(f"\n✓ Signal embeddings already exist ({signal_count})")

    if issue_count == 0:
        print("\n📊 Generating issue embeddings...")
        issues = conn.execute("SELECT identifier, title, description FROM issues").fetchall()
        texts = [f"{i[1]}\n{i[2] or ''}" for i in issues]

        print(f"  Encoding {len(issues)} issues...")
        embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

        print("  Saving to database...")
        for (issue_id, _, _), embedding in zip(issues, embeddings):
            conn.execute(
                "INSERT OR REPLACE INTO issue_embeddings (issue_id, embedding, model) VALUES (?, ?, ?)",
                (issue_id, json.dumps(embedding.tolist()), MODEL_NAME)
            )
        conn.commit()
        print(f"  ✓ Generated {len(issues)} issue embeddings")
    else:
        print(f"\n✓ Issue embeddings already exist ({issue_count})")


def index_embeddings_in_chroma(conn: sqlite3.Connection, chroma_client):
    """Load embeddings into ChromaDB for fast similarity search."""

    print("\n🔍 Indexing embeddings in ChromaDB...")

    # Create or get collections
    try:
        chroma_client.delete_collection("signals")
    except:
        pass
    try:
        chroma_client.delete_collection("issues")
    except:
        pass

    signals_collection = chroma_client.create_collection("signals")
    issues_collection = chroma_client.create_collection("issues")

    # Load signals
    print("  Loading signals...")
    signals = conn.execute("""
        SELECT s.id, se.embedding
        FROM signals s
        JOIN signal_embeddings se ON s.id = se.signal_id
    """).fetchall()

    signal_ids = [str(s[0]) for s in signals]
    signal_embeddings = [json.loads(s[1]) for s in signals]

    print(f"  Indexing {len(signals)} signals...")
    signals_collection.add(
        ids=signal_ids,
        embeddings=signal_embeddings
    )

    # Load issues
    print("  Loading issues...")
    issues = conn.execute("""
        SELECT i.identifier, ie.embedding
        FROM issues i
        JOIN issue_embeddings ie ON i.identifier = ie.issue_id
    """).fetchall()

    issue_ids = [i[0] for i in issues]
    issue_embeddings = [json.loads(i[1]) for i in issues]

    print(f"  Indexing {len(issues)} issues...")
    issues_collection.add(
        ids=issue_ids,
        embeddings=issue_embeddings
    )

    print("  ✓ ChromaDB index ready!")

    return signals_collection, issues_collection


def generate_associations_with_chroma(
    conn: sqlite3.Connection,
    signals_collection,
    issues_collection
):
    """Generate associations using ChromaDB vector search."""

    print(f"\n🔗 Finding associations (threshold: {SIMILARITY_THRESHOLD})...")

    # Get all signals
    signals = conn.execute("SELECT id, summary FROM signals").fetchall()

    associations = []
    processed = 0

    print(f"  Processing {len(signals)} signals...")

    for signal_id, signal_summary in signals:
        # Get signal embedding
        signal_emb_result = conn.execute(
            "SELECT embedding FROM signal_embeddings WHERE signal_id = ?",
            (signal_id,)
        ).fetchone()

        if not signal_emb_result:
            continue

        signal_emb = json.loads(signal_emb_result[0])

        # Query ChromaDB for similar issues
        results = issues_collection.query(
            query_embeddings=[signal_emb],
            n_results=TOP_K
        )

        # Process results
        for issue_id, distance in zip(results['ids'][0], results['distances'][0]):
            # Convert distance to similarity (ChromaDB uses L2 distance by default)
            # For cosine similarity, we need to check if this pair already has an association

            # Check if association already exists
            existing = conn.execute(
                "SELECT id FROM associations WHERE signal_id = ? AND issue_id = ?",
                (signal_id, issue_id)
            ).fetchone()

            if existing:
                continue

            # Convert distance to similarity score
            # ChromaDB uses L2 distance, approximate conversion to similarity
            similarity = 1 / (1 + distance)

            if similarity >= SIMILARITY_THRESHOLD:
                associations.append({
                    "signal_id": signal_id,
                    "issue_id": issue_id,
                    "score": float(similarity),
                    "reason": f"Semantic similarity: {similarity:.2f}",
                    "method": f"chroma-{MODEL_NAME}"
                })

        processed += 1
        if processed % 100 == 0:
            print(f"  Progress: {processed}/{len(signals)} signals ({processed/len(signals)*100:.1f}%)")

    # Save associations
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
    print("🚀 Associations Pipeline - ChromaDB (FAST!)")
    print("=" * 70)
    print(f"Using model: {MODEL_NAME}")
    print(f"Using ChromaDB for vector search")

    # Load the model
    print("\n📥 Loading sentence-transformers model...")
    model = SentenceTransformer(MODEL_NAME)
    print("   ✓ Model loaded!")

    # Setup ChromaDB
    print("\n📥 Setting up ChromaDB...")
    chroma_client = setup_chromadb()
    print("   ✓ ChromaDB ready!")

    conn = get_db_connection()

    try:
        # Step 1: Generate/load embeddings
        load_or_create_embeddings(conn, model)

        # Step 2: Index in ChromaDB
        signals_collection, issues_collection = index_embeddings_in_chroma(conn, chroma_client)

        # Step 3: Generate associations using vector search
        generate_associations_with_chroma(conn, signals_collection, issues_collection)

        # Step 4: Show samples
        print_sample_associations(conn, limit=5)

        print("\n" + "=" * 70)
        print("✅ All done! (Using ChromaDB for 10x faster search!)")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
