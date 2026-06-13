import Foundation
import Combine

@MainActor
final class OracleSettings: ObservableObject {
    private enum Keys {
        static let baseURL = "oracle.baseURL"
        static let autoSpeak = "oracle.autoSpeak"
        static let loadHistory = "oracle.loadHistory"
        static let bearerToken = "oracle.bearerToken"
    }

    @Published var baseURLText: String {
        didSet { UserDefaults.standard.set(baseURLText, forKey: Keys.baseURL) }
    }

    @Published var autoSpeak: Bool {
        didSet { UserDefaults.standard.set(autoSpeak, forKey: Keys.autoSpeak) }
    }

    @Published var loadHistoryOnLaunch: Bool {
        didSet { UserDefaults.standard.set(loadHistoryOnLaunch, forKey: Keys.loadHistory) }
    }

    @Published var bearerToken: String {
        didSet {
            if bearerToken.isEmpty {
                KeychainStore.delete(account: Keys.bearerToken)
            } else {
                try? KeychainStore.save(bearerToken, account: Keys.bearerToken)
            }
        }
    }

    init() {
        baseURLText = UserDefaults.standard.string(forKey: Keys.baseURL) ?? ""
        autoSpeak = UserDefaults.standard.object(forKey: Keys.autoSpeak) as? Bool ?? true
        loadHistoryOnLaunch = UserDefaults.standard.object(forKey: Keys.loadHistory) as? Bool ?? true
        bearerToken = KeychainStore.read(account: Keys.bearerToken) ?? ""
    }

    var baseURL: URL? {
        let trimmed = baseURLText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        let candidate = trimmed.contains("://") ? trimmed : "https://\(trimmed)"
        return URL(string: candidate.trimmingCharacters(in: CharacterSet(charactersIn: "/")))
    }

    var isConfigured: Bool { baseURL != nil }
}
