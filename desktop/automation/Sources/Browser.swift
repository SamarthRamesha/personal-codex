import AppKit
import ApplicationServices
import CoreGraphics

let browserIdentifiers: Set<String> = ["com.apple.Safari", "com.google.Chrome", "org.mozilla.firefox", "app.zen-browser.zen", "company.thebrowser.Browser", "com.microsoft.edgemac"]

@MainActor func focusedWindow(_ application: AXUIElement, equals window: AXUIElement) -> Bool {
    guard let focused = axValue(application, kAXFocusedWindowAttribute) else { return false }
    return CFEqual(focused, window)
}
@MainActor func browserKey(_ pid: pid_t, code: CGKeyCode, command: Bool = false) throws {
    guard CGPreflightPostEventAccess(), NSWorkspace.shared.frontmostApplication?.processIdentifier == pid,
          let down = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: true),
          let up = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: false) else { throw AutomationError.permissionRequired }
    if command { down.flags = .maskCommand; up.flags = .maskCommand }
    down.postToPid(pid); up.postToPid(pid)
}
func permittedBrowserURL(_ raw: String) -> Bool {
    guard AutomationPolicy.plain(raw, max: 2048), let url = URLComponents(string: raw),
          url.user == nil, url.password == nil, let host = url.host,
          url.scheme == "https" || url.scheme == "http" && ["127.0.0.1", "localhost", "::1"].contains(host) else { return false }
    return !(url.queryItems ?? []).contains { item in
        ["token", "password", "secret", "api_key", "access_token"].contains(item.name.lowercased())
    }
}

@MainActor func newBrowserWindow(bundle: String, destination: String) async throws -> NativeDriver {
    guard AXIsProcessTrusted(), CGPreflightPostEventAccess() else { throw AutomationError.permissionRequired }
    guard browserIdentifiers.contains(bundle), permittedBrowserURL(destination), let url = URL(string: destination) else { throw AutomationError.unsafeTarget }
    let app: NSRunningApplication
    if let running = NSWorkspace.shared.runningApplications.first(where: { $0.bundleIdentifier == bundle && !$0.isTerminated }) { app = running }
    else {
        guard let location = NSWorkspace.shared.urlForApplication(withBundleIdentifier: bundle) else { throw AutomationError.unsupported }
        let options = NSWorkspace.OpenConfiguration(); options.activates = false
        app = try await NSWorkspace.shared.openApplication(at: location, configuration: options)
    }
    let application = AXUIElementCreateApplication(app.processIdentifier); AXUIElementSetMessagingTimeout(application, 0.35)
    let before = axElements(application, kAXWindowsAttribute, max: 20)
    guard app.activate(options: []) else { throw AutomationError.targetChanged }
    let focusDeadline = ProcessInfo.processInfo.systemUptime + 1
    while NSWorkspace.shared.frontmostApplication?.processIdentifier != app.processIdentifier && ProcessInfo.processInfo.systemUptime < focusDeadline {
        try await Task.sleep(nanoseconds: 20_000_000)
    }
    try browserKey(app.processIdentifier, code: 45, command: true)
    let windowDeadline = ProcessInfo.processInfo.systemUptime + 2
    var created: (Int, AXUIElement)?
    while ProcessInfo.processInfo.systemUptime < windowDeadline {
        let windows = axElements(application, kAXWindowsAttribute, max: 20)
        let new = windows.enumerated().filter { candidate in !before.contains { CFEqual($0, candidate.element) } }
        if new.count > 1 { throw AutomationError.unsafeTarget }
        if let first = new.first { created = (first.offset, first.element); break }
        try await Task.sleep(nanoseconds: 30_000_000)
    }
    guard let (index, window) = created, focusedWindow(application, equals: window) else { throw AutomationError.targetChanged }
    let driver = try NativeDriver(pid: app.processIdentifier, windowIndex: index)
    try browserKey(app.processIdentifier, code: 37, command: true)
    try await Task.sleep(nanoseconds: 80_000_000)
    guard focusedWindow(application, equals: window), let focus = axValue(application, kAXFocusedUIElementAttribute),
          CFGetTypeID(focus) == AXUIElementGetTypeID() else { throw AutomationError.targetChanged }
    let field = unsafeBitCast(focus, to: AXUIElement.self)
    guard ["AXTextField", "AXComboBox"].contains(axString(field, kAXRoleAttribute)),
          !AutomationPolicy.sensitive(axString(field, kAXRoleAttribute), axString(field, kAXSubroleAttribute), axString(field, kAXTitleAttribute)),
          AXUIElementSetAttributeValue(field, kAXValueAttribute as CFString, url.absoluteString as CFString) == .success else { throw AutomationError.unsupported }
    guard focusedWindow(application, equals: window) else { throw AutomationError.targetChanged }
    try browserKey(app.processIdentifier, code: 36)
    let navigationDeadline = ProcessInfo.processInfo.systemUptime + 4
    while ProcessInfo.processInfo.systemUptime < navigationDeadline {
        driver.scopedOrigin = nil
        if let snapshot = try? driver.observe(scope: "browser-start"), snapshot.origin == AutomationPolicy.origin(url.absoluteString) {
            driver.scopedOrigin = snapshot.origin; return driver
        }
        try await Task.sleep(nanoseconds: 50_000_000)
    }
    throw AutomationError.verificationFailed
}
