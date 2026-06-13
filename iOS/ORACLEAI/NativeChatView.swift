import SwiftUI

struct NativeChatView: View {
    @EnvironmentObject private var settings: OracleSettings
    @StateObject private var client = OracleAPIClient()
    @StateObject private var voiceIn = VoiceInputManager()
    @StateObject private var voiceOut = VoiceOutputManager()
    @State private var inputText = ""
    @FocusState private var inputFocused: Bool

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            if settings.normalizedURL == nil {
                noServerView
            } else {
                VStack(spacing: 0) {
                    modeBar
                    messageList
                    inputBar
                }
            }
        }
        .onAppear {
            client.authToken = settings.authToken
            if let url = settings.normalizedURL { client.fetchMode(baseURL: url) }
            Task { await voiceIn.requestPermissions() }
        }
        .onChange(of: settings.authToken) { client.authToken = $0 }
        // Auto-read ORACLE replies aloud when they finish streaming
        .onChange(of: client.isStreaming) { streaming in
            guard !streaming,
                  settings.speakReplies,
                  let last = client.messages.last,
                  last.role == .oracle,
                  !last.text.isEmpty
            else { return }
            voiceOut.speak(last.text)
        }
        // Copy live transcript into the text field while listening
        .onChange(of: voiceIn.transcript) { t in
            if voiceIn.isListening { inputText = t }
        }
    }

    // MARK: - Sub-views

    private var noServerView: some View {
        VStack(spacing: 16) {
            Image(systemName: "waveform.slash")
                .font(.system(size: 52))
                .foregroundStyle(.yellow.opacity(0.6))
            Text("No ORACLE server configured.")
                .foregroundStyle(.secondary)
        }
    }

    private var modeBar: some View {
        HStack {
            Text("ORACLE")
                .font(.system(size: 13, weight: .bold, design: .rounded))
                .foregroundStyle(.yellow)
            Spacer()
            Text(client.currentMode.uppercased())
                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                .foregroundStyle(.secondary)
            if client.isStreaming {
                ProgressView().scaleEffect(0.65).tint(.yellow)
            }
            if voiceOut.isSpeaking {
                Button { voiceOut.stop() } label: {
                    Image(systemName: "speaker.wave.2.fill")
                        .font(.caption)
                        .foregroundStyle(.yellow)
                }
                .accessibilityLabel("Stop speaking")
            }
            Button {
                if let url = settings.normalizedURL { client.clearHistory(baseURL: url) }
            } label: {
                Image(systemName: "trash").font(.caption).foregroundStyle(.secondary)
            }
            .accessibilityLabel("Clear conversation")
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(.ultraThinMaterial)
        .overlay(alignment: .bottom) {
            Rectangle().frame(height: 1).foregroundStyle(Color.yellow.opacity(0.25))
        }
    }

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    if client.messages.isEmpty { emptyState.frame(maxWidth: .infinity).padding(.top, 80) }
                    ForEach(client.messages) { msg in
                        MessageBubble(message: msg).id(msg.id)
                    }
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 12)
            }
            .onChange(of: client.messages) { msgs in
                if let last = msgs.last {
                    withAnimation(.easeOut(duration: 0.25)) { proxy.scrollTo(last.id, anchor: .bottom) }
                }
            }
            .onChange(of: client.messages.last?.text) { _ in
                if let last = client.messages.last { proxy.scrollTo(last.id, anchor: .bottom) }
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 10) {
            Image(systemName: "waveform.circle")
                .font(.system(size: 44))
                .foregroundStyle(.yellow.opacity(0.6))
            Text("I'm here, Noah.")
                .font(.title3.bold())
                .foregroundStyle(.white.opacity(0.8))
            Text("Native chat · tap mic to speak · tap \(Image(systemName: "speaker.wave.2")) to enable voice replies.")
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
    }

    private var inputBar: some View {
        VStack(spacing: 0) {
            Rectangle().frame(height: 1).foregroundStyle(Color.yellow.opacity(0.25))
            if let err = client.error ?? voiceIn.error {
                Text(err).font(.caption).foregroundStyle(.red).padding(.horizontal, 14).padding(.top, 6)
            }
            HStack(spacing: 10) {
                // Mic button
                Button(action: toggleVoice) {
                    Image(systemName: voiceIn.isListening ? "mic.fill" : "mic")
                        .font(.system(size: 22))
                        .foregroundStyle(voiceIn.isListening ? .red : (voiceIn.canRecord ? .yellow : .gray))
                        .symbolEffect(.variableColor, isActive: voiceIn.isListening)
                }
                .accessibilityLabel(voiceIn.isListening ? "Stop recording" : "Start voice input")

                TextField("Message ORACLE…", text: $inputText, axis: .vertical)
                    .lineLimit(1...5)
                    .font(.system(size: 16))
                    .foregroundStyle(.white)
                    .focused($inputFocused)
                    .onSubmit { send() }
                    .submitLabel(.send)

                // Send / stop-speaking button
                Button(action: voiceOut.isSpeaking ? { voiceOut.stop() } : send) {
                    Image(systemName: voiceOut.isSpeaking
                          ? "speaker.slash.fill"
                          : (client.isStreaming ? "stop.circle.fill" : "arrow.up.circle.fill"))
                        .font(.system(size: 30))
                        .foregroundStyle(canSend ? .yellow : .gray)
                }
                .disabled(!canSend && !voiceOut.isSpeaking)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .background(Color.black)
        }
    }

    private var canSend: Bool { !inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || client.isStreaming }

    // MARK: - Actions

    private func send() {
        guard let url = settings.normalizedURL else { return }
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        if voiceIn.isListening { voiceIn.stopListening() }
        inputText = ""
        client.send(text, to: url)
    }

    private func toggleVoice() {
        if voiceIn.isListening {
            voiceIn.stopListening()
            // Send whatever was transcribed
            let t = voiceIn.transcript.trimmingCharacters(in: .whitespacesAndNewlines)
            if !t.isEmpty { inputText = t; send() }
        } else {
            inputFocused = false
            voiceIn.startListening()
        }
    }
}

// MARK: - Message bubble

private struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            if message.role == .oracle {
                Circle().fill(Color.yellow).frame(width: 6, height: 6).padding(.top, 8)
            }
            VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 4) {
                Text(message.text.isEmpty && message.isStreaming ? "…" : message.text)
                    .font(.system(size: 15))
                    .foregroundStyle(message.role == .oracle ? .white : .black)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 9)
                    .background(message.role == .oracle ? Color(white: 0.13) : Color.yellow)
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .frame(maxWidth: UIScreen.main.bounds.width * 0.82,
                           alignment: message.role == .user ? .trailing : .leading)
                if message.isStreaming { StreamingDot() }
            }
            .frame(maxWidth: .infinity, alignment: message.role == .user ? .trailing : .leading)
        }
    }
}

private struct StreamingDot: View {
    @State private var opacity: Double = 0.3
    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<3, id: \.self) { i in
                Circle().fill(Color.yellow).frame(width: 5, height: 5)
                    .opacity(opacity)
                    .animation(.easeInOut(duration: 0.5).repeatForever().delay(Double(i) * 0.15), value: opacity)
            }
        }
        .onAppear { opacity = 1.0 }
        .padding(.leading, 12)
    }
}
