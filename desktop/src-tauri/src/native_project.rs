use super::{api_url, bounded_body, snapshot, Bridge, Reply};
use serde::Serialize;
use std::{sync::Arc, time::{Duration, Instant}};
use tauri::{AppHandle, State};

#[derive(Serialize)]
pub(super) struct Selection {
    parent: String,
    name: String,
    existing: bool,
    device: u64,
    inode: u64,
    #[serde(skip)]
    generation: u64,
    #[serde(skip)]
    chosen_at: Instant,
}

fn valid_name(name: &str) -> bool {
    !name.is_empty() && name.len() <= 60
        && name.as_bytes()[0].is_ascii_alphanumeric()
        && name.bytes().all(|ch| ch.is_ascii_alphanumeric() || b" _-".contains(&ch))
        && !name.ends_with(' ')
}

#[cfg(target_os = "macos")]
pub(super) async fn pick_paths(app: &AppHandle, title: &'static str, folders: bool, limit: usize)
    -> Result<Vec<std::path::PathBuf>, String>
{
    use block2::RcBlock;
    use objc2::MainThreadMarker;
    use objc2_app_kit::{NSModalResponse, NSModalResponseOK, NSOpenPanel, NSWindow};
    use tauri::Manager;
    use objc2_foundation::NSString;
    use std::cell::Cell;

    let window = app.get_webview_window("main").ok_or("Personal Codex window is unavailable")?;
    let (sender, receiver) = tokio::sync::oneshot::channel();
    app.run_on_main_thread(move || {
        let Some(main) = MainThreadMarker::new() else {
            let _ = sender.send(Err("Finder must run on the main thread".into()));
            return;
        };
        let Ok(raw_window) = window.ns_window() else {
            let _ = sender.send(Err("Personal Codex window is unavailable".into()));
            return;
        };
        // Tauri provides its owned NSWindow handle on the main thread.
        let Some(parent) = (unsafe { raw_window.cast::<NSWindow>().as_ref() }) else {
            let _ = sender.send(Err("Personal Codex window is unavailable".into()));
            return;
        };
        let panel = NSOpenPanel::openPanel(main);
        panel.setTitle(Some(&NSString::from_str(title)));
        panel.setCanChooseFiles(!folders);
        panel.setCanChooseDirectories(folders);
        panel.setAllowsMultipleSelection(limit > 1);
        let selected = panel.clone();
        let sender = Cell::new(Some(sender));
        let callback = RcBlock::new(move |response: NSModalResponse| {
            if let Some(sender) = sender.take() {
                let result = if response != NSModalResponseOK {
                    Ok(Vec::new())
                } else {
                    let urls = selected.URLs();
                    if urls.count() > limit {
                        Err(format!("Select no more than {limit} items"))
                    } else {
                        (0..urls.count()).map(|index| {
                            let url = urls.objectAtIndex(index);
                            let path = url.path().ok_or("Finder returned an unsupported item")?;
                            Ok(std::path::PathBuf::from(path.to_string()))
                        }).collect()
                    }
                };
                let _ = sender.send(result);
            }
        });
        panel.beginSheetModalForWindow_completionHandler(parent, &callback);
    }).map_err(|_| "Cannot open Finder")?;
    receiver.await.map_err(|_| "Finder selection interrupted")?
}

#[cfg(not(target_os = "macos"))]
pub(super) async fn pick_paths(_: &AppHandle, _: &'static str, _: bool, _: usize)
    -> Result<Vec<std::path::PathBuf>, String>
{
    Err("The native Finder picker requires macOS".into())
}

#[cfg(unix)]
fn project_selection(raw: std::path::PathBuf, name: String, existing: bool, generation: u64)
    -> Result<Selection, String>
{
    use std::os::unix::fs::MetadataExt;

    let path = raw.canonicalize().map_err(|_| "Selected folder is unavailable")?;
    let meta = path.metadata().map_err(|_| "Selected folder is unavailable")?;
    if !meta.is_dir() { return Err("Select a directory".into()); }
    Ok(Selection {
        parent: path.to_str().ok_or("Selected path is not valid UTF-8")?.to_owned(),
        name, existing, device: meta.dev(), inode: meta.ino(), generation, chosen_at: Instant::now(),
    })
}

#[cfg(not(unix))]
fn project_selection(_: std::path::PathBuf, _: String, _: bool, _: u64) -> Result<Selection, String> {
    Err("The native Finder picker requires macOS".into())
}

#[tauri::command]
pub(super) async fn choose_project_folder(app: AppHandle, name: String, existing: bool, state: State<'_, Arc<Bridge>>) -> Result<Option<String>, String> {
    let connection = snapshot(&state)?;
    if state.native_grant.is_none() || state.offline_base.as_deref() != Some(connection.base.as_str().trim_end_matches('/')) {
        return Err("Use the offline desktop launcher to create a project".into());
    }
    if (existing && !name.is_empty()) || (!existing && !valid_name(&name)) { return Err("Enter up to 60 letters, digits, spaces, hyphens or underscores".into()); }
    *state.project_selection.lock().map_err(|_| "Folder selection unavailable")? = None;
    let title = if existing { "Choose an existing Git project" } else { "Choose a parent folder for the new project" };
    let selection = pick_paths(&app, title, true, 1).await?.pop()
        .map(|path| project_selection(path, name, existing, connection.generation)).transpose()?;
    if snapshot(&state)?.generation != connection.generation {
        return Err("Connection changed during selection".into());
    }
    let preview = selection.as_ref().map(|chosen| {
        if chosen.existing { chosen.parent.clone() }
        else { std::path::Path::new(&chosen.parent).join(&chosen.name).display().to_string() }
    });
    *state.project_selection.lock().map_err(|_| "Folder selection unavailable")? = selection;
    Ok(preview)
}

#[tauri::command]
pub(super) async fn create_selected_project(destination: String, state: State<'_, Arc<Bridge>>) -> Result<Reply, String> {
    let connection = snapshot(&state)?;
    if state.offline_base.as_deref() != Some(connection.base.as_str().trim_end_matches('/')) {
        return Err("Finder enrollment requires the local offline backend".into());
    }
    let key = state.native_grant.as_ref().ok_or("Native folder enrollment unavailable")?;
    let selected = state.project_selection.lock().map_err(|_| "Folder selection unavailable")?
        .take().ok_or("Choose a folder in Finder first")?;
    if selected.generation != connection.generation || selected.chosen_at.elapsed() > Duration::from_secs(300)
        || if selected.existing { selected.parent != destination }
           else { std::path::Path::new(&selected.parent).join(&selected.name).to_str() != Some(destination.as_str()) } {
        return Err("Folder selection expired or changed. Choose it again.".into());
    }
    let response = connection.client.post(api_url(&connection, "/api/native/projects")?)
        .bearer_auth(&connection.token).header("X-Personal-Codex-Native", key).json(&selected)
        .timeout(Duration::from_secs(32)).send().await.map_err(|_| "Project creation request interrupted")?;
    let status = response.status().as_u16();
    let body = bounded_body(response, 64_000).await?;
    Ok(Reply { status, body })
}

#[cfg(target_os = "macos")]
fn pick_attachment() -> Result<Option<std::path::PathBuf>, String> {
    use objc2::MainThreadMarker;
    use objc2_app_kit::NSOpenPanel;
    use objc2_foundation::NSString;

    let main = MainThreadMarker::new().ok_or("Finder must run on the main thread")?;
    let panel = NSOpenPanel::openPanel(main);
    panel.setTitle(Some(&NSString::from_str("Choose one project attachment")));
    panel.setCanChooseFiles(true);
    panel.setCanChooseDirectories(false);
    panel.setAllowsMultipleSelection(false);
    if panel.runModal() != 1 { return Ok(None); }
    let path = panel.URL().and_then(|url| url.path()).ok_or("Finder returned no file")?;
    Ok(Some(std::path::PathBuf::from(path.to_string())))
}

#[cfg(not(target_os = "macos"))]
fn pick_attachment() -> Result<Option<std::path::PathBuf>, String> {
    Err("The native attachment picker requires macOS".into())
}

#[tauri::command]
pub(super) async fn attach_project_file(app: AppHandle, project_id: String, from_drop: bool,
                                       state: State<'_, Arc<Bridge>>) -> Result<Option<Reply>, String> {
    let connection = snapshot(&state)?;
    let key = state.native_grant.as_ref().ok_or("Native attachment import is unavailable")?;
    if state.offline_base.as_deref() != Some(connection.base.as_str().trim_end_matches('/')) {
        return Err("Attachments require the local offline backend".into());
    }
    let selected = if from_drop {
        let (file, when) = state.dropped_file.lock().map_err(|_| "Dropped file unavailable")?
            .take().ok_or("Drop a single attachment first")?;
        if when.elapsed() > Duration::from_secs(90) { return Err("Drop the file again to renew the selection".into()); }
        Some(file)
    } else {
        let (sender, receiver) = tokio::sync::oneshot::channel();
        app.run_on_main_thread(move || { let _ = sender.send(pick_attachment()); })
            .map_err(|_| "Cannot open Finder")?;
        receiver.await.map_err(|_| "Finder selection interrupted")??
    };
    let Some(path) = selected else { return Ok(None); };
    let (path, device, inode) = file_identity(path)?;
    if snapshot(&state)?.generation != connection.generation { return Err("Connection changed".into()); }
    let payload = serde_json::json!({"project_id": project_id, "path": path, "device": device, "inode": inode});
    let response = connection.client.post(api_url(&connection, "/api/native/attachments")?)
        .bearer_auth(&connection.token).header("X-Personal-Codex-Native", key).json(&payload)
        .timeout(Duration::from_secs(38)).send().await.map_err(|_| "Local attachment import interrupted")?;
    let status = response.status().as_u16();
    let body = bounded_body(response, 64_000).await?;
    Ok(Some(Reply { status, body }))
}

#[cfg(unix)]
fn file_identity(path: std::path::PathBuf) -> Result<(String, u64, u64), String> {
    use std::os::unix::fs::MetadataExt;
    let info = path.symlink_metadata().map_err(|_| "Selected file is unavailable")?;
    if !info.is_file() || info.nlink() != 1 || info.len() > 12_000_000 {
        return Err("Select a regular document or image smaller than 12 MB".into());
    }
    let path = path.canonicalize().map_err(|_| "Selected file is unavailable")?;
    Ok((path.to_str().ok_or("Selected file path is not UTF-8")?.to_owned(), info.dev(), info.ino()))
}

#[cfg(not(unix))]
fn file_identity(_: std::path::PathBuf) -> Result<(String, u64, u64), String> {
    Err("The native attachment picker requires macOS".into())
}

#[derive(Serialize)]
pub(super) struct AttachmentSelection {
    path: String,
    device: u64,
    inode: u64,
}

pub(super) struct AttachmentBatch {
    generation: u64,
    chosen_at: Instant,
    files: Vec<AttachmentSelection>,
}

fn attachment_batch(paths: Vec<std::path::PathBuf>) -> Result<Vec<AttachmentSelection>, String> {
    let mut files = Vec::new();
    for raw in paths {
        let name = raw.file_name().map(|name| name.to_string_lossy().into_owned()).unwrap_or_default();
        let (path, device, inode) = file_identity(raw).map_err(|error| format!("{name}: {error}"))?;
        if files.iter().any(|item: &AttachmentSelection| item.path == path) {
            return Err("Select each task attachment once".into());
        }
        files.push(AttachmentSelection { path, device, inode });
    }
    Ok(files)
}

#[tauri::command]
pub(super) async fn choose_full_attachments(app: AppHandle, state: State<'_, Arc<Bridge>>) -> Result<Vec<String>, String> {
    let connection = snapshot(&state)?;
    if state.native_grant.is_none()
        || state.offline_base.as_deref() != Some(connection.base.as_str().trim_end_matches('/')) {
        return Err("Full-task attachments require the offline desktop profile".into());
    }
    *state.attachment_batch.lock().map_err(|_| "Attachment selection unavailable")? = None;
    let files = attachment_batch(pick_paths(&app, "Choose up to eight task attachments", false, 8).await?)?;
    let names = files.iter().map(|item| std::path::Path::new(&item.path)
        .file_name().unwrap_or_default().to_string_lossy().into_owned()).collect();
    if snapshot(&state)?.generation != connection.generation {
        return Err("Connection changed during selection".into());
    }
    *state.attachment_batch.lock().map_err(|_| "Attachment selection unavailable")? = Some(AttachmentBatch {
        generation: connection.generation, chosen_at: Instant::now(), files,
    });
    Ok(names)
}

#[tauri::command]
pub(super) async fn import_full_attachments(project_id: String, state: State<'_, Arc<Bridge>>) -> Result<Vec<Reply>, String> {
    let connection = snapshot(&state)?;
    let key = state.native_grant.as_ref().ok_or("Native attachment import is unavailable")?;
    if state.offline_base.as_deref() != Some(connection.base.as_str().trim_end_matches('/')) {
        return Err("Attachments require the local offline backend".into());
    }
    let selected = state.attachment_batch.lock().map_err(|_| "Attachment selection unavailable")?
        .take().ok_or("Select the attachments in Finder again")?;
    if selected.generation != connection.generation || selected.chosen_at.elapsed() > Duration::from_secs(600) {
        return Err("Attachment selection expired. Choose the files again.".into());
    }
    let mut replies = Vec::new();
    for file in selected.files {
        if snapshot(&state)?.generation != connection.generation {
            return Err("Connection changed during import".into());
        }
        let payload = serde_json::json!({"project_id":project_id,"path":file.path,"device":file.device,"inode":file.inode});
        let response = connection.client.post(api_url(&connection, "/api/native/attachments")?)
            .bearer_auth(&connection.token).header("X-Personal-Codex-Native", key).json(&payload)
            .timeout(Duration::from_secs(34)).send().await.map_err(|_| "Local attachment import interrupted")?;
        let status = response.status().as_u16();
        let body = bounded_body(response, 64_000).await?;
        replies.push(Reply { status, body });
    }
    Ok(replies)
}

#[tauri::command]
pub(super) async fn open_full_destination(task_id: String, state: State<'_, Arc<Bridge>>) -> Result<(), String> {
    let connection = snapshot(&state)?;
    if state.offline_base.as_deref() != Some(connection.base.as_str().trim_end_matches('/'))
        || task_id.len() != 36 || !task_id.bytes().all(|b| b.is_ascii_hexdigit() || b == b'-') {
        return Err("Select a local full task".into());
    }
    let response = connection.client.get(api_url(&connection, &format!("/api/tasks/{task_id}/full-destination"))?)
        .bearer_auth(&connection.token).send().await.map_err(|_| "Destination lookup interrupted")?;
    if !response.status().is_success() { return Err("The authorized destination is unavailable".into()); }
    let output: serde_json::Value = serde_json::from_str(&bounded_body(response, 8000).await?)
        .map_err(|_| "Invalid destination response")?;
    let path = output["path"].as_str().ok_or("No authorized destination")?;
    if !std::path::Path::new(path).is_absolute() {
        return Err("Invalid destination path".into());
    }
    let status = std::process::Command::new("/usr/bin/open").args(["-a", "Finder", path]).status()
        .map_err(|_| "Cannot open Finder")?;
    if status.success() { Ok(()) } else { Err("Finder could not open the project".into()) }
}
