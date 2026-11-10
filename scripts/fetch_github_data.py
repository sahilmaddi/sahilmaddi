#!/usr/bin/env python3
"""Fetch the data the README cards need.

Writes data/contributions.json (the last year's contribution calendar) and
data/repos.json (pinned repos + recently pushed public repos).

Env:
  GH_LOGIN  GitHub username (the Action passes the repo owner)
  GH_TOKEN  token for the GraphQL API. The Action's GITHUB_TOKEN works for public
            data. Without a token, the calendar is read from the public profile page.

Standard library only. If GitHub can't be reached, the previous data is kept so
the cards still render.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("DATA_DIR", os.path.join(ROOT, "data"))
LOGIN = os.environ.get("GH_LOGIN") or os.environ.get("GITHUB_REPOSITORY_OWNER")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
NOW = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

REPO_FIELDS = """name description url stargazerCount forkCount isFork pushedAt
  primaryLanguage { name color } repositoryTopics(first: 6) { nodes { topic { name } } }"""
QUERY = """query($login: String!) {
  user(login: $login) {
    login
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
    pinnedItems(first: 6, types: REPOSITORY) { nodes { ... on Repository { %s } } }
    repositories(first: 20, ownerAffiliations: OWNER, privacy: PUBLIC,
                 orderBy: { field: PUSHED_AT, direction: DESC }) {
      totalCount
      nodes { %s }
    }
  }
}""" % (REPO_FIELDS, REPO_FIELDS)


def http(url, body=None, headers=None):
    req = urllib.request.Request(url, data=body, headers={"User-Agent": "readme-cards", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def repo(n):
    return {
        "name": n["name"],
        "description": n.get("description"),
        "url": n["url"],
        "stars": n.get("stargazerCount", 0),
        "forks": n.get("forkCount", 0),
        "fork": n.get("isFork", False),
        "pushed_at": n.get("pushedAt"),
        "language": n.get("primaryLanguage"),
        "topics": [t["topic"]["name"] for t in (n.get("repositoryTopics") or {}).get("nodes", [])],
    }


def via_graphql():
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    res = json.loads(http("https://api.github.com/graphql", body,
                          {"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"}))
    if res.get("errors"):
        raise RuntimeError(res["errors"])
    u = res["data"]["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = [{"date": d["date"], "count": d["contributionCount"], "level": LEVELS.get(d["contributionLevel"], 0)}
            for w in cal["weeks"] for d in w["contributionDays"]]
    contrib = {"login": u["login"], "total": cal["totalContributions"], "source": "graphql", "fetched_at": NOW, "days": days}
    repos = {"login": u["login"], "public_repos": u["repositories"]["totalCount"], "fetched_at": NOW,
             "pinned": [repo(n) for n in u["pinnedItems"]["nodes"] if n],
             "recent": [repo(n) for n in u["repositories"]["nodes"]]}
    return contrib, repos


def via_html():
    """Fallback: read the calendar GitHub draws on the public profile."""
    page = http(f"https://github.com/users/{LOGIN}/contributions")
    tips = {m.group(1): m.group(2) for m in re.finditer(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page)}
    days = []
    for m in re.finditer(r'<td[^>]*class="ContributionCalendar-day"[^>]*>', page):
        tag = m.group(0)
        date = re.search(r'data-date="([\d-]+)"', tag)
        cid = re.search(r'id="([^"]+)"', tag)
        level = re.search(r'data-level="(\d)"', tag)
        if not date:
            continue
        tip = tips.get(cid.group(1) if cid else "", "")
        n = re.match(r"\s*([\d,]+) contribution", tip)
        days.append({"date": date.group(1), "count": int(n.group(1).replace(",", "")) if n else 0,
                     "level": int(level.group(1)) if level else 0})
    days.sort(key=lambda d: d["date"])
    if not days:
        raise RuntimeError("no calendar cells found")
    return {"login": LOGIN, "total": sum(d["count"] for d in days), "source": "html", "fetched_at": NOW, "days": days}


def save(name, obj):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)


def main():
    if not LOGIN:
        sys.exit("Set GH_LOGIN to your GitHub username")
    try:
        if not TOKEN:
            raise RuntimeError("no token")
        contrib, repos = via_graphql()
        save("contributions.json", contrib)
        save("repos.json", repos)
        print(f"graphql: {contrib['total']} contributions, {len(repos['pinned'])} pinned repos")
        return
    except Exception as e:  # noqa: BLE001
        print(f"graphql unavailable ({e}); trying the profile page", file=sys.stderr)
    try:
        contrib = via_html()
        save("contributions.json", contrib)
        print(f"html: {contrib['total']} contributions (repos.json left as is)")
    except Exception as e:  # noqa: BLE001
        if os.path.exists(os.path.join(DATA, "contributions.json")):
            print(f"fetch failed ({e}); keeping previous data", file=sys.stderr)
        else:
            sys.exit(f"fetch failed and no previous data: {e}")


if __name__ == "__main__":
    main()
