//! Local, one-use opening capabilities. No shell, scripts, file contents or backend transport.
use serde::Serialize;
use std::{path::{Path, PathBuf}, sync::{Arc, Mutex}, time::{Duration, Instant}};
use tauri::{AppHandle, State};
use super::Bridge;

#[derive(Serialize, Clone)]
pub(super) struct MacApp { name: String, path: String }
#[derive(Serialize, Clone)]
pub(super) struct Preview { id: String, kind: String, label: String, target: String, expires_in_seconds: u64 }
#[derive(Clone, PartialEq, Debug)]
struct Identity { device: u64, inode: u64, size: u64, modified: (i64, i64), changed: (i64, i64) }
struct Pending { preview: Preview, identity: Identity, created: Instant }
#[derive(Default)]
pub(super) struct Actions { pending: Option<Pending>, counter: u64 }

fn safe_path(path: &Path) -> Result<(), String> {
    let text = path.to_str().ok_or("Choose a path with a valid text name")?;
    if !path.is_absolute() || text.len() > 4096 || text.chars().any(char::is_control) {
        return Err("An absolute local path without control characters is required".into());
    }
    for part in path.components() {
        let name = part.as_os_str().to_string_lossy().to_ascii_lowercase();
        if [".ssh", ".aws", ".gnupg", ".codex", ".kube", ".netrc", ".npmrc", "keychains", ".env", "id_rsa", "id_ed25519"].contains(&name.as_str())
            || name.starts_with(".env.") || name.ends_with(".keychain-db") || name.ends_with(".pem")
            || name.contains("private_key") || name.contains("owner.token") || name.contains("owner-token")
            || name.contains("worker.token") || name.contains("worker-token") {
            return Err("Credential and private configuration paths cannot be opened through Mac actions".into());
        }
    }
    Ok(())
}

#[cfg(unix)]
fn identity(path: &Path) -> Result<Identity, String> {
    use std::os::unix::fs::MetadataExt;
    safe_path(path)?;
    let info = path.symlink_metadata().map_err(|_| "Selected item is unavailable")?;
    if info.file_type().is_symlink() || !(info.is_file() || info.is_dir()) {
        return Err("Choose a regular local file or folder, not a symbolic link".into());
    }
    Ok(Identity { device: info.dev(), inode: info.ino(), size: info.size(),
        modified: (info.mtime(), info.mtime_nsec()), changed: (info.ctime(), info.ctime_nsec()) })
}
#[cfg(not(unix))]
fn identity(_: &Path) -> Result<Identity, String> { Err("Mac actions require macOS".into()) }

fn app_roots() -> Vec<PathBuf> {
    let mut roots = vec![PathBuf::from("/Applications"), PathBuf::from("/System/Applications"),
        PathBuf::from("/System/Applications/Utilities")];
    if let Some(home) = std::env::var_os("HOME") { roots.push(PathBuf::from(home).join("Applications")); }
    roots.into_iter().filter_map(|p| p.canonicalize().ok()).collect()
}
fn app_allowed(path: &Path, roots: &[PathBuf]) -> bool {
    path.extension().is_some_and(|ext| ext == "app") && path.is_dir()
        && path.join("Contents/Info.plist").is_file()
        && path.parent().is_some_and(|parent| roots.iter().any(|root| root == parent))
}
fn document_allowed(path: &Path) -> bool {
    const EXTENSIONS: &[&str] = &["txt", "md", "pdf", "png", "jpg", "jpeg", "webp", "gif", "csv", "tsv", "json", "rtf", "docx", "xlsx", "pptx"];
    path.is_file() && path.extension().and_then(|s| s.to_str())
        .is_some_and(|ext| EXTENSIONS.contains(&ext.to_ascii_lowercase().as_str()))
}

fn install_preview(actions: &Mutex<Actions>, kind: &str, path: PathBuf) -> Result<Preview, String> {
    safe_path(&path)?;
    let original = identity(&path)?;
    let canonical = path.canonicalize().map_err(|_| "Selected item is unavailable")?;
    safe_path(&canonical)?;
    if identity(&canonical)? != original { return Err("Selected item changed. Choose it again.".into()); }
    match kind {
        "open_app" if app_allowed(&canonical, &app_roots()) => (),
        "open_document" if document_allowed(&canonical) => (),
        "reveal_item" => (),
        _ => return Err("Choose an installed app or a supported document. Scripts and executable files cannot be opened.".into()),
    }
    let label = canonical.file_name().ok_or("Choose a named item")?.to_string_lossy().into_owned();
    let mut guard = actions.lock().map_err(|_| "Mac actions are unavailable")?;
    guard.counter += 1;
    let preview = Preview { id: format!("mac-action-{}", guard.counter), kind: kind.into(), label,
        target: canonical.to_string_lossy().into_owned(), expires_in_seconds: 120 };
    guard.pending = Some(Pending { preview: preview.clone(), identity: original, created: Instant::now() });
    Ok(preview)
}

