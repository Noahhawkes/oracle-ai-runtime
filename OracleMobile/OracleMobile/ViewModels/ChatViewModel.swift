import Foundation
import Combine

@MainActor
final class ChatViewModel: ObservableObject {
    enum ConnectionState: Equatable {
        case disconnected
        case connecting
        case connected
        case failed(String)
    }

    @Published var messages: [ChatMessage] = []
    @Published var inputText = ""
    @Published var currentMode = "companion"
    @Published var statusText = ""
    @Published var connectionState: ConnectionState = .disconnected
    @Published var isStreaming = false

    private var streamTask: Task<Void, Never>?
    private let speaker = SpeechSpeaker()

    func connect(settings: OracleSettings, loadHistory: Bool = true) async {
        guard let client = makeClient(settings: settings) else {
            connectionState = .failed("Enter the ORACLE address in Settings.")
            return
        }

        connectionState = .connecting
        do {
            currentMode = try await client.fetchMode()
            if loadHistory && settings.loadHistoryOnLaunch {
                messages = try await client.fetchHistory()
            }
            connectionState = .connected
        } catch {
            connectionState = .failed(error.localizedDescription)
        }
    }

    func send(settings: OracleSettings, overrideText: String? = nil) {
        let text = (overrideText ?? inputText).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isStreaming else { return }
        guard let client = makeClient(settings: settings) else {
            connectionState = .failed("Enter the ORACLE address in Settings.")
            return
        }

        inputText = ""
        statusText = ""
        isStreaming = true
        connectionState = .connected
        messages.append(ChatMessage(role: .user, content: text))
        let replyID = UUID()
        messages.append(ChatMessage(id: replyID, role: .assistant, content: ""))

        streamTask?.cancel()
        streamTask = Task {
            var finalReply = ""
            do {
                for try await event in client.streamMessage(text) {
                    guard !Task.isCancelled else { break }
                    switch event {
                    case let .token(token):
                        finalReply += token
                        updateMessage(id: replyID, content: finalReply)
                    case let .status(status):
                        statusText = status
                    case let .mode(mode):
                        currentMode = mode
                    case let .done(mode):
                        if let mode { currentMode = mode }
                    case let .error(message):
                        throw NSError(domain: "ORACLE", code: 1, userInfo: [NSLocalizedDescriptionKey: message])
                    }
                }

                if finalReply.isEmpty {
                    finalReply = "ORACLE returned no text. Check the server log and try again."
                    updateMessage(id: replyID, content: finalReply)
                }
                if settings.autoSpeak { speaker.speak(finalReply) }
            } catch {
                let failure = "Connection error: \(error.localizedDescription)"
                updateMessage(id: replyID, content: failure)
                connectionState = .failed(error.localizedDescription)
            }
            statusText = ""
            isStreaming = false
        }
    }

    func setMode(_ mode: String, settings: OracleSettings) {
        guard currentMode != mode else { return }
        send(settings: settings, overrideText: mode == "builder" ? "/builder" : "/companion")
    }

    func clear(settings: OracleSettings) async {
        guard let client = makeClient(settings: settings) else { return }
        do {
            try await client.clearHistory()
            messages.removeAll()
        } catch {
            connectionState = .failed(error.localizedDescription)
        }
    }

    func cancelStream() {
        streamTask?.cancel()
        streamTask = nil
        isStreaming = false
        statusText = ""
    }

    private func makeClient(settings: OracleSettings) -> OracleAPIClient? {
        guard let baseURL = settings.baseURL else { return nil }
        return OracleAPIClient(baseURL: baseURL, bearerToken: settings.bearerToken)
    }

    private func updateMessage(id: UUID, content: String) {
        guard let index = messages.firstIndex(where: { $0.id == id }) else { return }
        messages[index].content = content
    }
}
