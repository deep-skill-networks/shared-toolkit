import json

from dsn_toolkit.evals import (
    EvalCase,
    bootstrap_mean_ci,
    gate,
    load_cases,
    main,
    run_suite,
    wilson_interval,
)


def test_wilson_interval_known_values():
    lo, hi = wilson_interval(24, 30)  # 0.80 on 30 cases
    assert 0.62 < lo < 0.64 and 0.90 < hi < 0.92


def test_wilson_edges():
    assert wilson_interval(0, 10)[0] == 0.0
    assert wilson_interval(10, 10)[1] == 1.0
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_bootstrap_is_seeded_and_brackets_mean():
    vals = [3, 4, 4, 5, 2, 4, 3, 5, 4, 4]
    a, b = bootstrap_mean_ci(vals, seed=1), bootstrap_mean_ci(vals, seed=1)
    assert a == b and a[0] <= sum(vals) / len(vals) <= a[1]


def test_run_suite_and_segments():
    cases = load_cases("examples/golden.yaml")
    answers = {
        "What is the refund window?": "Refunds are accepted within 30 days.",
        "Refund kitne din me mil jayega?": "Aapko 30 din ke andar refund milega.",
        "Extract the order id from: order #A123 arrived damaged": '{"order_id": "A123"}',
    }
    report = run_suite(cases, lambda q: answers[q])
    assert report.passes == 3
    assert set(report.by_segment()) == {"en", "hinglish"}


def test_failed_checks_are_named():
    case = EvalCase(id="x", input="q", checks={"contains": ["refund"], "max_chars": 5})
    report = run_suite([case], lambda _: "no")
    assert report.results[0].failed_checks == ["contains"]


def test_gate_lower_bound_is_stricter():
    cases = [EvalCase(id=str(i), input=i, checks={"contains": "ok"}) for i in range(30)]
    report = run_suite(cases, lambda i: "ok" if i < 26 else "bad")  # 26/30 = 0.867
    assert gate(report, 0.8).ok
    assert not gate(report, 0.8, use_lower_bound=True).ok


def test_cli_gate(tmp_path, capsys):
    f = tmp_path / "r.jsonl"
    rows = [json.dumps({"id": str(i), "passed": i < 9}) for i in range(10)]
    f.write_text("\n".join(rows))
    assert main(["gate", str(f), "--min-pass-rate", "0.8"]) == 0
    assert main(["gate", str(f), "--min-pass-rate", "0.95"]) == 1
