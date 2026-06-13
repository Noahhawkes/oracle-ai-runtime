import Foundation

// MARK: - Message model

struct ChatMessage: Identifiable, Equatable {
    let id: UUID
    let role: Role
    var text: String
    var isStreaming: Bool

    enum Role { case user, oracle }

    init(role: Role, text: String, isStreaming: Bool = false) {
        self.id = UUID()
        self.role = role
        self.text = text
        self.isStreaming = isStreaming
    }
}

// MARK: - SSE client

@MainActor
final class OracleAPIClient: NSObject, ObservableObject, URLSessionDataDelegate {

    @Published var messages: [ChatMessage] = []
    @Published var isStreaming = false
    @Published var currentMode: String = "companion"
    @Published var error: String? = nil

    var authToken: String = ""

    private var session: URLSession!
    private var streamingIndex: Int? = nil
    private var buffer = ""

    override init() {
        super.init()
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 60
        config.timeoutIntervalForResource = 300
        self.session = URLSession(configuration: config, delegate: self, delegateQueue: nil)
    }

    // MARK: - Send

    func send(_ text: String, to baseURL: URL) {
        guard !isStreaming else { return }
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        error = nil
        messages.append(ChatMessage(role: .user, text: text))

        // Placeholder oracle message that will be filled by streaming tokens
        var oracle = ChatMessage(role: .oracle, text: "", isStreaming: true)
        messages.append(oracle)
        streamingIndex = messages.count - 1
        isStreaming = true
        buffer = ""

        let chatURL = baseURL.appendingPathComponent("chat")
        var request = URLRequest(url: chatURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        if !authToken.isEmpty {
            request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        }

        let body = try? JSONEncoder().encode(["message": text])
        request.httpBody = body

        let task = session.dataTask(with: request)
        task.resume()
    }

    func clearHistory(baseURL: URL) {
        let url = baseURL.appendingPathComponent("api/clear")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        session.dataTask(with: req).resume()
        messages = []
        buffer = ""
        streamingIndex = nil
    }

    func fetchMode(baseURL: URL) {
        let url = baseURL.appendingPathComponent("api/mode")
        session.dataTask(with: url) { [weak self] data, _, _ in
            guard let data, let self else { return }
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let mode = json["mode"] as? String {
                Task { @MainActor in self.currentMode = mode }
            }
        }.resume()
    }

    // MARK: - URLSessionDataDelegate (SSE)

    nonisolated func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        guard let chunk = String(data: data, encoding: .utf8) else { return }
        Task { @MainActor in self.process(chunk: chunk) }
    }

    nonisolated func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        Task { @MainActor in
            self.isStreaming = false
            if let idx = self.streamingIndex {
                self.messages[idx].isStreaming = false
                self.streamingIndex = nil
            }
            if let err = error, (err as NSError).code != NSURLErrorCancelled {
                self.error = err.localizedDescription
            }
        }
    }

    // MARK: - SSE parser

    private func process(chunk: String) {
        buffer += chunk
        let lines = buffer.components(separatedBy: "\n")
        buffer = lines.last ?? ""

        for line in lines.dropLast() {
            guard line.hasPrefix("data: ") else { continue }
            let jsonStr = String(line.dropFirst(6))
            guard let data = jsonStr.data(using: .utf8),
                  let event = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            else { continue }

            if let type = event["type"] as? String {
                switch type {
                case "token":
                    if let text = event["text"] as? String, let idx = streamingIndex {
                        messages[idx].text += text
                    }
                case "mode":
                    if let mode = event["mode"] as? String { currentMode = mode }
                case "done":
                    if let mode = event["mode"] as? String { currentMode = mode }
                    isStreaming = false
                    if let idx = streamingIndex {
                        messages[idx].isStreaming = false
                        streamingIndex = nil
                    }
                default: break
                }
            }
        }
    }
}
