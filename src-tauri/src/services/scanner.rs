use std::cmp::Ordering;
use std::fs;

use crate::domain::errors::DomainError;
use crate::domain::models::{
    DirectoryOverview, ItemKind, MatchOptions, MatchPage, MatchSnapshot, MatchedItem, ScanProgress,
};
use crate::domain::rules::RenameRule;
use crate::state::job_manager::CancellationToken;

pub fn list_root_items(root: &std::path::Path, limit: usize) -> Result<MatchPage, DomainError> {
    if !root.is_dir() {
        return Err(DomainError::InvalidRoot);
    }
    let entries = fs::read_dir(root).map_err(|error| DomainError::Io(error.to_string()))?;
    let mut items: Vec<_> = entries
        .filter_map(Result::ok)
        .filter_map(|entry| {
            let kind = match entry.file_type().ok()? {
                value if value.is_symlink() => return None,
                value if value.is_dir() => ItemKind::Directory,
                value if value.is_file() => ItemKind::File,
                _ => return None,
            };
            Some(MatchedItem {
                source: entry.path(),
                kind,
            })
        })
        .collect();
    items.sort_by(|left, right| {
        kind_rank(left.kind)
            .cmp(&kind_rank(right.kind))
            .then_with(|| natural_compare(&file_name(&left.source), &file_name(&right.source)))
    });
    let total = items.len();
    items.truncate(limit);
    Ok(MatchPage {
        items,
        total,
        offset: 0,
        limit,
    })
}

pub fn search_matches(
    options: &MatchOptions,
    cancel: &CancellationToken,
    mut progress: impl FnMut(ScanProgress),
) -> Result<MatchSnapshot, DomainError> {
    if !options.include_files && !options.include_dirs {
        return Err(DomainError::NoItemKinds);
    }

    let rule = RenameRule::compile(&options.search, "", options.use_regex, true)?;
    let mut items = Vec::new();
    let overview = walk_directory(
        &options.root,
        options.max_depth,
        cancel,
        |event, overview| {
            let warning = match event {
                WalkEvent::Item(path, kind) => {
                    let selected = match kind {
                        ItemKind::Directory => options.include_dirs,
                        ItemKind::File => options.include_files,
                    };
                    if selected
                        && rule.matches(&path.file_name().unwrap_or_default().to_string_lossy())?
                    {
                        items.push(MatchedItem {
                            source: path.to_path_buf(),
                            kind,
                        });
                    }
                    None
                }
                WalkEvent::Warning(message) => Some(message),
            };
            emit_progress(overview, items.len(), warning, &mut progress);
            Ok(())
        },
    )?;

    let mut snapshot = MatchSnapshot {
        root: options.root.clone(),
        search: options.search.clone(),
        use_regex: options.use_regex,
        items,
        warnings: overview.warnings,
        scanned_directory_count: overview.directories,
        scanned_file_count: overview.files,
    };

    snapshot.items.sort_by(|left, right| {
        kind_rank(left.kind)
            .cmp(&kind_rank(right.kind))
            .then_with(|| compare_parent_directories(&left.source, &right.source, &snapshot.root))
            .then_with(|| natural_compare(&file_name(&left.source), &file_name(&right.source)))
    });
    emit_progress(
        &DirectoryOverview {
            directories: snapshot.scanned_directory_count,
            files: snapshot.scanned_file_count,
            warnings: snapshot.warnings.clone(),
        },
        snapshot.items.len(),
        None,
        &mut progress,
    );
    Ok(snapshot)
}

pub fn inspect_directory(
    root: &std::path::Path,
    max_depth: Option<usize>,
    cancel: &CancellationToken,
) -> Result<DirectoryOverview, DomainError> {
    walk_directory(root, max_depth, cancel, |_, _| Ok(()))
}

enum WalkEvent<'a> {
    Item(&'a std::path::Path, ItemKind),
    Warning(String),
}

fn walk_directory(
    root: &std::path::Path,
    max_depth: Option<usize>,
    cancel: &CancellationToken,
    mut visit: impl FnMut(WalkEvent<'_>, &DirectoryOverview) -> Result<(), DomainError>,
) -> Result<DirectoryOverview, DomainError> {
    if !root.is_dir() {
        return Err(DomainError::InvalidRoot);
    }
    if max_depth == Some(0) {
        return Err(DomainError::InvalidDepth);
    }
    cancel.check()?;

    let mut overview = DirectoryOverview::default();
    let mut pending = vec![(root.to_path_buf(), 1_usize)];
    while let Some((parent, depth)) = pending.pop() {
        cancel.check()?;
        let entries = match fs::read_dir(&parent) {
            Ok(entries) => entries,
            Err(error) => {
                let warning = format!("无法读取 {}：{error}", parent.display());
                overview.warnings.push(warning.clone());
                visit(WalkEvent::Warning(warning), &overview)?;
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
                    overview.warnings.push(warning.clone());
                    visit(WalkEvent::Warning(warning), &overview)?;
                    continue;
                }
            };
            if file_type.is_symlink() {
                continue;
            }
            let kind = if file_type.is_dir() {
                overview.directories += 1;
                if max_depth.is_none_or(|maximum| depth < maximum) {
                    pending.push((path.clone(), depth + 1));
                }
                Some(ItemKind::Directory)
            } else if file_type.is_file() {
                overview.files += 1;
                Some(ItemKind::File)
            } else {
                None
            };
            if let Some(kind) = kind {
                visit(WalkEvent::Item(&path, kind), &overview)?;
            }
        }
    }
    Ok(overview)
}

fn emit_progress(
    overview: &DirectoryOverview,
    matched_total: usize,
    warning: Option<String>,
    progress: &mut impl FnMut(ScanProgress),
) {
    progress(ScanProgress {
        job_id: String::new(),
        phase: "扫描".into(),
        scanned_total: overview.directories + overview.files,
        scanned_directory_count: overview.directories,
        scanned_file_count: overview.files,
        matched_total,
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

fn compare_parent_directories(
    left: &std::path::Path,
    right: &std::path::Path,
    root: &std::path::Path,
) -> Ordering {
    let left_parent = left.parent().unwrap_or(root);
    let right_parent = right.parent().unwrap_or(root);
    let left_relative = left_parent.strip_prefix(root).unwrap_or(left_parent);
    let right_relative = right_parent.strip_prefix(root).unwrap_or(right_parent);
    let depth_order = left_relative
        .components()
        .count()
        .cmp(&right_relative.components().count());
    if depth_order != Ordering::Equal {
        return depth_order;
    }

    for (left_part, right_part) in left_relative.components().zip(right_relative.components()) {
        let order = natural_compare(
            &left_part.as_os_str().to_string_lossy(),
            &right_part.as_os_str().to_string_lossy(),
        );
        if order != Ordering::Equal {
            return order;
        }
    }
    Ordering::Equal
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
