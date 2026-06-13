import Foundation

enum OracleStreamEvent: Equatable {
    case token(String)
    case status(String)
    case mode(String)
    case done(String?)
    case error(String)
}

struct OracleWireEvent: Decodable {
    let type: String
    let text: String?
    let mode: String?
    let message: String?
    let detail: String?
}
