import AppKit
import ApplicationServices
import CoreGraphics
import ScreenCaptureKit
import Vision

func axValue(_ element: AXUIElement, _ attribute: String) -> CFTypeRef? {
    var result: CFTypeRef?
    return AXUIElementCopyAttributeValue(element, attribute as CFString, &result) == .success ? result : nil
}
func axString(_ element: AXUIElement, _ attribute: String) -> String { axValue(element, attribute) as? String ?? "" }
func axElements(_ element: AXUIElement, _ attribute: String, max: Int) -> [AXUIElement] {
    var array: CFArray?
    guard AXUIElementCopyAttributeValues(element, attribute as CFString, 0, max, &array) == .success,
          let values = array as? [AXUIElement] else { return [] }
    return values
}
func axInt(_ element: AXUIElement, _ attribute: String) -> Int? {
    (axValue(element, attribute) as? NSNumber)?.intValue
}
func axElementValue(_ element: AXUIElement, _ attribute: String) -> AXUIElement? {
    guard let value = axValue(element, attribute), CFGetTypeID(value) == AXUIElementGetTypeID() else { return nil }
    return unsafeBitCast(value, to: AXUIElement.self)
}
func rect(_ element: AXUIElement) -> CGRect? {
    guard let position = axValue(element, kAXPositionAttribute), let size = axValue(element, kAXSizeAttribute),
          CFGetTypeID(position) == AXValueGetTypeID(), CFGetTypeID(size) == AXValueGetTypeID() else { return nil }
    var point = CGPoint.zero; var dimensions = CGSize.zero
    guard AXValueGetValue(unsafeBitCast(position, to: AXValue.self), .cgPoint, &point),
          AXValueGetValue(unsafeBitCast(size, to: AXValue.self), .cgSize, &dimensions) else { return nil }
    return CGRect(origin: point, size: dimensions)
}

