import Foundation
import CryptoKit

enum AutomationError: String, Error { case invalidRequest, permissionRequired, scopeExpired, targetChanged, unsupported,
    unsafeTarget, staleObservation, actionNotConfirmed, invalidPlan, cancelled, verificationFailed, capturePermissionRequired }

struct Control: Codable, Equatable {
    var id: String
    var role: String
    var label: String
    var value: String?
    var enabled: Bool
    var editable: Bool
    var pressable: Bool
    var sensitive: Bool
    var href: String? = nil
    var clipped: Bool = false
}
struct Observation: Codable, Equatable {
    var scopeID: String
    var window: String
    var controls: [Control]
    var truncated: Bool
    var browser: Bool = false
    var origin: String? = nil
    var digest: String {
        let encoder = JSONEncoder(); encoder.outputFormatting = [.sortedKeys]
        return SHA256.hash(data: (try? encoder.encode(self)) ?? Data()).map { String(format: "%02x", $0) }.joined()
    }
}
struct Step: Codable, Equatable { var operation: String; var target: String; var text: String? }
struct Expected: Codable, Equatable { var target: String; var attribute: String; var equals: String }
struct Proposal: Codable, Equatable { var summary: String; var steps: [Step]; var expected: Expected }

enum AutomationPolicy {
    static let blockedApps: Set<String> = ["com.apple.Passwords", "com.apple.keychainaccess", "com.apple.SecurityAgent",
        "com.apple.loginwindow", "com.apple.systempreferences", "com.apple.Terminal", "com.googlecode.iterm2",
        "dev.warp.Warp-Stable", "com.apple.ScriptEditor2", "com.apple.Automator", "com.apple.shortcuts",
        "com.microsoft.VSCode", "com.apple.dt.Xcode", "local.personalcodex.desktop",
        "local.personalcodex.desktop.macactionsverification", "local.personalcodex.automation"]
    static let sensitiveWords = ["password", "passphrase", "secret", "token", "credit card", "security code", "private key", "social security"]
    static let consequentialWords = ["delete", "erase", "remove", "uninstall", "purchase", "checkout", "transfer", "pay", "buy",
        "send", "publish", "post", "share", "submit", "install", "grant", "allow", "authorize", "approve", "sign in", "log in",
        "security", "reset", "restart", "shut down", "agree", "accept terms", "wallet"]
    static func plain(_ value: String, max: Int) -> Bool {
        value.utf8.count <= max && !value.unicodeScalars.contains {
            CharacterSet.controlCharacters.contains($0) || (0x202A...0x202E).contains($0.value) || (0x2066...0x2069).contains($0.value)
        }
    }
    static func sensitive(_ role: String, _ subrole: String, _ label: String) -> Bool {
        let joined = (role + " " + subrole + " " + label).lowercased()
        return joined.contains("secure") || sensitiveWords.contains(where: joined.contains)
    }
    static func credentialLike(_ value: String) -> Bool {
        value.contains("-----BEGIN") || value.range(of: "(?:ghp_|github_pat_|sk-proj-|sk-)[A-Za-z0-9_-]{16,}|(?i:bearer) [A-Za-z0-9_-]{24,}|(?i:token|password|secret|api[_-]?key)\\s*[:=]\\s*[^\\s&]{4,}|https?://[^ /:@]+:[^ @/]+@", options: .regularExpression) != nil
    }
    static func blockedLabel(_ value: String) -> Bool {
        let words = value.lowercased().components(separatedBy: CharacterSet.alphanumerics.inverted).filter { !$0.isEmpty }
        return consequentialWords.contains { term in
            term.contains(" ") ? value.lowercased().contains(term) : words.contains(term)
        }
    }
    static func permittedApp(_ identifier: String) -> Bool {
        !identifier.isEmpty && !blockedApps.contains(identifier) && !["1password", "onepassword", "bitwarden", "keepass", "dashlane"].contains(where: identifier.lowercased().contains) && !identifier.hasPrefix("com.jetbrains.")
            && !identifier.hasPrefix("local.personalcodex.desktop.")
    }
    static func origin(_ raw: String) -> String? {
        if raw == "about:blank" { return raw }
        guard let url = URLComponents(string: raw), ["http", "https"].contains(url.scheme ?? ""),
              let host = url.host, !host.isEmpty, url.user == nil, url.password == nil else { return nil }
        return (url.scheme ?? "") + "://" + host.lowercased() + (url.port.map { ":\($0)" } ?? "")
    }
    static func decode(_ data: Data) throws -> Proposal {
        guard data.count <= 24_000,
              let object = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              Set(object.keys) == ["summary", "steps", "expected"],
              let steps = object["steps"] as? [[String: Any]],
              let expected = object["expected"] as? [String: Any],
              Set(expected.keys) == ["target", "attribute", "equals"],
              steps.allSatisfy({ Set($0.keys).isSubset(of: ["operation", "target", "text"])
                  && Set($0.keys).isSuperset(of: ["operation", "target"]) }) else { throw AutomationError.invalidPlan }
        return try JSONDecoder().decode(Proposal.self, from: data)
    }
    static func validate(_ plan: Proposal, observation: Observation) throws {
        guard plain(plan.summary, max: 400), !plan.summary.isEmpty, (1...8).contains(plan.steps.count),
              (!observation.browser || observation.origin != nil), plain(plan.expected.equals, max: 2000), !plan.expected.equals.isEmpty,
              ["value", "label"].contains(plan.expected.attribute),
              let end = observation.controls.first(where: { $0.id == plan.expected.target }), !end.sensitive, !end.clipped,
              !end.pressable, ["AXStaticText", "AXTextField", "AXTextArea", "AXComboBox", "AXScrollBar"].contains(end.role),
              (plan.expected.attribute == "value" ? end.value != nil : !end.label.isEmpty),
              (plan.expected.attribute == "value" ? end.value : end.label) != plan.expected.equals else {
            throw AutomationError.invalidPlan
        }
        for step in plan.steps { try validateAction(step, observation: observation) }
    }
    static func validateAction(_ step: Step, observation: Observation) throws {
            guard let control = observation.controls.first(where: { $0.id == step.target }), control.enabled,
                  !control.sensitive, !control.clipped, !control.label.isEmpty, !blockedLabel(control.label) else { throw AutomationError.unsafeTarget }
            switch step.operation {
            case "press":
                guard control.pressable, step.text == nil,
                      ["AXButton", "AXCheckBox", "AXRadioButton", "AXPopUpButton", "AXMenuItem", "AXLink"].contains(control.role) else { throw AutomationError.invalidPlan }
                if control.role == "AXLink" {
                    guard let href = control.href, origin(href) == observation.origin else { throw AutomationError.unsafeTarget }
                }
            case "set_text":
                guard control.editable, let text = step.text, plain(text, max: 2000),
                      ["AXTextField", "AXTextArea", "AXComboBox"].contains(control.role),
                      !credentialLike(text), !text.contains("/.ssh/"), !text.contains("/.aws/"),
                      !["javascript:", "data:", "file:", "chrome:", "resource:"].contains(where: text.lowercased().contains) else { throw AutomationError.unsafeTarget }
                if observation.browser, let origin = origin(text), origin != observation.origin { throw AutomationError.unsafeTarget }
            case "key":
                guard control.editable, let key = step.text, ["enter", "tab", "escape"].contains(key) else { throw AutomationError.invalidPlan }
            case "scroll":
                guard control.role == "AXScrollBar", control.editable,
                      ["increment", "decrement", "start", "end"].contains(step.text ?? "") else { throw AutomationError.invalidPlan }
            default: throw AutomationError.invalidPlan
            }
    }
    static func matched(_ expected: Expected, in observation: Observation) -> Bool {
        guard let control = observation.controls.first(where: { $0.id == expected.target }), !control.sensitive, !control.clipped else { return false }
        return (expected.attribute == "value" ? control.value : control.label) == expected.equals
    }
}

