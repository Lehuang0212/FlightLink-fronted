import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import theme
import "../components"

Item {
    id: root
    objectName: "historyDetailPage"

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
            spacing: 10

            AppButton {
                objectName: "historyDetailBackButton"
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32
                compact: true
                variant: "secondary"
                text: "←"
                Accessible.name: qsTr("返回历史列表")
                onClicked: if (root.workspaceVm) root.workspaceVm.navigate("history")
            }

            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                elide: Text.ElideRight
                text: root.workspaceVm && root.workspaceVm.historyGroupMeta.nameSnapshot
                    ? root.workspaceVm.historyGroupMeta.nameSnapshot
                    : qsTr("历史切片")
                font.family: Theme.fontSans
                font.pixelSize: Theme.fontXl
                font.weight: Font.Medium
                color: Theme.text
            }

            StatusTag {
                visible: Boolean(root.workspaceVm && root.workspaceVm.historyGroupMeta.deleted)
                text: qsTr("已删除组 · 历史保留")
                tone: "idle"
            }

            Text {
                text: root.workspaceVm && root.workspaceVm.historyGroupMeta.dtuPort
                    ? qsTr("UDP %1 / %2 %3").arg(root.workspaceVm.historyGroupMeta.dtuPort).arg(root.workspaceVm.historyGroupMeta.gcsProtocol || "TCP").arg(root.workspaceVm.historyGroupMeta.gcsPort)
                    : ""
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontSm
                color: Theme.text2
            }
        }

        // Slices list (metadata first; lazy /entries loaded only on expand; NO regular download buttons!)
        ListView {
            objectName: "archiveSessionsListView"
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10
            model: root.workspaceVm ? root.workspaceVm.archiveSessionsModel : null
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                id: sliceCard
                required property string sessionId
                required property string statusLabel
                required property string closeReason
                required property string timeRange
                required property string expiresAt
                required property string sysidText
                required property bool expanded
                required property string localStatus
                required property string localStatusLabel
                required property string localStatusTone
                required property string localDetail
                required property bool showRetryAction
                required property string activeSource
                required property bool entriesLoading
                required property bool entriesHasMore
                required property string entriesText
                required property int entriesCount

                objectName: "historySliceCard_" + sliceCard.sessionId
                width: ListView.view ? ListView.view.width : 800
                height: sliceCol.implicitHeight + 24
                radius: Theme.radiusPanel
                color: Theme.surface
                border.width: 1
                border.color: sliceCard.localStatus === "failed" ? Theme.bad : Theme.divider

                ColumnLayout {
                    id: sliceCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 12
                    spacing: 8

                    // Metadata header row + independent retry button (ONLY when auto-save failed)
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 8

                        AppButton {
                            objectName: "toggleSliceBtn_" + sliceCard.sessionId
                            compact: true
                            variant: "ghost"
                            text: sliceCard.expanded ? "▼" : "▶"
                            Layout.preferredWidth: 28
                            Layout.preferredHeight: 28
                            onClicked: if (root.workspaceVm) root.workspaceVm.toggleHistorySlice(sliceCard.sessionId)
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 2

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Text {
                                    text: sliceCard.timeRange
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontBody
                                    font.weight: Font.Medium
                                    color: Theme.text
                                }
                                Text {
                                    text: sliceCard.sysidText
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontXs
                                    color: Theme.text3
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                elide: Text.ElideRight
                                text: qsTr("状态：%1 · 结束原因：%2 · 云端到期：%3").arg(sliceCard.statusLabel).arg(sliceCard.closeReason).arg(sliceCard.expiresAt)
                                font.family: Theme.fontSans
                                font.pixelSize: Theme.fontXs
                                color: Theme.text3
                            }
                        }

                        StatusTag {
                            objectName: "sliceLocalStatusTag_" + sliceCard.sessionId
                            text: sliceCard.localStatusLabel
                            tone: sliceCard.localStatusTone
                        }

                        // Strictly ONLY rendered when local auto-save failed after retries (NEVER for saved or source_gaps!)
                        Button {
                            id: retrySaveBtn
                            objectName: "retrySliceDownloadBtn_" + sliceCard.sessionId
                            visible: sliceCard.showRetryAction
                            text: qsTr("重新下载日志")
                            onClicked: if (root.workspaceVm) root.workspaceVm.requestManualArchiveRetry(sliceCard.sessionId)
                            contentItem: Text {
                                text: retrySaveBtn.text
                                font.family: Theme.fontSans
                                font.pixelSize: Theme.fontSm
                                font.weight: Font.Medium
                                color: Theme.textOnPrimary
                                leftPadding: 10; rightPadding: 10
                            }
                            background: Rectangle {
                                radius: Theme.radiusPill
                                color: Theme.bad
                            }
                        }
                    }

                    // Classified local save detail / source-gap explanation
                    Rectangle {
                        visible: sliceCard.localDetail.length > 0
                        Layout.fillWidth: true
                        Layout.preferredHeight: detailMsgLbl.implicitHeight + 12
                        radius: Theme.radiusTag
                        color: sliceCard.localStatus === "failed" ? Theme.badBg : Theme.warnBg

                        Text {
                            id: detailMsgLbl
                            anchors.fill: parent
                            anchors.margins: 6
                            wrapMode: Text.Wrap
                            text: sliceCard.localDetail
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSm
                            color: sliceCard.localStatus === "failed" ? Theme.bad : Theme.warn
                        }
                    }

                    // Expanded log body viewer (lazy loaded via /entries pagination)
                    ColumnLayout {
                        visible: sliceCard.expanded
                        Layout.fillWidth: true
                        spacing: 8

                        RowLayout {
                            spacing: 6
                            AppButton {
                                objectName: "sliceSourceRouterBtn_" + sliceCard.sessionId
                                compact: true
                                pill: true
                                active: sliceCard.activeSource === "router"
                                text: qsTr("Router 日志")
                                onClicked: if (root.workspaceVm) root.workspaceVm.selectHistorySliceSource(sliceCard.sessionId, "router")
                            }
                            AppButton {
                                objectName: "sliceSourceMavproxyBtn_" + sliceCard.sessionId
                                compact: true
                                pill: true
                                active: sliceCard.activeSource === "mavproxy"
                                text: qsTr("MAVProxy 日志")
                                onClicked: if (root.workspaceVm) root.workspaceVm.selectHistorySliceSource(sliceCard.sessionId, "mavproxy")
                            }
                            Text {
                                text: sliceCard.entriesLoading ? qsTr("正在加载正文…") : qsTr("已加载 %1 行").arg(sliceCard.entriesCount)
                                font.family: Theme.fontSans
                                font.pixelSize: Theme.fontXs
                                color: Theme.text3
                            }
                            Item { Layout.fillWidth: true }
                            AppButton {
                                visible: sliceCard.entriesHasMore && !sliceCard.entriesLoading
                                compact: true
                                variant: "subtle"
                                text: qsTr("加载更多")
                                onClicked: if (root.workspaceVm) root.workspaceVm.loadMoreSliceEntries(sliceCard.sessionId)
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 200
                            radius: Theme.radiusCard
                            color: Theme.bg
                            border.width: 1
                            border.color: Theme.divider
                            clip: true

                            ScrollView {
                                anchors.fill: parent
                                anchors.margins: 8
                                TextArea {
                                    readOnly: true
                                    selectByMouse: true
                                    text: sliceCard.entriesText
                                    font.family: Theme.fontMono
                                    font.pixelSize: Theme.fontSm
                                    color: Theme.text
                                    background: null
                                }
                            }
                        }
                    }
                }
            }
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            visible: Boolean(root.workspaceVm && root.workspaceVm.archiveSessionsModel.count === 0)
            text: qsTr("该端口组暂无已记录的飞控会话切片。")
            font.family: Theme.fontSans
            font.pixelSize: Theme.fontBody
            color: Theme.text3
        }
    }
}
