---
name: security-audit
description: Analyzes code for OWASP vulnerabilities using Snowflake Cortex.
allowed-tools: [Read, Write, Bash]
---
# Skill: Security Audit Playbook

When auditing code, follow these steps:
1. **Identify Language:** Determine the file type (Python, JS, Ruby, etc.).
2. **Scan for Secrets:** Look for high-entropy strings or keys.
3. **Logic Check:** Look for Injection, Broken Auth, or Memory Safety issues.
4. **Draft Result:** Create a JSON finding with:
   - `severity`: (CRITICAL, HIGH, MEDIUM, LOW)
   - `vuln_type`: Name of the vulnerability.
   - `description`: How an attacker would exploit this.
   - `fix`: The corrected code snippet.

## Reference
See `docs/security_policy.md` for company-specific rules to enforce.