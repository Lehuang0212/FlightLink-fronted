import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import theme

Rectangle {
    id: root
    objectName: "logPane"

    required property var logModel
    property string title: ""
    property string subtitle: ""
    property bool showGroupBadge: false

    radius: Theme.radiusPanel
    color: Theme.surface
    border.width: 1
    border.color: Theme.divider

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        // Header + local controls (pause scroll & local clear ONLY — no export button)
        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2
                visible: root.title.length > 0

                Text {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    elide: Text.ElideRight
                    text: root.title
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontMd
                    font.weight: Font.Medium
                    color: Theme.text
                }

                Text {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    elide: Text.ElideRight
                    text: root.subtitle.length > 0
                        ? qsTr("%1 · %2 行").arg(root.subtitle).arg(root.logModel ? root.logModel.count : 0)
                        : qsTr("%1 行").arg(root.logModel ? root.logModel.count : 0)
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontXs
                    color: Theme.text3
                }
            }

            Button {
                id: followBtn
                objectName: "logFollowButton"
                Layout.preferredHeight: 28
                text: root.logModel && root.logModel.follow ? qsTr("暂停滚动") : qsTr("继续滚动")
                onClicked: {
                    if (!root.logModel)
                        return
                    root.logModel.toggleFollow()
                    if (root.logModel.follow && logListView.count > 0)
                        logListView.positionViewAtEnd()
                }
                contentItem: Text {
                    text: followBtn.text
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontSm
                    color: root.logModel && !root.logModel.follow ? Theme.primary : Theme.text2
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 8
                    rightPadding: 8
                }
                background: Rectangle {
                    radius: Theme.radiusTag
                    color: root.logModel && !root.logModel.follow
                        ? Theme.primaryContainer
                        : (followBtn.hovered ? Theme.surfaceTint : "#00000000")
                    border.width: 1
                    border.color: Theme.divider
                }
            }

            Button {
                id: clearBtn
                objectName: "logClearButton"
                Layout.preferredHeight: 28
                text: qsTr("清屏")
                onClicked: if (root.logModel) root.logModel.clearLocalDisplay()
                contentItem: Text {
                    text: clearBtn.text
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontSm
                    color: Theme.text2
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: 8
                    rightPadding: 8
                }
                background: Rectangle {
                    radius: Theme.radiusTag
                    color: clearBtn.hovered ? Theme.surfaceTint : "#00000000"
                    border.width: 1
                    border.color: Theme.divider
                }
            }
        }

        // Log rows viewport (12px mono, 20px row height, 500-row incremental model)
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 140
            radius: Theme.radiusCard
            color: Theme.bg
            border.width: 1
            border.color: Theme.divider
            clip: true

            ListView {
                id: logListView
                objectName: "logListView"
                anchors.fill: parent
                anchors.margins: 6
                model: root.logModel
                reuseItems: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                onCountChanged: {
                    if (root.logModel && root.logModel.follow && count > 0)
                        Qt.callLater(logListView.positionViewAtEnd)
                }

                delegate: Rectangle {
                    id: rowRect
                    required property string timestamp
                    required property string groupName
                    required property string sourceShort
                    required property string level
                    required property string text

                    width: ListView.view ? ListView.view.width : 400
                    height: Theme.logRowHeight
                    color: rowRect.level === "ERROR" ? Theme.badRow : "#00000000"

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 4
                        anchors.rightMargin: 4
                        spacing: 8

                        Text {
                            Layout.preferredWidth: 84
                            text: rowRect.timestamp
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSm
                            color: Theme.text3
                        }

                        Text {
                            visible: root.showGroupBadge
                            Layout.preferredWidth: 58
                            elide: Text.ElideRight
                            text: rowRect.groupName
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontXs
                            color: Theme.text2
                        }

                        Text {
                            visible: root.showGroupBadge
                            Layout.preferredWidth: 24
                            text: rowRect.sourceShort
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontXs
                            font.weight: Font.Medium
                            color: Theme.primary
                        }

                        Text {
                            Layout.preferredWidth: 42
                            text: rowRect.level
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSm
                            font.weight: Font.Medium
                            color: rowRect.level === "ERROR"
                                ? Theme.bad
                                : rowRect.level === "WARN"
                                    ? Theme.warn
                                    : rowRect.level === "DEBUG"
                                        ? Theme.text3
                                        : Theme.ok
                        }

                        Text {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            elide: Text.ElideRight
                            text: rowRect.text
                            font.family: Theme.fontMono
                            font.pixelSize: Theme.fontSm
                            color: Theme.text
                        }
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: !root.logModel || root.logModel.count === 0
                text: qsTr("暂无新日志（仅保留最近 500 行实时缓冲）")
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontSm
                color: Theme.text3
            }

            // Floating "new logs" jump button when scroll is paused
            Button {
                id: jumpBtn
                objectName: "logJumpLatestButton"
                visible: Boolean(root.logModel && !root.logModel.follow && root.logModel.unreadCount > 0)
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 10
                text: qsTr("新日志 (%1) ↓").arg(root.logModel ? root.logModel.unreadCount : 0)
                onClicked: {
                    if (!root.logModel)
                        return
                    root.logModel.setFollow(true)
                    if (logListView.count > 0)
                        logListView.positionViewAtEnd()
                }
                contentItem: Text {
                    text: jumpBtn.text
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontSm
                    font.weight: Font.Medium
                    color: Theme.textOnPrimary
                    leftPadding: 10
                    rightPadding: 10
                }
                background: Rectangle {
                    radius: Theme.radiusPill
                    color: Theme.primary
                }
            }
        }
    }
}
