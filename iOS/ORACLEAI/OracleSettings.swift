import Foundation

@MainActor
final class OracleSettings: ObservableObject {
    @Published var serverAddress: String {
        didSet { UserDefaults.standard.set(serverAddress, forKey: "oracle.serverAddress") }
    }

    @Published var showStatusBar: Bool {
        didSet { UserDefaults.standard.set(showStatusBar, forKey: "oracle.showStatusBar") }
    }

    @Published var speakReplies: Bool {
        didSet { UserDefaults.standard.set(speakReplies, forKey: "oracle.speakReplies") }
    }

    @Published var authToken: String {
        didSet { UserDefaults.standard.set(authToken, forKey: "oracle.authToken") }
    }

    init() {
        self.serverAddress = UserDefaults.standard.string(forKey: "oracle.serverAddress")
            ?? "http://192.168.1.100:7777/"
        self.showStatusBar = UserDefaults.standard.object(forKey: "oracle.showStatusBar") as? Bool ?? true
        self.speakReplies = UserDefaults.standard.object(forKey: "oracle.speakReplies") as? Bool ?? false
        self.authToken = UserDefaults.standard.string(forKey: "oracle.authToken") ?? ""
    }

    var normalizedURL: URL? {
        var value = serverAddress.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty else { return nil }
        if !value.contains("://") { value = "http://" + value }
        if !value.hasSuffix("/") { value += "/" }
        return URL(string: value)
    }
}
