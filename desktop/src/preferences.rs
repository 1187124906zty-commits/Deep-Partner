//! Small native UI preferences survive the random loopback origin.
use anyhow::{Result, bail};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Preferences {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub theme: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub language: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub response_language: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub code_block_theme: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub code_block_show_line_numbers: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub code_block_wrap_long_lines: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ui_layout: Option<String>,
}
pub struct PreferenceStore {
    path: PathBuf,
}
impl PreferenceStore {
    pub fn new(directory: &Path) -> Self {
        Self {
            path: directory.join("ui-preferences.json"),
        }
    }
    pub fn load(&self) -> Result<Preferences> {
        if !self.path.exists() {
            return Ok(Preferences::default());
        }
        let value: Preferences = serde_json::from_slice(&std::fs::read(&self.path)?)?;
        value.validate()?;
        Ok(value)
    }
    pub fn update(&self, patch: Preferences) -> Result<Preferences> {
        patch.validate()?;
        let mut value = self.load()?;
        if patch.theme.is_some() {
            value.theme = patch.theme;
        }
        if patch.language.is_some() {
            value.language = patch.language;
        }
        if patch.response_language.is_some() {
            value.response_language = patch.response_language;
        }
        if patch.code_block_theme.is_some() { value.code_block_theme = patch.code_block_theme; }
        if patch.code_block_show_line_numbers.is_some() { value.code_block_show_line_numbers = patch.code_block_show_line_numbers; }
        if patch.code_block_wrap_long_lines.is_some() { value.code_block_wrap_long_lines = patch.code_block_wrap_long_lines; }
        if patch.ui_layout.is_some() { value.ui_layout = patch.ui_layout; }
        let directory = self.path.parent().unwrap();
        std::fs::create_dir_all(directory)?;
        let temporary = directory.join(format!("ui-preferences-{}.tmp", uuid::Uuid::new_v4()));
        std::fs::write(&temporary, serde_json::to_vec_pretty(&value)?)?;
        std::fs::rename(temporary, &self.path)?;
        Ok(value)
    }
}
impl Preferences {
    fn validate(&self) -> Result<()> {
        if self
            .theme
            .as_deref()
            .is_some_and(|v| !matches!(v, "light" | "dark" | "snow" | "glass"))
        {
            bail!("Unknown theme");
        }
        if self.language.as_deref().is_some_and(|v| !matches!(v,"zh"|"en"|"fr"|"de"|"uk"|"pl")) { bail!("Unknown interface language"); }
        if self.response_language.as_deref().is_some_and(|v| !matches!(v,"zh"|"en"|"zh-tw"|"ja"|"ko"|"es"|"fr"|"de"|"ru"|"pt"|"it"|"ar"|"pl"|"uk"|"ms")) { bail!("Unknown response language"); }
        if self.ui_layout.as_deref().is_some_and(|v| !matches!(v,"classic"|"modern")) { bail!("Unknown UI layout"); }
        if self.code_block_theme.as_deref().is_some_and(|v|v.is_empty()||v.len()>80||!v.chars().all(|c|c.is_ascii_alphanumeric()||c=='-'||c=='_')) { bail!("Unknown code block theme"); }
        Ok(())
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn saved_preferences_survive_reopen_and_partial_updates() {
        let temp = tempfile::tempdir().unwrap();
        let store = PreferenceStore::new(temp.path());
        assert_eq!(
            serde_json::to_value(store.load().unwrap()).unwrap(),
            serde_json::json!({})
        );
        store
            .update(Preferences {
                theme: Some("light".into()),
                language: Some("zh".into()),
                ..Default::default()
            })
            .unwrap();
        let reopened = PreferenceStore::new(temp.path());
        let actual = reopened
            .update(Preferences {
                response_language: Some("en".into()),
                code_block_theme: Some("oneDark".into()),
                code_block_show_line_numbers: Some(false),
                code_block_wrap_long_lines: Some(true),
                ui_layout: Some("classic".into()),
                ..Default::default()
            })
            .unwrap();
        assert_eq!(actual.theme.as_deref(), Some("light"));
        assert_eq!(actual.language.as_deref(), Some("zh"));
        assert_eq!(actual.response_language.as_deref(), Some("en"));
        assert_eq!(reopened.load().unwrap(),actual);
        assert_eq!(actual.ui_layout.as_deref(),Some("classic"));
        assert_eq!(actual.code_block_show_line_numbers,Some(false));
        assert!(reopened.update(Preferences {language:Some("fr".into()),response_language:Some("ja".into()),..Default::default()}).is_ok());
        assert!(
            reopened
                .update(Preferences {
                    theme: Some("remote-code".into()),
                    ..Default::default()
                })
                .is_err()
        );
    }
}
