import importlib.util
from pathlib import Path

import pytest

from dsn_toolkit.faults import Fault, FaultSet

spec = importlib.util.spec_from_file_location("provision", Path("scripts/provision.py"))
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)


def test_disabled_fault_is_a_no_op():
    fs = FaultSet([Fault("FS-RAG-03", "retrieval.chunker", {"chunk_size": 120}, enabled=False)])
    assert fs.apply("retrieval.chunker", {"chunk_size": 800}) == {"chunk_size": 800}


def test_enabled_fault_overrides():
    fs = FaultSet([Fault("FS-RAG-03", "retrieval.chunker", {"chunk_size": 120}, enabled=True)])
    assert fs.apply("retrieval.chunker", {"chunk_size": 800})["chunk_size"] == 120


def test_timestamp_fault_is_seeded():
    f = Fault("FS-COST-03", "prompt.prefix", {"inject": "timestamp"}, enabled=True, seed=42)
    a = FaultSet([f]).apply("prompt.prefix", "You are a helpful assistant.")
    b = FaultSet([f]).apply("prompt.prefix", "You are a helpful assistant.")
    assert a == b and a.startswith("[ts=")


def test_unknown_hook_point_rejected():
    with pytest.raises(ValueError):
        Fault("X", "nowhere")


def test_provision_dry_run(tmp_path, capsys):
    roster = tmp_path / "roster.csv"
    roster.write_text("github_username,batch\nasha-dev,b1\nravi99,b3\n")
    code = provision.main(
        [
            str(roster),
            "--cohort",
            "cohort-2027-01",
            "--template",
            "deep-skill-networks/capstone-template",
            "--kind",
            "capstone",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "deep-skill-networks/capstone-cohort-2027-01-asha-dev" in out
    assert "Dry run: 2 repos" in out


def test_provision_rejects_bad_batch(tmp_path):
    roster = tmp_path / "roster.csv"
    roster.write_text("github_username,batch\nasha-dev,b9\n")
    with pytest.raises(SystemExit):
        provision.read_roster(str(roster))
