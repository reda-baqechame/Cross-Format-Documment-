"""Morphological stemming in the shared search normalizer (_norm)."""

from __future__ import annotations

from docos.services.semantic.reader import _norm, _tokens


def test_norm_stems_morphological_variants():
    # Inflected forms collapse to a shared stem so queries match across word forms.
    assert _norm("renting") == _norm("rent")
    assert _norm("payments") == _norm("payment")
    assert _norm("processed") == _norm("processing")


def test_norm_does_not_conflate_distinct_words():
    # Stemming is morphology, not synonymy: unrelated words stay distinct.
    assert _norm("salary") != _norm("compensation")
    assert _norm("lease") != _norm("rent")


def test_tokens_match_across_inflection():
    a = _tokens("the tenant is renting the property")
    b = _tokens("rent paid by the tenant")
    # "renting"/"rent" and "tenant" overlap after stemming.
    assert _norm("rent") in a and _norm("rent") in b
    assert _norm("tenant") in (a & b)
