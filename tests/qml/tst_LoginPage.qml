import QtQuick
import QtTest
import "../../src/flightlink_desktop/qml/pages"

Item {
    id: root
    width: 480
    height: 640

    QtObject {
        id: fakeSessionVm
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
    }
}
