#!/usr/bin/env python3
"""Check the user-facing documents for forbidden overclaims and broken links.

Scope is the fixed document list in docs/release/policy.json.  Dated process
records under docs/history/ are not checked: their wording describes the time
they were written.  This check does not validate evidence; the aggregator does.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
POLICY = "docs/release/policy.json"
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
STATUS_ROW = re.compile(r"^\|\s*([A-Za-z/ ]+?)\s*\|(?:[^|\n]*\|){5}\s*([a-z-]+)\s*\|[ \t]*$", re.MULTILINE)


def require(value, message):
    if not value:
        raise RuntimeError(message)


def load_policy(root):
    value = json.loads((Path(root) / POLICY).read_text())
    cfg = dict(value["public_claims"])
    require(type(cfg["documents"]) is list and cfg["documents"] and
            type(cfg["forbidden"]) is list and cfg["forbidden"], "public-claims policy incomplete")
    cfg["generated_roots"] = list(value["clean_room"]["generated_roots"])
    return cfg


def without_code(body):
    return re.sub(r"```.*?```", "", body, flags=re.DOTALL)


def check_links(root, name, body, generated):
    """Relative links must resolve inside the checkout.  Links into the ignored
    artifacts/ tree or a generated root are counted but not required to exist:
    evidence ships in the release package and generated models are rebuilt."""
    checked, evidence = 0, 0
    base = (Path(root) / name).parent
    for target in LINK.findall(without_code(body)):
        if target.startswith("#") or target.startswith("<"):
            continue
        parsed = urllib.parse.urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue
        decoded = urllib.parse.unquote(parsed.path)
        require(decoded and not Path(decoded).is_absolute(), "absolute/empty link in " + name + ": " + target)
        resolved = (base / decoded).resolve()
        require(resolved.is_relative_to(Path(root).resolve()), "escaping link in " + name + ": " + target)
        relative = resolved.relative_to(Path(root).resolve()).as_posix()
        if relative.split("/", 1)[0] == "artifacts" or any(
                relative == g or relative.startswith(g + "/") for g in generated):
            evidence += 1
            continue
        require(resolved.exists(), "broken link in " + name + ": " + target)
        checked += 1
    return checked, evidence


def check_coverage(body, allowed):
    rows = STATUS_ROW.findall(body)
    require(rows, "coverage matrix has no status rows")
    for family, status in rows:
        if family.strip().lower().startswith("instruction family") or set(family.strip()) <= set("-: "):
            continue
        require(status in allowed, "coverage status outside the allowed vocabulary: " + family.strip() + " = " + status)
    return len(rows)


def check(root=ROOT):
    root = Path(root)
    cfg = load_policy(root)
    result = {"documents": {}, "forbidden_phrases": len(cfg["forbidden"]), "status": "passed"}
    for name in cfg["documents"]:
        path = root / name
        require(path.is_file() and not path.is_symlink(), "public document missing: " + name)
        body = path.read_text()
        for phrase in cfg["forbidden"]:
            require(phrase not in body, "forbidden public overclaim in " + name + ": " + phrase)
        checked, evidence = check_links(root, name, body, cfg["generated_roots"])
        row = {"links_checked": checked, "evidence_links_not_shipped_with_source": evidence}
        if name == "docs/coverage.md":
            row["coverage_rows"] = check_coverage(body, cfg["coverage_status_values"])
        result["documents"][name] = row
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, help="write the JSON result here (new file)")
    args = parser.parse_args()
    try:
        result = check(args.root)
    except Exception as error:
        print("public claims rejected: " + str(error), file=sys.stderr)
        return 1
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x") as stream:
            stream.write(text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
