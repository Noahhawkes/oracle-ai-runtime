import AVFoundation
import Speech
import SwiftUI

// MARK: - Voice input (Speech → text)

@MainActor
final class VoiceInputManager: ObservableObject {

    @Published var isListening = false
    @Published var transcript = ""
    @Published var authStatus: SFSpeechRecognizerAuthorizationStatus = .notDetermined
    @Published var error: String? = nil

    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let audioEngine = AVAudioEngine()

    init() {
        authStatus = SFSpeechRecognizer.authorizationStatus()
    }

    // MARK: - Permissions

    func requestPermissions() async {
        let speech = await withCheckedContinuation { cont in
            SFSpeechRecognizer.requestAuthorization { status in
                cont.resume(returning: status)
            }
        }
        authStatus = speech

        do {
            try AVAudioSession.sharedInstance().requestRecordPermission()
        } catch {}
    }

    private func micGranted() -> Bool {
        AVAudioSession.sharedInstance().recordPermission == .granted
    }

    var canRecord: Bool {
        authStatus == .authorized && micGranted() && recognizer?.isAvailable == true
    }

    // MARK: - Recording

    func startListening() {
        guard !isListening else { return }
        guard canRecord else {
            error = "Microphone or speech recognition permission denied."
            return
        }

        error = nil
        transcript = ""

        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.record, mode: .measurement, options: .duckOthers)
            try session.setActive(true, options: .notifyOthersOnDeactivation)
        } catch {
            self.error = "Audio session error: \(error.localizedDescription)"
            return
        }

        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let req = recognitionRequest else { return }
        req.shouldReportPartialResults = true
        req.requiresOnDeviceRecognition = false

        let inputNode = audioEngine.inputNode
        let fmt = inputNode.outputFormat(forBus: 0)

        recognitionTask = recognizer?.recognitionTask(with: req) { [weak self] result, err in
            guard let self else { return }
            Task { @MainActor in
                if let result {
                    self.transcript = result.bestTranscription.formattedString
                }
                if err != nil || result?.isFinal == true {
                    self.stopListening()
                }
            }
        }

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: fmt) { [weak self] buffer, _ in
            self?.recognitionRequest?.append(buffer)
        }

        audioEngine.prepare()
        do {
            try audioEngine.start()
            isListening = true
        } catch {
            self.error = "Could not start audio engine: \(error.localizedDescription)"
            cleanup()
        }
    }

    func stopListening() {
        guard isListening else { return }
        isListening = false
        audioEngine.stop()
        recognitionRequest?.endAudio()
        cleanup()
    }

    private func cleanup() {
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionTask?.cancel()
        recognitionTask = nil
        recognitionRequest = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
}

// MARK: - AVAudioSession permission helper

extension AVAudioSession {
    func requestRecordPermission() throws {
        // Bridges callback-based API; result checked via .recordPermission
        requestRecordPermission { _ in }
    }
}

// MARK: - Voice output (text → speech)

@MainActor
final class VoiceOutputManager: NSObject, ObservableObject, AVSpeechSynthesizerDelegate {

    @Published var isSpeaking = false

    private let synth = AVSpeechSynthesizer()

    override init() {
        super.init()
        synth.delegate = self
    }

    func speak(_ text: String) {
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        do {
            try AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio, options: .duckOthers)
            try AVAudioSession.sharedInstance().setActive(true)
        } catch {}

        if synth.isSpeaking { synth.stopSpeaking(at: .immediate) }

        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(identifier: "com.apple.voice.compact.en-US.Samantha")
            ?? AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = 0.48
        utterance.pitchMultiplier = 0.95
        utterance.volume = 1.0
        utterance.preUtteranceDelay = 0.1

        synth.speak(utterance)
    }

    func stop() {
        synth.stopSpeaking(at: .word)
    }

    // AVSpeechSynthesizerDelegate
    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didStart utterance: AVSpeechUtterance) {
        Task { @MainActor in self.isSpeaking = true }
    }

    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        Task { @MainActor in self.isSpeaking = false }
    }

    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        Task { @MainActor in self.isSpeaking = false }
    }
}