@MainActor final class NativeDriver: AutomationDriver {
    let app: NSRunningApplication
    let launched: Date?
    let identifier: String
    let application: AXUIElement
    let window: AXUIElement
    var references: [String: AXUIElement] = [:]
    var sensitivePresent = false
    var scopedOrigin: String?
    var browser: Bool { browserIdentifiers.contains(identifier) }
    init(pid: pid_t, windowIndex: Int, expectedTitle: String? = nil, expectedNumber: Int? = nil) throws {
        guard AXIsProcessTrusted() else { throw AutomationError.permissionRequired }
        _ = NSApplication.shared
        guard let app = NSRunningApplication(processIdentifier: pid), let identifier = app.bundleIdentifier,
              AutomationPolicy.permittedApp(identifier), !app.isTerminated else { throw AutomationError.unsafeTarget }
        let application = AXUIElementCreateApplication(pid)
        AXUIElementSetMessagingTimeout(application, 0.35)
        let windows = axElements(application, kAXWindowsAttribute, max: 20)
        guard windows.indices.contains(windowIndex) else { throw AutomationError.invalidRequest }
        let selected = windows[windowIndex]
        // A window index is only a position. Refuse when the window now at that position is not the one
        // the caller listed, instead of silently controlling a different window.
        if let expectedTitle, axString(selected, kAXTitleAttribute) != expectedTitle { throw AutomationError.targetChanged }
        // The window number survives reordering and title edits, so it is the stronger identity.
        // It is optional: some apps expose none, and the title check above still applies.
        if let expectedNumber, let observedNumber = axInt(selected, "AXWindowNumber"), observedNumber != expectedNumber {
            throw AutomationError.targetChanged
        }
        self.app = app; self.launched = app.launchDate; self.identifier = identifier
        self.application = application; self.window = selected
    }
    func permitted() -> Bool { AXIsProcessTrusted() }
    func targetValid() -> Bool {
        guard let current = NSRunningApplication(processIdentifier: app.processIdentifier), !current.isTerminated,
              current.bundleIdentifier == identifier, current.launchDate == launched else { return false }
        return axElements(application, kAXWindowsAttribute, max: 20).contains { CFEqual($0, window) }
    }
    func diagnostics() -> [String: Bool] {
        let current = NSRunningApplication(processIdentifier: app.processIdentifier)
        return ["permission_available": permitted(), "process_present": current != nil && current?.isTerminated == false,
                "bundle_matches": current?.bundleIdentifier == identifier, "launch_matches": current?.launchDate == launched,
                "selected_window_present": axElements(application, kAXWindowsAttribute, max: 20).contains { CFEqual($0, window) },
                "frontmost_target": NSWorkspace.shared.frontmostApplication?.processIdentifier == app.processIdentifier,
                "focused_window_matches": focusedWindow(application, equals: window)]
    }
    func activate() throws {
        guard permitted(), targetValid() else { throw AutomationError.targetChanged }
        let requested = app.activate(options: [])
        let frontmost = AXUIElementSetAttributeValue(application, kAXFrontmostAttribute as CFString, kCFBooleanTrue)
        guard requested || frontmost == .success else { throw AutomationError.activationDenied }
        // Raising a window does not by itself establish key focus. Request focus only for this bound window.
        _ = AXUIElementSetAttributeValue(window, kAXMainAttribute as CFString, kCFBooleanTrue)
        _ = AXUIElementSetAttributeValue(window, kAXFocusedAttribute as CFString, kCFBooleanTrue)
        guard AXUIElementPerformAction(window, kAXRaiseAction as CFString) == .success else { throw AutomationError.unsupported }
        let deadline = ProcessInfo.processInfo.systemUptime + 1.5
        while ProcessInfo.processInfo.systemUptime < deadline {
            guard targetValid() else { throw AutomationError.targetChanged }
            if NSWorkspace.shared.frontmostApplication?.processIdentifier == app.processIdentifier,
               focusedWindow(application, equals: window) { return }
            RunLoop.current.run(until: Date().addingTimeInterval(0.02))
        }
        throw AutomationError.windowNotFocused
    }
    func observe(scope: String) throws -> Observation {
        guard permitted(), targetValid() else { throw AutomationError.targetChanged }
        var controls: [Control] = []; var visited: Set<CFHashCode> = []; var truncated = false
        var bytes = 0; let deadline = ProcessInfo.processInfo.systemUptime + 3
        var documentOrigins: Set<String> = []
        var originChanged = false
        sensitivePresent = false; references = [:]
        func short(_ value: String, max: Int = 500) -> String {
            var result = String(value.prefix(max)).replacingOccurrences(of: "\u{0000}", with: "")
            while result.utf8.count > max { result.removeLast() }
            return AutomationPolicy.plain(result, max: max) ? result : "[unsupported text]"
        }
        func walk(_ element: AXUIElement, path: String, depth: Int) {
            guard controls.count < 240, depth <= 12, bytes < 20_000, ProcessInfo.processInfo.systemUptime < deadline else { truncated = true; return }
            let hash = CFHash(element); guard !visited.contains(hash) else { return }; visited.insert(hash)
            let role = axString(element, kAXRoleAttribute)
            let subrole = axString(element, kAXSubroleAttribute)
            if (axValue(element, "AXHidden") as? Bool) == true { return }
            let href: String? = ["AXWebArea", "AXLink"].contains(role)
                ? ((axValue(element, kAXURLAttribute) as? URL)?.absoluteString ?? (axValue(element, kAXURLAttribute) as? String)) : nil
            if browser, role == "AXWebArea", let href, let origin = AutomationPolicy.origin(href) {
                if documentOrigins.isEmpty, let scopedOrigin, origin != scopedOrigin { originChanged = true; return }
                if !documentOrigins.isEmpty && !documentOrigins.contains(origin) {
                    sensitivePresent = true
                    controls.append(Control(id: path, role: role, label: "[other origin omitted]", enabled: false, editable: false, pressable: false, sensitive: true))
                    return
                }
                documentOrigins.insert(origin)
            }
            let parts = [axString(element, kAXTitleAttribute), axString(element, kAXDescriptionAttribute),
                         axString(element, kAXHelpAttribute), axString(element, "AXPlaceholderValue")].filter { !$0.isEmpty }
            let label = short(parts.first ?? (role == "AXScrollBar" ? "Scroll bar" : ""))
            var sensitive = AutomationPolicy.sensitive(role, subrole, parts.joined(separator: " ")) || parts.contains(where: AutomationPolicy.credentialLike)
            if let href, let url = URLComponents(string: href) {
                sensitive = sensitive || url.user != nil || url.password != nil || (url.queryItems ?? []).contains {
                    AutomationPolicy.sensitiveWords.contains(where: $0.name.lowercased().contains)
                }
            }
            // Never request the value or descendants of a known secure control.
            let characters = sensitive ? 0 : ((axValue(element, kAXNumberOfCharactersAttribute) as? NSNumber)?.intValue ?? 0)
            let rawValue = sensitive || characters > 2000 ? nil : axValue(element, kAXValueAttribute)
            let rawText = rawValue as? String
            if rawText.map(AutomationPolicy.credentialLike) == true { sensitive = true }
            let clipped = characters > 2000 || (rawText?.utf8.count ?? 0) > 2000 || (parts.first?.utf8.count ?? 0) > 500
            let value = sensitive ? nil : rawText.map { short($0, max: 2000) }
                ?? (role == "AXScrollBar" ? (rawValue as? NSNumber).map { String(format: "%.4f", $0.doubleValue) } : nil)
            sensitivePresent = sensitivePresent || sensitive
            var editable: DarwinBoolean = false
            if !sensitive { AXUIElementIsAttributeSettable(element, kAXValueAttribute as CFString, &editable) }
            var actions: CFArray?
            AXUIElementCopyActionNames(element, &actions)
            let pressable = !sensitive && ((actions as? [String]) ?? []).contains(kAXPressAction)
            let enabled = (axValue(element, kAXEnabledAttribute) as? Bool) ?? true
            let node = Control(id: path, role: role, label: sensitive ? "[protected control]" : label,
                value: value, enabled: enabled, editable: !sensitive && !clipped && editable.boolValue && (rawText != nil || role == "AXScrollBar"),
                pressable: pressable && !clipped, sensitive: sensitive, href: sensitive ? nil : href, clipped: clipped)
            controls.append(node); references[path] = element; bytes += label.utf8.count + (value?.utf8.count ?? 0)
            if !sensitive {
                if role == "AXScrollArea" {
                    // macOS overlay scrollers are not reliably children of the scroll area until they are
                    // revealed; Apple also exposes them through dedicated relationships. Each is walked with
                    // the same bounds, deadline and window: everything here is inside the bound window.
                    for (suffix, attribute) in [("scrollV", "AXVerticalScrollBar"), ("scrollH", "AXHorizontalScrollBar")] {
                        guard controls.count < 240, depth + 1 <= 12, bytes < 20_000,
                              ProcessInfo.processInfo.systemUptime < deadline else { truncated = true; break }
                        if let scroller = axElementValue(element, attribute) {
                            walk(scroller, path: path + "." + suffix, depth: depth + 1)
                        }
                    }
                }
                var count: CFIndex = 0
                if AXUIElementGetAttributeValueCount(element, kAXChildrenAttribute as CFString, &count) == .success && count > 80 { truncated = true }
                for (index, child) in axElements(element, kAXChildrenAttribute, max: 80).enumerated() { walk(child, path: path + "." + String(index), depth: depth + 1) }
            }
        }
        walk(window, path: "n", depth: 0)
        if originChanged { throw AutomationError.targetChanged }
        let origin = browser && documentOrigins.count == 1 ? documentOrigins.first : nil
        if browser, let scopedOrigin, origin != scopedOrigin { throw AutomationError.targetChanged }
        if browser, scopedOrigin == nil { scopedOrigin = origin }
        return Observation(scopeID: scope, window: short(axString(window, kAXTitleAttribute)), controls: controls, truncated: truncated, browser: browser, origin: origin)
    }
    func perform(_ step: Step, control: Control) throws {
        guard permitted(), targetValid(), NSWorkspace.shared.frontmostApplication?.processIdentifier == app.processIdentifier,
              focusedWindow(application, equals: window),
              let element = references[control.id] else { throw AutomationError.targetChanged }
        switch step.operation {
        case "press":
            guard AXUIElementPerformAction(element, kAXPressAction as CFString) == .success else { throw AutomationError.unsupported }
        case "set_text":
            guard let text = step.text,
                  AXUIElementSetAttributeValue(element, kAXValueAttribute as CFString, text as CFString) == .success else { throw AutomationError.unsupported }
        case "key":
            guard CGPreflightPostEventAccess(),
                  AXUIElementSetAttributeValue(element, kAXFocusedAttribute as CFString, kCFBooleanTrue) == .success,
                  focusedWindow(application, equals: window),
                  let focused = axValue(application, kAXFocusedUIElementAttribute), CFEqual(focused, element) else { throw AutomationError.permissionRequired }
            let key: CGKeyCode
            switch step.text { case "enter": key = 36; case "tab": key = 48; case "escape": key = 53; default: throw AutomationError.invalidPlan }
            guard let down = CGEvent(keyboardEventSource: nil, virtualKey: key, keyDown: true),
                  let up = CGEvent(keyboardEventSource: nil, virtualKey: key, keyDown: false) else { throw AutomationError.unsupported }
            down.postToPid(app.processIdentifier); up.postToPid(app.processIdentifier)
        case "scroll":
            guard let old = axValue(element, kAXValueAttribute) as? NSNumber else { throw AutomationError.unsupported }
            let low = (axValue(element, kAXMinValueAttribute) as? NSNumber)?.doubleValue ?? 0
            let high = (axValue(element, kAXMaxValueAttribute) as? NSNumber)?.doubleValue ?? 1
            guard high > low else { throw AutomationError.unsupported }
            let value: Double
            switch step.text {
            case "start": value = low
            case "end": value = high
            case "increment": value = min(high, old.doubleValue + (high-low)*0.2)
            case "decrement": value = max(low, old.doubleValue - (high-low)*0.2)
            default: throw AutomationError.invalidPlan
            }
            guard AXUIElementSetAttributeValue(element, kAXValueAttribute as CFString, NSNumber(value: value)) == .success else { throw AutomationError.unsupported }
        default: throw AutomationError.invalidPlan
        }
        // Allow the target's event loop to apply the event; never keep retrying an action.
        RunLoop.current.run(until: Date().addingTimeInterval(0.12))
    }
    func capture(scope: String) async throws -> [String: Any] {
        guard CGPreflightScreenCaptureAccess() else { throw AutomationError.capturePermissionRequired }
        let before = try observe(scope: scope)
        guard !sensitivePresent, !before.truncated, let frame = rect(window) else { throw AutomationError.unsafeTarget }
        let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: true)
        let matches = content.windows.filter { $0.owningApplication?.processID == app.processIdentifier
            && ($0.title ?? "") == before.window && abs($0.frame.minX-frame.minX) < 2 && abs($0.frame.minY-frame.minY) < 2
            && abs($0.frame.width-frame.width) < 2 && abs($0.frame.height-frame.height) < 2 }
        guard matches.count == 1 else { throw AutomationError.unsafeTarget }
        let filter = SCContentFilter(desktopIndependentWindow: matches[0]); let config = SCStreamConfiguration()
        let scale = min(1, 1024/max(frame.width, frame.height))
        config.width = max(1, Int(frame.width * scale)); config.height = max(1, Int(frame.height * scale)); config.showsCursor = false
        let image = try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: config)
        let after = try observe(scope: scope)
        guard targetValid(), !sensitivePresent, after.digest == before.digest else { throw AutomationError.staleObservation }
        let bitmap = NSBitmapImageRep(cgImage: image)
        guard let data = bitmap.representation(using: .jpeg, properties: [.compressionFactor: 0.65]), data.count <= 1_000_000 else { throw AutomationError.unsupported }
        let request = VNRecognizeTextRequest(); request.recognitionLevel = .accurate; request.usesLanguageCorrection = false
        try VNImageRequestHandler(cgImage: image).perform([request])
        let text = String((request.results ?? []).prefix(100).compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n").prefix(6000))
        // A screenshot can show text that a secure field would have hidden. The owner approved one
        // capture of this window, not the disclosure of a credential-shaped string, so publish
        // neither the image nor the text rather than filtering afterwards.
        guard !AutomationPolicy.credentialLike(text) else { throw AutomationError.unsafeTarget }
        return ["mime": "image/jpeg", "image_base64": data.base64EncodedString(), "ocr": text,
                "window": before.window, "scope_id": scope, "width": config.width, "height": config.height,
                "sent_to_model": false, "persisted": false]
    }
}

@MainActor func runningApplications() -> [[String: Any]] {
    NSWorkspace.shared.runningApplications.filter { $0.activationPolicy == .regular && $0.bundleIdentifier != nil }.prefix(100).map {
        ["pid": $0.processIdentifier, "name": String(($0.localizedName ?? "Application").prefix(100)),
         "bundle_id": $0.bundleIdentifier!, "allowed": AutomationPolicy.permittedApp($0.bundleIdentifier!)]
    }
}
