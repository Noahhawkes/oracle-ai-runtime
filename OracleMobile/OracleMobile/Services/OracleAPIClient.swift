import Foundation

struct OracleAPIClient {
    enum ClientError: LocalizedError {
        case invalidBaseURL
        case invalidResponse
        case httpStatus(Int, String)
        case malformedEvent

        var errorDescription: String? {
            switch self {
            case .invalidBaseURL:
                return "The ORACLE address is not valid."
            case .invalidResponse:
                return "ORACLE returned an invalid response."
            case let .httpStatus(code, body):
                return "ORACLE returned HTTP \(code). \(body)"
            case .malformedEvent:
                return "ORACLE sent an unreadable stream event."
            }
        }
    }

    let baseURL: URL
    let bearerToken: String

    private let decoder = JSONDecoder()

    private var session: URLSession {
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 45
        configuration.timeoutIntervalForResource = 300
        configuration.waitsForConnectivity = true
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        return URLSession(configuration: configuration)
    }

    func streamMessage(_ message: String) -> AsyncThrowingStream<OracleStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    let url = try endpoint("/chat")
                    var request = URLRequest(url: url)
                    request.httpMethod = "POST"
                    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                    applyAuthorization(to: &request)
                    request.httpBody = try JSONEncoder().encode(["message": message])

                    let (bytes, response) = try await session.bytes(for: request)
                    try validate(response: response, body: nil)

                    var sawDone = false
                    for try await rawLine in bytes.lines {
                        try Task.checkCancellation()
                        let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
                        guard line.hasPrefix("data:") else { continue }

                        let payload = line.dropFirst(5).trimmingCharacters(in: .whitespaces)
                        guard !payload.isEmpty else { continue }
                        if payload == "[DONE]" {
                            continuation.yield(.done(nil))
                            sawDone = true
                            break
                        }

                        guard let data = payload.data(using: .utf8),
                              let event = try? decoder.decode(OracleWireEvent.self, from: data) else {
                            continue
                        }

                        switch event.type.lowercased() {
                        case "token":
                            continuation.yield(.token(event.text ?? ""))
                        case "status", "thinking", "focus":
                            continuation.yield(.status(event.text ?? event.message ?? ""))
                        case "mode":
                            continuation.yield(.mode(event.mode ?? event.text ?? "companion"))
                        case "done":
                            continuation.yield(.done(event.mode))
                            sawDone = true
                        case "error":
                            continuation.yield(.error(event.detail ?? event.message ?? event.text ?? "Unknown ORACLE error"))
                        default:
                            if let text = event.text, !text.isEmpty {
                                continuation.yield(.status(text))
                            }
                        }
                    }

                    if !sawDone {
                        continuation.yield(.done(nil))
                    }
                    continuation.finish()
                } catch is CancellationError {
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }

            continuation.onTermination = { _ in task.cancel() }
        }
    }

    func fetchHistory() async throws -> [ChatMessage] {
        var request = URLRequest(url: try endpoint("/api/history"))
        request.httpMethod = "GET"
        applyAuthorization(to: &request)
        let (data, response) = try await session.data(for: request)
        try validate(response: response, body: data)
        let payload = try decoder.decode(OracleHistoryResponse.self, from: data)
        return payload.history.compactMap { entry in
            let role: ChatMessage.Role
            switch entry.role.lowercased() {
            case "user": role = .user
            case "assistant", "oracle": role = .assistant
            default: role = .system
            }
            return ChatMessage(role: role, content: entry.content)
        }
    }

    func fetchMode() async throws -> String {
        var request = URLRequest(url: try endpoint("/api/mode"))
        request.httpMethod = "GET"
        applyAuthorization(to: &request)
        let (data, response) = try await session.data(for: request)
        try validate(response: response, body: data)

        guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw ClientError.invalidResponse
        }
        return (object["mode"] as? String) ?? "companion"
    }

    func clearHistory() async throws {
        var request = URLRequest(url: try endpoint("/api/clear"))
        request.httpMethod = "POST"
        applyAuthorization(to: &request)
        let (data, response) = try await session.data(for: request)
        try validate(response: response, body: data)
    }

    private func endpoint(_ path: String) throws -> URL {
        guard var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else {
            throw ClientError.invalidBaseURL
        }
        let basePath = components.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let endpointPath = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        components.path = "/" + [basePath, endpointPath].filter { !$0.isEmpty }.joined(separator: "/")
        guard let url = components.url else { throw ClientError.invalidBaseURL }
        return url
    }

    private func applyAuthorization(to request: inout URLRequest) {
        let token = bearerToken.trimmingCharacters(in: .whitespacesAndNewlines)
        if !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
    }

    private func validate(response: URLResponse, body: Data?) throws {
        guard let http = response as? HTTPURLResponse else {
            throw ClientError.invalidResponse
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyText = body.flatMap { String(data: $0, encoding: .utf8) } ?? ""
            throw ClientError.httpStatus(http.statusCode, bodyText)
        }
    }
}
