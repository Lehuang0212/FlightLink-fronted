import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import theme
import "../components"

Flickable {
    id: root
    objectName: "overviewPage"

    required property var workspaceVm
    required property var sessionVm
    property bool compact: false

    contentWidth: width
    contentHeight: mainCol.implicitHeight + (compact ? 40 : 48)
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

    readonly property int marginSize: compact ? Theme.contentMarginCompact : Theme.contentMarginWide
    readonly property int gapSize: compact ? Theme.columnGapCompact : Theme.columnGapWide

    ColumnLayout {
        id: mainCol
        x: root.marginSize
        y: root.marginSize
        width: Math.max(0, root.width - root.marginSize * 2)
        spacing: root.gapSize

        // Header row
        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 12

            Text {
                text: qsTr("总览")
                font.family: Theme.fontSans
                font.pixelSize: Theme.font2xl
                font.weight: Font.Medium
                color: Theme.text
            }

            StatusTag {
                visible: Boolean(root.workspaceVm && root.workspaceVm.overviewStale)
                text: qsTr("观测已过期 · %1").arg(root.workspaceVm ? root.workspaceVm.overviewObservedAt : "—")
                tone: "warn"
            }

            Item { Layout.fillWidth: true }

            Text {
                text: root.workspaceVm
                    ? qsTr("端口组 %1 / %2 · 在线飞控 %3").arg(root.workspaceVm.overviewMetrics.group_count || 0).arg(root.workspaceVm.overviewMetrics.max_groups || 5).arg(root.workspaceVm.overviewMetrics.online_fc_count || 0)
                    : ""
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontSm
                color: Theme.text2
            }
        }

        // Host 3 components & disk quota bar
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: compCol.implicitHeight + 28
            radius: Theme.radiusPanel
            color: Theme.surface
            border.width: 1
            border.color: Theme.divider

            ColumnLayout {
                id: compCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 14
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 10

                    Text {
                        text: qsTr("ECS 三组件状态与归档磁盘水位")
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontMd
                        font.weight: Font.Medium
                        color: Theme.text
                    }

                    AppButton {
                        objectName: "overviewInstanceId"
                        visible: Boolean(root.sessionVm && root.sessionVm.ecsInstanceId.length > 0)
                        compact: true
                        variant: "subtle"
                        text: root.sessionVm ? qsTr("实例 %1").arg(root.sessionVm.ecsInstanceId) : ""
                        ToolTip.visible: hovered
                        ToolTip.text: qsTr("点击复制 ECS 实例 ID")
                        onClicked: {
                            if (root.sessionVm && root.sessionVm.ecsInstanceId) {
                                root.sessionVm.copyToClipboard(root.sessionVm.ecsInstanceId)
                                if (root.workspaceVm)
                                    root.workspaceVm.showToast(qsTr("已复制实例 ID：%1").arg(root.sessionVm.ecsInstanceId), "info")
                            }
                        }
                    }

                    Item { Layout.fillWidth: true }

                    StatusTag {
                        text: root.workspaceVm && root.workspaceVm.diskStatus === "ok"
                            ? qsTr("磁盘正常")
                            : root.workspaceVm && root.workspaceVm.diskStatus === "warning"
                                ? qsTr("磁盘预警")
                                : qsTr("配额降级")
                        tone: root.workspaceVm && root.workspaceVm.diskStatus === "ok"
                            ? "ok"
                            : root.workspaceVm && root.workspaceVm.diskStatus === "warning"
                                ? "warn"
                                : "bad"
                    }

                    Text {
                        text: root.workspaceVm ? root.workspaceVm.diskSummary : "—"
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.fontSm
                        color: Theme.text2
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: root.gapSize

                    Repeater {
                        model: root.workspaceVm ? root.workspaceVm.components : []

                        delegate: Rectangle {
                            id: compCard
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.preferredHeight: 58
                            radius: Theme.radiusCard
                            color: Theme.surfaceTint

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 8

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: 2
                                    Text {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        elide: Text.ElideRight
                                        text: compCard.modelData.name
                                        font.family: Theme.fontMono
                                        font.pixelSize: Theme.fontBody
                                        font.weight: Font.Medium
                                        color: Theme.text
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        elide: Text.ElideRight
                                        text: compCard.modelData.stale
                                            ? qsTr("观测过期 · %1").arg(compCard.modelData.observedAt)
                                            : qsTr("观测于 %1").arg(compCard.modelData.observedAt)
                                        font.family: Theme.fontSans
                                        font.pixelSize: Theme.fontXs
                                        color: compCard.modelData.stale ? Theme.warn : Theme.text3
                                    }
                                }

                                StatusTag {
                                    text: compCard.modelData.statusLabel
                                    tone: compCard.modelData.tone
                                }

                                StatusTag {
                                    visible: Boolean(compCard.modelData.stale)
                                    text: qsTr("已过期")
                                    tone: "warn"
                                }
                            }
                        }
                    }
                }
            }
        }

        // Configured port groups link cards (max 5 groups)
        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: root.gapSize
            rowSpacing: root.gapSize

            Repeater {
                model: root.workspaceVm ? root.workspaceVm.overviewGroupsModel : null

                delegate: Rectangle {
                    id: groupCard
                    required property string groupId
                    required property string name
                    required property int dtuPort
                    required property string gcsProtocol
                    required property int gcsPort
                    required property string lifecycleState
                    required property string lifecycleLabel
                    required property string lifecycleTone
                    required property string fcState
                    required property string gcsState
                    required property string dtuPeer
                    required property string gcsPeer
                    required property string sysidText
                    required property string routerState
                    required property string routerLabel
                    required property string routerTone
                    required property string mavproxyLabel
                    required property string mavproxyTone
                    required property string sgLabel
                    required property string sgTone
                    required property bool stale
                    required property string observedAt

                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredHeight: 184
                    radius: Theme.radiusPanel
                    color: Theme.surface
                    border.width: 1
                    border.color: cardTap.pressed ? Theme.primary : Theme.divider

                    TapHandler {
                        id: cardTap
                        onTapped: if (root.workspaceVm) root.workspaceVm.openGroupDetail(groupCard.groupId)
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 10

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 8

                            Text {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                elide: Text.ElideRight
                                text: groupCard.name
                                font.family: Theme.fontSans
                                font.pixelSize: Theme.fontLg
                                font.weight: Font.Medium
                                color: Theme.text
                            }

                            Text {
                                text: groupCard.sysidText
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontXs
                                color: Theme.text3
                            }

                            StatusTag {
                                text: groupCard.lifecycleLabel
                                tone: groupCard.lifecycleTone
                            }

                            StatusTag {
                                visible: groupCard.stale
                                text: qsTr("过期")
                                tone: "warn"
                            }
                        }

                        LinkWireCard {
                            Layout.fillWidth: true
                            dtuPort: groupCard.dtuPort
                            gcsProtocol: groupCard.gcsProtocol
                            gcsPort: groupCard.gcsPort
                            dtuPeer: groupCard.dtuPeer
                            gcsPeer: groupCard.gcsPeer
                            fcOnline: groupCard.fcState === "online"
                            routerRunning: groupCard.routerState === "running"
                            routerStatusText: groupCard.routerLabel
                            gcsConnected: groupCard.gcsState === "connected"
                            liveActive: Boolean(root.workspaceVm && root.workspaceVm.liveUpdatesEnabled)
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            StatusTag { text: qsTr("Router %1").arg(groupCard.routerLabel); tone: groupCard.routerTone }
                            StatusTag { text: qsTr("MAVProxy %1").arg(groupCard.mavproxyLabel); tone: groupCard.mavproxyTone }
                            StatusTag { text: qsTr("安全组 %1").arg(groupCard.sgLabel); tone: groupCard.sgTone }
                            Item { Layout.fillWidth: true }
                            Text {
                                text: groupCard.observedAt
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontXs
                                color: Theme.text3
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 120
            visible: Boolean(root.workspaceVm && root.workspaceVm.overviewGroupsModel.count === 0)
            radius: Theme.radiusPanel
            color: Theme.surface
            border.width: 1
            border.color: Theme.divider

            Text {
                anchors.centerIn: parent
                text: qsTr("当前还没有已配置的端口组。管理员可点击左侧「新建端口组」创建（最多 5 组）。")
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontBody
                color: Theme.text3
            }
        }
    }
}
