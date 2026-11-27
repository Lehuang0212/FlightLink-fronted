import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import theme
import "../components"

FocusScope {
    id: root
    objectName: "loginPage"

    required property var sessionVm

    property bool showPassword: false
    property bool rememberSession: true

    signal loginSubmitted(string serverUrl, string username)

    function submitLogin() {
        if (!sessionVm || sessionVm.loggingIn)
            return
        root.loginSubmitted(serverInput.text, usernameInput.text)
        sessionVm.login(serverInput.text, usernameInput.text, passwordInput.text, root.rememberSession)
    }

    function probeServer() {
        if (!sessionVm)
            return
        sessionVm.probeHealth(serverInput.text)
    }

    Component.onCompleted: {
        if (sessionVm && sessionVm.serverUrl)
            serverInput.text = sessionVm.serverUrl
        usernameInput.forceActiveFocus()
    }

    Connections {
        target: root.sessionVm
        function onServerUrlChanged() {
            if (root.sessionVm && serverInput.text !== root.sessionVm.serverUrl && !serverInput.activeFocus)
                serverInput.text = root.sessionVm.serverUrl
        }
    }

    Shortcut {
        sequences: [StandardKey.Cancel]
        context: Qt.WindowShortcut
        enabled: root.visible
        onActivated: {
            if (root.sessionVm)
                root.sessionVm.clearLoginError()
        }
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.bg
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 10
        width: Math.min(Theme.loginCardWidth, Math.max(320, root.width - 24))

        Rectangle {
            objectName: "loginCard"
            Layout.fillWidth: true
            Layout.preferredHeight: cardColumn.implicitHeight + 40
            radius: Theme.radiusPanel
            color: Theme.surface
            border.width: 1
            border.color: Theme.divider

            ColumnLayout {
                id: cardColumn
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 20
                spacing: 11

                Label {
                    objectName: "loginTitle"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    elide: Text.ElideRight
                    text: qsTr("FlightLink Desktop 1.0")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontXl
                    font.weight: Font.Medium
                    color: Theme.text
                }

                // Server address field + connectivity probe
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 5

                    Label {
                        text: qsTr("服务器地址")
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSm
                        color: Theme.text2
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 8

                        TextField {
                            id: serverInput
                            objectName: "serverInput"
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.preferredWidth: 0
                            Layout.preferredHeight: Theme.controlHeight
                            placeholderText: qsTr("https://host 或 http://127.0.0.1:8000")
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSm
                            color: Theme.text
                            selectByMouse: true
                            activeFocusOnTab: true
                            KeyNavigation.tab: probeButton
                            onAccepted: root.probeServer()
                            background: Rectangle {
                                radius: Theme.radiusField
                                color: Theme.field
                                border.width: serverInput.activeFocus ? 2 : 1
                                border.color: serverInput.activeFocus ? Theme.primary : "#00000000"
                            }
                        }

                        Button {
                            id: probeButton
                            objectName: "probeHealthButton"
                            Layout.preferredWidth: 72
                            Layout.preferredHeight: Theme.controlHeight
                            text: root.sessionVm && root.sessionVm.healthStatus === "checking"
                                ? qsTr("检测中")
                                : qsTr("测连接")
                            enabled: !root.sessionVm || root.sessionVm.healthStatus !== "checking"
                            activeFocusOnTab: true
                            KeyNavigation.tab: usernameInput
                            onClicked: root.probeServer()
                            contentItem: Text {
                                text: probeButton.text
                                font.family: Theme.fontSans
                                font.pixelSize: Theme.fontSm
                                font.weight: Font.Medium
                                color: Theme.primary
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                radius: Theme.radiusField
                                color: probeButton.hovered ? Theme.primaryContainer : Theme.surfaceTint
                                border.width: probeButton.activeFocus ? 2 : 1
                                border.color: probeButton.activeFocus ? Theme.primary : Theme.divider
                            }
                        }
                    }
                }

                // Username field (never prefilled)
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 5

                    Label {
                        text: qsTr("账号")
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSm
                        color: Theme.text2
                    }

                    TextField {
                        id: usernameInput
                        objectName: "usernameInput"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredWidth: 0
                        Layout.preferredHeight: Theme.controlHeight
                        placeholderText: qsTr("请输入管理员或只读账号")
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontBody
                        color: Theme.text
                        selectByMouse: true
                        activeFocusOnTab: true
                        KeyNavigation.tab: passwordInput
                        onAccepted: passwordInput.forceActiveFocus()
                        background: Rectangle {
                            radius: Theme.radiusField
                            color: Theme.field
                            border.width: usernameInput.activeFocus ? 2 : 1
                            border.color: usernameInput.activeFocus ? Theme.primary : "#00000000"
                        }
                    }
                }

                // Password field with visibility toggle (never prefilled)
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 5

                    Label {
                        text: qsTr("密码")
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSm
                        color: Theme.text2
                    }

                    Item {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredHeight: Theme.controlHeight

                        TextField {
                            id: passwordInput
                            objectName: "passwordInput"
                            anchors.fill: parent
                            rightPadding: 44
                            echoMode: root.showPassword ? TextInput.Normal : TextInput.Password
                            placeholderText: qsTr("请输入密码")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontBody
                            color: Theme.text
                            selectByMouse: true
                            activeFocusOnTab: true
                            KeyNavigation.tab: togglePasswordButton
                            onAccepted: root.submitLogin()
                            background: Rectangle {
                                radius: Theme.radiusField
                                color: Theme.field
                                border.width: passwordInput.activeFocus ? 2 : 1
                                border.color: passwordInput.activeFocus ? Theme.primary : "#00000000"
                            }
                        }

                        Button {
                            id: togglePasswordButton
                            objectName: "togglePasswordButton"
                            anchors.right: parent.right
                            anchors.rightMargin: 4
                            anchors.verticalCenter: parent.verticalCenter
                            width: 36
                            height: 28
                            activeFocusOnTab: true
                            KeyNavigation.tab: rememberCheck
                            text: root.showPassword ? qsTr("隐藏") : qsTr("显示")
                            Accessible.name: root.showPassword ? qsTr("隐藏密码") : qsTr("显示密码")
                            onClicked: root.showPassword = !root.showPassword
                            contentItem: Text {
                                text: togglePasswordButton.text
                                font.family: Theme.fontSans
                                font.pixelSize: Theme.fontXs
                                color: Theme.text2
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                radius: 6
                                color: togglePasswordButton.hovered ? Theme.divider : "#00000000"
                                border.width: togglePasswordButton.activeFocus ? 1 : 0
                                border.color: Theme.primary
                            }
                        }
                    }
                }

                CheckBox {
                    id: rememberCheck
                    objectName: "rememberSessionCheck"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    checked: root.rememberSession
                    activeFocusOnTab: true
                    KeyNavigation.tab: loginButton
                    onToggled: root.rememberSession = checked
                    text: qsTr("使用 Windows 凭据库保持登录会话")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontSm
                }

                // Inline error message with automatic horizontal marquee scrolling on overflow
                Rectangle {
                    id: errorBanner
                    objectName: "loginErrorBanner"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    visible: Boolean(root.sessionVm && root.sessionVm.loginError.length > 0)
                    Layout.preferredHeight: visible ? 34 : 0
                    radius: Theme.radiusTag
                    color: Theme.badBg

                    MarqueeText {
                        id: errorLabel
                        objectName: "loginErrorLabel"
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        text: root.sessionVm ? root.sessionVm.loginError : ""
                        fontFamily: Theme.fontSans
                        pixelSize: Theme.fontSm
                        color: Theme.bad
                    }
                }

                // Primary login button
                Button {
                    id: loginButton
                    objectName: "loginSubmitButton"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredHeight: 38
                    enabled: !root.sessionVm || !root.sessionVm.loggingIn
                    activeFocusOnTab: true
                    KeyNavigation.tab: serverInput
                    text: root.sessionVm && root.sessionVm.loggingIn ? qsTr("正在连接…") : qsTr("登录")
                    onClicked: root.submitLogin()
                    Keys.onReturnPressed: root.submitLogin()
                    Keys.onEnterPressed: root.submitLogin()
                    contentItem: Text {
                        text: loginButton.text
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontMd
                        font.weight: Font.Medium
                        color: Theme.textOnPrimary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: Theme.radiusPill
                        color: !loginButton.enabled
                            ? Theme.outline
                            : (loginButton.hovered ? Theme.primaryHover : Theme.primary)
                        border.width: loginButton.activeFocus ? 2 : 0
                        border.color: Theme.textOnPrimaryContainer
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: Theme.divider
                }

                // Health status footer with automatic horizontal marquee scrolling on overflow
                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 8

                    Rectangle {
                        objectName: "healthStatusDot"
                        Layout.preferredWidth: 8
                        Layout.preferredHeight: 8
                        radius: 4
                        color: !root.sessionVm || root.sessionVm.healthStatus === "idle"
                            ? Theme.outline
                            : root.sessionVm.healthStatus === "checking"
                                ? Theme.warn
                                : root.sessionVm.healthStatus === "ok"
                                    ? Theme.ok
                                    : Theme.bad
                    }

                    MarqueeText {
                        objectName: "healthStatusLabel"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredWidth: 0
                        Layout.preferredHeight: 20
                        fontFamily: Theme.fontSans
                        pixelSize: Theme.fontSm
                        color: root.sessionVm && root.sessionVm.healthStatus === "error" ? Theme.bad : Theme.text2
                        text: {
                            if (!root.sessionVm || root.sessionVm.healthMessage.length === 0)
                                return qsTr("登录前将自动检测 /api/v1/health 连通性")
                            return root.sessionVm.healthMessage
                        }
                    }
                }
            }
        }

        Label {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            elide: Text.ElideRight
            horizontalAlignment: Text.AlignHCenter
            font.family: Theme.fontSans
            font.pixelSize: Theme.fontXs
            color: Theme.text3
            text: qsTr("连接真实 FlightLink ECS 1.0 · 不保存明文密码")
        }
    }
}
