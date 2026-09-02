use std::collections::HashSet;

use fancy_regex::{Regex as FancyRegex, RegexBuilder as FancyRegexBuilder};
use regex::Regex;

use crate::domain::errors::DomainError;

const MAX_REGEX_LENGTH: usize = 4096;

#[derive(Debug)]
enum RegexEngine {
    Standard(Regex),
    Advanced(FancyRegex),
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum ReplacementToken {
    Literal(String),
    Index(usize),
    Name(String),
}

#[derive(Debug)]
pub struct RenameRule {
    search: String,
    replacement: String,
    regex: Option<RegexEngine>,
    tokens: Vec<ReplacementToken>,
    rename_extension: bool,
}

impl RenameRule {
    pub fn compile(
        search: &str,
        replacement: &str,
        use_regex: bool,
        rename_extension: bool,
    ) -> Result<Self, DomainError> {
        if search.is_empty() {
            return Err(DomainError::EmptySearch);
        }
        if use_regex && search.chars().count() > MAX_REGEX_LENGTH {
            return Err(DomainError::RegexTooLong);
        }

        let (regex, tokens) = if use_regex {
            let tokens = parse_replacement(replacement)?;
            let engine = if needs_advanced_engine(search) {
                let mut builder = FancyRegexBuilder::new(search);
                builder.backtrack_limit(1_000_000);
                RegexEngine::Advanced(
                    builder
                        .build()
                        .map_err(|error| DomainError::InvalidRegex(error.to_string()))?,
                )
            } else {
                RegexEngine::Standard(
                    Regex::new(search)
                        .map_err(|error| DomainError::InvalidRegex(error.to_string()))?,
                )
            };
            validate_references(&engine, &tokens)?;
            (Some(engine), tokens)
        } else {
            (None, Vec::new())
        };

        Ok(Self {
            search: search.to_owned(),
            replacement: replacement.to_owned(),
            regex,
            tokens,
            rename_extension,
        })
    }

    pub fn matches(&self, name: &str) -> Result<bool, DomainError> {
        match &self.regex {
            Some(RegexEngine::Standard(pattern)) => Ok(pattern.is_match(name)),
            Some(RegexEngine::Advanced(pattern)) => pattern
                .is_match(name)
                .map_err(|error| DomainError::RegexRuntime(error.to_string())),
            None => Ok(name.contains(&self.search)),
        }
    }

