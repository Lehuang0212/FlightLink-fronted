import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import theme

FocusScope {
    id: root
    objectName: "deleteGroupDialog"

    required property var opsVm
    visible: Boolean(opsVm && opsVm.deleteDialogOpen)
    focus: visible

    Shortcut {
        sequences: [StandardKey.Cancel]
        context: Qt.WindowShortcut
        enabled: root.visible
        onActivated: if (root.opsVm) root.opsVm.closeDeleteDialog()
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.scrim
        MouseArea {
            anchors.fill: parent
            onClicked: if (root.opsVm) root.opsVm.closeDeleteDialog()
        }
    }

    Rectangle {
        anchors.centerIn: parent
        width: 420
        height: delCol.implicitHeight + 48
        radius: Theme.radiusDialog
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider

        MouseArea { anchors.fill: parent }

        ColumnLayout {
            id: delCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 24
            spacing: 12

            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: qsTr("确认删除端口组 “%1”？").arg(root.opsVm ? root.opsVm.deleteGroupName : "")
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontLg
                font.weight: Font.Medium
                color: Theme.text
            }

            // Contract mandatory notice: history & local files are retained!
            Text {
                objectName: "deleteHistoryNotice"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                wrapMode: Text.Wrap
                text: qsTr("删除后将停止该组 Router、撤回自有云安全组规则并释放端口。未到期的历史归档日志仍将保留，且不会删除本机已保存副本；若后续使用同名同端口重建，将以新的 group_id 独立展示。")
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontSm
                color: Theme.text2
            }

            Rectangle {
                visible: Boolean(root.opsVm && root.opsVm.deleteError.length > 0)
                Layout.fillWidth: true
                Layout.preferredHeight: delErrLbl.implicitHeight + 14
                radius: Theme.radiusTag
                color: Theme.badBg

                Text {
                    id: delErrLbl
                    anchors.fill: parent
                    anchors.margins: 7
                    wrapMode: Text.Wrap
                    text: root.opsVm ? root.opsVm.deleteError : ""
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontSm
                    color: Theme.bad
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item { Layout.fillWidth: true }

                Button {
                    objectName: "cancelDeleteButton"
                    enabled: !root.opsVm || !root.opsVm.deleteSubmitting
                    text: qsTr("取消")
                    onClicked: if (root.opsVm) root.opsVm.closeDeleteDialog()
                }

                Button {
                    id: confirmDelBtn
                    objectName: "confirmDeleteButton"
                    enabled: !root.opsVm || !root.opsVm.deleteSubmitting
                    text: root.opsVm && root.opsVm.deleteSubmitting ? qsTr("提交中…") : qsTr("确认删除")
                    onClicked: if (root.opsVm) root.opsVm.confirmDeleteGroup()
                    contentItem: Text {
                        text: confirmDelBtn.text
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSm
                        font.weight: Font.Medium
                        color: Theme.textOnPrimary
                        leftPadding: 14; rightPadding: 14
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: Theme.radiusPill
                        color: confirmDelBtn.enabled ? Theme.bad : Theme.outline
                    }
                }
            }
        }
    }
}
