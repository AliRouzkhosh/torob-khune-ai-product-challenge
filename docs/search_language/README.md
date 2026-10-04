# KhaneYab Persian Search Language Pack v0.2

This package is the expanded language specification for the KhaneYab housing-search demo.

## Files

- `SEARCH_LANGUAGE_SPEC.yaml`
  - canonical intent concepts
  - normalization
  - NEW_SEARCH / PATCH semantics
  - evidence policy
  - precedence
  - conditional and fallback grammar

- `SEARCH_LANGUAGE_PHRASE_BANK.yaml`
  - expanded Persian synonyms
  - colloquial forms
  - common spelling variants
  - Tehran-market terminology
  - positive / negative / required / preferred phrase families

- `SEARCH_LANGUAGE_REGRESSION.yaml`
  - 320 unique utterances with expected partial semantics
  - direct queries
  - patches
  - contextual references
  - conditional rules
  - fallback rules
  - colloquial Persian
  - evidence-awareness tests

- `COVERAGE_REPORT.md`
  - coverage counts and recommended implementation order

- `IMPLEMENTATION_STATUS.md`
  - cumulative implementation contracts and historical batch coverage

## Important architecture rule

This is **not** intended to become a giant sequence of `if phrase in text` statements.

The YAML is the declarative source of truth. The parser should use reusable mechanisms for normalization,
phrase families, quantifiers, negation, priority, contextual references, conditionals, and staged fallback.

Unsupported or missing listing evidence must degrade to `unknown`, never fabricated facts.
