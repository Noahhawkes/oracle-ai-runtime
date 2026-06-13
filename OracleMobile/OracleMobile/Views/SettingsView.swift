import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var settings: OracleSettings
    @ObservedObject var viewModel: ChatViewModel
    @State private var showToken = false
    @State private var testResult: String?
    @State private var testing = false

    var body: some View {
        Form {
            Section("ORACLE address") {
                TextField("https://your-pc.tailnet.ts.net", text: $settings.baseURLText)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.URL)

                Text("Recommended: use the HTTPS address printed by `tailscale serve --bg localhost:7777`. For home Wi-Fi only, you can use `http://YOUR-PC-IP:7777` after explicitly enabling LAN access.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section("Optional app token") {
                HStack {
                    Group {
                        if showToken {
                            TextField("Bearer token", text: $settings.bearerToken)
                        } else {
                            SecureField("Bearer token", text: $settings.bearerToken)
                        }
                    }
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()

                    Button(showToken ? "Hide" : "Show") { showToken.toggle() }
                        .font(.caption)
                }
                Text("Leave blank when Tailscale is your only access gate. A token is stored in the iPhone Keychain, not UserDefaults.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section("Conversation") {
                Toggle("Speak ORACLE replies", isOn: $settings.autoSpeak)
                Toggle("Load server history at launch", isOn: $settings.loadHistoryOnLaunch)
            }

            Section {
                Button {
                    testing = true
                    testResult = nil
                    Task {
                        await viewModel.connect(settings: settings, loadHistory: false)
                        switch viewModel.connectionState {
                        case .connected:
                            testResult = "Connected. ORACLE mode: \(viewModel.currentMode)."
                        case let .failed(message):
                            testResult = message
                        default:
                            testResult = "Connection did not complete."
                        }
                        testing = false
                    }
                } label: {
                    HStack {
                        if testing { ProgressView() }
                        Text(testing ? "Testing…" : "Test connection")
                    }
                }
                .disabled(!settings.isConfigured || testing)

                if let testResult {
                    Text(testResult)
                        .font(.callout)
                        .foregroundStyle(testResult.hasPrefix("Connected") ? .green : .orange)
                }
            }

            Section("Security boundary") {
                Label("ORACLE memory stays on your PC", systemImage: "externaldrive.badge.checkmark")
                Label("The app holds only its current screen transcript", systemImage: "iphone.gen3")
                Label("Remote access should stay inside Tailscale", systemImage: "lock.shield")
                Text("Do not port-forward 7777 on your router. Do not use Tailscale Funnel for this private service.")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.orange)
            }
        }
        .navigationTitle("Phone Connection")
    }
}
