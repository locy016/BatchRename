use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

use uuid::Uuid;

use crate::domain::errors::DomainError;
use crate::domain::models::{MatchSnapshot, PreviewResult};

#[derive(Debug, Clone, Default)]
pub struct CancellationToken(Arc<AtomicBool>);

impl CancellationToken {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn cancel(&self) {
        self.0.store(true, Ordering::Release);
    }

    pub fn is_cancelled(&self) -> bool {
        self.0.load(Ordering::Acquire)
    }

    pub fn check(&self) -> Result<(), DomainError> {
        if self.is_cancelled() {
            Err(DomainError::Cancelled)
        } else {
            Ok(())
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum JobType {
    Scan,
    Execute,
    Undo,
}

impl JobType {
    fn mutates_disk(self) -> bool {
        matches!(self, Self::Execute | Self::Undo)
    }
}

#[derive(Debug, Clone)]
pub struct JobHandle {
    pub id: String,
    pub kind: JobType,
    pub token: CancellationToken,
}

#[derive(Debug, Default)]
struct JobState {
    active: Option<JobHandle>,
    snapshot: Option<(String, MatchSnapshot)>,
    preview: Option<(String, PreviewResult)>,
}

#[derive(Debug, Clone, Default)]
pub struct JobManager(Arc<Mutex<JobState>>);

impl JobManager {
    pub fn begin(&self, kind: JobType) -> Result<JobHandle, DomainError> {
        let mut state = self.0.lock().expect("任务状态锁不应中毒");
        if let Some(active) = &state.active {
            if active.kind.mutates_disk() || kind.mutates_disk() {
                return Err(DomainError::Busy);
            }
            active.token.cancel();
        }
        let handle = JobHandle {
            id: Uuid::new_v4().simple().to_string(),
            kind,
            token: CancellationToken::new(),
        };
        state.active = Some(handle.clone());
        Ok(handle)
    }

    pub fn finish(&self, identifier: &str) {
        let mut state = self.0.lock().expect("任务状态锁不应中毒");
        if state
            .active
            .as_ref()
            .is_some_and(|job| job.id == identifier)
        {
            state.active = None;
        }
    }

    pub fn complete_scan(&self, identifier: &str, snapshot: MatchSnapshot) {
        let mut state = self.0.lock().expect("任务状态锁不应中毒");
        if state
            .active
            .as_ref()
            .is_some_and(|job| job.id == identifier)
        {
            state.snapshot = Some((identifier.to_owned(), snapshot));
            state.preview = None;
            state.active = None;
        }
    }

    pub fn save_preview(
        &self,
        identifier: &str,
        preview: PreviewResult,
    ) -> Result<(), DomainError> {
        let mut state = self.0.lock().expect("任务状态锁不应中毒");
        if state
            .snapshot
            .as_ref()
            .is_none_or(|(job_id, _)| job_id != identifier)
        {
            return Err(DomainError::StaleSnapshot);
        }
        state.preview = Some((identifier.to_owned(), preview));
        Ok(())
    }

    pub fn preview(&self, identifier: &str) -> Option<PreviewResult> {
        self.0
            .lock()
            .expect("任务状态锁不应中毒")
            .preview
            .as_ref()
            .filter(|(job_id, _)| job_id == identifier)
            .map(|(_, preview)| preview.clone())
    }

    pub fn snapshot(&self, identifier: &str) -> Option<MatchSnapshot> {
        self.0
            .lock()
            .expect("任务状态锁不应中毒")
            .snapshot
            .as_ref()
            .filter(|(job_id, _)| job_id == identifier)
            .map(|(_, snapshot)| snapshot.clone())
    }

    pub fn cancel_active(&self) {
        if let Some(active) = &self.0.lock().expect("任务状态锁不应中毒").active {
            active.token.cancel();
        }
    }
}
