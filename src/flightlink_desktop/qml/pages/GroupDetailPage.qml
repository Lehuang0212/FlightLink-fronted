import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import theme
import "../components"

Flickable {
    id: root
    objectName: "groupDetailPage"

    required property var workspaceVm
    required property var sessionVm
    property bool compact: false
    property bool commandsExpanded: false

    signal groupActionRequested(string groupId, string action)
    signal editGroupRequested(string groupId)
    signal deleteGroupRequested(string groupId, string groupName)

    contentWidth: width
    contentHeight: detailCol.implicitHeight + (compact ? 36 : 44)
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

    readonly property int marginSize: compact ? Theme.contentMarginCompact : Theme.contentMarginWide
    readonly property int gapSize: compact ? Theme.columnGapCompact : Theme.columnGapWide

    ColumnLayout {
        id: detailCol
        x: root.marginSize
        y: root.compact ? 14 : 20
        width: Math.max(0, root.width - root.marginSize * 2)
        spacing: root.compact ? 10 : 14

        // Page header
        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 10

            Button {
                objectName: "detailBackButton"
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32
                text: "←"
                Accessible.name: qsTr("返回端口组")
                onClicked: if (root.workspaceVm) root.workspaceVm.navigate("groups")
            }

            Text {
                objectName: "detailGroupTitle"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                elide: Text.ElideRight
                text: root.workspaceVm ? root.workspaceVm.detailName : ""
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontXl
                font.weight: Font.Medium
                color: Theme.text
            }

            StatusTag {
                text: root.workspaceVm ? root.workspaceVm.detailLifecycleLabel : ""
                tone: root.workspaceVm ? root.workspaceVm.detailLifecycleTone : "idle"
            }

            StatusTag {
                visible: Boolean(root.workspaceVm && root.workspaceVm.detailStale)
                text: qsTr("观测过期 · %1").arg(root.workspaceVm ? root.workspaceVm.detailObservedAt : "—")
                tone: "warn"
            }

            // Admin-only write action controls (hidden for viewer)
            RowLayout {
                visible: Boolean(root.sessionVm && root.sessionVm.isAdmin)
                spacing: 8

                Button {
                    objectName: "detailStartStopButton"
                    text: root.workspaceVm && root.workspaceVm.detailLifecycleState === "running"
                        ? qsTr("停止 Router")
                        : qsTr("启动 Router")
                    onClicked: {
                        if (!root.workspaceVm)
                            return
                        let act = root.workspaceVm.detailLifecycleState === "running" ? "stop" : "start"
                        root.groupActionRequested(root.workspaceVm.activeGroupId, act)
                    }
                }

                Button {
                    objectName: "detailRestartButton"
                    enabled: Boolean(root.workspaceVm && root.workspaceVm.detailLifecycleState === "running")
                    text: qsTr("重启 Router")
                    onClicked: if (root.workspaceVm) root.groupActionRequested(root.workspaceVm.activeGroupId, "restart")
                }

                Button {
                    objectName: "detailSyncSgButton"
                    text: qsTr("同步安全组")
                    onClicked: if (root.workspaceVm) root.groupActionRequested(root.workspaceVm.activeGroupId, "sync-security-group")
                }

                Button {
                    objectName: "detailEditButton"
                    text: qsTr("编辑配置")
                    onClicked: if (root.workspaceVm) root.editGroupRequested(root.workspaceVm.activeGroupId)
                }

                Button {
                    objectName: "detailDeleteButton"
                    text: qsTr("删除")
                    onClicked: if (root.workspaceVm) root.deleteGroupRequested(root.workspaceVm.activeGroupId, root.workspaceVm.detailName)
                }
            }
        }

        // Link wire diagram panel
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 84
            radius: Theme.radiusPanel
            color: Theme.surface
            border.width: 1
            border.color: Theme.divider

            LinkWireCard {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                anchors.topMargin: 8
                anchors.bottomMargin: 8
                dtuPort: root.workspaceVm ? root.workspaceVm.detailDtuPort : 0
                gcsProtocol: root.workspaceVm ? root.workspaceVm.detailGcsProtocol : "tcp"
                gcsPort: root.workspaceVm ? root.workspaceVm.detailGcsPort : 0
                dtuPeer: root.workspaceVm ? root.workspaceVm.detailDtuPeer : "—"
                gcsPeer: root.workspaceVm ? root.workspaceVm.detailGcsPeer : "—"
                fcOnline: Boolean(root.workspaceVm && root.workspaceVm.detailFcState === "online")
                routerRunning: Boolean(root.workspaceVm && root.workspaceVm.detailLifecycleState === "running")
                gcsConnected: Boolean(root.workspaceVm && root.workspaceVm.detailGcsState === "connected")
                liveActive: Boolean(root.workspaceVm && root.workspaceVm.liveUpdatesEnabled)
            }
        }

        // Three independent per-group services (state, observed_at, stale kept distinct)
        Rectangle {
            objectName: "detailServicesPanel"
            Layout.fillWidth: true
            Layout.preferredHeight: servicesCol.implicitHeight + 20
            radius: Theme.radiusPanel
            color: Theme.surface
            border.width: 1
            border.color: Theme.divider

            ColumnLayout {
                id: servicesCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 10
                spacing: 8

                Text {
                    text: qsTr("服务（独立状态与观测时效）")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontMd
                    font.weight: Font.Medium
                    color: Theme.text
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: root.gapSize

                    Repeater {
                        model: root.workspaceVm ? root.workspaceVm.detailServices : []

                        delegate: Rectangle {
                            id: svcCard
                            required property var modelData
                            objectName: "serviceCard_" + svcCard.modelData.key
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.preferredHeight: 62
                            radius: Theme.radiusCard
                            color: Theme.surfaceTint

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 4

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: 6

                                    Text {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        elide: Text.ElideRight
                                        text: svcCard.modelData.title
                                        font.family: Theme.fontSans
                                        font.pixelSize: Theme.fontBody
                                        font.weight: Font.Medium
                                        color: Theme.text
                                    }

                                    StatusTag {
                                        objectName: "serviceStateTag_" + svcCard.modelData.key
                                        text: svcCard.modelData.stateLabel
                                        tone: svcCard.modelData.tone
                                    }

                                    // Separate stale badge — stale is NEVER drawn as offline
                                    StatusTag {
                                        objectName: "serviceStaleTag_" + svcCard.modelData.key
                                        visible: Boolean(svcCard.modelData.stale)
                                        text: qsTr("已过期")
                                        tone: "warn"
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: 6

                                    Text {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        elide: Text.ElideRight
                                        text: svcCard.modelData.meta
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontXs
                                        color: Theme.text2
                                    }

                                    Text {
                                        text: svcCard.modelData.observedAt
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontXs
                                        color: svcCard.modelData.stale ? Theme.warn : Theme.text3
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // 12 Telemetry cards (4x3 grid — fits on first screen at 1280x800)
        Rectangle {
            objectName: "detailTelemetryPanel"
            Layout.fillWidth: true
            Layout.preferredHeight: teleCol.implicitHeight + 20
            radius: Theme.radiusPanel
            color: Theme.surface
            border.width: 1
            border.color: Theme.divider

            ColumnLayout {
                id: teleCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 10
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0

                    Text {
                        text: qsTr("遥测")
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontMd
                        font.weight: Font.Medium
                        color: Theme.text
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: root.workspaceVm ? root.workspaceVm.detailTelemetryNote : ""
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSm
                        color: Theme.text3
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 4
                    columnSpacing: root.compact ? 8 : 10
                    rowSpacing: root.compact ? 8 : 10

                    Repeater {
                        model: root.workspaceVm ? root.workspaceVm.detailTelemetryCards : []

                        delegate: Rectangle {
                            id: tCard
                            required property var modelData
                            objectName: "telemetryCard_" + tCard.modelData.key
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.preferredHeight: root.compact ? 72 : 80
                            radius: Theme.radiusCard
                            color: tCard.modelData.tone === "bad"
                                ? Theme.badBg
                                : tCard.modelData.tone === "warn"
                                    ? Theme.warnBg
                                    : Theme.surfaceTint

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: root.compact ? 8 : 10
                                spacing: 2

                                Text {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    elide: Text.ElideRight
                                    text: tCard.modelData.label
                                    font.family: Theme.fontSans
                                    font.pixelSize: Theme.fontXs
                                    color: Theme.text2
                                }

                                Text {
                                    objectName: "telemetryValue_" + tCard.modelData.key
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    elide: Text.ElideRight
                                    text: tCard.modelData.value
                                    font.family: Theme.fontMono
                                    font.pixelSize: root.compact ? Theme.fontLg : Theme.fontXl
                                    font.weight: Font.Medium
                                    color: tCard.modelData.empty
                                        ? Theme.text3
                                        : tCard.modelData.tone === "bad"
                                            ? Theme.bad
                                            : tCard.modelData.tone === "warn"
                                                ? Theme.warn
                                                : Theme.text
                                }

                                Text {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    elide: Text.ElideRight
                                    text: tCard.modelData.sub
                                    font.family: Theme.fontSans
                                    font.pixelSize: Theme.fontXs
                                    color: Theme.text3
                                }
                            }
                        }
                    }
                }
            }
        }

        // Read-only GCS commands disclosure (strictly zero send-command inputs)
        Rectangle {
            objectName: "detailGcsCommandsPanel"
            Layout.fillWidth: true
            Layout.preferredHeight: cmdCol.implicitHeight + 16
            radius: Theme.radiusPanel
            color: Theme.surface
            border.width: 1
            border.color: Theme.divider

            ColumnLayout {
                id: cmdCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 8
                spacing: 8

                Button {
                    id: cmdToggleBtn
                    objectName: "gcsCommandsToggleButton"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 30
                    onClicked: root.commandsExpanded = !root.commandsExpanded
                    contentItem: RowLayout {
                        spacing: 8
                        Text {
                            text: qsTr("地面站指令（只读观测）")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontBody
                            font.weight: Font.Medium
                            color: Theme.text
                        }
                        Text {
                            text: qsTr("%1 条最近指令").arg(root.workspaceVm ? root.workspaceVm.detailGcsCommands.length : 0)
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSm
                            color: Theme.text3
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: root.commandsExpanded ? "▲" : "▼"
                            font.pixelSize: Theme.fontXs
                            color: Theme.text2
                        }
                    }
                    background: Rectangle {
                        radius: Theme.radiusTag
                        color: cmdToggleBtn.hovered ? Theme.surfaceTint : "#00000000"
                    }
                }

                ColumnLayout {
                    visible: root.commandsExpanded
                    Layout.fillWidth: true
                    spacing: 6

                    Repeater {
                        model: root.workspaceVm ? root.workspaceVm.detailGcsCommands : []
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 8
                            Text {
                                text: modelData.command
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSm
                                font.weight: Font.Medium
                                color: Theme.text
                            }
                            Text {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                elide: Text.ElideRight
                                text: modelData.detail || modelData.sourceLabel
                                font.family: Theme.fontSans
                                font.pixelSize: Theme.fontSm
                                color: Theme.text2
                            }
                            StatusTag { text: modelData.status; tone: modelData.tone }
                            Text {
                                text: modelData.observedAt
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontXs
                                color: Theme.text3
                            }
                        }
                    }

                    Text {
                        visible: Boolean(root.workspaceVm && root.workspaceVm.detailGcsCommands.length === 0)
                        text: qsTr("暂未观测到地面站下发指令。")
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSm
                        color: Theme.text3
                    }
                }
            }
        }

        // Detail real-time logs: Tabs at <=1360px (1280x800), Dual-pane side-by-side at >1360px (1440/1600)
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            // Tab switcher bar visible ONLY in compact mode (<=1360px)
            RowLayout {
                id: tabBar
                objectName: "detailLogTabs"
                visible: root.compact
                spacing: 6

                Button {
                    id: routerTabBtn
                    objectName: "detailRouterTabButton"
                    readonly property bool active: !root.workspaceVm || root.workspaceVm.detailLogTab === "router"
                    text: qsTr("Router 日志")
                    onClicked: if (root.workspaceVm) root.workspaceVm.setDetailLogTab("router")
                    contentItem: Text {
                        text: routerTabBtn.text
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSm
                        font.weight: routerTabBtn.active ? Font.Medium : Font.Normal
                        color: routerTabBtn.active ? Theme.textOnPrimaryContainer : Theme.text2
                        leftPadding: 12; rightPadding: 12
                    }
                    background: Rectangle {
                        radius: Theme.radiusPill
                        color: routerTabBtn.active ? Theme.primaryContainer : Theme.surface
                        border.width: 1
                        border.color: routerTabBtn.active ? Theme.primary : Theme.divider
                    }
                }

                Button {
                    id: mavTabBtn
                    objectName: "detailMavproxyTabButton"
                    readonly property bool active: Boolean(root.workspaceVm && root.workspaceVm.detailLogTab === "mavproxy")
                    text: qsTr("MAVProxy 日志")
                    onClicked: if (root.workspaceVm) root.workspaceVm.setDetailLogTab("mavproxy")
                    contentItem: Text {
                        text: mavTabBtn.text
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSm
                        font.weight: mavTabBtn.active ? Font.Medium : Font.Normal
                        color: mavTabBtn.active ? Theme.textOnPrimaryContainer : Theme.text2
                        leftPadding: 12; rightPadding: 12
                    }
                    background: Rectangle {
                        radius: Theme.radiusPill
                        color: mavTabBtn.active ? Theme.primaryContainer : Theme.surface
                        border.width: 1
                        border.color: mavTabBtn.active ? Theme.primary : Theme.divider
                    }
                }
            }

            // Responsive container: single visible pane in compact mode, two equal panes side-by-side when wide
            RowLayout {
                objectName: "detailLogPanesRow"
                Layout.fillWidth: true
                Layout.preferredHeight: root.compact ? 250 : 300
                spacing: root.gapSize

                LogPane {
                    id: routerLogPane
                    objectName: "detailRouterLogPane"
                    visible: !root.compact || !root.workspaceVm || root.workspaceVm.detailLogTab === "router"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumWidth: 0
                    title: qsTr("MAVLink-Router systemd 服务日志")
                    subtitle: qsTr("systemd")
                    logModel: root.workspaceVm ? root.workspaceVm.detailRouterLogsModel : null
                }

                LogPane {
                    id: mavproxyLogPane
                    objectName: "detailMavproxyLogPane"
                    visible: !root.compact || Boolean(root.workspaceVm && root.workspaceVm.detailLogTab === "mavproxy")
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumWidth: 0
                    title: qsTr("MAVProxy 旁路会话日志")
                    subtitle: qsTr("session")
                    logModel: root.workspaceVm ? root.workspaceVm.detailMavproxyLogsModel : null
                }
            }
        }
    }
}
