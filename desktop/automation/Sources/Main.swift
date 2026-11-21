import AppKit
import ApplicationServices
import CoreGraphics

func encoded<T: Encodable>(_ value: T) throws -> Any { try JSONSerialization.jsonObject(with: JSONEncoder().encode(value)) }
func encoded(_ value: Observation) throws -> Any {
    var result = try JSONSerialization.jsonObject(with: JSONEncoder().encode(value)) as! [String: Any]
    result["digest"] = value.digest; return result
}
func emit(_ value: [String: Any]) {
    guard let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]) else { return }
    FileHandle.standardOutput.write(data); FileHandle.standardOutput.write(Data([10]))
}

@MainActor final class Engine {
    var session: AutomationSession?
    func handle(_ request: [String: Any], id: String) async throws -> [String: Any] {
        guard let operation = request["op"] as? String else { throw AutomationError.invalidRequest }
        switch operation {
        case "self_check":
            guard request["confirmed"] as? Bool == true else { throw AutomationError.actionNotConfirmed }
            session = nil
            return try await actualUISelfCheck(includeCapture: request["capture"] as? Bool == true)
        case "status": return ["accessibility": AXIsProcessTrusted(), "screen_capture": CGPreflightScreenCaptureAccess(),
                               "key_events": CGPreflightPostEventAccess(), "helper": Bundle.main.bundleIdentifier ?? "local.personalcodex.automation",
                               "session_active": session != nil]
        case "request_accessibility":
            guard request["confirmed"] as? Bool == true else { throw AutomationError.actionNotConfirmed }
            let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true]
            return ["accessibility": AXIsProcessTrustedWithOptions(options as CFDictionary), "owner_approval_required": true]
        case "request_capture":
            guard request["confirmed"] as? Bool == true else { throw AutomationError.actionNotConfirmed }
            return ["screen_capture": CGRequestScreenCaptureAccess(), "owner_approval_required": true]
        case "applications": return ["applications": runningApplications()]
        case "new_browser":
            guard request["confirmed"] as? Bool == true, let bundle = request["browser"] as? String,
                  let destination = request["url"] as? String else { throw AutomationError.actionNotConfirmed }
            session = nil
            let driver = try await newBrowserWindow(bundle: bundle, destination: destination)
            let selected = AutomationSession(driver: driver); session = selected
            return ["scope_id": selected.id, "snapshot": try encoded(selected.observe()), "expires_in_seconds": 600,
                    "app": driver.app.localizedName ?? "Browser", "bundle_id": driver.identifier, "pid": driver.app.processIdentifier, "new_window_verified": true]
        case "windows":
            guard AXIsProcessTrusted(), request["confirmed"] as? Bool == true, let pid = request["pid"] as? Int,
                  let app = NSRunningApplication(processIdentifier: pid_t(pid)), let bundle = app.bundleIdentifier,
                  AutomationPolicy.permittedApp(bundle) else { throw AutomationError.permissionRequired }
            let ax = AXUIElementCreateApplication(pid_t(pid)); AXUIElementSetMessagingTimeout(ax, 0.35)
            return ["windows": axElements(ax, kAXWindowsAttribute, max: 20).enumerated().map { position, window -> [String: Any] in
                var entry: [String: Any] = ["index": position, "title": String(axString(window, kAXTitleAttribute).prefix(200))]
                // A stable identity across reordering; the title alone is not. Omitted when unavailable.
                if let number = axInt(window, "AXWindowNumber") { entry["number"] = number }
                return entry
            }]
        case "begin":
            session = nil
            guard request["confirmed"] as? Bool == true, let pid = request["pid"] as? Int, let index = request["window_index"] as? Int else { throw AutomationError.actionNotConfirmed }
            // The caller's listed title is carried through so a shifted index is refused, not obeyed.
            let driver = try NativeDriver(pid: pid_t(pid), windowIndex: index, expectedTitle: request["window_title"] as? String,
                                          expectedNumber: request["window_number"] as? Int)
            let selected = AutomationSession(driver: driver); session = selected
            return ["scope_id": selected.id, "snapshot": try encoded(selected.observe()), "expires_in_seconds": 600,
                    "app": driver.app.localizedName ?? "Application", "bundle_id": driver.identifier, "pid": driver.app.processIdentifier]
        case "cancel": session?.cancelled = true; session = nil; return ["status": "cancelled"]
        default: break
        }
        guard let selected = session, request["scope_id"] as? String == selected.id else { throw AutomationError.scopeExpired }
        switch operation {
        case "observe": return ["snapshot": try encoded(selected.observe())]
        case "prepare":
            guard let json = request["proposal"] as? String, let data = json.data(using: .utf8),
                  let digest = request["observation_digest"] as? String else { throw AutomationError.invalidPlan }
            let proposal = try AutomationPolicy.decode(data)
            let key = try selected.prepare(proposal, digest: digest)
            return ["plan_id": key, "proposal": try encoded(proposal), "observation_digest": digest,
                    "expires_in_seconds": 120, "effect": "Focus the selected window and perform only these approved controls."]
        case "execute":
            guard let key = request["plan_id"] as? String else { throw AutomationError.invalidPlan }
            selected.onEvent = { stage, index, operation in emit(["id": id, "event": "action", "stage": stage, "index": index, "operation": operation]) }
            defer { selected.onEvent = nil }
            let result = try selected.execute(id: key, confirmed: request["confirmed"] as? Bool == true)
            return result.merging(["snapshot": try encoded(selected.observation!)]) { _, new in new }
        case "capture":
            guard request["confirmed"] as? Bool == true, let driver = selected.driver as? NativeDriver else { throw AutomationError.actionNotConfirmed }
            try selected.check(); return try await driver.capture(scope: selected.id)
        default: throw AutomationError.invalidRequest
        }
    }
}

