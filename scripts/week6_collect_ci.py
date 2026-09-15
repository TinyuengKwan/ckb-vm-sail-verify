#!/usr/bin/env python3
"""Externally download and record one successful Week6 GitHub Actions run.

All GitHub operations are read-only. The producer downloads the named artifact
twice into new directories, downloads the provenance bundle, extracts the
inner tar through the strict CI gate, replays the archived case, captures
run/job metadata and then invokes the existing fail-closed CI validator.
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile


def project_root():
    for parent in Path(__file__).resolve().parents:
        if (parent / "scripts/release_external_evidence.py").is_file():
            return parent
    raise RuntimeError("project root not found")


ROOT = project_root()
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_external_evidence as external
import release_evidence as common
import week6_release_ci_gate as gate


OID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def write(path, value):
    path = Path(path)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def ref(out, path):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink() and path.is_relative_to(out),
            "record reference outside output")
    return {"path": path.relative_to(out).as_posix(), "sha256": sha(path)}


def run_command(out, label, argv, cwd):
    stdout, stderr = out / (label + ".stdout"), out / (label + ".stderr")
    with stdout.open("xb") as a, stderr.open("xb") as b:
        result = subprocess.run(list(map(str, argv)), cwd=cwd, env=os.environ.copy(),
                                stdout=a, stderr=b, timeout=1800)
    return {"argv": list(map(str, argv)), "exit_code": result.returncode,
            "stdout": ref(out, stdout), "stderr": ref(out, stderr)}


def read_json(path, label):
    try:
        return common.read(path)
    except Exception as error:
        raise RuntimeError("invalid " + label + " JSON") from error


def select_remote(run, jobs_payload, artifacts_payload, policy, run_id, candidate):
    require(type(run) is dict and run.get("id") == run_id and run.get("head_sha") == candidate and
            run.get("event") in ("push", "workflow_dispatch") and run.get("conclusion") == "success" and
            run.get("path") == policy["ci_download"]["workflow"] and
            type(run.get("run_attempt")) is int and run["run_attempt"] > 0 and
            type(run.get("html_url")) is str and run["html_url"], "remote run identity/result")
    rows = jobs_payload.get("jobs") if type(jobs_payload) is dict else None
    require(type(rows) is list and len(rows) == len(policy["ci_download"]["required_jobs"]),
            "remote job count")
    jobs = {}
    for row in rows:
        require(type(row) is dict and type(row.get("id")) is int and row["id"] > 0 and
                row.get("conclusion") == "success" and type(row.get("name")) is str and
                row["name"] not in jobs, "remote job identity/result")
        jobs[row["name"]] = row
    require(set(jobs) == set(policy["ci_download"]["required_jobs"]), "remote job names")
    artifacts = artifacts_payload.get("artifacts") if type(artifacts_payload) is dict else None
    require(type(artifacts) is list, "remote artifact payload")
    expected_name = policy["ci_download"]["artifact_name_prefix"] + candidate
    matches = [row for row in artifacts if type(row) is dict and row.get("name") == expected_name]
    require(len(matches) == 1 and type(matches[0].get("id")) is int and matches[0]["id"] > 0 and
            matches[0].get("expired") is False, "remote artifact identity/expiry")
    return jobs, matches[0]


def manifest_bytes(archive):
    found = []
    with tarfile.open(archive, "r:gz") as stream:
        for member in stream:
            if member.name == "MANIFEST.json":
                require(member.isfile(), "archived manifest is not regular")
                source = stream.extractfile(member)
                require(source is not None, "archived manifest unreadable")
                found.append(source.read())
    require(len(found) == 1, "missing/duplicate archived manifest")
    return found[0]


def unique_bundle(directory):
    rows = sorted(Path(directory).glob("*.jsonl"))
    require(len(rows) == 1 and rows[0].is_file() and not rows[0].is_symlink(),
            "missing/ambiguous attestation bundle")
    return rows[0]


def collect(args):
    out = Path(args.out).resolve()
    require(not out.exists() and not out.is_symlink(), "collector output already exists")
    require(out.parent.is_dir() and not out.parent.is_symlink(), "collector output parent missing/linked")
    require(OID.fullmatch(args.candidate), "candidate must be a full Git OID")
    require(type(args.run_id) is int and args.run_id > 0, "positive run id required")
    policy = external.load_policy(ROOT)
    require(args.repository == policy["repository"], "repository differs from external policy")
    out.mkdir()
    report = {"schema_version": 1, "kind": "ci-download-evidence-v1", "status": "running",
              "candidate": args.candidate,
              "boundaries": {"remote_state_queried": False, "ci_download_verified": False,
                             "release_claimed": False, "week6_closed": False}}
    try:
        remote_argv = ["gh", "api", f"repos/{args.repository}/actions/runs/{args.run_id}"]
        remote = run_command(out, "remote-query", remote_argv, ROOT)
        require(remote["exit_code"] == 0, "remote run query failed")
        run = read_json(out / remote["stdout"]["path"], "remote run")

        jobs_argv = ["gh", "api", f"repos/{args.repository}/actions/runs/{args.run_id}/jobs"]
        jobs_record = run_command(out, "jobs-query", jobs_argv, ROOT)
        require(jobs_record["exit_code"] == 0, "remote jobs query failed")
        jobs_payload = read_json(out / jobs_record["stdout"]["path"], "remote jobs")

        artifacts_argv = ["gh", "api", f"repos/{args.repository}/actions/runs/{args.run_id}/artifacts"]
        artifacts_record = run_command(out, "artifacts-query", artifacts_argv, ROOT)
        require(artifacts_record["exit_code"] == 0, "remote artifacts query failed")
        artifacts_payload = read_json(out / artifacts_record["stdout"]["path"], "remote artifacts")
        jobs, artifact = select_remote(run, jobs_payload, artifacts_payload, policy, args.run_id, args.candidate)
        name = artifact["name"]

        first = out / "first-download"
        require(not first.exists(), "first download destination reused")
        first_record = run_command(out, "first-download", ["gh", "run", "download", str(args.run_id),
            "--repo", args.repository, "--name", name, "--dir", "first-download"], out)
        require(first_record["exit_code"] == 0, "first artifact download failed")

        downloaded = out / "downloaded"
        initially_absent = not downloaded.exists() and not downloaded.is_symlink()
        download_argv = ["gh", "run", "download", str(args.run_id), "--repo", args.repository,
                         "--name", name, "--dir", "downloaded"]
        download_record = run_command(out, "external-download", download_argv, out)
        require(initially_absent and download_record["exit_code"] == 0, "external artifact download failed/reused")
        upload_archive = first / "week6-evidence.tar.gz"
        download_archive = downloaded / "week6-evidence.tar.gz"
        require(upload_archive.is_file() and download_archive.is_file() and
                upload_archive.resolve() != download_archive.resolve() and
                sha(upload_archive) == sha(download_archive), "independent artifact downloads differ")

        inner_manifest, archive_sha = gate.extract_and_validate(download_archive, downloaded, args.candidate)
        top_manifest = downloaded / "MANIFEST.json"
        require(top_manifest.is_file() and not top_manifest.is_symlink() and
                top_manifest.read_bytes() == manifest_bytes(download_archive),
                "top-level and archived manifests differ")

        attest_dir = out / "attestation"
        attest_dir.mkdir()
        attest_record = run_command(out, "attestation-download",
            ["gh", "attestation", "download", str(download_archive), "--repo", args.repository], attest_dir)
        require(attest_record["exit_code"] == 0, "attestation download failed")
        attestation = unique_bundle(attest_dir)

        replay_name = inner_manifest["replay_case"]
        replay_source = downloaded / replay_name
        replay_argv = [str(downloaded / "bin/ckb-vm-sail-diff"),
                       "--sail-bin", str(downloaded / "bin/sail_riscv_sim"),
                       "--sail-config", str(downloaded / "config/ckb_vm_config.json"),
                       "--replay", str(replay_source),
                       "--artifact-dir", str(out / "replay-result")]
        replay_record = run_command(out, "replay", replay_argv, out)
        require(replay_record["exit_code"] == 0, "downloaded replay failed")

        job_records = {}
        for expected in policy["ci_download"]["required_jobs"]:
            row = jobs[expected]
            label = "job-" + expected
            record = run_command(out, label,
                ["gh", "api", f"repos/{args.repository}/actions/jobs/{row['id']}/logs"], ROOT)
            require(record["exit_code"] == 0, "job log download failed: " + expected)
            job_records[expected] = {"job_id": row["id"], "conclusion": "success", "log": record["stdout"]}

        clean_name = inner_manifest["clean_room_report"]
        clean_path = downloaded / clean_name
        clean_value = common.read(clean_path)
        source_ref = clean_value["source_snapshot"]
        source_path = clean_path.parent / source_ref["path"]
        require(source_path.is_file() and sha(source_path) == source_ref["sha256"],
                "clean-room source snapshot reference differs")
        report.update(
            status="passed",
            provider={"kind": policy["ci_download"]["provider"], "repository": args.repository,
                      "run_id": args.run_id, "run_attempt": run["run_attempt"], "event": run["event"],
                      "head_sha": run["head_sha"], "conclusion": "success", "html_url": run["html_url"]},
            workflow={"path": policy["ci_download"]["workflow"],
                      "sha256": sha(ROOT / policy["ci_download"]["workflow"])},
            source_snapshot=ref(out, source_path), clean_room=ref(out, clean_path), jobs=job_records,
            artifact={"name": name, "artifact_id": artifact["id"], "format": "tar.gz",
                      "sha256": archive_sha, "upload_archive": ref(out, upload_archive),
                      "download_archive": ref(out, download_archive), "manifest": ref(out, top_manifest),
                      "attestation": ref(out, attestation), "expired": False},
            external_download={**download_record, "destination_initially_absent": initially_absent},
            replay={"case": "add-signed-overflow", "source": "downloaded/" + replay_name,
                    "argv": replay_argv, "exit_code": replay_record["exit_code"],
                    "stdout": replay_record["stdout"], "stderr": replay_record["stderr"]},
            remote_query=remote, jobs_query=jobs_record,
            boundaries={"remote_state_queried": True, "ci_download_verified": True,
                        "release_claimed": False, "week6_closed": False})
        write(out / "report.json", report)
        validated = external.check_ci_download(out / "report.json", args.candidate, root=ROOT)
        require(validated["ci_download_verified"] is True and validated["remote_state_queried"] is True,
                "final CI evidence validation did not close its slot")
        return validated
    except BaseException:
        if not (out / "report.json").exists():
            report["status"] = "failed"
            write(out / "report.json", report)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="TinyuengKwan/ckb-vm-sail-verify")
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(collect(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