fn consume(actions: &Mutex<Actions>, id: &str, confirmed: bool) -> Result<Preview, String> {
    let mut guard = actions.lock().map_err(|_| "Mac actions are unavailable")?;
    let pending = guard.pending.take().ok_or("Review an action first")?;
    if !confirmed || pending.preview.id != id || pending.created.elapsed() > Duration::from_secs(120) {
        return Err("Action was not confirmed, expired or changed. Review it again.".into());
    }
    let path = Path::new(&pending.preview.target);
    if identity(path)? != pending.identity || path.canonicalize().ok().as_deref() != Some(path) {
        return Err("Selected item changed after review. Choose it again.".into());
    }
    if pending.preview.kind == "open_app" && !app_allowed(path, &app_roots())
        || pending.preview.kind == "open_document" && !document_allowed(path) {
        return Err("Selected item is no longer permitted".into());
    }
    Ok(pending.preview)
}

#[tauri::command]
pub(super) fn mac_applications(query: String) -> Result<Vec<MacApp>, String> {
    if !cfg!(target_os = "macos") { return Err("Mac actions require macOS".into()); }
    if query.len() > 100 || query.chars().any(char::is_control) { return Err("Use a short application name".into()); }
    let query = query.trim().to_lowercase();
    let roots = app_roots();
    let mut apps = Vec::new();
    for root in &roots {
        let Ok(entries) = root.read_dir() else { continue };
        for entry in entries.take(500).flatten() {
            let path = entry.path();
            if !app_allowed(&path, &roots) || identity(&path).is_err() { continue; }
            let name = path.file_stem().unwrap_or_default().to_string_lossy().into_owned();
            if name.to_lowercase().contains(&query) {
                apps.push(MacApp { name, path: path.to_string_lossy().into_owned() });
            }
        }
    }
    apps.sort_by_key(|app| (app.name.to_lowercase(), app.path.clone()));
    apps.dedup_by(|a,b| a.path == b.path);
    apps.truncate(100);
    Ok(apps)
}

#[tauri::command]
pub(super) fn prepare_mac_app(path: String, state: State<'_, Arc<Bridge>>) -> Result<Preview, String> {
    if !cfg!(target_os = "macos") { return Err("Mac actions require macOS".into()); }
    state.mac_actions.lock().map_err(|_| "Mac actions unavailable")?.pending = None;
    install_preview(&state.mac_actions, "open_app", PathBuf::from(path))
}

#[tauri::command]
pub(super) async fn choose_mac_item(app: AppHandle, kind: String, folder: bool,
    state: State<'_, Arc<Bridge>>) -> Result<Option<Preview>, String> {
    if kind != "open_document" && kind != "reveal_item" || folder && kind != "reveal_item" {
        return Err("Choose a document to open or an item to reveal in Finder".into());
    }
    state.mac_actions.lock().map_err(|_| "Mac actions unavailable")?.pending = None;
    let path = super::native_project::pick_paths(&app, "Choose an item for this Mac action", folder, 1).await?.pop();
    path.map(|p| install_preview(&state.mac_actions, &kind, p)).transpose()
}

#[tauri::command]
pub(super) fn cancel_mac_action(state: State<'_, Arc<Bridge>>) -> Result<(), String> {
    state.mac_actions.lock().map_err(|_| "Mac actions unavailable")?.pending = None;
    Ok(())
}

