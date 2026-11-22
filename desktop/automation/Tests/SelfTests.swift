import Foundation

@MainActor final class FakeDriver: AutomationDriver {
    var trust = true; var valid = true; var values = ["input": "", "result": "Ready"]; var actions = 0
    var mutateBeforeAction = false; var afterAction: (() -> Void)?
    var ignoreActions = false
    var buttonLabel = "Preview"
    func permitted() -> Bool { trust }
    func targetValid() -> Bool { valid }
    func activate() throws { if !valid { throw AutomationError.targetChanged } }
    func observe(scope: String) throws -> Observation {
        Observation(scopeID: scope, window: "Synthetic fixture", controls: [
            Control(id: "input", role: "AXTextField", label: "Message", value: values["input"], enabled: true, editable: true, pressable: false, sensitive: false),
            Control(id: "button", role: "AXButton", label: buttonLabel, value: nil, enabled: true, editable: false, pressable: true, sensitive: false),
            Control(id: "result", role: "AXStaticText", label: "Result", value: values["result"]!, enabled: true, editable: false, pressable: false, sensitive: false),
            Control(id: "protected", role: "AXTextField", label: "[protected control]", value: nil, enabled: true, editable: false, pressable: false, sensitive: true)
        ], truncated: false)
    }
    func perform(_ step: Step, control: Control) throws {
        actions += 1
        if ignoreActions { return }
        if step.operation == "set_text" { values["input"] = step.text }
        if step.operation == "press" { values["result"] = "Preview: " + values["input"]! }
        afterAction?()
    }
}

