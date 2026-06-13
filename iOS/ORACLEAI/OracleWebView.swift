import SwiftUI
import WebKit

struct OracleWebView: UIViewRepresentable {
    let url: URL
    let reloadToken: UUID
    @Binding var connectionState: ConnectionState

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []

        let preferences = WKWebpagePreferences()
        preferences.allowsContentJavaScript = true
        configuration.defaultWebpagePreferences = preferences

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator
        webView.allowsBackForwardNavigationGestures = true
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.isOpaque = false
        webView.backgroundColor = .black
        webView.load(URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 15))
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        context.coordinator.parent = self

        if context.coordinator.lastURL != url {
            context.coordinator.lastURL = url
            connectionState = .checking
            webView.load(URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 15))
        }

        if context.coordinator.lastReloadToken != reloadToken {
            context.coordinator.lastReloadToken = reloadToken
            connectionState = .checking
            webView.reloadFromOrigin()
        }
    }

    final class Coordinator: NSObject, WKNavigationDelegate {
        var parent: OracleWebView
        var lastURL: URL?
        var lastReloadToken: UUID?

        init(_ parent: OracleWebView) {
            self.parent = parent
            self.lastURL = parent.url
            self.lastReloadToken = parent.reloadToken
        }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            parent.connectionState = .checking
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            parent.connectionState = .online
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            parent.connectionState = .offline(error.localizedDescription)
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            parent.connectionState = .offline(error.localizedDescription)
        }
    }
}
