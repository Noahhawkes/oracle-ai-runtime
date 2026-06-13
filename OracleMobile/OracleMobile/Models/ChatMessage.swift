import Foundation

struct ChatMessage: Identifiable, Codable, Equatable {
    enum Role: String, Codable {
        case user
        case assistant
        case system
    }

    let id: UUID
    var role: Role
    var content: String
    let createdAt: Date

    init(id: UUID = UUID(), role: Role, content: String, createdAt: Date = Date()) {
        self.id = id
        self.role = role
        self.content = content
        self.createdAt = createdAt
    }
}

struct OracleHistoryResponse: Decodable {
    struct Entry: Decodable {
        let role: String
        let content: String
    }

    let history: [Entry]
    let sessionId: String?

    private enum CodingKeys: String, CodingKey {
        case history
        case sessionId = "session_id"
    }
}
