import SwiftUI

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject private var settings: OracleSettings

    var body: some View {
        NavigationStack {
            Form {
                Section("ORACLE server") {
                    TextField("192.168.1.100:7777", text: $settings.serverAddress)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()

                    Text("Use the Windows computer's LAN or Tailscale address. Do not use localhost on the iPhone.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("Appearance") {
                    Toggle("Show connection header", isOn: $settings.showStatusBar)
                }

                Section("Voice") {
                    Toggle("Speak ORACLE replies", isOn: $settings.speakReplies)
                    Text("ORACLE's responses will be read aloud using on-device speech synthesis when enabled.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("Authentication") {
                    SecureField("Bearer token (optional)", text: $settings.authToken)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Text("If ORACLE server authentication is enabled, enter the shared bearer token here. Leave blank for local-only access with no auth.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("Security") {
                    Label("Do not expose port 7777 directly to the public internet.", systemImage: "lock.shield")
                    Text("For access away from home, use a private network such as Tailscale and require ORACLE authentication.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("ORACLE Settings")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}
