use anyhow::{Result, bail};
use serde::Serialize;
use std::{
    collections::HashMap,
    path::{Path, PathBuf},
    sync::Mutex,
    time::{Instant, SystemTime},
};

struct Entry {
    modified: SystemTime,
    length: u64,
    text: String,
    used: Instant,
}
pub struct TextCache {
    entries: Mutex<HashMap<PathBuf, Entry>>,
    budget: usize,
    hits: std::sync::atomic::AtomicU64,
    misses: std::sync::atomic::AtomicU64,
}

#[derive(Serialize)]
pub struct CacheStats {
    pub entries: usize,
    pub bytes: usize,
    pub budget_bytes: usize,
    pub hits: u64,
    pub misses: u64,
}

impl TextCache {
    pub fn new(budget: usize) -> Self {
        Self {
            entries: Mutex::new(HashMap::new()),
            budget,
            hits: 0.into(),
            misses: 0.into(),
        }
    }
    pub fn read(&self, path: &Path) -> Result<String> {
        use std::sync::atomic::Ordering::Relaxed;
        let meta = std::fs::metadata(path)?;
        if !meta.is_file() || meta.len() > 2 * 1024 * 1024 {
            bail!("文本读取上限 2 MB；较大的文件请在应用中打开");
        }
        let modified = meta.modified()?;
        let mut entries = self.entries.lock().unwrap();
        if let Some(entry) = entries.get_mut(path) {
            if entry.modified == modified && entry.length == meta.len() {
                entry.used = Instant::now();
                self.hits.fetch_add(1, Relaxed);
                return Ok(entry.text.clone());
            }
        }
        // Disk I/O happens on the CPU worker pool, outside the cache lock.
        entries.remove(path);
        drop(entries);
        let text = std::fs::read_to_string(path)?;
        self.misses.fetch_add(1, Relaxed);
        let mut entries = self.entries.lock().unwrap();
        while entries.len() >= 128
            || entries.values().map(|e| e.text.len()).sum::<usize>() + text.len() > self.budget
        {
            let Some(oldest) = entries
                .iter()
                .min_by_key(|(_, e)| e.used)
                .map(|(p, _)| p.clone())
            else {
                break;
            };
            entries.remove(&oldest);
        }
        if text.len() <= self.budget {
            entries.insert(
                path.to_path_buf(),
                Entry {
                    modified,
                    length: meta.len(),
                    text: text.clone(),
                    used: Instant::now(),
                },
            );
        }
        Ok(text)
    }
    pub fn stats(&self) -> CacheStats {
        use std::sync::atomic::Ordering::Relaxed;
        let entries = self.entries.lock().unwrap();
        CacheStats {
            entries: entries.len(),
            bytes: entries.values().map(|e| e.text.len()).sum(),
            budget_bytes: self.budget,
            hits: self.hits.load(Relaxed),
            misses: self.misses.load(Relaxed),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn cached_read_invalidates_on_change_and_obeys_budget() {
        let tmp = tempfile::tempdir().unwrap();
        let p = tmp.path().join("a.txt");
        let cache = TextCache::new(16);
        std::fs::write(&p, "first").unwrap();
        assert_eq!(cache.read(&p).unwrap(), "first");
        assert_eq!(cache.read(&p).unwrap(), "first");
        assert_eq!(cache.stats().hits, 1);
        std::fs::write(&p, "second longer").unwrap();
        assert_eq!(cache.read(&p).unwrap(), "second longer");
        let q = tmp.path().join("b.txt");
        std::fs::write(&q, "12345678").unwrap();
        cache.read(&q).unwrap();
        assert!(cache.stats().bytes <= 16);
        assert_eq!(cache.stats().entries, 1);
    }
}
