import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import theme

FocusScope {
    id: root
    objectName: "closeConfirmDialog"

    property bool open: false
    property bool authenticated: false

    signal cancelRequested()
    signal backgroundRequested()
    signal quitRequested()

    visible: root.open
    focus: visible

    Shortcut {
        sequences: [StandardKey.Cancel]
        context: Qt.WindowShortcut
        enabled: root.visible
        onActivated: root.cancelRequested()
    }

    // Modal scrim covering full window
    Rectangle {
        anchors.fill: parent
        color: Theme.scrim
        MouseArea {
            anchors.fill: parent
            onClicked: root.cancelRequested()
        }
    }

    Rectangle {
        id: dialogCard
        objectName: "closeConfirmCard"
        anchors.centerIn: parent
        width: Math.min(380, Math.max(300, root.width - 32))
        height: cardCol.implicitHeight + 40
        radius: Theme.radiusDialog
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider

        // Swallow clicks inside card so scrim doesn't close it
        MouseArea { anchors.fill: parent }

        ColumnLayout {
            id: cardCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 20
            spacing: 12

            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: qsTr("关闭 FlightLink Desktop")
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontLg
                font.weight: Font.Medium
                color: Theme.text
            }

            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                wrapMode: Text.Wrap
                text: root.authenticated
                    ? qsTr("请选择要执行的操作：\n• 后台运行：隐藏主窗口到任务栏小图标，后台继续自动归档与操作追踪，点击小图标可随时恢复界面。\n• 完全退出：停止所有后台任务并彻底关闭程序。")
                    : qsTr("请选择要执行的操作：\n• 后台运行：隐藏窗口到任务栏小图标，点击小图标可随时恢复界面。\n• 完全退出：彻底关闭程序。")
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontSm
                lineHeight: 1.4
                color: Theme.text2
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 4
                spacing: 8

                Item { Layout.fillWidth: true }

                AppButton {
                    objectName: "cancelCloseButton"
                    variant: "secondary"
                    pill: true
                    text: qsTr("取消")
                    onClicked: root.cancelRequested()
                }

                AppButton {
                    objectName: "minimizeToTrayButton"
                    variant: "primary"
                    pill: true
                    text: qsTr("后台运行")
                    onClicked: root.backgroundRequested()
                }

                AppButton {
                    objectName: "confirmQuitButton"
                    variant: "dangerFilled"
                    pill: true
                    text: qsTr("完全退出")
                    onClicked: root.quitRequested()
                }
            }
        }
    }
}