@main struct Main {
    @MainActor static func main() async {
        if CommandLine.arguments.contains("--self-test") { selfTests(); return }
        if CommandLine.arguments.contains("--synthetic-observation") {
            do { emit(["snapshot": try encoded(FakeDriver().observe(scope: "synthetic-model-acceptance")), "actual_ui_exercised": false]) }
            catch { emit(["error": "invalid_synthetic_fixture"]) }; return
        }
        if CommandLine.arguments.contains("--validate-synthetic-plan") {
            do {
                guard let data = try FileHandle.standardInput.read(upToCount: 24_001), data.count <= 24_000 else { throw AutomationError.invalidPlan }
                let proposal = try AutomationPolicy.decode(data)
                guard proposal.expected.target == "result", proposal.expected.attribute == "value", proposal.expected.equals == "Preview: hello" else { throw AutomationError.verificationFailed }
                let selected = AutomationSession(driver: FakeDriver())
                let key = try selected.prepare(proposal, digest: selected.observe().digest)
                let report = try selected.execute(id: key, confirmed: true)
                emit(report.merging(["actual_ui_exercised": false, "synthetic_goal": "Preview: hello"]) { _, new in new })
            } catch { emit(["error": "synthetic_plan_failed", "reason": String(describing: error), "actual_ui_exercised": false]); exit(2) }
            return
        }
        let engine = Engine()
        if CommandLine.arguments.contains("--ui-self-check") {
            do { emit(try await actualUISelfCheck(includeCapture: CommandLine.arguments.contains("--capture"))) }
            catch { emit(["status": "failed", "error": String(describing: error), "actual_ui_exercised": true]) }
            return
        }
        if CommandLine.arguments.contains("--status") {
            do { emit(try await engine.handle(["op": "status"], id: "status")) }
            catch { emit(["error": "status_unavailable"]) }; return
        }
        do {
            for try await line in FileHandle.standardInput.bytes.lines {
                guard line.utf8.count <= 48_000, let data = line.data(using: .utf8),
                      let request = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let id = request["id"] as? String, id.utf8.count <= 80 else {
                    emit(["id": "invalid", "ok": false, "error": "invalidRequest"]); continue
                }
                do { let result = try await engine.handle(request, id: id); emit(["id": id, "ok": true, "result": result]) }
                catch let error as AutomationError { emit(["id": id, "ok": false, "error": error.rawValue]) }
                catch { emit(["id": id, "ok": false, "error": "operation_failed"]) }
            }
        } catch { emit(["id": "closed", "ok": false, "error": "transport_closed"]) }
    }
}
