"""CLI entry point for CodeBouncer security scans."""

import argparse
import logging
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv

load_dotenv()

from bouncer_logic import scanner


def main():
    parser = argparse.ArgumentParser(
        description="CodeBouncer — AI-powered security scanner"
    )
    parser.add_argument("repo_url", help="GitHub repository URL to scan")
    parser.add_argument("--name", help="Repository name override")
    parser.add_argument("--deep", action="store_true", help="Force deep scan with Pro model")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Validate env vars
    required = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD", "GEMINI_API_KEY"]
    missing = [v for v in required if v not in os.environ]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}")
        print("Create a .env file — see .env.example")
        sys.exit(1)

    print(f"\n  CodeBouncer Security Scan")
    print(f"  Target: {args.repo_url}\n")

    result = scanner.run_security_scan(
        repo_url=args.repo_url,
        repo_name=args.name,
        deep_scan=args.deep,
    )

    # Print summary
    print(f"\n  Results")
    print(f"  Files scanned:  {result['total_files']}")
    print(f"  Files skipped:  {result['skipped_files']}")
    print(f"  Findings:       {result['total_findings']}")

    if result["errors"]:
        print(f"\n  Errors:")
        for err in result["errors"]:
            print(f"    {err['repo']}: {err['error']}")

    if result["total_findings"] > 0:
        print(f"\n  Run the dashboard to see details:")
        print(f"    streamlit run src/dashboard.py\n")
    else:
        print(f"\n  No vulnerabilities found.\n")


if __name__ == "__main__":
    main()
