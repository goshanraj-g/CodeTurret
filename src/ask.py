"""CLI entry point for asking questions about scanned repositories."""

import argparse
import logging
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv

load_dotenv()

from bouncer_logic import config, repo_chat


def main():
    parser = argparse.ArgumentParser(
        description="CodeBouncer — Ask questions about scan results"
    )
    parser.add_argument("repo_name", help="Repository name (as stored in Snowflake)")
    parser.add_argument("question", help="Natural language question about the repo")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Validate env vars
    required = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD"]
    missing = [v for v in required if v not in os.environ]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}")
        print("Create a .env file — see .env.example")
        sys.exit(1)

    conn = config.get_snowflake_connection()
    try:
        print(f"\n  CodeBouncer Q&A")
        print(f"  Repo: {args.repo_name}")
        print(f"  Question: {args.question}\n")

        answer = repo_chat.ask_about_repo(conn, args.repo_name, args.question)
        print(f"  {answer}\n")

    except repo_chat.RepoChatError as exc:
        print(f"\n  Error: {exc}\n")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
