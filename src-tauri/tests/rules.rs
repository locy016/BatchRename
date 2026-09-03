use std::fs;
use std::path::PathBuf;

use batch_rename_lib::domain::rules::RenameRule;
use batch_rename_lib::domain::validation::validate_windows_name;
use serde::Deserialize;

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RuleFixture {
    id: String,
    search: String,
    replacement: String,
    input: String,
    is_file: bool,
    rename_extension: bool,
    expected_name: Option<String>,
    expected_error: Option<String>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct RuleFixtureSet {
    schema_version: u32,
    cases: Vec<RuleFixture>,
}

fn fixture_set() -> RuleFixtureSet {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("tests")
        .join("fixtures")
        .join("rules-v1.json");
    serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap()
}

#[test]
fn reproduces_all_stable_rule_fixtures() {
    let fixtures = fixture_set();
    assert_eq!(fixtures.schema_version, 1);

    for case in fixtures.cases {
        let use_regex = case.id.starts_with("template-") || case.id == "invalid-reference";
        let compiled = RenameRule::compile(
            &case.search,
            &case.replacement,
            use_regex,
            case.rename_extension,
        );
        match case.expected_error {
            Some(expected) => assert_eq!(compiled.unwrap_err().code(), expected, "{}", case.id),
            None => assert_eq!(
                compiled.unwrap().rename(&case.input, case.is_file).unwrap(),
                case.expected_name.unwrap(),
                "{}",
                case.id
            ),
        }
    }
}

#[test]
fn supports_python_named_and_numeric_replacement_references() {
    let rule = RenameRule::compile(
        r"(?P<label>[A-Z]+)-(\d+)",
        r"\g<2>_\g<label>_\1",
        true,
        false,
    )
    .unwrap();

    assert_eq!(rule.rename("ABC-007.txt", true).unwrap(), "007_ABC_ABC.txt");
}

#[test]
fn uses_advanced_engine_for_supported_lookbehind() {
    let rule = RenameRule::compile(r"(?<=项目)\d+", "编号", true, false).unwrap();
    assert_eq!(rule.rename("项目12.txt", true).unwrap(), "项目编号.txt");
}

#[test]
fn protects_file_extension_but_matches_the_full_name() {
    let rule = RenameRule::compile(r"(?i)\.txt$", ".md", true, false).unwrap();
    assert!(rule.matches("说明.TXT").unwrap());
    assert_eq!(rule.rename("说明.TXT", true).unwrap(), "说明.TXT");
}

#[test]
fn validates_windows_names_with_stable_error_codes() {
    assert!(validate_windows_name("正常名称.txt").is_ok());
    assert_eq!(validate_windows_name("").unwrap_err().code(), "emptyName");
    assert_eq!(
        validate_windows_name("CON.txt").unwrap_err().code(),
        "reservedName"
    );
    assert_eq!(
        validate_windows_name("错误?.txt").unwrap_err().code(),
        "invalidNameCharacter"
    );
    assert_eq!(
        validate_windows_name("尾随. ").unwrap_err().code(),
        "trailingDotOrSpace"
    );
}

#[test]
fn rejects_empty_search_and_overlong_regular_expressions() {
    assert_eq!(
        RenameRule::compile("", "", false, false)
            .unwrap_err()
            .code(),
        "emptySearch"
    );
    let pattern = "a".repeat(4097);
    assert_eq!(
        RenameRule::compile(&pattern, "", true, false)
            .unwrap_err()
            .code(),
        "regexTooLong"
    );
}