@MainActor func selfTests() {
    var passed = 0
    func expect(_ value: @autoclosure () -> Bool, _ message: String) { guard value() else { fatalError(message) }; passed += 1 }
    func fails(_ body: () throws -> Void) -> Bool { do { try body(); return false } catch { return true } }
    let driver = FakeDriver(); var tick: TimeInterval = 10
    let session = AutomationSession(driver: driver, now: { tick })
    let proposal = Proposal(summary: "Preview synthetic text", steps: [Step(operation: "set_text", target: "input", text: "hello"), Step(operation: "press", target: "button")], expected: Expected(target: "result", attribute: "value", equals: "Preview: hello"))
    do {
        let observation = try session.observe(); let key = try session.prepare(proposal, digest: observation.digest)
        expect(driver.actions == 0, "Preparation must not act")
        let report = try session.execute(id: key, confirmed: true)
        expect(report["status"] as? String == "verified" && driver.actions == 2, "Actual predicate must match")
        expect(fails { _ = try session.execute(id: key, confirmed: true) }, "No replay")
        driver.values = ["input": "", "result": "Ready"]
        let fresh = try session.observe(); let unconfirmed = try session.prepare(proposal, digest: fresh.digest)
        expect(fails { _ = try session.execute(id: unconfirmed, confirmed: false) }, "Explicit confirmation")
        expect(fails { _ = try session.execute(id: unconfirmed, confirmed: true) }, "Rejected approval consumed")
        let stale = try session.prepare(proposal, digest: fresh.digest); driver.values["input"] = "external edit"
        expect(fails { _ = try session.execute(id: stale, confirmed: true) }, "External changes refuse execution")
        driver.values = ["input": "", "result": "Ready"]
        let expired = try session.prepare(proposal, digest: session.observe().digest); tick += 121
        expect(fails { _ = try session.execute(id: expired, confirmed: true) }, "Approval expires")
        tick = 10
        var unsafe = proposal; unsafe.steps[0].target = "protected"
        expect(fails { _ = try session.prepare(unsafe, digest: session.observe().digest) }, "Secure control denied")
        unsafe = proposal; unsafe.steps[0].operation = "shell"
        expect(fails { _ = try session.prepare(unsafe, digest: session.observe().digest) }, "No arbitrary operation")
        unsafe = proposal; unsafe.expected = Expected(target: "button", attribute: "label", equals: "Preview")
        expect(fails { _ = try session.prepare(unsafe, digest: session.observe().digest) }, "Button text cannot fake verification")
        unsafe = proposal; unsafe.expected = Expected(target: "result", attribute: "value", equals: "Ready")
        expect(fails { _ = try session.prepare(unsafe, digest: session.observe().digest) }, "Already-present text cannot prove changes")
        driver.trust = false
        expect(fails { _ = try session.observe() }, "Revoked permission denies reads")
        driver.trust = true; driver.valid = false
        expect(fails { _ = try session.observe() }, "Changed target refused")
        driver.valid = true; tick = 611
        expect(fails { _ = try session.observe() }, "Session expires")
        tick = 10; session.cancelled = true
        expect(fails { _ = try session.observe() }, "Cancellation denies future work")
        expect(AutomationPolicy.sensitive("AXTextField", "AXSecureTextField", ""), "Secure subrole")
        expect(AutomationPolicy.blockedLabel("Delete item"), "Consequential action")
        expect(!AutomationPolicy.blockedLabel("Calculate total"), "Ordinary controls")
        expect(!AutomationPolicy.permittedApp("com.apple.Terminal"), "No shell UI workaround")
        expect(fails { _ = try AutomationPolicy.decode(Data("{\"summary\":\"x\",\"steps\":[],\"expected\":{},\"extra\":true}".utf8)) }, "Extra proposal field refused")
        let pristine = try FakeDriver().observe(scope: "policy")
        var clipped = pristine; clipped.controls[0].clipped = true
        expect(fails { try AutomationPolicy.validate(proposal, observation: clipped) }, "Never replace unseen clipped text")
        unsafe = proposal; unsafe.steps[0] = Step(operation: "set_text", target: "protected", text: "synthetic")
        expect(fails { try AutomationPolicy.validate(unsafe, observation: pristine) }, "Protected field cannot be typed")
        unsafe = proposal; unsafe.steps[0].text = "javascript:alert(1)"
        expect(fails { try AutomationPolicy.validate(unsafe, observation: pristine) }, "No script navigation")
        unsafe = proposal; unsafe.steps = Array(repeating: proposal.steps[0], count: 9)
        expect(fails { try AutomationPolicy.validate(unsafe, observation: pristine) }, "Bounded steps")
        expect(!permittedBrowserURL("file:///etc/passwd") && !permittedBrowserURL("https://u:p@example.com"), "Private file and credential URL refused")
        expect(!permittedBrowserURL("http://example.com") && !permittedBrowserURL("https://example.com/?token=synthetic"), "Insecure remote and token URL refused")
        expect(permittedBrowserURL("https://example.com/path") && permittedBrowserURL("http://127.0.0.1:9876/"), "HTTPS and synthetic loopback URL")
        // Capture refuses on the same predicate that hides credential-shaped field values.
        expect(AutomationPolicy.credentialLike("password: hunter2") && AutomationPolicy.credentialLike("Authorization: Bearer abcdefghijklmnopqrstuvwx"), "Credential-shaped screen text is refused")
        expect(!AutomationPolicy.credentialLike("AMBER WORKFLOW · Synthetic data only"), "Ordinary captured text is allowed")
        // Browser scopes bind one origin. These are the refusals the browser workflow depends on, so
        // they are asserted here instead of only in a source-string contract test.
        let page = Observation(scopeID: "policy", window: "Synthetic page", controls: [
            Control(id: "field", role: "AXTextField", label: "Search", value: "", enabled: true, editable: true, pressable: false, sensitive: false),
            Control(id: "button", role: "AXButton", label: "Preview", value: nil, enabled: true, editable: false, pressable: true, sensitive: false),
            Control(id: "away", role: "AXLink", label: "Elsewhere", value: "Elsewhere", enabled: true, editable: false, pressable: true, sensitive: false, href: "https://other.example/"),
            Control(id: "result", role: "AXStaticText", label: "Result", value: "Ready", enabled: true, editable: false, pressable: false, sensitive: false)
        ], truncated: false, browser: true, origin: "https://example.com")
        let browserPlan = Proposal(summary: "Search the synthetic page", steps: [Step(operation: "set_text", target: "field", text: "hello"), Step(operation: "press", target: "button")], expected: Expected(target: "result", attribute: "value", equals: "Preview: hello"))
        expect(!fails { try AutomationPolicy.validate(browserPlan, observation: page) }, "A same-origin browser plan is allowed")
        var crossLink = browserPlan; crossLink.steps = [Step(operation: "press", target: "away")]
        expect(fails { try AutomationPolicy.validate(crossLink, observation: page) }, "A link to another origin is refused")
        var crossText = browserPlan; crossText.steps[0].text = "https://other.example/login"
        expect(fails { try AutomationPolicy.validate(crossText, observation: page) }, "Typing another origin's URL is refused")
        var sameText = browserPlan; sameText.steps[0].text = "https://example.com/next"
        expect(!fails { try AutomationPolicy.validate(sameText, observation: page) }, "Same-origin URL text is allowed")
        var scopeless = page; scopeless.origin = nil
        expect(fails { try AutomationPolicy.validate(browserPlan, observation: scopeless) }, "A browser scope without an origin is refused")
        // The postcondition is the only completion evidence, so a secure control cannot supply it.
        expect(fails { try AutomationPolicy.validate(Proposal(summary: "x", steps: browserPlan.steps, expected: Expected(target: "protected", attribute: "value", equals: "x")), observation: pristine) }, "A secure control cannot prove completion")
        expect(!AutomationPolicy.matched(Expected(target: "protected", attribute: "value", equals: "x"), in: pristine), "A sensitive control never satisfies verification")
        expect(fails { _ = try AutomationPolicy.decode(Data(String(repeating: " ", count: 24_001).utf8)) }, "Oversized proposals are refused")
        expect(fails { _ = try AutomationPolicy.decode(Data("{\"summary\":\"x\",\"steps\":[{\"operation\":\"press\",\"target\":\"a\",\"extra\":1}],\"expected\":{\"target\":\"a\",\"attribute\":\"value\",\"equals\":\"b\"}}".utf8)) }, "Extra step fields are refused")
        let partial = FakeDriver(); let scoped = AutomationSession(driver: partial)
        let partialKey = try scoped.prepare(proposal, digest: scoped.observe().digest)
        partial.afterAction = { partial.valid = false }
        expect(fails { _ = try scoped.execute(id: partialKey, confirmed: true) } && partial.actions == 1, "Target change stops remaining actions")
        expect(partial.values["input"] == "hello", "Partial edits are preserved")
        let relabelled = FakeDriver(); let changedLabel = AutomationSession(driver: relabelled)
        let changedKey = try changedLabel.prepare(proposal, digest: changedLabel.observe().digest)
        relabelled.afterAction = { relabelled.buttonLabel = "Send" }
        expect(fails { _ = try changedLabel.execute(id: changedKey, confirmed: true) } && relabelled.actions == 1, "Revalidate safety after every action")
        let ignoring = FakeDriver(); ignoring.ignoreActions = true; let ignored = AutomationSession(driver: ignoring)
        let ignoredKey = try ignored.prepare(proposal, digest: ignored.observe().digest)
        let notVerified = try ignored.execute(id: ignoredKey, confirmed: true)
        expect(notVerified["status"] as? String == "needs_review" && ignoring.actions == 2, "An ignored action must not look successful or be retried")
        emit(["self_tests_passed": passed, "actual_ui_exercised": false, "scope": "in-memory driver, no permission or network changes"])
    } catch { fatalError("Self-test failed: \(error)") }
}
