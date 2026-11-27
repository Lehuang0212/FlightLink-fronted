import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import theme
import "components"
import "pages"

ApplicationWindow {
    id: root
    objectName: "flightlinkMainWindow"
    required property var sessionVm
    required property var workspaceVm
    property var opsVm: null
    property bool systemReducedMotion: false

    // Compact WeChat-style portrait login window (384x548), expands to full workspace after login
    readonly property int loginDefaultWidth: 384
    readonly property int loginDefaultHeight: 548
    property int workspaceSavedWidth: 1280
    property int workspaceSavedHeight: 800
    readonly property bool isAuthed: Boolean(root.sessionVm && root.sessionVm.authenticated)
    readonly property bool isMaximized: root.visibility === Window.Maximized

    width: isAuthed ? workspaceSavedWidth : loginDefaultWidth
    height: isAuthed ? workspaceSavedHeight : loginDefaultHeight
    minimumWidth: isAuthed ? 1024 : 360
    minimumHeight: isAuthed ? 640 : 480
    visible: true
    title: qsTr("FlightLink Desktop 1.0")
    color: Theme.bg
    flags: Qt.Window | Qt.FramelessWindowHint

    function centerOnScreen(targetW, targetH) {
        let availW = Screen.desktopAvailableWidth > 0 ? Screen.desktopAvailableWidth : 1920
        let availH = Screen.desktopAvailableHeight > 0 ? Screen.desktopAvailableHeight : 1080
        root.x = Math.round(Screen.virtualX + Math.max(0, (availW - targetW) / 2))
        root.y = Math.round(Screen.virtualY + Math.max(0, (availH - targetH) / 2))
    }

    function applyWindowMode(authed) {
        if (authed) {
            let w = Math.max(1024, root.workspaceSavedWidth)
            let h = Math.max(640, root.workspaceSavedHeight)
            root.minimumWidth = 1024
            root.minimumHeight = 640
            root.width = w
            root.height = h
            root.centerOnScreen(w, h)
        } else {
            if (!root.isMaximized && root.width >= 1024 && root.height >= 640) {
                root.workspaceSavedWidth = root.width
                root.workspaceSavedHeight = root.height
            }
            if (root.isMaximized)
                root.showNormal()
            root.minimumWidth = 360
            root.minimumHeight = 480
            root.width = root.loginDefaultWidth
            root.height = root.loginDefaultHeight
            root.centerOnScreen(root.loginDefaultWidth, root.loginDefaultHeight)
        }
    }

    onIsAuthedChanged: applyWindowMode(isAuthed)

    Component.onCompleted: {
        Theme.reducedMotion = root.systemReducedMotion
        centerOnScreen(root.width, root.height)
    }

    // Global Ctrl+K shortcut focuses top search box when authenticated
    Shortcut {
        sequences: ["Ctrl+K"]
        context: Qt.WindowShortcut
        enabled: root.isAuthed
        onActivated: globalSearchInput.forceActiveFocus()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Custom 40px titlebar driving real Windows minimize / maximize / restore / close + Ctrl+K global search
        Rectangle {
            id: titleBar
            objectName: "windowTitleBar"
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.titlebarHeight
            color: Theme.bg

            DragHandler {
                target: null
                onActiveChanged: if (active) root.startSystemMove()
            }

            TapHandler {
                enabled: root.isAuthed
                onDoubleTapped: root.isMaximized ? root.showNormal() : root.showMaximized()
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 8
                spacing: 8

                Label {
                    text: qsTr("FlightLink Desktop")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontMd
                    font.weight: Font.Medium
                    color: Theme.text
                }

                Label {
                    text: qsTr("1.0")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontSm
                    color: Theme.text3
                }

                Item { Layout.fillWidth: true }

                // Global search pill (authenticated only)
                TextField {
                    id: globalSearchInput
                    objectName: "globalSearchInput"
                    visible: root.isAuthed
                    Layout.preferredWidth: Math.min(340, Math.max(200, root.width * 0.28))
                    Layout.preferredHeight: 30
                    placeholderText: qsTr("搜索端口组、端口或日志（Ctrl+K）")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontSm
                    color: Theme.text
                    text: root.workspaceVm ? root.workspaceVm.globalSearchQuery : ""
                    onTextEdited: if (root.workspaceVm) root.workspaceVm.setGlobalSearchQuery(text)
                    Keys.onEscapePressed: {
                        if (root.workspaceVm)
                            root.workspaceVm.clearGlobalSearch()
                        globalSearchInput.focus = false
                    }
                    background: Rectangle {
                        radius: Theme.radiusPill
                        color: Theme.field
                        border.width: globalSearchInput.activeFocus ? 2 : 0
                        border.color: Theme.primary
                    }
                }

                Item {
                    Layout.fillWidth: true
                    visible: root.isAuthed
                }

                Button {
                    id: minBtn
                    objectName: "winMinimizeButton"
                    Layout.preferredWidth: 34
                    Layout.preferredHeight: 28
                    text: "—"
                    Accessible.name: qsTr("最小化")
                    onClicked: root.showMinimized()
                    contentItem: Text {
                        text: minBtn.text
                        font.pixelSize: 12
                        color: Theme.text2
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 6
                        color: minBtn.hovered ? Theme.field : "#00000000"
                    }
                }

                Button {
                    id: maxBtn
                    objectName: "winMaximizeButton"
                    visible: root.isAuthed
                    Layout.preferredWidth: 34
                    Layout.preferredHeight: 28
                    text: root.isMaximized ? "❐" : "□"
                    Accessible.name: root.isMaximized ? qsTr("还原窗口") : qsTr("最大化")
                    onClicked: root.isMaximized ? root.showNormal() : root.showMaximized()
                    contentItem: Text {
                        text: maxBtn.text
                        font.pixelSize: 12
                        color: Theme.text2
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 6
                        color: maxBtn.hovered ? Theme.field : "#00000000"
                    }
                }

                Button {
                    id: closeBtn
                    objectName: "winCloseButton"
                    Layout.preferredWidth: 34
                    Layout.preferredHeight: 28
                    text: "×"
                    Accessible.name: qsTr("关闭")
                    onClicked: root.close()
                    contentItem: Text {
                        text: closeBtn.text
                        font.pixelSize: 15
                        color: closeBtn.hovered ? Theme.textOnPrimary : Theme.text2
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 6
                        color: closeBtn.hovered ? Theme.bad : "#00000000"
                    }
                }
            }
        }

        // Main body: LoginPage vs AppShell (clip strictly protects titleBar from overflow)
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            LoginPage {
                id: loginPage
                anchors.fill: parent
                visible: !root.isAuthed
                sessionVm: root.sessionVm
            }

            AppShell {
                id: appShell
                anchors.fill: parent
                visible: root.isAuthed
                sessionVm: root.sessionVm
                workspaceVm: root.workspaceVm
                opsVm: root.opsVm
                onNewGroupRequested: if (root.opsVm) root.opsVm.openCreateDialog()
                onEditGroupRequested: function(gid) { if (root.opsVm) root.opsVm.openEditDialog(gid) }
                onDeleteGroupRequested: function(gid, gname) { if (root.opsVm) root.opsVm.openDeleteDialog(gid, gname) }
                onGroupActionRequested: function(gid, act) { if (root.opsVm) root.opsVm.triggerGroupAction(gid, act) }
            }

            // Modal write dialogs (P3)
            GroupFormDialog {
                anchors.fill: parent
                opsVm: root.opsVm
                z: 80
            }

            DeleteGroupDialog {
                anchors.fill: parent
                opsVm: root.opsVm
                z: 85
            }

            // Global search dropdown overlay
            Rectangle {
                id: searchPopup
                objectName: "globalSearchResultsPopup"
                visible: Boolean(root.isAuthed && root.workspaceVm && root.workspaceVm.globalSearchResults.length > 0)
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: 4
                width: 360
                height: Math.min(280, searchList.contentHeight + 16)
                radius: Theme.radiusCard
                color: Theme.surface
                border.width: 1
                border.color: Theme.divider
                z: 50

                ListView {
                    id: searchList
                    anchors.fill: parent
                    anchors.margins: 8
                    model: root.workspaceVm ? root.workspaceVm.globalSearchResults : []
                    clip: true
                    delegate: Button {
                        id: srItem
                        required property var modelData
                        width: searchList.width
                        height: 40
                        onClicked: {
                            if (!root.workspaceVm)
                                return
                            if (srItem.modelData.kind === "group") {
                                root.workspaceVm.openGroupDetail(srItem.modelData.groupId)
                            } else {
                                root.workspaceVm.setLiveLogsFilter("", "all", "all", srItem.modelData.query || "")
                                root.workspaceVm.navigate("logs")
                            }
                            root.workspaceVm.clearGlobalSearch()
                        }
                        contentItem: ColumnLayout {
                            spacing: 2
                            Text {
                                text: srItem.modelData.title
                                font.family: Theme.fontSans
                                font.pixelSize: Theme.fontSm
                                font.weight: Font.Medium
                                color: Theme.text
                            }
                            Text {
                                text: srItem.modelData.subtitle
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontXs
                                color: Theme.text3
                            }
                        }
                        background: Rectangle {
                            radius: Theme.radiusTag
                            color: srItem.hovered ? Theme.surfaceTint : "#00000000"
                        }
                    }
                }
            }
        }
    }

    // Subtle 1px outer border when window is not maximized
    Rectangle {
        anchors.fill: parent
        color: "#00000000"
        border.width: root.isMaximized ? 0 : 1
        border.color: Theme.divider
        z: 190
    }

    // Native 8-direction border & corner resize handles for frameless Windows window
    WindowResizeHandles {
        anchors.fill: parent
        targetWindow: root
        z: 200
    }
}
