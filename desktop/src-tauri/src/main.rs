#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::{net::IpAddr, sync::{Arc, Mutex}, time::Duration};
use tauri::{ipc::Channel, State};
use tokio::sync::watch;
use url::Url;

#[derive(Clone)]
struct Connection { base: Url, token: String, client: reqwest::Client, generation: u64 }
#[derive(Default)]
struct Bridge { connection: Mutex<Option<Connection>>, generation: Mutex<u64>, cancel: Mutex<Option<watch::Sender<bool>>> }
#[derive(Serialize, Clone)]
struct Reply { status: u16, body: String }
#[derive(Serialize, Clone)]
struct StreamChunk { text: String }

fn validate_base(raw: &str) -> Result<Url, String> {
    let url = Url::parse(raw).map_err(|_| "Enter a valid backend URL")?;
    if !url.username().is_empty() || url.password().is_some() || url.query().is_some() || url.fragment().is_some() || url.path() != "/" {
        return Err("Backend URL must contain only scheme, hostname and port".into());
    }
    let host = url.host_str().ok_or("Backend hostname is required")?;
    let loopback = host == "localhost" || host.parse::<IpAddr>().map(|ip| ip.is_loopback()).unwrap_or(false);
    let tailnet = host.ends_with(".ts.net") && host.len() > 7;
    if !(loopback && (url.scheme() == "http" || url.scheme() == "https") || tailnet && url.scheme() == "https") {
        return Err("Use loopback for local development or verified HTTPS at your Tailscale .ts.net hostname".into());
    }
    Ok(url)
}
fn api_url(connection: &Connection, path: &str) -> Result<Url, String> {
    if !path.starts_with("/api/") || path.contains('\\') || path.contains('#') || path.split('?').next().unwrap_or("").contains('%') || path.contains("..") || !path.is_ascii() {
        return Err("Invalid API path".into());
    }
    let url = connection.base.join(path).map_err(|_| "Invalid API path")?;
    if url.origin() != connection.base.origin() { return Err("Cross-origin API request refused".into()); }
    Ok(url)
}
fn snapshot(state: &Bridge) -> Result<Connection, String> {
    state.connection.lock().map_err(|_| "Connection unavailable")?.clone().ok_or("Connect to a backend first".into())
}
async fn bounded_body(mut response: reqwest::Response, limit: usize) -> Result<String, String> {
    let mut body = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(|_| "Connection interrupted")? {
        if body.len() + chunk.len() > limit { return Err("Backend response exceeds limit".into()); }
        body.extend_from_slice(&chunk);
    }
    String::from_utf8(body).map_err(|_| "Backend returned invalid UTF-8".into())
}
#[tauri::command]
async fn connect_backend(base_url: String, token: String, state: State<'_, Arc<Bridge>>) -> Result<Reply, String> {
    let base = validate_base(&base_url)?;
    if !token.is_empty() && (token.len() < 32 || token.len() > 512 || !token.is_ascii() || token.chars().any(char::is_whitespace)) {
        return Err("Invalid owner token format".into());
    }
    if base.scheme() == "https" && token.is_empty() { return Err("Remote connections require an owner token".into()); }
    let client = reqwest::Client::builder().no_proxy().redirect(reqwest::redirect::Policy::none())
        .connect_timeout(Duration::from_secs(8)).timeout(Duration::from_secs(310))
        .build().map_err(|_| "Cannot initialize secure transport")?;
    let epoch = { let mut generation = state.generation.lock().map_err(|_| "Connection unavailable")?; *generation += 1; *generation };
    let connection = Connection { base, token, client, generation: epoch };
    let mut request = connection.client.get(api_url(&connection, "/api/connection")?);
    if !connection.token.is_empty() { request = request.bearer_auth(&connection.token); }
    let response = request.timeout(Duration::from_secs(10)).send().await.map_err(|_| "Backend unreachable or TLS identity verification failed")?;
    let status = response.status().as_u16();
    let body = bounded_body(response, 64_000).await?;
    if status != 200 { return Err(format!("Connection rejected (HTTP {status}); check the owner token")); }
    let report: serde_json::Value = serde_json::from_str(&body).map_err(|_| "Invalid backend identity response")?;
    if report["api_version"] != 1 || report["ok"] != true || (connection.base.scheme() == "https" && report["authenticated"] != true) {
        return Err("Backend identity or authentication policy is incompatible".into());
    }
    // A disconnect or newer connection invalidates a slow handshake.
    if *state.generation.lock().map_err(|_| "Connection unavailable")? != epoch { return Err("Connection superseded".into()); }
    if let Some(cancel) = state.cancel.lock().map_err(|_| "Connection unavailable")?.take() { let _ = cancel.send(true); }
    *state.connection.lock().map_err(|_| "Connection unavailable")? = Some(connection);
    Ok(Reply { status, body })
}
#[tauri::command]
fn disconnect_backend(state: State<'_, Arc<Bridge>>) -> Result<(), String> {
    *state.generation.lock().map_err(|_| "Connection unavailable")? += 1;
    *state.connection.lock().map_err(|_| "Connection unavailable")? = None;
    if let Some(cancel) = state.cancel.lock().map_err(|_| "Connection unavailable")?.take() { let _ = cancel.send(true); }
    Ok(())
}
#[tauri::command]
async fn backend_request(method: String, path: String, body: Option<serde_json::Value>, state: State<'_, Arc<Bridge>>) -> Result<Reply, String> {
    let connection = snapshot(&state)?;
    let method = match method.as_str() { "GET" => reqwest::Method::GET, "POST" => reqwest::Method::POST, "PATCH" => reqwest::Method::PATCH, "DELETE" => reqwest::Method::DELETE, _ => return Err("Unsupported API method".into()) };
    let mut request = connection.client.request(method, api_url(&connection, &path)?);
    if !connection.token.is_empty() { request = request.bearer_auth(&connection.token); }
    if let Some(data) = body {
        if data.to_string().len() > 1_000_000 { return Err("Request exceeds limit".into()); }
        request = request.json(&data);
    }
    let response = request.send().await.map_err(|_| "Backend connection interrupted; reconnect to resume persisted history")?;
    let status = response.status().as_u16();
    let body = bounded_body(response, 4_000_000).await?;
    if state.connection.lock().map_err(|_| "Connection unavailable")?.as_ref().map(|c| c.generation) != Some(connection.generation) { return Err("Connection changed".into()); }
    Ok(Reply { status, body })
}
#[tauri::command]
async fn backend_stream(path: String, on_chunk: Channel<StreamChunk>, state: State<'_, Arc<Bridge>>) -> Result<(), String> {
    let connection = snapshot(&state)?;
    if !path.split('?').next().unwrap_or("").ends_with("/stream") { return Err("Only persisted event streams are supported".into()); }
    let mut request = connection.client.get(api_url(&connection, &path)?);
    if !connection.token.is_empty() { request = request.bearer_auth(&connection.token); }
    let (cancel, mut cancelled) = watch::channel(false);
    if let Some(previous) = state.cancel.lock().map_err(|_| "Connection unavailable")?.replace(cancel) { let _ = previous.send(true); }
    let mut response = tokio::select! { _ = cancelled.changed() => return Ok(()), result = request.send() => result.map_err(|_| "Event stream interrupted")? };
    if response.status() != 200 { return Err(format!("Stream rejected (HTTP {})", response.status().as_u16())); }
    let mut total = 0;
    // A chunk may end inside a UTF-8 character: send bytes as a lossless array, decode incrementally in JS.
    let mut pending = Vec::new();
    loop {
        let chunk = tokio::select! { _ = cancelled.changed() => return Ok(()), result = response.chunk() => result.map_err(|_| "Event stream interrupted")? };
        match chunk {
            None => break,
            Some(chunk) => {
                total += chunk.len(); if total > 4_000_000 { return Err("Stream exceeds limit".into()); }
                pending.extend_from_slice(&chunk);
                let valid = match std::str::from_utf8(&pending) { Ok(_) => pending.len(), Err(error) if error.error_len().is_none() => error.valid_up_to(), Err(_) => return Err("Invalid stream encoding".into()) };
                if valid > 0 {
                    let text = String::from_utf8(pending.drain(..valid).collect()).map_err(|_| "Invalid stream encoding")?;
                    on_chunk.send(StreamChunk { text }).map_err(|_| "Stream viewer closed")?;
                }
            }
        }
    }
    if !pending.is_empty() { return Err("Incomplete stream encoding".into()); }
    Ok(())
}
fn main() {
    tauri::Builder::default().manage(Arc::new(Bridge::default()))
        .invoke_handler(tauri::generate_handler![connect_backend, disconnect_backend, backend_request, backend_stream])
        .run(tauri::generate_context!()).expect("Personal Codex could not start");
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn connection_policy_rejects_public_insecure_and_credential_urls() {
        for raw in ["http://jarvis.example.com", "https://example.com", "http://jarvis.tail.ts.net", "http://0.0.0.0:8787", "http://u:password@localhost:8787", "http://localhost:8787/api", "https://jarvis.tail.ts.net/?x=1"] { assert!(validate_base(raw).is_err(), "{raw}"); }
        for raw in ["http://127.0.0.1:8787", "https://jarvis.tail.ts.net:8787", "http://localhost:8787"] { assert!(validate_base(raw).is_ok(), "{raw}"); }
    }
}
