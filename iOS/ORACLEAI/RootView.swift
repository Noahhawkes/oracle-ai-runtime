import SwiftUI

struct RootView: View {
    @EnvironmentObject private var settings: OracleSettings
    @State private var showingSettings = false
    @State private var reloadToken = UUID()
    @State private var connectionState: ConnectionState = .checking
    @State private var selectedTab: Tab = .chat

    enum Tab { case chat, web, settings }

    var body: some View {
        ZStack(alignment: .top) {
            Color.black.ignoresSafeArea()

            TabView(selection: $selectedTab) {
                NativeChatView()
                    .environmentObject(settings)
                    .tabItem {
                        Label("Chat", systemImage: "bubble.left.and.bubble.right")
                    }
                    .tag(Tab.chat)

                webTab
                    .tabItem {
                        Label("Web", systemImage: "globe")
                    }
                    .tag(Tab.web)

                SettingsView()
                    .environmentObject(settings)
                    .tabItem {
                        Label("Settings", systemImage: "gearshape")
                    }
                    .tag(Tab.settings)
            }
            .tint(.yellow)
        }
        .sheet(isPresented: $showingSettings) {
            SettingsView()
                .environmentObject(settings)
        }
    }

    @ViewBuilder
    private var webTab: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            if let url = settings.normalizedURL {
                OracleWebView(url: url, reloadToken: reloadToken, connectionState: $connectionState)
                    .ignoresSafeArea(edges: .bottom)
            } else {
                ConfigurationRequiredView { selectedTab = .settings }
            }
        }
        .safeAreaInset(edge: .top, spacing: 0) {
            if settings.showStatusBar {
                StatusHeader(
                    state: connectionState,
                    reload: { reloadToken = UUID() },
                    settings: { selectedTab = .settings }
                )
            }
        }
    }
}

enum ConnectionState: Equatable {
    case checking
    case online
    case offline(String)

    var label: String {
        switch self {
        case .checking: return "CHECKING"
        case .online: return "ONLINE"
        case .offline: return "OFFLINE"
        }
    }
}

private struct StatusHeader: View {
    let state: ConnectionState
    let reload: () -> Void
    let settings: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 1) {
                Text("ORACLE.AI")
                    .font(.system(size: 17, weight: .bold, design: .rounded))
                Text("Resident Intelligence")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            HStack(spacing: 6) {
                Circle()
                    .fill(state == .online ? Color.green : (state == .checking ? Color.yellow : Color.red))
                    .frame(width: 8, height: 8)
                Text(state.label)
                    .font(.caption2.bold())
            }

            Button(action: reload) {
                Image(systemName: "arrow.clockwise")
            }
            .accessibilityLabel("Reload ORACLE")

            Button(action: settings) {
                Image(systemName: "gearshape")
            }
            .accessibilityLabel("ORACLE settings")
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(.ultraThinMaterial)
        .overlay(alignment: .bottom) {
            Rectangle().frame(height: 1).foregroundStyle(Color.yellow.opacity(0.45))
        }
    }
}

private struct ConfigurationRequiredView: View {
    let openSettings: () -> Void

    var body: some View {
        VStack(spacing: 18) {
            Image(systemName: "brain.head.profile")
                .font(.system(size: 64))
                .foregroundStyle(.yellow)
            Text("Connect to ORACLE")
                .font(.title.bold())
            Text("Enter the address of the Windows computer running ORACLE, such as 192.168.1.100:7777.")
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
            Button("Open Settings", action: openSettings)
                .buttonStyle(.borderedProminent)
                .tint(.yellow)
                .foregroundStyle(.black)
        }
        .padding(28)
    }
}
