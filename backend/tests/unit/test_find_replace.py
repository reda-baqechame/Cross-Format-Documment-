"""Find & replace planner — deterministic, case/whole-word aware, redaction-safe."""

from __future__ import annotations

from docos.services.docengine.adapters.txt import TxtAdapter
from docos.services.docengine.find_replace import plan_find_replace


def _doc(text: bytes):
    return TxtAdapter().parse(text)


def _run_ids(doc):
    return [n.id for n in doc.nodes.values() if n.type == "run"]


def test_counts_occurrences_across_runs_case_insensitive():
    doc = _doc(b"foo bar foo\n\nFOO and foo\n\nplain block")
    replacements, total = plan_find_replace(doc, "foo", "X")
    assert total == 4  # 2 in run 0, 2 (FOO, foo) in run 1
    assert len(replacements) == 2
    assert {r.after for r in replacements} == {"X bar X", "X and X"}


def test_match_case_is_respected():
    doc = _doc(b"foo bar foo\n\nFOO and foo\n\nplain block")
    _replacements, total = plan_find_replace(doc, "foo", "X", match_case=True)
    assert total == 3  # FOO no longer matches


def test_whole_word_only_matches_standalone_tokens():
    doc = _doc(b"foofoo foo")
    _r, loose = plan_find_replace(doc, "foo", "X")
    assert loose == 3  # two inside "foofoo" + the standalone one
    _r, strict = plan_find_replace(doc, "foo", "X", whole_word=True)
    assert strict == 1


def test_replacement_is_literal_not_regex_backreference():
    doc = _doc(b"foo")
    replacements, total = plan_find_replace(doc, "foo", r"\1$&")
    assert total == 1
    assert replacements[0].after == r"\1$&"


def test_redacted_runs_are_skipped():
    doc = _doc(b"foo bar foo\n\nFOO and foo")
    run_ids = _run_ids(doc)
    doc.redaction.redacted_node_ids.append(run_ids[1])  # hide the second block
    replacements, total = plan_find_replace(doc, "foo", "X")
    assert total == 2  # only the first, non-redacted run
    assert len(replacements) == 1
    assert replacements[0].node_id == run_ids[0]


def test_empty_find_is_a_no_op():
    doc = _doc(b"foo bar")
    assert plan_find_replace(doc, "", "X") == ([], 0)