@MainActor protocol AutomationDriver: AnyObject {
    func permitted() -> Bool
    func targetValid() -> Bool
    func observe(scope: String) throws -> Observation
    func activate() throws
    func perform(_ step: Step, control: Control) throws
}

@MainActor final class AutomationSession {
    let id = UUID().uuidString
    let driver: AutomationDriver
    let now: () -> TimeInterval
    let created: TimeInterval
    var observation: Observation?
    var pending: (id: String, proposal: Proposal, digest: String, created: TimeInterval)?
    var cancelled = false
    var completedActions = 0
    var onEvent: ((String, Int, String) -> Void)?
    init(driver: AutomationDriver, now: @escaping () -> TimeInterval = { ProcessInfo.processInfo.systemUptime }) { self.driver = driver; self.now = now; created = now() }
    func check() throws {
        guard !cancelled else { throw AutomationError.cancelled }
        guard now()-created >= 0, now()-created < 600, completedActions < 32 else { throw AutomationError.scopeExpired }
        guard driver.permitted() else { throw AutomationError.permissionRequired }
        guard driver.targetValid() else { throw AutomationError.targetChanged }
    }
    func observe() throws -> Observation { try check(); let result = try driver.observe(scope: id); observation = result; return result }
    func prepare(_ proposal: Proposal, digest: String) throws -> String {
        pending = nil
        let current = try observe()
        guard current.digest == digest else { throw AutomationError.staleObservation }
        try AutomationPolicy.validate(proposal, observation: current)
        let key = UUID().uuidString
        pending = (key, proposal, current.digest, now()); return key
    }
    func execute(id key: String, confirmed: Bool) throws -> [String: Any] {
        let chosen = pending; pending = nil
        guard let chosen, chosen.id == key, confirmed, now()-chosen.created >= 0, now()-chosen.created < 120 else { throw AutomationError.actionNotConfirmed }
        let start = try observe()
        guard start.digest == chosen.digest else { throw AutomationError.staleObservation }
        try driver.activate()
        var current = start
        var performed = 0
        for (index, step) in chosen.proposal.steps.enumerated() {
            try check()
            let latest = try driver.observe(scope: id)
            guard latest.digest == current.digest,
                  let control = latest.controls.first(where: { $0.id == step.target }) else { throw AutomationError.staleObservation }
            try check()
            try AutomationPolicy.validateAction(step, observation: latest)
            onEvent?("started", index, step.operation)
            try driver.perform(step, control: control)
            performed += 1; completedActions += 1
            onEvent?("finished", index, step.operation)
            current = try driver.observe(scope: id)
        }
        let deadline = ProcessInfo.processInfo.systemUptime + 2
        while !AutomationPolicy.matched(chosen.proposal.expected, in: current), ProcessInfo.processInfo.systemUptime < deadline {
            try check()
            RunLoop.current.run(until: Date().addingTimeInterval(0.05))
            current = try driver.observe(scope: id)
        }
        observation = current
        let matched = AutomationPolicy.matched(chosen.proposal.expected, in: current)
        return ["status": matched ? "verified" : "needs_review", "actions": performed,
                "postcondition_matched": matched, "scope_id": id, "observation": try jsonObject(current),
                "meaning": "Approved actions and this exact postcondition only; not general task correctness."]
    }
}

func jsonObject<T: Encodable>(_ value: T) throws -> Any { try JSONSerialization.jsonObject(with: JSONEncoder().encode(value)) }