    pub fn rename(&self, name: &str, is_file: bool) -> Result<String, DomainError> {
        let (target, suffix) = if is_file && !self.rename_extension {
            split_extension(name)
        } else {
            (name, "")
        };
        let renamed = match &self.regex {
            Some(RegexEngine::Standard(pattern)) => replace_standard(pattern, target, &self.tokens),
            Some(RegexEngine::Advanced(pattern)) => {
                replace_advanced(pattern, target, &self.tokens)?
            }
            None => target.replace(&self.search, &self.replacement),
        };
        Ok(format!("{renamed}{suffix}"))
    }
}

fn needs_advanced_engine(pattern: &str) -> bool {
    ["(?=", "(?!", "(?<=", "(?<!"]
        .iter()
        .any(|item| pattern.contains(item))
        || regex::Regex::new(r"\\[1-9]")
            .expect("静态表达式有效")
            .is_match(pattern)
}

fn split_extension(name: &str) -> (&str, &str) {
    let Some(dot) = name.rfind('.') else {
        return (name, "");
    };
    if name[..dot].trim_matches('.').is_empty() {
        return (name, "");
    }
    (&name[..dot], &name[dot..])
}

fn parse_replacement(replacement: &str) -> Result<Vec<ReplacementToken>, DomainError> {
    let mut tokens = Vec::new();
    let mut literal = String::new();
    let mut chars = replacement.chars().peekable();

    while let Some(character) = chars.next() {
        if character != '\\' {
            literal.push(character);
            continue;
        }
        let Some(escaped) = chars.next() else {
            return Err(DomainError::InvalidReplacementReference(
                "末尾反斜杠".into(),
            ));
        };
        if escaped == '\\' {
            literal.push('\\');
            continue;
        }
        if !literal.is_empty() {
            tokens.push(ReplacementToken::Literal(std::mem::take(&mut literal)));
        }
        if escaped.is_ascii_digit() && escaped != '0' {
            let mut digits = escaped.to_string();
            while chars.peek().is_some_and(char::is_ascii_digit) {
                digits.push(chars.next().expect("已经检查后续字符"));
            }
            tokens.push(ReplacementToken::Index(digits.parse().unwrap()));
            continue;
        }
        if escaped == 'g' && chars.next() == Some('<') {
            let mut reference = String::new();
            for part in chars.by_ref() {
                if part == '>' {
                    break;
                }
                reference.push(part);
            }
            if reference.is_empty() {
                return Err(DomainError::InvalidReplacementReference(
                    "空捕获引用".into(),
                ));
            }
            if reference.chars().all(|part| part.is_ascii_digit()) {
                tokens.push(ReplacementToken::Index(reference.parse().unwrap()));
            } else {
                tokens.push(ReplacementToken::Name(reference));
            }
            continue;
        }
        return Err(DomainError::InvalidReplacementReference(format!(
            "\\{escaped}"
        )));
    }
    if !literal.is_empty() {
        tokens.push(ReplacementToken::Literal(literal));
    }
    Ok(tokens)
}

fn validate_references(
    engine: &RegexEngine,
    tokens: &[ReplacementToken],
) -> Result<(), DomainError> {
    let (capture_count, names): (usize, HashSet<String>) = match engine {
        RegexEngine::Standard(pattern) => (
            pattern.captures_len(),
            pattern
                .capture_names()
                .flatten()
                .map(str::to_owned)
                .collect(),
        ),
        RegexEngine::Advanced(pattern) => (
            pattern.captures_len(),
            pattern
                .capture_names()
                .flatten()
                .map(str::to_owned)
                .collect(),
        ),
    };
    for token in tokens {
        match token {
            ReplacementToken::Index(index) if *index >= capture_count => {
                return Err(DomainError::InvalidReplacementReference(index.to_string()));
            }
            ReplacementToken::Name(name) if !names.contains(name) => {
                return Err(DomainError::InvalidReplacementReference(name.clone()));
            }
            _ => {}
        }
    }
    Ok(())
}

fn replace_standard(pattern: &Regex, text: &str, tokens: &[ReplacementToken]) -> String {
    let mut output = String::new();
    let mut last = 0;
    for captures in pattern.captures_iter(text) {
        let whole = captures.get(0).expect("完整匹配始终存在");
        output.push_str(&text[last..whole.start()]);
        expand_tokens(
            &mut output,
            tokens,
            |index| captures.get(index).map(|item| item.as_str()),
            |name| captures.name(name).map(|item| item.as_str()),
        );
        last = whole.end();
    }
    output.push_str(&text[last..]);
    output
}

fn replace_advanced(
    pattern: &FancyRegex,
    text: &str,
    tokens: &[ReplacementToken],
) -> Result<String, DomainError> {
    let mut output = String::new();
    let mut last = 0;
    for captures in pattern.captures_iter(text) {
        let captures = captures.map_err(|error| DomainError::RegexRuntime(error.to_string()))?;
        let whole = captures.get(0).expect("完整匹配始终存在");
        output.push_str(&text[last..whole.start()]);
        expand_tokens(
            &mut output,
            tokens,
            |index| captures.get(index).map(|item| item.as_str()),
            |name| captures.name(name).map(|item| item.as_str()),
        );
        last = whole.end();
    }
    output.push_str(&text[last..]);
    Ok(output)
}

fn expand_tokens<'a>(
    output: &mut String,
    tokens: &[ReplacementToken],
    mut by_index: impl FnMut(usize) -> Option<&'a str>,
    mut by_name: impl FnMut(&str) -> Option<&'a str>,
) {
    for token in tokens {
        match token {
            ReplacementToken::Literal(value) => output.push_str(value),
            ReplacementToken::Index(index) => {
                if let Some(value) = by_index(*index) {
                    output.push_str(value);
                }
            }
            ReplacementToken::Name(name) => {
                if let Some(value) = by_name(name) {
                    output.push_str(value);
                }
            }
        }
    }
}
