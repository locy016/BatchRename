use std::cmp::Ordering;
use std::fs;

use crate::domain::errors::DomainError;
use crate::domain::models::{ItemKind, MatchOptions, MatchSnapshot, MatchedItem, ScanProgress};
use crate::domain::rules::RenameRule;
use crate::state::job_manager::CancellationToken;

pub fn search_matches(
    options: &MatchOptions,
    cancel: &CancellationToken,
    mut progress: impl FnMut(ScanProgress),
) -> Result<MatchSnapshot, DomainError> {
    if !options.root.is_dir() {
        return Err(DomainError::InvalidRoot);
    }
    if options.max_depth == Some(0) {
        return Err(DomainError::InvalidDepth);
    }
    if !options.include_files && !options.include_dirs {
        return Err(DomainError::NoItemKinds);
    }
    cancel.check()?;

    let rule = RenameRule::compile(&options.search, "", options.use_regex, true)?;
    let mut snapshot = MatchSnapshot {
        root: options.root.clone(),
        search: options.search.clone(),
        use_regex: options.use_regex,
        items: Vec::new(),
        warnings: Vec::new(),
        scanned_directory_count: 0,
        scanned_file_count: 0,
    };
    let mut pending = vec![(options.root.clone(), 1_usize)];

    while let Some((parent, depth)) = pending.pop() {
        cancel.check()?;
        let entries = match fs::read_dir(&parent) {
            Ok(entries) => entries,
            Err(error) => {
                let warning = format!("无法读取 {}：{error}", parent.display());
                snapshot.warnings.push(warning.clone());
                emit_progress(&snapshot, Some(warning), &mut progress);
                continue;
            }
        };
        let mut entries: Vec<_> = entries.filter_map(Result::ok).collect();
        entries.sort_by(|left, right| {
            natural_compare(
                &left.file_name().to_string_lossy(),
                &right.file_name().to_string_lossy(),
            )
        });

        for entry in entries {
            cancel.check()?;
            let path = entry.path();
            let file_type = match entry.file_type() {
                Ok(value) => value,
                Err(error) => {
                    let warning = format!("无法检查 {}：{error}", path.display());
                    snapshot.warnings.push(warning.clone());
                    emit_progress(&snapshot, Some(warning), &mut progress);
                    continue;
                }
            };
            if file_type.is_symlink() {
                continue;
            }
            let kind = if file_type.is_dir() {
                snapshot.scanned_directory_count += 1;
                if options.max_depth.is_none_or(|maximum| depth < maximum) {
                    pending.push((path.clone(), depth + 1));
                }
                Some(ItemKind::Directory)
            } else if file_type.is_file() {
                snapshot.scanned_file_count += 1;
                Some(ItemKind::File)
            } else {
                None
            };

            if let Some(kind) = kind {
                let selected = match kind {
                    ItemKind::Directory => options.include_dirs,
                    ItemKind::File => options.include_files,
                };
                if selected && rule.matches(&entry.file_name().to_string_lossy())? {
                    snapshot.items.push(MatchedItem { source: path, kind });
                }
                emit_progress(&snapshot, None, &mut progress);
            }
        }
    }

    snapshot.items.sort_by(|left, right| {
        kind_rank(left.kind)
            .cmp(&kind_rank(right.kind))
            .then_with(|| natural_compare(&file_name(&left.source), &file_name(&right.source)))
            .then_with(|| left.source.parent().cmp(&right.source.parent()))
    });
    emit_progress(&snapshot, None, &mut progress);
    Ok(snapshot)
}

fn emit_progress(
    snapshot: &MatchSnapshot,
    warning: Option<String>,
    progress: &mut impl FnMut(ScanProgress),
) {
    progress(ScanProgress {
        job_id: String::new(),
        phase: "扫描".into(),
        scanned_total: snapshot.scanned_directory_count + snapshot.scanned_file_count,
        matched_total: snapshot.items.len(),
        warning,
    });
}

fn kind_rank(kind: ItemKind) -> u8 {
    match kind {
        ItemKind::Directory => 0,
        ItemKind::File => 1,
    }
}

fn file_name(path: &std::path::Path) -> String {
    path.file_name()
        .unwrap_or_default()
        .to_string_lossy()
        .into_owned()
}

fn natural_compare(left: &str, right: &str) -> Ordering {
    let left = left.to_lowercase();
    let right = right.to_lowercase();
    let mut left_parts = NaturalParts::new(&left);
    let mut right_parts = NaturalParts::new(&right);
    loop {
        match (left_parts.next(), right_parts.next()) {
            (Some(NaturalPart::Number(a)), Some(NaturalPart::Number(b))) => {
                let order = a.cmp(&b);
                if order != Ordering::Equal {
                    return order;
                }
            }
            (Some(NaturalPart::Text(a)), Some(NaturalPart::Text(b))) => {
                let order = a.cmp(b);
                if order != Ordering::Equal {
                    return order;
                }
            }
            (Some(NaturalPart::Number(_)), Some(NaturalPart::Text(_))) => return Ordering::Greater,
            (Some(NaturalPart::Text(_)), Some(NaturalPart::Number(_))) => return Ordering::Less,
            (None, None) => return left.cmp(&right),
            (None, Some(_)) => return Ordering::Less,
            (Some(_), None) => return Ordering::Greater,
        }
    }
}

enum NaturalPart<'a> {
    Text(&'a str),
    Number(u128),
}

struct NaturalParts<'a> {
    value: &'a str,
    offset: usize,
}

impl<'a> NaturalParts<'a> {
    fn new(value: &'a str) -> Self {
        Self { value, offset: 0 }
    }
}

impl<'a> Iterator for NaturalParts<'a> {
    type Item = NaturalPart<'a>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.offset >= self.value.len() {
            return None;
        }
        let start = self.offset;
        let numeric = self.value[start..].chars().next()?.is_ascii_digit();
        for (relative, character) in self.value[start..].char_indices() {
            if character.is_ascii_digit() != numeric {
                self.offset = start + relative;
                let part = &self.value[start..self.offset];
                return Some(if numeric {
                    NaturalPart::Number(part.parse().unwrap_or(u128::MAX))
                } else {
                    NaturalPart::Text(part)
                });
            }
        }
        self.offset = self.value.len();
        let part = &self.value[start..];
        Some(if numeric {
            NaturalPart::Number(part.parse().unwrap_or(u128::MAX))
        } else {
            NaturalPart::Text(part)
        })
    }
}
