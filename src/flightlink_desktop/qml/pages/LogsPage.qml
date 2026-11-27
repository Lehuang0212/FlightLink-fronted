import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import theme
import "../components"

Item {
    id: root
    objectName: "logsPage"

    required property var workspaceVm
    property bool compact: false

    readonly property int marginSize: compact ? Theme.contentMarginCompact : Theme.contentMarginWide
    readonly property int gapSize: compact ? Theme.columnGapCompact : Theme.columnGapWide

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.marginSize
        spacing: root.gapSize

        // Header
        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 12

            Text {
                text: qsTr("实时日志")
                font.family: Theme.fontSans
                font.pixelSize: Theme.font2xl
                font.weight: Font.Medium
                color: Theme.text
            }

            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                elide: Text.ElideRight
                text: root.workspaceVm && root.workspaceVm.archiveLocalRoot
                    ? qsTr("本机自动保存目录：%1（切片封存后自动落盘，云端保留 7 天）").arg(root.workspaceVm.archiveLocalRoot)
                    : qsTr("切片封存后自动保存到本机文档目录，云端保留 7 天")
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontSm
                color: Theme.text3
            }
        }

        // Filter bar (NO export button in regular UI)
        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 8

            RowLayout {
                spacing: 4
                Repeater {
                    model: [
                        { key: "all", label: qsTr("全部来源") },
                        { key: "router", label: qsTr("Router") },
                        { key: "mavproxy", label: qsTr("MAVProxy") }
                    ]
                    delegate: Button {
                        id: srcBtn
                        required property var modelData
                        readonly property bool active: Boolean(root.workspaceVm && root.workspaceVm.logsSourceFilter === modelData.key)
                        text: modelData.label
                        onClicked: if (root.workspaceVm) root.workspaceVm.setLiveLogsFilter(
                            root.workspaceVm.logsGroupFilter,
                            modelData.key,
                            root.workspaceVm.logsLevelFilter,
                            logsSearchField.text
                        )
                        contentItem: Text {
                            text: srcBtn.text
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSm
                            color: srcBtn.active ? Theme.textOnPrimaryContainer : Theme.text2
                            leftPadding: 10; rightPadding: 10
                        }
                        background: Rectangle {
                            radius: Theme.radiusPill
                            color: srcBtn.active ? Theme.primaryContainer : Theme.surface
                            border.width: 1
                            border.color: srcBtn.active ? Theme.primary : Theme.divider
                        }
                    }
                }
            }

            AppComboBox {
                id: levelCombo
                objectName: "liveLogsLevelCombo"
                Layout.preferredWidth: 116
                Layout.preferredHeight: 32
                model: ["all", "INFO", "WARN", "ERROR", "DEBUG"]
                currentIndex: Math.max(0, model.indexOf(root.workspaceVm ? root.workspaceVm.logsLevelFilter : "all"))
                onActivated: if (root.workspaceVm) root.workspaceVm.setLiveLogsFilter(
                    root.workspaceVm.logsGroupFilter,
                    root.workspaceVm.logsSourceFilter,
                    currentText,
                    logsSearchField.text
                )
            }

            TextField {
                id: logsSearchField
                objectName: "liveLogsSearchInput"
                Layout.fillWidth: true
                Layout.minimumWidth: 120
                Layout.preferredWidth: 0
                Layout.preferredHeight: 32
                placeholderText: qsTr("按关键词筛选日志内容…")
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontSm
                color: Theme.text
                text: root.workspaceVm ? root.workspaceVm.logsQueryFilter : ""
                onTextEdited: if (root.workspaceVm) root.workspaceVm.setLiveLogsFilter(
                    root.workspaceVm.logsGroupFilter,
                    root.workspaceVm.logsSourceFilter,
                    root.workspaceVm.logsLevelFilter,
                    text
                )
                background: Rectangle {
                    radius: Theme.radiusField
                    color: Theme.field
                    border.width: logsSearchField.activeFocus ? 2 : 0
                    border.color: Theme.primary
                }
            }
        }

        // Combined 500-row incremental log pane
        LogPane {
            objectName: "combinedLogPane"
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: qsTr("合并实时日志")
            subtitle: qsTr("500 行增量环形缓冲")
            showGroupBadge: true
            logModel: root.workspaceVm ? root.workspaceVm.liveLogsModel : null
        }
    }
}
