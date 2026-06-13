import SwiftUI

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            if message.role == .user { Spacer(minLength: 44) }

            VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 4) {
                Text(message.role == .user ? "NOAH" : message.role == .assistant ? "ORACLE" : "SYSTEM")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(.secondary)

                markdownText(message.content.isEmpty ? "…" : message.content)
                    .textSelection(.enabled)
                    .padding(.horizontal, 13)
                    .padding(.vertical, 10)
                    .background(background)
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
            }

            if message.role != .user { Spacer(minLength: 44) }
        }
        .padding(.horizontal)
        .padding(.vertical, 3)
    }

    @ViewBuilder
    private func markdownText(_ text: String) -> some View {
        if let attributed = try? AttributedString(markdown: text) {
            Text(attributed)
        } else {
            Text(text)
        }
    }

    private var background: some ShapeStyle {
        switch message.role {
        case .user:
            return AnyShapeStyle(Color.purple.opacity(0.72))
        case .assistant:
            return AnyShapeStyle(Color.white.opacity(0.10))
        case .system:
            return AnyShapeStyle(Color.orange.opacity(0.18))
        }
    }
}
