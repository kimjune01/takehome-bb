#!/usr/bin/env python3
"""
Fetch Linear issues using GraphQL API and insert into database
"""

import os
import json
import sqlite3
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

LINEAR_API_URL = "https://api.linear.app/graphql"
LINEAR_API_KEY = os.getenv('LINEAR_API_KEY')
DB_PATH = 'signals.db'


def fetch_all_issues():
    """Fetch all issues from Linear with pagination"""

    if not LINEAR_API_KEY:
        raise ValueError("LINEAR_API_KEY not found in environment variables. Please set it in .env file")

    all_issues = []
    has_next_page = True
    cursor = None
    page = 1

    query_with_pagination = """
    query($first: Int!, $after: String) {
      issues(first: $first, after: $after) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          identifier
          title
          description
          state {
            name
            type
          }
          team {
            name
            key
          }
          assignee {
            name
            email
          }
          creator {
            name
            email
          }
          priority
          estimate
          labels {
            nodes {
              name
            }
          }
          createdAt
          updatedAt
          completedAt
        }
      }
    }
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": LINEAR_API_KEY
    }

    while has_next_page:
        variables = {
            "first": 100,
            "after": cursor
        }

        print(f"Fetching page {page}...")

        response = requests.post(
            LINEAR_API_URL,
            json={"query": query_with_pagination, "variables": variables},
            headers=headers
        )

        if response.status_code != 200:
            raise Exception(f"Query failed with status {response.status_code}: {response.text}")

        data = response.json()

        if "errors" in data:
            raise Exception(f"GraphQL errors: {data['errors']}")

        issues_data = data["data"]["issues"]
        issues = issues_data["nodes"]
        all_issues.extend(issues)

        page_info = issues_data["pageInfo"]
        has_next_page = page_info["hasNextPage"]
        cursor = page_info["endCursor"]

        print(f"  Fetched {len(issues)} issues (total: {len(all_issues)})")
        page += 1

    return all_issues


def insert_issues_to_db(issues):
    """Insert issues into the SQLite database."""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    insert_query = """
    INSERT OR REPLACE INTO issues (
        id, identifier, title, description, state_name, state_type,
        team_name, team_key, assignee_name, assignee_email,
        creator_name, creator_email, priority, estimate, labels,
        created_at, updated_at, completed_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    inserted_count = 0

    for issue in issues:
        # Extract label names
        labels = [label['name'] for label in issue.get('labels', {}).get('nodes', [])]
        labels_json = json.dumps(labels) if labels else None

        # Prepare data
        data = (
            issue['id'],
            issue['identifier'],
            issue['title'],
            issue.get('description'),
            issue['state']['name'] if issue.get('state') else None,
            issue['state']['type'] if issue.get('state') else None,
            issue['team']['name'] if issue.get('team') else None,
            issue['team']['key'] if issue.get('team') else None,
            issue['assignee']['name'] if issue.get('assignee') else None,
            issue['assignee']['email'] if issue.get('assignee') else None,
            issue['creator']['name'] if issue.get('creator') else None,
            issue['creator']['email'] if issue.get('creator') else None,
            issue.get('priority'),
            issue.get('estimate'),
            labels_json,
            issue['createdAt'],
            issue['updatedAt'],
            issue.get('completedAt'),
        )

        cursor.execute(insert_query, data)
        inserted_count += 1

    conn.commit()
    conn.close()

    print(f"✓ Inserted {inserted_count} issues into database")


def main():
    """Fetch and insert Linear issues"""
    print("Fetching Linear issues...")
    print()

    try:
        # Fetch issues from Linear
        issues = fetch_all_issues()

        print()
        print(f"✓ Fetched {len(issues)} total issues")
        print()

        # Insert into database
        print("Inserting into database...")
        insert_issues_to_db(issues)
        print()

        # Display some statistics
        teams = {}
        states = {}

        for issue in issues:
            team_name = issue["team"]["name"] if issue["team"] else "No Team"
            state_name = issue["state"]["name"] if issue["state"] else "No State"

            teams[team_name] = teams.get(team_name, 0) + 1
            states[state_name] = states.get(state_name, 0) + 1

        print("Issues by team:")
        for team, count in sorted(teams.items(), key=lambda x: x[1], reverse=True):
            print(f"  {team}: {count}")

        print()
        print("Issues by state:")
        for state, count in sorted(states.items(), key=lambda x: x[1], reverse=True):
            print(f"  {state}: {count}")

        print()
        print("✓ Done! All Linear issues have been synced to the database.")

    except Exception as e:
        print(f"✗ Error: {e}")
        raise


if __name__ == '__main__':
    main()