#[tauri::command]
pub(super) async fn execute_mac_action(id: String, confirmed: bool, state: State<'_, Arc<Bridge>>) -> Result<String, String> {
    if !cfg!(target_os = "macos") { return Err("Mac actions require macOS".into()); }
    let preview = consume(&state.mac_actions, &id, confirmed)?;
    tauri::async_runtime::spawn_blocking(move || {
        use std::process::{Command, Stdio};
        let mut command = Command::new("/usr/bin/open");
        command.env_clear().env("PATH", "/usr/bin:/bin:/usr/sbin:/sbin");
        for key in ["HOME", "USER", "LOGNAME", "TMPDIR", "LANG"] {
            if let Some(value) = std::env::var_os(key) { command.env(key, value); }
        }
        match preview.kind.as_str() {
            "open_app" => { command.arg("-a"); },
            "reveal_item" => { command.arg("-R"); },
            _ => (),
        }
        let mut child = command.arg(&preview.target).stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null())
            .spawn().map_err(|_| "macOS could not receive the open request")?;
        let deadline = Instant::now() + Duration::from_secs(10);
        loop {
            if let Some(status) = child.try_wait().map_err(|_| "Could not check the open request")? {
                return if status.success() { Ok(format!("macOS accepted the request for {}.", preview.label)) }
                    else { Err("macOS declined the open request. The action was consumed; review it again before retrying.".into()) };
            }
            if Instant::now() >= deadline {
                let _ = child.kill(); let _ = child.wait();
                return Err("Open request timed out; its outcome is uncertain. Check your Mac before retrying.".into());
            }
            std::thread::sleep(Duration::from_millis(40));
        }
    }).await.map_err(|_| "Open request interrupted; check your Mac before retrying")?
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> PathBuf {
        use std::sync::atomic::{AtomicU64, Ordering};
        static SEQUENCE: AtomicU64 = AtomicU64::new(0);
        for _ in 0..100 {
            let sequence = SEQUENCE.fetch_add(1, Ordering::Relaxed);
            let base = std::env::temp_dir().join(format!("pc-mac-actions-{}-{}-{}", std::process::id(),
                std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos(), sequence));
            match std::fs::create_dir(&base) {
                Ok(()) => return base,
                Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(error) => panic!("Cannot create disposable native fixture: {error}"),
            }
        }
        panic!("No unique disposable native fixture available")
    }
    #[test]
    fn credential_paths_and_control_characters_are_refused() {
        for name in ["/Users/example/.ssh/id_ed25519", "/tmp/.env", "/tmp/owner.token", "/tmp/a\nb.txt", "relative.txt"] {
            assert!(safe_path(Path::new(name)).is_err(), "{name}");
        }
    }
    #[test]
    fn scripts_are_not_documents_and_apps_require_standard_root() {
        let base=fixture(); let script=base.join("run.command"); std::fs::write(&script,"echo no").unwrap();
        assert!(!document_allowed(&script));
        assert!(install_preview(&Mutex::default(),"open_document",script).is_err());
        let app=base.join("Synthetic.app"); std::fs::create_dir_all(app.join("Contents")).unwrap(); std::fs::write(app.join("Contents/Info.plist"),"fixture").unwrap();
        assert!(app_allowed(&app,std::slice::from_ref(&base)));
        assert!(install_preview(&Mutex::default(),"open_app",app).is_err());
        std::fs::remove_dir_all(base).unwrap();
    }
    #[test]
    fn confirmation_is_one_use_and_changed_files_are_refused() {
        let base=fixture().canonicalize().unwrap(); let file=base.join("notes.txt"); std::fs::write(&file,"synthetic").unwrap();
        let actions=Mutex::default(); let preview=install_preview(&actions,"open_document",file.clone()).unwrap();
        assert!(consume(&actions,&preview.id,false).is_err());
        assert!(consume(&actions,&preview.id,true).is_err());
        let preview=install_preview(&actions,"open_document",file.clone()).unwrap(); std::fs::write(&file,"changed and longer").unwrap();
        assert!(consume(&actions,&preview.id,true).is_err());
        let preview=install_preview(&actions,"open_document",file).unwrap(); assert!(consume(&actions,&preview.id,true).is_ok());
        assert!(consume(&actions,&preview.id,true).is_err()); std::fs::remove_dir_all(base).unwrap();
    }
    #[test]
    fn expired_replaced_and_symlink_choices_are_refused() {
        let base=fixture().canonicalize().unwrap(); let file=base.join("notes.txt"); std::fs::write(&file,"fixture").unwrap();
        let actions=Mutex::default(); let first=install_preview(&actions,"reveal_item",file.clone()).unwrap();
        let second=install_preview(&actions,"reveal_item",file.clone()).unwrap();
        assert!(consume(&actions,&first.id,true).is_err()); assert!(consume(&actions,&second.id,true).is_err());
        let preview=install_preview(&actions,"reveal_item",file.clone()).unwrap();
        actions.lock().unwrap().pending.as_mut().unwrap().created=Instant::now()-Duration::from_secs(121);
        assert!(consume(&actions,&preview.id,true).is_err());
        #[cfg(unix)] { let link=base.join("link.txt"); std::os::unix::fs::symlink(file, &link).unwrap(); assert!(install_preview(&actions,"open_document",link).is_err()); }
        std::fs::remove_dir_all(base).unwrap();
    }
}
