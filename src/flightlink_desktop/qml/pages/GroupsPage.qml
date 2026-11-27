import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import theme
import "../components"

Item {
    id: root
    objectName: "groupsPage"

    required property var workspaceVm
    required property var sessionVm
    property bool compact: false

    signal createGroupRequested()
    signal editGroupRequested(string groupId)
    signal deleteGroupRequested(string groupId, string groupName)

    readonly property int marginSize: compact ? Theme.contentMarginCompact : Theme.contentMarginWide
    readonly property int gapSize: compact ? Theme.columnGapCompact : Theme.columnGapWide

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.marginSize
        spacing: root.gapSize

        // Header + search + filter pills
        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 12

            Text {
                text: qsTr("端口组")
                font.family: Theme.fontSans
                font.pixelSize: Theme.font2xl
                font.weight: Font.Medium
                color: Theme.text
            }

            Text {
                text: root.workspaceVm ? qsTr("%1 / %2 组").arg(root.workspaceVm.groupsTotal).arg(root.workspaceVm.maxGroups) : ""
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontSm
                color: Theme.text3
            }

            Item { Layout.fillWidth: true }

            TextField {
                id: filterSearchInput
                objectName: "groupsSearchInput"
                Layout.preferredWidth: 220
                Layout.preferredHeight: Theme.controlHeight
                placeholderText: qsTr("按名称、端口或 SYSID 筛选")
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontSm
                color: Theme.text
                text: root.workspaceVm ? root.workspaceVm.groupQuery : ""
                onTextEdited: if (root.workspaceVm) root.workspaceVm.setGroupsFilter(text, root.workspaceVm.groupFilter)
                background: Rectangle {
                    radius: Theme.radiusPill
                    color: Theme.field
                    border.width: filterSearchInput.activeFocus ? 2 : 0
                    border.color: Theme.primary
                }
            }

            RowLayout {
                spacing: 4
                Repeater {
                    model: [
                        { key: "all", label: qsTr("全部") },
                        { key: "online", label: qsTr("在线") },
                        { key: "idle", label: qsTr("待机") },
                        { key: "attention", label: qsTr("需关注") }
                    ]
                    delegate: Button {
                        id: segBtn
                        required property var modelData
                        readonly property bool active: Boolean(root.workspaceVm && root.workspaceVm.groupFilter === modelData.key)
                        Layout.preferredHeight: 32
                        text: modelData.label
                        onClicked: if (root.workspaceVm) root.workspaceVm.setGroupsFilter(filterSearchInput.text, modelData.key)
                        contentItem: Text {
                            text: segBtn.text
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSm
                            font.weight: segBtn.active ? Font.Medium : Font.Normal
                            color: segBtn.active ? Theme.textOnPrimaryContainer : Theme.text2
                            leftPadding: 12
                            rightPadding: 12
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            radius: Theme.radiusPill
                            color: segBtn.active ? Theme.primaryContainer : (segBtn.hovered ? Theme.surfaceTint : Theme.surface)
                            border.width: 1
                            border.color: segBtn.active ? Theme.primary : Theme.divider
                        }
                    }
                }
            }
        }

        // Port groups table panel
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

                // Table header
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    color: Theme.surfaceTint

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 16
                        anchors.rightMargin: 16
                        spacing: 12

                        Text { Layout.fillWidth: true; Layout.minimumWidth: 120; text: qsTr("端口组"); font.family: Theme.fontSans; font.pixelSize: Theme.fontSm; font.weight: Font.Medium; color: Theme.text2 }
                        Text { Layout.preferredWidth: 170; text: qsTr("双端口（DTU / GCS）"); font.family: Theme.fontSans; font.pixelSize: Theme.fontSm; font.weight: Font.Medium; color: Theme.text2 }
                        Text { Layout.preferredWidth: 96; text: qsTr("状态"); font.family: Theme.fontSans; font.pixelSize: Theme.fontSm; font.weight: Font.Medium; color: Theme.text2 }
                        Text { Layout.preferredWidth: 96; text: qsTr("MAVProxy"); font.family: Theme.fontSans; font.pixelSize: Theme.fontSm; font.weight: Font.Medium; color: Theme.text2 }
                        Text { Layout.preferredWidth: 96; text: qsTr("安全组"); font.family: Theme.fontSans; font.pixelSize: Theme.fontSm; font.weight: Font.Medium; color: Theme.text2 }
                        Text { Layout.preferredWidth: 180; horizontalAlignment: Text.AlignRight; text: qsTr("操作"); font.family: Theme.fontSans; font.pixelSize: Theme.fontSm; font.weight: Font.Medium; color: Theme.text2 }
                    }
                }

                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

                ListView {
                    id: groupsListView
                    objectName: "groupsListView"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: root.workspaceVm ? root.workspaceVm.groupListModel : null
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    delegate: Rectangle {
                        id: gRow
                        required property string groupId
                        required property string name
                        required property int dtuPort
                        required property string gcsProtocol
                        required property int gcsPort
                        required property string lifecycleLabel
                        required property string lifecycleTone
                        required property string sysidText
                        required property string mavproxyLabel
                        required property string mavproxyTone
                        required property bool mavproxyStale
                        required property string sgLabel
                        required property string sgTone
                        required property bool sgStale
                        required property bool stale

                        width: ListView.view ? ListView.view.width : 800
                        height: 54
                        color: rowHover.hovered ? Theme.surfaceTint : Theme.surface

                        HoverHandler { id: rowHover }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 16
                            anchors.rightMargin: 16
                            spacing: 12

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 120
                                spacing: 2
                                Text {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    elide: Text.ElideRight
                                    text: gRow.name
                                    font.family: Theme.fontSans
                                    font.pixelSize: Theme.fontMd
                                    font.weight: Font.Medium
                                    color: Theme.text
                                }
                                Text {
                                    text: gRow.stale ? qsTr("%1 · 观测过期").arg(gRow.sysidText) : gRow.sysidText
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontXs
                                    color: gRow.stale ? Theme.warn : Theme.text3
                                }
                            }

                            Text {
                                Layout.preferredWidth: 170
                                text: qsTr("UDP %1 / %2 %3").arg(gRow.dtuPort).arg(gRow.gcsProtocol).arg(gRow.gcsPort)
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSm
                                color: Theme.text
                            }

                            Item {
                                Layout.preferredWidth: 96
                                Layout.preferredHeight: Theme.tagHeight
                                StatusTag { text: gRow.lifecycleLabel; tone: gRow.lifecycleTone }
                            }

                            Item {
                                Layout.preferredWidth: 96
                                Layout.preferredHeight: Theme.tagHeight
                                StatusTag { text: gRow.mavproxyStale ? qsTr("%1(过期)").arg(gRow.mavproxyLabel) : gRow.mavproxyLabel; tone: gRow.mavproxyStale ? "warn" : gRow.mavproxyTone }
                            }

                            Item {
                                Layout.preferredWidth: 96
                                Layout.preferredHeight: Theme.tagHeight
                                StatusTag { text: gRow.sgStale ? qsTr("%1(过期)").arg(gRow.sgLabel) : gRow.sgLabel; tone: gRow.sgStale ? "warn" : gRow.sgTone }
                            }

                            RowLayout {
                                Layout.preferredWidth: 180
                                spacing: 6
                                Item { Layout.fillWidth: true }

                                Button {
                                    objectName: "openDetailBtn_" + gRow.groupId
                                    text: qsTr("详情")
                                    onClicked: if (root.workspaceVm) root.workspaceVm.openGroupDetail(gRow.groupId)
                                }

                                Button {
                                    visible: Boolean(root.sessionVm && root.sessionVm.isAdmin)
                                    text: qsTr("编辑")
                                    onClicked: root.editGroupRequested(gRow.groupId)
                                }

                                Button {
                                    visible: Boolean(root.sessionVm && root.sessionVm.isAdmin)
                                    text: qsTr("删除")
                                    onClicked: root.deleteGroupRequested(gRow.groupId, gRow.name)
                                }
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
                    visible: Boolean(root.workspaceVm && root.workspaceVm.groupListModel.count === 0)
                    text: qsTr("当前筛选条件下没有端口组。")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontBody
                    color: Theme.text3
                }
            }
        }
    }
}
