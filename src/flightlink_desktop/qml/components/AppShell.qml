import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import theme
import "../pages"

Item {
    id: root
    objectName: "appShell"

    required property var sessionVm
    required property var workspaceVm
    property var opsVm: null

    signal newGroupRequested()
    signal editGroupRequested(string groupId)
    signal deleteGroupRequested(string groupId, string groupName)
    signal groupActionRequested(string groupId, string action)
    signal focusGlobalSearchRequested()

    readonly property bool compact: root.width <= Theme.compactBreakpoint
    readonly property int sidebarWidth: compact ? Theme.sidebarWidthCompact : Theme.sidebarWidthWide
    property bool userMenuOpen: false

    // Main shell keyboard shortcuts: Ctrl+1..4 navigation, Esc dismiss popups/search
    Shortcut {
        sequences: ["Ctrl+1"]
        context: Qt.WindowShortcut
        enabled: root.visible
        onActivated: if (root.workspaceVm) root.workspaceVm.navigate("overview")
    }
    Shortcut {
        sequences: ["Ctrl+2"]
        context: Qt.WindowShortcut
        enabled: root.visible
        onActivated: if (root.workspaceVm) root.workspaceVm.navigate("groups")
    }
    Shortcut {
        sequences: ["Ctrl+3"]
        context: Qt.WindowShortcut
        enabled: root.visible
        onActivated: if (root.workspaceVm) root.workspaceVm.navigate("logs")
    }
    Shortcut {
        sequences: ["Ctrl+4"]
        context: Qt.WindowShortcut
        enabled: root.visible
        onActivated: if (root.workspaceVm) root.workspaceVm.navigate("history")
    }
    Shortcut {
        sequences: [StandardKey.Cancel]
        context: Qt.WindowShortcut
        enabled: root.visible
        onActivated: {
            root.userMenuOpen = false
            if (root.workspaceVm)
                root.workspaceVm.clearGlobalSearch()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Main horizontal split: Sidebar + Active Page
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Left sidebar (208px wide, 192px at <=1360px)
            Rectangle {
                id: sidebar
                objectName: "appSidebar"
                Layout.preferredWidth: root.sidebarWidth
                Layout.fillHeight: true
                color: Theme.bg

                ColumnLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    anchors.topMargin: 8
                    anchors.bottomMargin: 12
                    spacing: 12

                    // ECS connectivity & RTT row
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Rectangle {
                            width: 8; height: 8; radius: 4
                            color: root.sessionVm && root.sessionVm.healthStatus === "ok" ? Theme.ok : Theme.warn
                        }

                        Text {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            elide: Text.ElideRight
                            text: root.sessionVm && root.sessionVm.healthRttMs > 0
                                ? qsTr("ECS %1 ms").arg(root.sessionVm.healthRttMs)
                                : qsTr("ECS 已连接")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSm
                            color: Theme.text2
                        }
                    }

                    // New Port Group FAB (admin only; disabled when at 5-group limit)
                    Button {
                        id: fabButton
                        objectName: "newGroupFab"
                        visible: Boolean(root.sessionVm && root.sessionVm.isAdmin)
                        enabled: Boolean(!root.workspaceVm || !root.workspaceVm.atGroupLimit)
                        Layout.fillWidth: true
                        Layout.preferredHeight: 44
                        text: qsTr("+  新建端口组")
                        onClicked: root.newGroupRequested()
                        contentItem: Text {
                            text: fabButton.text
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontMd
                            font.weight: Font.Medium
                            color: fabButton.enabled ? Theme.textOnPrimaryContainer : Theme.text3
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            radius: Theme.radiusFab
                            color: !fabButton.enabled
                                ? Theme.idleBg
                                : (fabButton.hovered ? Theme.fabHover : Theme.fab)
                        }
                    }

                    // Primary 4 navigation tabs
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Repeater {
                            model: [
                                { key: "overview", label: qsTr("总览"), shortcut: "Ctrl+1" },
                                { key: "groups", label: qsTr("端口组"), shortcut: "Ctrl+2" },
                                { key: "logs", label: qsTr("日志"), shortcut: "Ctrl+3" },
                                { key: "history", label: qsTr("历史日志"), shortcut: "Ctrl+4" }
                            ]

                            delegate: Button {
                                id: navBtn
                                required property var modelData
                                objectName: "navItem_" + modelData.key
                                readonly property bool active: {
                                    if (!root.workspaceVm)
                                        return false
                                    if (modelData.key === "groups" && root.workspaceVm.route === "detail")
                                        return true
                                    if (modelData.key === "history" && root.workspaceVm.route === "historyDetail")
                                        return true
                                    return root.workspaceVm.route === modelData.key
                                }
                                Layout.fillWidth: true
                                Layout.preferredHeight: 38
                                onClicked: if (root.workspaceVm) root.workspaceVm.navigate(modelData.key)
                                contentItem: RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 12
                                    anchors.rightMargin: 12
                                    Text {
                                        text: navBtn.modelData.label
                                        font.family: Theme.fontSans
                                        font.pixelSize: Theme.fontMd
                                        font.weight: navBtn.active ? Font.Medium : Font.Normal
                                        color: navBtn.active ? Theme.textOnPrimaryContainer : Theme.text2
                                    }
                                    Item { Layout.fillWidth: true }
                                }
                                background: Rectangle {
                                    radius: Theme.radiusPill
                                    color: navBtn.active
                                        ? Theme.primaryContainer
                                        : (navBtn.hovered ? Theme.surfaceTint : "#00000000")
                                }
                            }
                        }
                    }

                    // Host 3-component summary (API / Agent / Archive)
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 8
                        spacing: 6

                        Rectangle {
                            width: 8; height: 8; radius: 4
                            color: root.workspaceVm && root.workspaceVm.componentsOkCount === root.workspaceVm.componentsTotalCount
                                ? Theme.ok
                                : Theme.warn
                        }

                        Text {
                            text: qsTr("服务状态")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSm
                            color: Theme.text2
                        }

                        Text {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            elide: Text.ElideRight
                            text: root.workspaceVm
                                ? qsTr("%1 / %2 正常").arg(root.workspaceVm.componentsOkCount).arg(root.workspaceVm.componentsTotalCount)
                                : "3 / 3 正常"
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSm
                            font.weight: Font.Medium
                            color: Theme.text
                        }
                    }

                    Item { Layout.fillHeight: true }

                    // User menu popup above user row
                    Rectangle {
                        visible: root.userMenuOpen
                        Layout.fillWidth: true
                        Layout.preferredHeight: userMenuCol.implicitHeight + 16
                        radius: Theme.radiusCard
                        color: Theme.surface
                        border.width: 1
                        border.color: Theme.divider

                        ColumnLayout {
                            id: userMenuCol
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 8
                            spacing: 6

                            Text {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                elide: Text.ElideRight
                                text: root.sessionVm ? root.sessionVm.serverUrl : ""
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontXs
                                color: Theme.text3
                            }

                            Text {
                                objectName: "sidebarInstanceId"
                                visible: Boolean(root.sessionVm && root.sessionVm.ecsInstanceId.length > 0)
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                elide: Text.ElideRight
                                text: root.sessionVm ? qsTr("实例：%1").arg(root.sessionVm.ecsInstanceId) : ""
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontXs
                                color: Theme.text2
                            }

                            AppButton {
                                objectName: "sidebarLogoutButton"
                                Layout.fillWidth: true
                                compact: true
                                variant: "danger"
                                text: qsTr("退出登录 / 切换服务器")
                                onClicked: {
                                    root.userMenuOpen = false
                                    if (root.sessionVm)
                                        root.sessionVm.logout()
                                }
                            }
                        }
                    }

                    // Bottom user card
                    Button {
                        id: userBtn
                        objectName: "sidebarUserButton"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 46
                        onClicked: root.userMenuOpen = !root.userMenuOpen
                        contentItem: RowLayout {
                            spacing: 8
                            Rectangle {
                                Layout.preferredWidth: 30
                                Layout.preferredHeight: 30
                                radius: 15
                                color: Theme.primaryContainer
                                Text {
                                    anchors.centerIn: parent
                                    text: root.sessionVm && root.sessionVm.currentDisplayName
                                        ? root.sessionVm.currentDisplayName.slice(0, 1).toUpperCase()
                                        : "U"
                                    font.family: Theme.fontSans
                                    font.pixelSize: Theme.fontBody
                                    font.weight: Font.Medium
                                    color: Theme.textOnPrimaryContainer
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 1
                                Text {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    elide: Text.ElideRight
                                    text: root.sessionVm ? root.sessionVm.currentDisplayName : ""
                                    font.family: Theme.fontSans
                                    font.pixelSize: Theme.fontSm
                                    font.weight: Font.Medium
                                    color: Theme.text
                                }
                                Text {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    elide: Text.ElideRight
                                    text: root.sessionVm ? root.sessionVm.currentRoleLabel : ""
                                    font.family: Theme.fontSans
                                    font.pixelSize: Theme.fontXs
                                    color: Theme.text3
                                }
                            }
                        }
                        background: Rectangle {
                            radius: Theme.radiusCard
                            color: userBtn.hovered ? Theme.surfaceTint : "#00000000"
                        }
                    }
                }
            }

            // Right main content area
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    // Prominent archive failure banner ONLY when auto-save failed after retries
                    Rectangle {
                        objectName: "archiveFailureBanner"
                        visible: Boolean(root.workspaceVm && root.workspaceVm.archiveFailedCount > 0)
                        Layout.fillWidth: true
                        Layout.preferredHeight: 40
                        color: Theme.badBg

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 16
                            anchors.rightMargin: 16
                            spacing: 10

                            MarqueeText {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                Layout.preferredHeight: 20
                                text: root.workspaceVm
                                    ? qsTr("自动归档失败（%1 个切片）：%2").arg(root.workspaceVm.archiveFailedCount).arg(root.workspaceVm.archiveFailedMessage || "请前往历史日志重新下载")
                                    : ""
                                fontFamily: Theme.fontSans
                                pixelSize: Theme.fontSm
                                fontWeight: Font.Medium
                                color: Theme.bad
                            }

                            AppButton {
                                objectName: "jumpFailedArchiveButton"
                                compact: true
                                variant: "dangerFilled"
                                text: qsTr("重新下载日志")
                                onClicked: {
                                    if (root.workspaceVm && root.workspaceVm.archiveFailedGroupId)
                                        root.workspaceVm.openHistoryGroup(root.workspaceVm.archiveFailedGroupId, root.workspaceVm.archiveFailedSessionId)
                                    else if (root.workspaceVm)
                                        root.workspaceVm.navigate("history")
                                }
                            }
                        }
                    }

                    // Active async operation progress / needs_verification banner (P3)
                    Rectangle {
                        objectName: "operationTrackerBanner"
                        visible: Boolean(root.opsVm && root.opsVm.hasActiveOperation)
                        Layout.fillWidth: true
                        Layout.preferredHeight: opBannerCol.implicitHeight + 16
                        color: root.opsVm && root.opsVm.activeStatus === "needs_verification"
                            ? Theme.warnBg
                            : root.opsVm && root.opsVm.activeStatus === "failed"
                                ? Theme.badBg
                                : root.opsVm && root.opsVm.activeStatus === "succeeded"
                                    ? Theme.okBg
                                    : Theme.primaryContainer

                        ColumnLayout {
                            id: opBannerCol
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 8
                            spacing: 4

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10

                                MarqueeText {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.preferredHeight: 20
                                    text: root.opsVm ? root.opsVm.activeSummaryText : ""
                                    fontFamily: Theme.fontSans
                                    pixelSize: Theme.fontSm
                                    fontWeight: Font.Medium
                                    color: Theme.text
                                }

                                AppButton {
                                    objectName: "retryOperationButton"
                                    compact: true
                                    variant: "primary"
                                    visible: Boolean(root.opsVm && root.opsVm.canRetryActive && root.sessionVm && root.sessionVm.isAdmin)
                                    text: qsTr("重试核验")
                                    onClicked: if (root.opsVm) root.opsVm.retryActiveOperation()
                                }

                                AppButton {
                                    objectName: "dismissOperationButton"
                                    compact: true
                                    variant: "secondary"
                                    visible: Boolean(root.opsVm && root.opsVm.activeIsTerminal)
                                    text: qsTr("关闭提示")
                                    onClicked: if (root.opsVm) root.opsVm.dismissActiveOperation()
                                }
                            }

                            Text {
                                visible: Boolean(root.opsVm && root.opsVm.activeStepsText.length > 0)
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                wrapMode: Text.Wrap
                                text: root.opsVm ? root.opsVm.activeStepsText : ""
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontXs
                                color: Theme.text2
                            }
                        }
                    }

                    // Active page stack
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        OverviewPage {
                            anchors.fill: parent
                            visible: !root.workspaceVm || root.workspaceVm.route === "overview"
                            workspaceVm: root.workspaceVm
                            sessionVm: root.sessionVm
                            compact: root.compact
                        }

                        GroupsPage {
                            anchors.fill: parent
                            visible: Boolean(root.workspaceVm && root.workspaceVm.route === "groups")
                            workspaceVm: root.workspaceVm
                            sessionVm: root.sessionVm
                            compact: root.compact
                            onCreateGroupRequested: root.newGroupRequested()
                            onEditGroupRequested: function(gid) { root.editGroupRequested(gid) }
                            onDeleteGroupRequested: function(gid, gname) { root.deleteGroupRequested(gid, gname) }
                        }

                        GroupDetailPage {
                            anchors.fill: parent
                            visible: Boolean(root.workspaceVm && root.workspaceVm.route === "detail")
                            workspaceVm: root.workspaceVm
                            sessionVm: root.sessionVm
                            compact: root.compact
                            onGroupActionRequested: function(gid, act) { root.groupActionRequested(gid, act) }
                            onEditGroupRequested: function(gid) { root.editGroupRequested(gid) }
                            onDeleteGroupRequested: function(gid, gname) { root.deleteGroupRequested(gid, gname) }
                        }

                        LogsPage {
                            anchors.fill: parent
                            visible: Boolean(root.workspaceVm && root.workspaceVm.route === "logs")
                            workspaceVm: root.workspaceVm
                            compact: root.compact
                        }

                        HistoryPage {
                            anchors.fill: parent
                            visible: Boolean(root.workspaceVm && root.workspaceVm.route === "history")
                            workspaceVm: root.workspaceVm
                            compact: root.compact
                        }

                        HistoryDetailPage {
                            anchors.fill: parent
                            visible: Boolean(root.workspaceVm && root.workspaceVm.route === "historyDetail")
                            workspaceVm: root.workspaceVm
                            compact: root.compact
                        }
                    }
                }

                // Toast overlay
                Rectangle {
                    objectName: "toastBanner"
                    visible: Boolean(root.workspaceVm && root.workspaceVm.toastVisible)
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 16
                    width: Math.min(parent.width - 40, toastLbl.implicitWidth + 32)
                    height: 36
                    radius: Theme.radiusPill
                    color: root.workspaceVm && root.workspaceVm.toastTone === "bad"
                        ? Theme.bad
                        : root.workspaceVm && root.workspaceVm.toastTone === "warn"
                            ? Theme.warn
                            : Theme.text

                    Text {
                        id: toastLbl
                        anchors.centerIn: parent
                        text: root.workspaceVm ? root.workspaceVm.toastMessage : ""
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSm
                        color: Theme.textOnPrimary
                    }
                }
            }
        }

        // Bottom 24px statusbar
        Rectangle {
            objectName: "appStatusBar"
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.statusbarHeight
            color: Theme.bg

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 1
                color: Theme.divider
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 12

                Text {
                    text: root.sessionVm && root.sessionVm.healthRttMs > 0
                        ? qsTr("ECS %1 ms").arg(root.sessionVm.healthRttMs)
                        : qsTr("ECS 已连接")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontXs
                    color: Theme.text3
                }

                Button {
                    id: instanceIdCopyBtn
                    objectName: "statusBarInstanceId"
                    visible: Boolean(root.sessionVm && root.sessionVm.ecsInstanceId.length > 0)
                    Layout.preferredHeight: 20
                    text: root.sessionVm ? root.sessionVm.ecsInstanceId : ""
                    ToolTip.visible: hovered
                    ToolTip.text: qsTr("点击复制 ECS 实例 ID")
                    onClicked: {
                        if (root.sessionVm && root.sessionVm.ecsInstanceId) {
                            root.sessionVm.copyToClipboard(root.sessionVm.ecsInstanceId)
                            if (root.workspaceVm)
                                root.workspaceVm.showToast(qsTr("已复制实例 ID：%1").arg(root.sessionVm.ecsInstanceId), "info")
                        }
                    }
                    HoverHandler { cursorShape: Qt.PointingHandCursor }
                    contentItem: Text {
                        text: instanceIdCopyBtn.text
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontXs
                        color: instanceIdCopyBtn.hovered ? Theme.primary : Theme.text2
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 4
                        color: instanceIdCopyBtn.hovered ? Theme.surfaceTint : "#00000000"
                    }
                }

                Text {
                    visible: Boolean(root.workspaceVm && root.workspaceVm.archiveFailedCount > 0)
                    text: root.workspaceVm ? qsTr("归档失败 %1 项").arg(root.workspaceVm.archiveFailedCount) : ""
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontXs
                    font.weight: Font.Medium
                    color: Theme.bad
                }

                Text {
                    visible: Boolean(!root.workspaceVm || root.workspaceVm.archiveFailedCount === 0)
                    text: root.workspaceVm ? root.workspaceVm.archiveStatusText : ""
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontXs
                    color: Theme.text3
                }

                Item { Layout.fillWidth: true }

                // Switch #2: Pause live updates (pauses page reads ONLY — NEVER background archive or operations)
                Button {
                    id: liveToggleBtn
                    objectName: "liveUpdatesToggleButton"
                    Layout.preferredHeight: 20
                    text: root.workspaceVm && root.workspaceVm.liveUpdatesEnabled ? qsTr("⏸ 实时更新") : qsTr("▶ 已暂停更新")
                    onClicked: if (root.workspaceVm) root.workspaceVm.toggleLiveUpdates()
                    contentItem: Text {
                        text: liveToggleBtn.text
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontXs
                        color: root.workspaceVm && !root.workspaceVm.liveUpdatesEnabled ? Theme.warn : Theme.text2
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle { color: "#00000000" }
                }

                Text {
                    text: qsTr("最近同步 %1").arg(root.workspaceVm ? root.workspaceVm.lastSyncText : "--:--:--")
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontXs
                    color: Theme.text3
                }

                Text {
                    text: qsTr("v1.0.0")
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontXs
                    color: Theme.text3
                }
            }
        }
    }
}
