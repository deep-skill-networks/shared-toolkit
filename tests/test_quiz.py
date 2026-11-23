import json

import pytest
import yaml

from dsn_toolkit.quiz import (
    QuizError,
    draw_attempts,
    load_bank,
    main,
    to_csv,
    to_forms_json,
    to_gift,
)


def make_item(i, week=1, **over):
    item = {
        "id": f"M01-Q{i:03d}",
        "module": "M01",
        "week": week,
        "pillar": "C2",
        "bloom": "Analyse",
        "difficulty": "medium",
        "spaced": True,
        "stem": f"Scenario {i}: what fails first?",
        "options": {"a": f"A{i}", "b": f"B{i}", "c": f"C{i}", "d": f"D{i}"},
        "correct": "b",
        "explanations": {"a": "no", "b": "yes", "c": "no", "d": "no"},
    }
    item.update(over)
    return item


def bank_file(tmp_path, items):
    p = tmp_path / "bank.yaml"
    p.write_text(yaml.safe_dump(items, allow_unicode=True))
    return p


def test_example_practice_bank_is_valid():
    assert len(load_bank("examples/practice-quiz.yaml")) == 2


@pytest.mark.parametrize(
    "over,msg",
    [
        ({"correct": "z"}, "not an option"),
        ({"bloom": "Memorise"}, "bloom"),
        ({"explanations": {"a": "x", "b": "y"}}, "explanation"),
        ({"module": "M09"}, "module"),
        ({"pillar": "C7"}, "pillar"),
    ],
)
def test_validation_errors(tmp_path, over, msg):
    with pytest.raises(QuizError, match=msg):
        load_bank(bank_file(tmp_path, [make_item(1, **over)]))


def test_duplicate_ids_rejected(tmp_path):
    with pytest.raises(QuizError, match="duplicate"):
        load_bank(bank_file(tmp_path, [make_item(1), make_item(1)]))


def test_two_attempts_disjoint_when_bank_allows(tmp_path):
    items = [make_item(i) for i in range(20)] + [make_item(100 + i, week=0) for i in range(6)]
    bank = load_bank(bank_file(tmp_path, items))
    a1, a2 = draw_attempts(bank, week=1, per_attempt=10, spaced=3, seed=7)
    new1 = {i.id for i in a1.items if i.week == 1}
    new2 = {i.id for i in a2.items if i.week == 1}
    assert len(new1) == len(new2) == 10 and not new1 & new2
    assert sum(i.week < 1 for i in a1.items) == 3
    assert draw_attempts(bank, 1, seed=7)[0].items == a1.items  # reproducible


def test_too_small_bank_errors(tmp_path):
    bank = load_bank(bank_file(tmp_path, [make_item(i) for i in range(5)]))
    with pytest.raises(QuizError, match="need at least"):
        draw_attempts(bank, week=1, per_attempt=10)


def test_gift_escapes_and_marks_answer(tmp_path):
    bank = load_bank(bank_file(tmp_path, [make_item(1, stem="Cost = tokens × price: why?")]))
    gift = to_gift(bank)
    assert "\\=" in gift and "\\:" in gift and "\t=B1#yes" in gift


def test_csv_has_expected_columns(tmp_path):
    bank = load_bank(bank_file(tmp_path, [make_item(1)]))
    header = to_csv(bank).splitlines()[0]
    assert header.startswith("question,option_a,option_b,option_c,option_d,correct,explanation")


def test_forms_json_marks_one_correct(tmp_path):
    items = [make_item(i) for i in range(10)]
    bank = load_bank(bank_file(tmp_path, items))
    payload = to_forms_json(draw_attempts(bank, 1, per_attempt=5, spaced=0)[0])
    assert all(sum(c["isCorrect"] for c in it["choices"]) == 1 for it in payload["items"])
    assert "attempt 1" in payload["title"]


def test_cli_draw_writes_two_files(tmp_path):
    bank = bank_file(tmp_path, [make_item(i) for i in range(12)])
    out = tmp_path / "exports"
    assert main(["draw", str(bank), "--week", "1", "--per-attempt", "5", "--out", str(out)]) == 0
    files = sorted(out.iterdir())
    assert [f.name for f in files] == ["week01-attempt1.json", "week01-attempt2.json"]
    assert json.loads(files[0].read_text())["items"]
