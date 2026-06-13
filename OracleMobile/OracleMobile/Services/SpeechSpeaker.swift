import AVFoundation

@MainActor
final class SpeechSpeaker {
    private let synthesizer = AVSpeechSynthesizer()

    func speak(_ text: String) {
        let cleaned = text
            .replacingOccurrences(of: "[ATTENTION FILTER]", with: "")
            .replacingOccurrences(of: "[ORACLE FOCUS]", with: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleaned.isEmpty else { return }

        synthesizer.stopSpeaking(at: .immediate)
        let utterance = AVSpeechUtterance(string: cleaned)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = 0.48
        utterance.pitchMultiplier = 1.02
        synthesizer.speak(utterance)
    }

    func stop() {
        synthesizer.stopSpeaking(at: .immediate)
    }
}
