import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import theme
import "../components"

Item {
    id: root
    objectName: "historyPage"

    required property var workspaceVm
    property bool compact: false

    readonly property int marginSize: compact ? Theme.contentMarginCompact : Theme.contentMarginWide
    readonly property int gapSize: compact ? Theme.columnGapCompact : Theme.columnGapWide

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.marginSize
        spacing: root.gapSize

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 12

            Text {
                text: qsTr("历史日志")
                font.family: Theme.fontSans
                font.pixelSize: Theme.font2xl
                font.weight: Font.Medium
                color: Theme.text
            }

            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                elide: Text.ElideRight
                text: qsTr("按端口组与飞控会话切片归档 · 切片封存后自动保存到本机，云端保留 7 天，云端到期或删组均不删除本地副本")
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontSm
                color: Theme.text3
            }

            AppButton {
                objectName: "refreshHistoryGroupsButton"
                variant: "secondary"
                text: qsTr("刷新")
                onClicked: if (root.workspaceVm) root.workspaceVm.loadArchiveGroups()
            }
        }

        // Retention gap notice (shown when 410 CURSOR_EXPIRED detected)
        Rectangle {
            visible: Boolean(root.workspaceVm && root.workspaceVm.archiveRetentionGapNote.length > 0)
            Layout.fillWidth: true
            Layout.preferredHeight: gapLbl.implicitHeight + 16
            radius: Theme.radiusCard
            color: Theme.warnBg

            Text {
                id: gapLbl
                anchors.fill: parent
                anchors.margins: 8
                wrapMode: Text.Wrap
                text: root.workspaceVm ? root.workspaceVm.archiveRetentionGapNote : ""
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontSm
                color: Theme.warn
            }
        }

        // Local save path hint (read-only informational line, no save dialog or toggle)
        Text {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            elide: Text.ElideRight
            text: root.workspaceVm && root.workspaceVm.archiveLocalRoot
                ? qsTr("本机自动保存位置：%1").arg(root.workspaceVm.archiveLocalRoot)
                : qsTr("本机自动保存位置：文档\\FlightLink\\Logs")
            font.family: Theme.fontMono
            font.pixelSize: Theme.fontSm
            color: Theme.text2
        }

        // Archive groups table (preserves deleted groups & empty active groups, distinct by group_id)
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.radiusPanel
            color: Theme.surface
            border.width: 1
            border.color: Theme.divider
            clip: true

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    color: Theme.surfaceTint

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 16
                        anchors.rightMargin: 16
                        spacing: 12

                        Text { Layout.fillWidth: true; Layout.minimumWidth: 140; text: qsTr("端口组快照"); font.family: Theme.fontSans; font.pixelSize: Theme.fontSm; font.weight: Font.Medium; color: Theme.text2 }
                        Text { Layout.preferredWidth: 165; text: qsTr("端口快照"); font.family: Theme.fontSans; font.pixelSize: Theme.fontSm; font.weight: Font.Medium; color: Theme.text2 }
                        Text { Layout.preferredWidth: 96; text: qsTr("已封存切片"); font.family: Theme.fontSans; font.pixelSize: Theme.fontSm; font.weight: Font.Medium; color: Theme.text2 }
                        Text { Layout.preferredWidth: 84; text: qsTr("最近状态"); font.family: Theme.fontSans; font.pixelSize: Theme.fontSm; font.weight: Font.Medium; color: Theme.text2 }
                        Text { Layout.preferredWidth: 220; text: qsTr("最近切片时间"); font.family: Theme.fontSans; font.pixelSize: Theme.fontSm; font.weight: Font.Medium; color: Theme.text2 }
                        Text { Layout.preferredWidth: 88; horizontalAlignment: Text.AlignRight; text: qsTr("查看"); font.family: Theme.fontSans; font.pixelSize: Theme.fontSm; font.weight: Font.Medium; color: Theme.text2 }
                    }
                }

                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

                ListView {
                    objectName: "archiveGroupsListView"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: root.workspaceVm ? root.workspaceVm.archiveGroupsModel : null
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    delegate: Rectangle {
                        id: aRow
                        required property string groupId
                        required property string nameSnapshot
                        required property int dtuPort
                        required property string gcsProtocol
                        required property int gcsPort
                        required property bool deleted
                        required property int sealedSessionCount
                        required property string latestRange
                        required property string latestStatus

                        width: ListView.view ? ListView.view.width : 800
                        height: 52
                        color: Theme.surface

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 16
                            anchors.rightMargin: 16
                            spacing: 12

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 140
                                spacing: 6

                                Text {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    elide: Text.ElideRight
                                    text: aRow.nameSnapshot
                                    font.family: Theme.fontSans
                                    font.pixelSize: Theme.fontMd
                                    font.weight: Font.Medium
                                    color: Theme.text
                                }

                                StatusTag {
                                    visible: aRow.deleted
                                    text: qsTr("已删除")
                                    tone: "idle"
                                }
                            }

                            Text {
                                Layout.preferredWidth: 165
                                text: qsTr("UDP %1 / %2 %3").arg(aRow.dtuPort).arg(aRow.gcsProtocol).arg(aRow.gcsPort)
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSm
                                color: Theme.text
                            }

                            Text {
                                Layout.preferredWidth: 96
                                text: qsTr("%1 条").arg(aRow.sealedSessionCount)
                                font.family: Theme.fontSans
                                font.pixelSize: Theme.fontSm
                                color: Theme.text
                            }

                            Text {
                                Layout.preferredWidth: 84
                                text: aRow.latestStatus
                                font.family: Theme.fontSans
                                font.pixelSize: Theme.fontSm
                                color: Theme.text2
                            }

                            Text {
                                Layout.preferredWidth: 220
                                elide: Text.ElideRight
                                text: aRow.latestRange
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontXs
                                color: Theme.text2
                            }

                            AppButton {
                                objectName: "openHistoryGroupBtn_" + aRow.groupId
                                Layout.preferredWidth: 88
                                compact: true
                                variant: "subtle"
                                text: qsTr("查看历史")
                                onClicked: if (root.workspaceVm) root.workspaceVm.openHistoryGroup(aRow.groupId, "")
                            }
                        }

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: Theme.divider
                        }
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.margins: 32
                    visible: Boolean(root.workspaceVm && root.workspaceVm.archiveGroupsModel.count === 0)
                    text: qsTr("还没有端口组或未到期的历史归档记录。")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontBody
                    color: Theme.text3
                }
            }
        }
    }
}
