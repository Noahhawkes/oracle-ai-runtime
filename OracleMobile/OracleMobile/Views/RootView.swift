import SwiftUI

struct RootView: View {
    @EnvironmentObject private var settings: OracleSettings
    @StateObject private var chat = ChatViewModel()
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            NavigationStack {
                ChatView(viewModel: chat, selectedTab: $selectedTab)
            }
            .tabItem { Label("ORACLE", systemImage: "waveform.circle.fill") }
            .tag(0)

            NavigationStack {
                SettingsView(viewModel: chat)
            }
            .tabItem { Label("Settings", systemImage: "gearshape.fill") }
            .tag(1)
        }
        .tint(.purple)
        .task {
            guard settings.isConfigured else {
                selectedTab = 1
                return
            }
            await chat.connect(settings: settings)
        }
    }
}
