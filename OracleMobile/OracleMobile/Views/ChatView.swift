import SwiftUI

struct ChatView: View {
    @EnvironmentObject private var settings: OracleSettings
    @ObservedObject var viewModel: ChatViewModel
    @Binding var selectedTab: Int
    @StateObject private var speech = SpeechRecognizer()
    @FocusState private var inputFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            statusHeader
            Divider().opacity(0.3)
            messageList
            if !viewModel.statusText.isEmpty {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text(viewModel.statusText)
                        .font(.caption)
                        .lineLimit(2)
                    Spacer()
                }
                .padding(.horizontal)
                .padding(.vertical, 6)
                .background(.thinMaterial)
            }
            composer
        }
        .navigationTitle("ORACLE")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Button("Reconnect", systemImage: "arrow.clockwise") {
                        Task { await viewModel.connect(settings: settings, loadHistory: false) }
                    }
                    Button("Clear conversation", systemImage: "trash", role: .destructive) {
                        Task { await viewModel.clear(settings: settings) }
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
        }
        .onChange(of: speech.transcript) { _, newValue in
            if speech.isRecording || !newValue.isEmpty { viewModel.inputText = newValue }
        }
        .alert("Voice input", isPresented: Binding(
            get: { speech.errorMessage != nil },
            set: { if !$0 { speech.errorMessage = nil } }
        )) {
            Button("OK", role: .cancel) { speech.errorMessage = nil }
        } message: {
            Text(speech.errorMessage ?? "")
        }
    }

    private var statusHeader: some View {
        VStack(spacing: 8) {
            HStack {
                Circle()
                    .fill(connectionColor)
                    .frame(width: 9, height: 9)
                Text(connectionLabel)
                    .font(.caption.weight(.semibold))
                Spacer()
                Picker("Mode", selection: Binding(
                    get: { viewModel.currentMode },
                    set: { viewModel.setMode($0, settings: settings) }
                )) {
                    Text("Companion").tag("companion")
                    Text("Builder").tag("builder")
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 220)
                .disabled(viewModel.isStreaming)
            }

            if case let .failed(message) = viewModel.connectionState {
                Button {
                    selectedTab = 1
                } label: {
                    Label(message, systemImage: "exclamationmark.triangle.fill")
                        .font(.caption)
                        .foregroundStyle(.orange)
                        .lineLimit(2)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 10)
        .background(.ultraThinMaterial)
    }

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 4) {
                    if viewModel.messages.isEmpty {
                        VStack(spacing: 14) {
                            Image(systemName: "waveform.circle.fill")
                                .font(.system(size: 58))
                                .foregroundStyle(.purple)
                            Text("ORACLE is ready when your PC is awake and connected.")
                                .font(.headline)
                                .multilineTextAlignment(.center)
                            Text("Talk normally in Companion mode. Switch to Builder only when you want code, tools, or execution.")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                                .multilineTextAlignment(.center)
                        }
                        .padding(36)
                    }

                    ForEach(viewModel.messages) { message in
                        MessageBubble(message: message)
                            .id(message.id)
                    }
                }
                .padding(.vertical, 8)
            }
            .onChange(of: viewModel.messages) { _, messages in
                guard let last = messages.last else { return }
                withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
            }
        }
    }

    private var composer: some View {
        HStack(alignment: .bottom, spacing: 10) {
            Button {
                speech.toggle()
            } label: {
                Image(systemName: speech.isRecording ? "stop.circle.fill" : "mic.circle.fill")
                    .font(.system(size: 31))
                    .symbolEffect(.pulse, isActive: speech.isRecording)
            }
            .accessibilityLabel(speech.isRecording ? "Stop listening" : "Start listening")

            TextField("Message ORACLE", text: $viewModel.inputText, axis: .vertical)
                .textFieldStyle(.plain)
                .lineLimit(1...6)
                .focused($inputFocused)
                .padding(.horizontal, 13)
                .padding(.vertical, 10)
                .background(Color.white.opacity(0.09))
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                .submitLabel(.send)
                .onSubmit { send() }

            if viewModel.isStreaming {
                Button {
                    viewModel.cancelStream()
                } label: {
                    Image(systemName: "stop.fill")
                        .frame(width: 34, height: 34)
                        .background(.red)
                        .foregroundStyle(.white)
                        .clipShape(Circle())
                }
                .accessibilityLabel("Stop response")
            } else {
                Button(action: send) {
                    Image(systemName: "arrow.up")
                        .font(.headline)
                        .frame(width: 34, height: 34)
                        .background(viewModel.inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? Color.gray : Color.purple)
                        .foregroundStyle(.white)
                        .clipShape(Circle())
                }
                .disabled(viewModel.inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                .accessibilityLabel("Send message")
            }
        }
        .padding(.horizontal)
        .padding(.top, 9)
        .padding(.bottom, 7)
        .background(.ultraThinMaterial)
    }

    private func send() {
        if speech.isRecording { speech.stop() }
        viewModel.send(settings: settings)
        inputFocused = true
    }

    private var connectionColor: Color {
        switch viewModel.connectionState {
        case .connected: return .green
        case .connecting: return .yellow
        case .failed: return .red
        case .disconnected: return .gray
        }
    }

    private var connectionLabel: String {
        switch viewModel.connectionState {
        case .connected: return "Connected"
        case .connecting: return "Connecting"
        case .failed: return "Offline"
        case .disconnected: return "Not connected"
        }
    }
}
