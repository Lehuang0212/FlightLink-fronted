import QtQuick
import QtTest
import "../../src/flightlink_desktop/qml/pages"

Item {
    id: root
    width: 480
    height: 640

    QtObject {
        id: fakeSessionVm
        signal sessionEnded(int epoch, string reason)
        property string serverUrl: "http://127.0.0.1:8000"
        property string healthStatus: "idle"
        property string healthMessage: ""
        property int healthRttMs: 0
        property string ecsInstanceId: ""
        property bool loggingIn: false
        property string loginError: ""
        property bool authenticated: false

        property int probeCalls: 0
        property string lastProbedUrl: ""
        property int loginCalls: 0
        property string lastLoginUrl: ""
        property string lastLoginUser: ""
        property string lastLoginPassword: ""
        property bool lastRemember: false

        function probeHealth(url) {
            probeCalls += 1
            lastProbedUrl = url
            healthStatus = "ok"
            healthRttMs = 14
            healthMessage = "ECS 已连接，14 ms"
        }

        function login(url, user, pwd, remember) {
            loginCalls += 1
            lastLoginUrl = url
            lastLoginUser = user
            lastLoginPassword = pwd
            lastRemember = remember
        }

        function clearLoginError() {
            loginError = ""
        }

        function reset() {
            serverUrl = "http://127.0.0.1:8000"
            healthStatus = "idle"
            healthMessage = ""
            healthRttMs = 0
            loggingIn = false
            loginError = ""
            authenticated = false
            probeCalls = 0
            lastProbedUrl = ""
            loginCalls = 0
            lastLoginUrl = ""
            lastLoginUser = ""
            lastLoginPassword = ""
            lastRemember = false
        }
    }

    Component {
        id: loginComponent
        LoginPage {
            width: root.width
            height: root.height
            sessionVm: fakeSessionVm
        }
    }

    SignalSpy {
        id: submitSpy
        signalName: "loginSubmitted"
    }

    TestCase {
        name: "LoginPage"
        when: windowShown

        function init() {
            fakeSessionVm.reset()
        }

        function test_login_card_width_and_no_prefilled_credentials() {
            let page = createTemporaryObject(loginComponent, root)
            verify(!!page, "Component exists")

            let card = findChild(page, "loginCard")
            verify(!!card, "Object exists")
            let userField = findChild(page, "usernameInput")
            verify(!!userField, "Object exists")
            let passField = findChild(page, "passwordInput")
            verify(!!passField, "Object exists")

            compare(card.width, 360)
            compare(userField.text, "")
            compare(passField.text, "")
            compare(passField.echoMode, TextInput.Password)
        }

        function test_keyboard_login_submission_and_password_toggle() {
            let page = createTemporaryObject(loginComponent, root)
            verify(!!page, "Component exists")

            let serverField = findChild(page, "serverInput")
            verify(!!serverField, "Object exists")
            let probeBtn = findChild(page, "probeHealthButton")
            verify(!!probeBtn, "Object exists")
            let userField = findChild(page, "usernameInput")
            verify(!!userField, "Object exists")
            let passField = findChild(page, "passwordInput")
            verify(!!passField, "Object exists")
            let toggleBtn = findChild(page, "togglePasswordButton")
            verify(!!toggleBtn, "Object exists")

            submitSpy.target = page
            submitSpy.clear()
            waitForRendering(page)

            serverField.text = "https://ecs.example.com:8443"
            mouseClick(probeBtn)
            tryCompare(fakeSessionVm, "probeCalls", 1)
            compare(fakeSessionVm.lastProbedUrl, "https://ecs.example.com:8443")

            mouseClick(toggleBtn)
            tryCompare(passField, "echoMode", TextInput.Normal)

            userField.text = "ops_admin"
            passField.text = "StrongPass!2026"
            passField.forceActiveFocus()
            tryCompare(passField, "activeFocus", true)

            keyClick(Qt.Key_Return)
            tryCompare(submitSpy, "count", 1)
            compare(fakeSessionVm.loginCalls, 1)
            compare(fakeSessionVm.lastLoginUrl, "https://ecs.example.com:8443")
            compare(fakeSessionVm.lastLoginUser, "ops_admin")
            compare(fakeSessionVm.lastLoginPassword, "StrongPass!2026")
            compare(fakeSessionVm.lastRemember, true)
        }

        function test_escape_clears_login_error() {
            let page = createTemporaryObject(loginComponent, root)
            verify(!!page, "Component exists")

            fakeSessionVm.loginError = "账号或密码错误。"
            let errorBanner = findChild(page, "loginErrorBanner")
            verify(!!errorBanner, "Object exists")
            tryCompare(errorBanner, "visible", true)

            page.forceActiveFocus()
            keyClick(Qt.Key_Escape)
            tryCompare(fakeSessionVm, "loginError", "")
            tryCompare(errorBanner, "visible", false)
        }

        function test_overflowing_disconnect_error_activates_marquee_scrolling() {
            let page = createTemporaryObject(loginComponent, root, { width: 384, height: 484 })
            verify(!!page, "Component exists")
            waitForRendering(page)

            let card = findChild(page, "loginCard")
            let healthLabel = findChild(page, "healthStatusLabel")
            let errorLabel = findChild(page, "loginErrorLabel")
            verify(!!card, "Object exists")
            verify(!!healthLabel, "Object exists")
            verify(!!errorLabel, "Object exists")
            compare(card.width, 360)

            fakeSessionVm.healthStatus = "ok"
            fakeSessionVm.healthMessage = "ECS 已连接，14 ms"
            tryCompare(healthLabel, "isOverflowing", false)
            compare(healthLabel.scrollingActive, false)

            let longDisconnect = "无法连接服务器（远端断开连接，请检查端口与 HTTP/HTTPS 协议是否匹配）：Server disconnected without sending a response."
            fakeSessionVm.healthStatus = "error"
            fakeSessionVm.healthMessage = longDisconnect
            fakeSessionVm.loginError = longDisconnect
            tryCompare(healthLabel, "isOverflowing", true)
            compare(healthLabel.scrollingActive, true)
            tryCompare(errorLabel, "isOverflowing", true)
            compare(errorLabel.scrollingActive, true)
        }

        function test_credentials_and_show_password_cleared_on_auth_and_logout() {
            let page = createTemporaryObject(loginComponent, root)
            verify(!!page, "Component exists")
            waitForRendering(page)

            let userField = findChild(page, "usernameInput")
            let passField = findChild(page, "passwordInput")
            let toggleBtn = findChild(page, "togglePasswordButton")
            verify(!!userField && !!passField && !!toggleBtn)

            // 1. Successful login clears password, username, and resets showPassword
            userField.text = "ops_admin"
            passField.text = "MarkerSecret#1"
            mouseClick(toggleBtn)
            tryCompare(passField, "echoMode", TextInput.Normal)
            compare(page.showPassword, true)

            fakeSessionVm.authenticated = true
            tryCompare(passField, "text", "")
            compare(userField.text, "")
            compare(page.showPassword, false)
            compare(passField.echoMode, TextInput.Password)

            // 2. Returning to login on logout / sessionEnded keeps inputs clean & masked
            fakeSessionVm.authenticated = false
            userField.text = "ops_admin"
            passField.text = "MarkerSecret#2"
            mouseClick(toggleBtn)
            compare(page.showPassword, true)

            fakeSessionVm.sessionEnded(2, "USER_LOGOUT")
            tryCompare(passField, "text", "")
            compare(userField.text, "")
            compare(page.showPassword, false)
            compare(passField.echoMode, TextInput.Password)

            // 3. Server switch also clears password and resets mask
            passField.text = "MarkerSecret#3"
            mouseClick(toggleBtn)
            compare(page.showPassword, true)
            fakeSessionVm.serverUrl = "http://127.0.0.1:18080"
            tryCompare(passField, "text", "")
            compare(page.showPassword, false)
        }

        function test_minimum_size_error_does_not_overlap_top_edge() {
            // Simulate 360x480 minimum window minus 40px titlebar => 360x440 body
            let page = createTemporaryObject(loginComponent, root, { width: 360, height: 440 })
            verify(!!page, "Component exists")
            waitForRendering(page)

            fakeSessionVm.loginError = "请输入账号。"
            let card = findChild(page, "loginCard")
            let scrollView = findChild(page, "loginScrollView")
            let errorBanner = findChild(page, "loginErrorBanner")
            verify(!!card && !!scrollView && !!errorBanner)
            tryCompare(errorBanner, "visible", true)

            // Card top must stay inside page bounds (y >= 0), never overlapping top titlebar
            let topLeft = card.mapToItem(page, 0, 0)
            verify(topLeft.y >= 0, "Login card must not overflow upward into titlebar, got y=" + topLeft.y)
            verify(scrollView.contentHeight >= card.height, "Scrollable area must accommodate full card")
        }
    }
}
