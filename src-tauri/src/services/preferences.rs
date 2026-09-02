use crate::domain::errors::DomainError;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Appearance {
    System,
    Light,
    Dark,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Preferences {
    pub appearance: Appearance,
}
#[derive(Debug, Clone)]
pub struct PreferencesStore {
    path: PathBuf,
}
impl PreferencesStore {
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self { path: path.into() }
    }
    pub fn default_for_user() -> Self {
        let base = std::env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("AppData").join("Local"));
        Self::new(base.join("BatchRename/settings.json"))
    }
    pub fn load(&self) -> Preferences {
        fs::read(&self.path)
            .ok()
            .and_then(|v| serde_json::from_slice(&v).ok())
            .unwrap_or(Preferences {
                appearance: Appearance::System,
            })
    }
    pub fn save(&self, appearance: Appearance) -> Result<(), DomainError> {
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent).map_err(|e| DomainError::Io(e.to_string()))?
        }
        fs::write(
            &self.path,
            serde_json::to_vec_pretty(&Preferences { appearance }).unwrap(),
        )
        .map_err(|e| DomainError::Io(e.to_string()))
    }
}
