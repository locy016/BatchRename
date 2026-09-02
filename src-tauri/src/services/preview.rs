use std::collections::HashMap;

use crate::domain::errors::DomainError;
use crate::domain::models::{
    CandidateStatus, ItemKind, MatchSnapshot, PreviewPage, PreviewResult, PreviewSummary,
    RenameCandidate,
};
use crate::domain::rules::RenameRule;
use crate::domain::validation::validate_windows_name;

const MAX_PAGE_SIZE: usize = 500;

pub fn build_preview(
    snapshot: &MatchSnapshot,
    replacement: &str,
    rename_extension: bool,
) -> Result<PreviewResult, DomainError> {
    let rule = RenameRule::compile(
        &snapshot.search,
        replacement,
        snapshot.use_regex,
        rename_extension,
    )?;
    let mut candidates = Vec::with_capacity(snapshot.items.len());

    for item in &snapshot.items {
        let is_file = item.kind == ItemKind::File;
        let old_name = item
            .source
            .file_name()
            .unwrap_or_default()
            .to_string_lossy();
        let new_name = rule.rename(&old_name, is_file)?;
        let target = item.source.with_file_name(&new_name);
        let (status, detail) = if new_name == old_name {
            let protected_extension = is_file
                && !rename_extension
                && item
                    .source
                    .file_stem()
                    .is_some_and(|stem| !rule.matches(&stem.to_string_lossy()).unwrap_or(false));
            if protected_extension {
                (
                    CandidateStatus::Unchanged,
                    "搜索内容位于受保护的文件扩展名中，因此名称没有变化".into(),
                )
            } else {
                (
                    CandidateStatus::Unchanged,
                    "名称符合搜索条件，但替换后没有变化".into(),
                )
            }
        } else if let Err(error) = validate_windows_name(&new_name) {
            (CandidateStatus::Invalid, error.to_string())
        } else if target.exists() && path_key(&target) != path_key(&item.source) {
            (
                CandidateStatus::Conflict,
                "同一目录中已存在该目标名称".into(),
            )
        } else {
            (CandidateStatus::Ready, "可以安全修改".into())
        };
        candidates.push(RenameCandidate {
            source: item.source.clone(),
            target,
            kind: item.kind,
            status,
            detail,
        });
    }

    let mut target_groups: HashMap<String, Vec<usize>> = HashMap::new();
    for (index, candidate) in candidates.iter().enumerate() {
        if candidate.status == CandidateStatus::Ready {
            target_groups
                .entry(path_key(&candidate.target))
                .or_default()
                .push(index);
        }
    }
    for group in target_groups.values().filter(|group| group.len() > 1) {
        for index in group {
            candidates[*index].status = CandidateStatus::Duplicate;
            candidates[*index].detail = "多个来源会生成同一个目标名称".into();
        }
    }

    let summary = summarize(&candidates);
    Ok(PreviewResult {
        root: snapshot.root.clone(),
        candidates,
        summary,
        warnings: snapshot.warnings.clone(),
    })
}

pub fn preview_page(result: &PreviewResult, offset: usize, limit: usize) -> PreviewPage {
    let limit = limit.clamp(1, MAX_PAGE_SIZE);
    let items = result
        .candidates
        .iter()
        .skip(offset)
        .take(limit)
        .cloned()
        .collect();
    PreviewPage {
        items,
        total: result.candidates.len(),
        offset,
        limit,
        summary: result.summary.clone(),
        warnings: result.warnings.clone(),
    }
}

fn summarize(candidates: &[RenameCandidate]) -> PreviewSummary {
    let mut summary = PreviewSummary {
        matched: candidates.len(),
        ..PreviewSummary::default()
    };
    for candidate in candidates {
        match candidate.status {
            CandidateStatus::Ready => summary.ready += 1,
            CandidateStatus::Unchanged => summary.unchanged += 1,
            CandidateStatus::Conflict | CandidateStatus::Duplicate => summary.conflicts += 1,
            CandidateStatus::Invalid | CandidateStatus::Error => summary.invalid += 1,
        }
    }
    summary
}

fn path_key(path: &std::path::Path) -> String {
    path.to_string_lossy().replace('/', "\\").to_lowercase()
}
