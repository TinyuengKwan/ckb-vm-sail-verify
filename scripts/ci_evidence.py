#!/usr/bin/env python3
"""Externally collect one successful release-evidence GitHub Actions run.

All GitHub operations are read-only.  The collector queries the run, its jobs
and artifacts, downloads the attested evidence bundle twice into new
directories, verifies the attestation, extracts the bundle, requires the
archived clean-room report to be byte-identical to the local one, replays the
archived case with the archived binaries, and fetches every job log.  The
resulting record is the clean_room slot's input for audit_release.py.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence_bundle
import release_common as common

ROOT = common.ROOT
require, sha, read = common.require, common.sha, common.read
BUNDLE_NAME = "vm-evidence.tar.gz"


def select_remote(run, jobs_payload, artifacts_payload, policy, run_id, candidate):
    cfg = policy["ci"]
    require(type(run) is dict and run.get("id") == run_id and run.get("head_sha") == candidate and
            run.get("event") in ("push", "workflow_dispatch") and run.get("conclusion") == "success" and
            run.get("path") == cfg["workflow"] and type(run.get("run_attempt")) is int, "remote run identity/result")
    rows = jobs_payload.get("jobs") if type(jobs_payload) is dict else None
    require(type(rows) is list and len(rows) == len(cfg["jobs"]), "remote job count")
    jobs = {}
    for row in rows:
        require(type(row) is dict and type(row.get("id")) is int and row.get("conclusion") == "success" and
                row.get("name") not in jobs, "remote job identity/result")
        jobs[row["name"]] = row
    require(set(jobs) == set(cfg["jobs"]), "remote job names")
    artifacts = artifacts_payload.get("artifacts") if type(artifacts_payload) is dict else None
    expected_name = cfg["artifact_name_prefix"] + candidate
    matches = [row for row in (artifacts or []) if type(row) is dict and row.get("name") == expected_name]
    require(len(matches) == 1 and type(matches[0].get("id")) is int and matches[0].get("expired") is False,
            "remote artifact identity/expiry")
    return jobs, matches[0]


def unique_bundle(directory):
    rows = sorted(Path(directory).glob("*.jsonl"))
    require(len(rows) == 1 and rows[0].is_file() and not rows[0].is_symlink(), "missing/ambiguous attestation bundle")
    return rows[0]


def collect(args, root=ROOT):
    out = Path(args.out).resolve()
    require(not out.exists() and not out.is_symlink(), "collector output already exists")
    require(common.GIT_OID.fullmatch(args.candidate or ""), "candidate must be a full commit OID")
    require(type(args.run_id) is int and args.run_id > 0, "positive run id required")
    policy = common.load_policy(root)
    repository, cfg = policy["repository"], policy["ci"]
    out.mkdir()
    report = {"schema_version": 2, "kind": "ci-evidence-v2", "status": "running", "candidate": args.candidate,
              "repository": repository, "boundaries": {"release_claimed": False, "week6_closed": False}}
    try:
        api = f"repos/{repository}/actions/runs/{args.run_id}"
        queries = {name: common.run_command(out, "query-" + name, ["gh", "api", api + suffix], root)
                   for name, suffix in [("run", ""), ("jobs", "/jobs"), ("artifacts", "/artifacts")]}
        for name, row in queries.items():
            require(row["exit_code"] == 0, "remote query failed: " + name)
        payloads = {name: read(out / row["stdout"]["path"]) for name, row in queries.items()}
        jobs, artifact = select_remote(payloads["run"], payloads["jobs"], payloads["artifacts"], policy, args.run_id, args.candidate)
        downloads = {}
        for label in ("first-download", "second-download"):
            record = common.run_command(out, label, ["gh", "run", "download", str(args.run_id), "--repo", repository,
                                                     "--name", artifact["name"], "--dir", label], out)
            require(record["exit_code"] == 0, "artifact download failed: " + label)
            downloads[label] = common.regular(out / label / BUNDLE_NAME)
        first, second = downloads["first-download"], downloads["second-download"]
        bundle_sha = sha(second)
        require(sha(first) == bundle_sha, "independent artifact downloads differ")
        attest_dir = out / "attestation"
        attest_dir.mkdir()
        fetched = common.run_command(out, "attestation-download", ["gh", "attestation", "download", str(second), "--repo", repository],
                                     attest_dir)
        require(fetched["exit_code"] == 0, "attestation download failed")
        attestation = unique_bundle(attest_dir)
        verified = common.run_command(out, "attestation-verify", ["gh", "attestation", "verify", str(second), "--repo", repository,
                                                                   "--bundle", str(attestation), "--signer-workflow",
                                                                   repository + "/" + cfg["workflow"], "--source-digest",
                                                                   args.candidate, "--deny-self-hosted-runners", "--format", "json"], out)
        require(verified["exit_code"] == 0, "attestation verification failed")
        extracted = out / "extracted"
        evidence_bundle.extract(second, bundle_sha, extracted)
        archived_report = extracted / evidence_bundle.CLEAN / "report.json"
        local_report = Path(root) / evidence_bundle.CLEAN / "report.json"
        require(local_report.is_file() and sha(local_report) == sha(archived_report),
                "archived clean-room report differs from the local evidence root")
        clean = extracted / evidence_bundle.CLEAN
        case = cfg["replay_case"]
        replay_argv = [str(clean / "runtime/ckb-vm-sail-diff"), "--sail-bin", str(clean / "replay-inputs/sail_riscv_sim"),
                       "--sail-config", str(clean / "replay-inputs/ckb_vm_config.json"),
                       "--replay", str(clean / "runtime/original" / (case + ".json")), "--artifact-dir", str(out / "replay-result")]
        (clean / "runtime/ckb-vm-sail-diff").chmod(0o755)
        (clean / "replay-inputs/sail_riscv_sim").chmod(0o755)
        replay = common.run_command(out, "replay", replay_argv, out)
        require(replay["exit_code"] == 0, "downloaded replay failed")
        job_records = {}
        for name in cfg["jobs"]:
            record = common.run_command(out, "job-log-" + name, ["gh", "api", f"repos/{repository}/actions/jobs/{jobs[name]['id']}/logs"], root)
            require(record["exit_code"] == 0, "job log download failed: " + name)
            job_records[name] = {"job_id": jobs[name]["id"], "conclusion": "success", "log": record["stdout"]}
        run = payloads["run"]
        report.update(
            status="passed",
            run={"run_id": args.run_id, "run_attempt": run["run_attempt"], "event": run["event"], "head_sha": run["head_sha"],
                 "conclusion": "success", "html_url": run["html_url"], "workflow_path": run["path"]},
            jobs=job_records,
            artifact={"name": artifact["name"], "artifact_id": artifact["id"], "expired": False, "sha256": bundle_sha,
                      "first_download": common.ref(out, first), "second_download": common.ref(out, second),
                      "attestation": common.ref(out, attestation)},
            attestation={k: verified[k] for k in ("argv", "exit_code", "stdout", "stderr")},
            clean_room={"report": common.ref(root, local_report), "bundle_sha256": bundle_sha,
                        "archived_report_sha256": sha(archived_report)},
            replay={"case": case, "argv": replay_argv, "exit_code": replay["exit_code"], "stdout": replay["stdout"], "stderr": replay["stderr"]},
            queries={name: {k: row[k] for k in ("argv", "exit_code", "stdout", "stderr")} for name, row in queries.items()})
        common.write(out / "report.json", report)
        import audit_release
        return audit_release.check_ci(out / "report.json", args.candidate, root)
    except BaseException:
        if not (out / "report.json").exists():
            report["status"] = "failed"
            common.write(out / "report.json", report)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(collect(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
