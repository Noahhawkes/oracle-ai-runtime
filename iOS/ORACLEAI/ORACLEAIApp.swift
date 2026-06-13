import SwiftUI

@main
struct ORACLEAIApp: App {
    @StateObject private var settings = OracleSettings()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(settings)
                .preferredColorScheme(.dark)
        }
    }
}
