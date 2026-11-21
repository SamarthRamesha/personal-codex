import AppKit
import WebKit

@MainActor final class Fixture: NSObject, NSApplicationDelegate {
    var windows: [NSWindow] = []
    let input = NSTextField(string: "")
    let output = NSTextField(labelWithString: "Ready")
    let uppercase = NSButton(checkboxWithTitle: "Uppercase", target: nil, action: nil)
    func window(_ title: String, x: CGFloat) -> NSWindow {
        let result = NSWindow(contentRect: NSRect(x: x, y: 180, width: 640, height: 480),
            styleMask: [.titled, .closable, .resizable], backing: .buffered, defer: false)
        result.title = title; result.isReleasedWhenClosed = false; windows.append(result); return result
    }
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Bounds cleanup even if a cancelled self-check's helper is killed.
        Timer.scheduledTimer(withTimeInterval: 120, repeats: false) { _ in NSApplication.shared.terminate(nil) }
        let primary = window("Personal Codex Automation Fixture", x: 150)
        let heading = NSTextField(labelWithString: "AMBER WORKFLOW · Synthetic data only")
        heading.frame = NSRect(x: 28, y: 415, width: 580, height: 24); heading.font = .boldSystemFont(ofSize: 20)
        input.frame = NSRect(x: 28, y: 345, width: 570, height: 32)
        input.setAccessibilityLabel("Message"); input.setAccessibilityIdentifier("fixture-message")
        let button = NSButton(title: "Preview", target: self, action: #selector(preview))
        button.frame = NSRect(x: 28, y: 290, width: 120, height: 32)
        uppercase.frame = NSRect(x: 180, y: 290, width: 180, height: 32)
        output.frame = NSRect(x: 28, y: 230, width: 570, height: 36); output.font = .systemFont(ofSize: 22)
        output.setAccessibilityLabel("Result"); output.setAccessibilityIdentifier("fixture-result")
        let scroll = NSScrollView(frame: NSRect(x: 28, y: 20, width: 570, height: 180)); scroll.hasVerticalScroller = true
        // Overlay scrollers stay hidden until the user scrolls, so a synthetic check could never observe one.
        // Legacy style keeps a real, always-present scroller that the accessibility tree exposes.
        scroll.scrollerStyle = .legacy
        scroll.setAccessibilityLabel("Synthetic list")
        let document = NSView(frame: NSRect(x: 0, y: 0, width: 540, height: 900))
        for index in 0..<15 {
            let line = NSTextField(labelWithString: "Synthetic row \(index + 1)")
            line.frame = NSRect(x: 12, y: 840-CGFloat(index)*56, width: 480, height: 24); document.addSubview(line)
        }
        scroll.documentView = document
        for view in [heading, input, button, uppercase, output, scroll] as [NSView] { primary.contentView?.addSubview(view) }
        primary.orderBack(nil)

        let protected = window("Personal Codex Protected Fixture", x: 820)
        let label = NSTextField(labelWithString: "Synthetic secure-field test; no real credential")
        label.frame = NSRect(x: 25, y: 390, width: 590, height: 30)
        let password = NSSecureTextField(string: "DISPOSABLE-SYNTHETIC-SECRET")
        password.frame = NSRect(x: 25, y: 330, width: 560, height: 32); password.setAccessibilityLabel("Password")
        protected.contentView?.addSubview(label); protected.contentView?.addSubview(password); protected.orderBack(nil)
        primary.makeKeyAndOrderFront(nil)
    }
    @objc func preview() {
        let value = uppercase.state == .on ? input.stringValue.uppercased() : input.stringValue
        output.stringValue = "Preview: " + value
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}
@main struct Main {
    @MainActor static func main() { let app = NSApplication.shared; app.setActivationPolicy(.regular)
        let delegate = Fixture(); app.delegate = delegate; withExtendedLifetime(delegate) { app.run() } }
}
