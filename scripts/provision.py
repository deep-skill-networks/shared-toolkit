#!/usr/bin/env python3
"""Create each learner's private repos inside the org from template repos.

Dry run by default: prints what it would do. Pass --apply to call the GitHub REST API.

Roster CSV columns: github_username,batch   (batch = b1 | b2 | b3)

    python scripts/provision.py roster.csv --cohort cohort-2027-01 \
        --template deep-skill-networks/capstone-template --kind capstone [--apply]

Needs GITHUB_TOKEN with admin rights on the org (a fine-grained token or GitHub App token).
Repo name pattern: <kind>-<cohort>-<username>, e.g. capstone-cohort-2027-01-asha-dev.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
USER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


def repo_name(kind: str, cohort: str, user: str) -> str:
    return f"{kind}-{cohort}-{user}".lower()


def read_roster(path: str) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if not USER_RE.match(r.get("github_username", "")):
            raise SystemExit(f"invalid GitHub username: {r.get('github_username')!r}")
        if r.get("batch") not in {"b1", "b2", "b3"}:
            raise SystemExit(f"invalid batch for {r['github_username']}: {r.get('batch')!r}")
    return rows


def _call(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(
        API + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"{}")


def plan(rows: list[dict[str, str]], org: str, kind: str, cohort: str) -> list[dict[str, str]]:
    return [
        {
            "user": r["github_username"],
            "batch": r["batch"],
            "repo": f"{org}/{repo_name(kind, cohort, r['github_username'])}",
        }
        for r in rows
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("roster")
    ap.add_argument("--cohort", required=True)
    ap.add_argument("--template", required=True, help="owner/repo of the template")
    ap.add_argument("--kind", required=True, help="capstone, m01, m02, ...")
    ap.add_argument("--org", default="deep-skill-networks")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    steps = plan(read_roster(args.roster), args.org, args.kind, args.cohort)
    for s in steps:
        verb = "CREATE" if args.apply else "would create"
        print(f"{verb} {s['repo']} for @{s['user']} ({s['batch']})")
    if not args.apply:
        print(f"\nDry run: {len(steps)} repos. Re-run with --apply to create them.")
        return 0

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is not set", file=sys.stderr)
        return 1
    owner, template = args.template.split("/")
    failures = 0
    for s in steps:
        name = s["repo"].split("/")[1]
        status, body = _call(
            "POST",
            f"/repos/{owner}/{template}/generate",
            token,
            {
                "owner": args.org,
                "name": name,
                "private": True,
                "description": f"{args.kind} for @{s['user']} ({args.cohort}, {s['batch']})",
            },
        )
        if status not in (201, 422):  # 422 = already exists; safe to re-run
            print(f"FAILED {name}: {status} {body.get('message')}", file=sys.stderr)
            failures += 1
            continue
        status, body = _call(
            "PUT",
            f"/repos/{args.org}/{name}/collaborators/{s['user']}",
            token,
            {"permission": "push"},
        )
        if status not in (201, 204):
            print(
                f"FAILED invite @{s['user']} to {name}: {status} {body.get('message')}",
                file=sys.stderr,
            )
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
