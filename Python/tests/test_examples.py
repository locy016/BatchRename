from batch_rename.core import RenameRule
from batch_rename.examples import REGEX_EXAMPLES


def test_every_regex_example_produces_its_documented_result():
    assert len(REGEX_EXAMPLES) >= 12
    assert len({example.category for example in REGEX_EXAMPLES}) >= 4

    for example in REGEX_EXAMPLES:
        rule = RenameRule(
            example.search,
            example.replacement,
            use_regex=True,
            rename_extension=example.rename_extension,
        )
        assert rule.rename(example.before, is_file=True) == example.after, example.title


def test_regex_examples_have_complete_user_facing_explanations():
    for example in REGEX_EXAMPLES:
        assert example.category.strip()
        assert example.title.strip()
        assert example.purpose.strip()
        assert example.search.strip()
        assert example.before != example.after
        assert isinstance(example.rename_extension, bool)
