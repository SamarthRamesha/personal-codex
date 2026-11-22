import AppKit
import ApplicationServices
import CoreGraphics

/// Exercises the production driver against an owned disposable app. Never selects a personal app.
@MainActor func actualUISelfCheck(includeCapture: Bool) async throws -> [String: Any] {
    guard AXIsProcessTrusted() else {
        return ["status": "permission_required", "actual_ui_exercised": false,
                "reason": "Grant Accessibility manually to this application, then run the self-check again."]
    }
    _ = NSApplication.shared
    var stage = "launch_fixture"
    var checks: [[String: Any]] = []
    var targetState: (() -> [String: Bool])?
    var actionCount: (() -> Int)?
    var actualUI = false
    var beforeCleanup: [String: Bool] = [:]
    var completedBeforeCleanup = 0
    do {
    let identifier = "local.personalcodex.automation.fixture"
    guard !NSWorkspace.shared.runningApplications.contains(where: { $0.bundleIdentifier == identifier }),
          let resources = Bundle.main.resourceURL else { throw AutomationError.unsafeTarget }
    let fixtureURL = resources.appendingPathComponent("Fixtures/Personal Codex Automation Fixture.app")
    guard FileManager.default.fileExists(atPath: fixtureURL.appendingPathComponent("Contents/MacOS/automation-fixture").path) else { throw AutomationError.unsupported }
    let options = NSWorkspace.OpenConfiguration(); options.activates = true; options.createsNewApplicationInstance = true
    let app = try await NSWorkspace.shared.openApplication(at: fixtureURL, configuration: options)
    // Terminate only the exact new fixture instance launched here. It contains no user documents.
    defer {
        beforeCleanup = targetState?() ?? [:]; completedBeforeCleanup = actionCount?() ?? 0
        if app.bundleIdentifier == identifier && !app.isTerminated { app.terminate() }
    }
    guard app.bundleIdentifier == identifier else { throw AutomationError.unsafeTarget }
    actualUI = true; stage = "find_fixture_windows"
    let application = AXUIElementCreateApplication(app.processIdentifier)
    AXUIElementSetMessagingTimeout(application, 0.35)
    let deadline = ProcessInfo.processInfo.systemUptime + 3
    var windows: [AXUIElement] = []
    while ProcessInfo.processInfo.systemUptime < deadline {
        windows = axElements(application, kAXWindowsAttribute, max: 20)
        if windows.count == 2 { break }
        try await Task.sleep(nanoseconds: 30_000_000)
    }
    // Both windows must exist, but the primary is bound by title rather than by whatever index the
    // first listing happened to give it.
    guard windows.contains(where: { axString($0, kAXTitleAttribute) == "Personal Codex Protected Fixture" }),
          let primary = windows.firstIndex(where: { axString($0, kAXTitleAttribute) == "Personal Codex Automation Fixture" }) else { throw AutomationError.verificationFailed }
    // Bind with the identity the listing reported, so the guarded path is the one under test.
    let driver = try NativeDriver(pid: app.processIdentifier, windowIndex: primary,
                                  expectedTitle: axString(windows[primary], kAXTitleAttribute),
                                  expectedNumber: axInt(windows[primary], "AXWindowNumber"))
    let session = AutomationSession(driver: driver)
    targetState = { driver.diagnostics() }; actionCount = { session.completedActions }
    stage = "read_primary_window"
    let initial = try session.observe()
    func find(_ snapshot: Observation, label: String, role: String) throws -> Control {
        guard let node = snapshot.controls.first(where: { $0.label == label && $0.role == role }) else { throw AutomationError.verificationFailed }
        return node
    }
    let input = try find(initial, label: "Message", role: "AXTextField")
    let button = try find(initial, label: "Preview", role: "AXButton")
    let result = try find(initial, label: "Result", role: "AXStaticText")
    let plan = Proposal(summary: "Preview synthetic text in the disposable fixture",
        steps: [Step(operation: "set_text", target: input.id, text: "hello"), Step(operation: "press", target: button.id)],
        expected: Expected(target: result.id, attribute: "value", equals: "Preview: hello"))
    stage = "prepare_native_text_and_press"
    let key = try session.prepare(plan, digest: initial.digest)
    func record(_ name: String, _ pass: Bool) { checks.append(["name": name, "passed": pass]) }
    record("prepare_is_read_only", try session.observe().digest == initial.digest)
    stage = "window_identity_check"
    // A wrong identity must be refused rather than silently controlling this window.
    var identityRefused = false
    do { _ = try NativeDriver(pid: app.processIdentifier, windowIndex: primary, expectedTitle: "Not this window") }
    catch AutomationError.targetChanged { identityRefused = true }
    catch { }
    record("window_identity_refused", identityRefused)
    // The window number is the stronger identity, so exercise it too when the fixture exposes one.
    if let number = axInt(windows[primary], "AXWindowNumber") {
        var numberRefused = false
        do { _ = try NativeDriver(pid: app.processIdentifier, windowIndex: primary,
                                  expectedTitle: axString(windows[primary], kAXTitleAttribute),
                                  expectedNumber: number + 1) }
        catch AutomationError.targetChanged { numberRefused = true }
        catch { }
        record("window_number_identity_refused", numberRefused)
    }
    stage = "execute_native_text_and_press"
    let run = try session.execute(id: key, confirmed: true)
    record("native_text_and_press_result", run["status"] as? String == "verified")
    // A consumed approval must be refused for that reason; any other error is reported as a failure
    // so an unrelated fault cannot make one-use enforcement look proven.
    do { _ = try session.execute(id: key, confirmed: true); record("approval_is_one_use", false) }
    catch AutomationError.actionNotConfirmed { record("approval_is_one_use", true) }
    catch { record("approval_is_one_use", false) }
    stage = "native_checkbox"
    let observed = try session.observe()
    let checkbox = try find(observed, label: "Uppercase", role: "AXCheckBox")
    let uppercase = Proposal(summary: "Preview uppercase synthetic text",
        steps: [Step(operation: "press", target: checkbox.id), Step(operation: "press", target: button.id)],
        expected: Expected(target: result.id, attribute: "value", equals: "Preview: HELLO"))
    let upperKey = try session.prepare(uppercase, digest: observed.digest)
    record("native_checkbox_and_result", try session.execute(id: upperKey, confirmed: true)["status"] as? String == "verified")
    stage = "native_scrollbar"
    let fresh = try session.observe()
    let bars = fresh.controls.filter { $0.role == "AXScrollBar" && $0.editable && $0.value != nil }
    // A scroll area can expose both bars. The synthetic list scrolls vertically, and a horizontal bar
    // can be present but immovable, so prefer the vertical one deterministically instead of whichever
    // the traversal reached first. Paths from the relationship walk end in .scrollV / .scrollH.
    let bar = bars.first(where: { $0.id.hasSuffix(".scrollV") }) ?? bars.first
    if let bar {
        let destination = bar.value == "1.0000" ? "start" : "end"
        let scroll = Proposal(summary: "Scroll the synthetic list", steps: [Step(operation: "scroll", target: bar.id, text: destination)],
            expected: Expected(target: bar.id, attribute: "value", equals: destination == "end" ? "1.0000" : "0.0000"))
        let scrollKey = try session.prepare(scroll, digest: fresh.digest)
        record("native_scrollbar_result", try session.execute(id: scrollKey, confirmed: true)["status"] as? String == "verified")
    } else {
        // Report why, so an owner-run failure can be diagnosed without guessing.
        checks.append(["name": "native_scrollbar_result", "passed": false,
                       "detail": "no editable scrollbar with a value was observed"])
    }
    stage = "stale_approval_check"
    let stale = try session.observe()
    var changed = plan; changed.expected.equals = "Preview: new"
    changed.steps[0].text = "new"
    let staleKey = try session.prepare(changed, digest: stale.digest)
    // Simulate a concurrent user edit only inside our own fixture.
    try driver.activate(); try driver.perform(Step(operation: "set_text", target: input.id, text: "external fixture edit"), control: input)
    do { _ = try session.execute(id: staleKey, confirmed: true); record("stale_window_refused", false) }
    catch AutomationError.staleObservation { record("stale_window_refused", true) }
    stage = "secure_window_check"
    // Focus changes reorder the accessible window list, so an index captured at launch can name the
    // ordinary window here. Re-resolve the protected window by identity instead of trusting it.
    let liveWindows = axElements(application, kAXWindowsAttribute, max: 20)
    guard let protectedIndex = liveWindows.firstIndex(where: { axString($0, kAXTitleAttribute) == "Personal Codex Protected Fixture" }) else {
        throw AutomationError.verificationFailed
    }
    let secure = try NativeDriver(pid: app.processIdentifier, windowIndex: protectedIndex,
                                  expectedTitle: "Personal Codex Protected Fixture")
    let secureSnapshot = try secure.observe(scope: "disposable-secure-check")
    let serialized = try JSONEncoder().encode(secureSnapshot)
    record("secure_control_omitted", secureSnapshot.controls.contains(where: { $0.sensitive })
        && !String(decoding: serialized, as: UTF8.self).contains("DISPOSABLE-SYNTHETIC-SECRET"))
    record("selected_window_isolation", !initial.controls.contains(where: { $0.sensitive }) && initial.window != secureSnapshot.window)
    stage = "optional_capture"
    if includeCapture {
        if CGPreflightScreenCaptureAccess() {
            let capture = try await driver.capture(scope: session.id)
            record("selected_window_capture_and_ocr", capture["window"] as? String == initial.window
                && (capture["ocr"] as? String ?? "").contains("AMBER") && capture["image_base64"] != nil)
            do { _ = try await secure.capture(scope: "disposable-secure-check"); record("secure_window_capture_refused", false) }
            catch AutomationError.unsafeTarget { record("secure_window_capture_refused", true) }
        } else { record("selected_window_capture_and_ocr", false) }
    }
    session.cancelled = true
    do { _ = try session.observe(); record("cancelled_scope_refused", false) }
    catch AutomationError.cancelled { record("cancelled_scope_refused", true) }
    stage = "complete"
    return ["status": checks.allSatisfy { $0["passed"] as? Bool == true } ? "passed" : "needs_review",
            "actual_ui_exercised": true, "target": identifier, "checks": checks,
            "capture_requested": includeCapture, "browser_exercised": false,
            "meaning": "Only these synthetic native-window checks; not universal app compatibility or visual product acceptance."]
    } catch {
        return ["status": "failed", "stage": stage, "error": String(describing: error),
                "actual_ui_exercised": actualUI, "checks": checks, "completed_actions": completedBeforeCleanup,
                "target_state": beforeCleanup,
                "meaning": "Stopped without retry. Only synthetic fixture metadata is reported; no personal window data."]
    }

}
