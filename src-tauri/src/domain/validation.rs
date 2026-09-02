use crate::domain::errors::DomainError;

const RESERVED_NAMES: [&str; 22] = [
    "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8",
    "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
];

pub fn validate_windows_name(name: &str) -> Result<(), DomainError> {
    if name.is_empty() {
        return Err(DomainError::EmptyName);
    }
    if matches!(name, "." | "..") {
        return Err(DomainError::DotName);
    }
    if name.chars().count() > 255 {
        return Err(DomainError::NameTooLong);
    }
    if name
        .chars()
        .any(|character| character < ' ' || r#"<>:"/\|?*"#.contains(character))
    {
        return Err(DomainError::InvalidNameCharacter);
    }
    if name.ends_with([' ', '.']) {
        return Err(DomainError::TrailingDotOrSpace);
    }
    let stem = name.split('.').next().unwrap_or_default().to_uppercase();
    if RESERVED_NAMES.contains(&stem.as_str()) {
        return Err(DomainError::ReservedName(stem));
    }
    Ok(())
}
