import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import theme

FocusScope {
    id: root
    objectName: "groupFormDialog"

    required property var opsVm
    visible: Boolean(opsVm && opsVm.dialogOpen)
    focus: visible

    Shortcut {
        sequences: [StandardKey.Cancel]
        context: Qt.WindowShortcut
        enabled: root.visible
        onActivated: if (root.opsVm) root.opsVm.requestCloseDialog()
    }

    // Modal backdrop blocking background clicks
    Rectangle {
        anchors.fill: parent
        color: Theme.scrim

        MouseArea {
            anchors.fill: parent
            onClicked: if (root.opsVm) root.opsVm.requestCloseDialog()
        }
    }

    // Dialog card (only 2 ports: DTU fixed UDP + GCS TCP/UDP; NO SYSID)
    Rectangle {
        id: dialogCard
        objectName: "groupFormCard"
        anchors.centerIn: parent
        width: 460
        height: Math.min(parent.height - 48, formCol.implicitHeight + 48)
        radius: Theme.radiusDialog
        color: Theme.surface
        border.width: 1
        border.color: Theme.divider

        MouseArea { anchors.fill: parent } // Keep inside clicks from closing modal

        Flickable {
            anchors.fill: parent
            anchors.margins: 24
            contentWidth: width
            contentHeight: formCol.implicitHeight
            clip: true

            ColumnLayout {
                id: formCol
                width: parent.width
                spacing: 12

                Text {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    text: root.opsVm && root.opsVm.dialogMode === "edit"
                        ? qsTr("编辑端口组（版本 v%1）").arg(root.opsVm.dialogConfigVersion)
                        : qsTr("新建端口组")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontXl
                    font.weight: Font.Medium
                    color: Theme.text
                }

                Text {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    wrapMode: Text.Wrap
                    text: qsTr("每组仅配置双端口：DTU 侧固定 UDP，GCS 侧支持 TCP/UDP。SYSID 由真实飞控消息观测，无需手工分配。")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontSm
                    color: Theme.text3
                }

                // 412 reloaded version banner (draft preserved)
                Rectangle {
                    objectName: "versionReloadedBanner"
                    visible: Boolean(root.opsVm && root.opsVm.versionReloadedNotice.length > 0)
                    Layout.fillWidth: true
                    Layout.preferredHeight: verLbl.implicitHeight + 14
                    radius: Theme.radiusTag
                    color: Theme.warnBg

                    Text {
                        id: verLbl
                        anchors.fill: parent
                        anchors.margins: 7
                        wrapMode: Text.Wrap
                        text: root.opsVm ? root.opsVm.versionReloadedNotice : ""
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSm
                        color: Theme.warn
                    }
                }

                // Name field
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text { text: qsTr("端口组名称"); font.family: Theme.fontSans; font.pixelSize: Theme.fontSm; color: Theme.text2 }
                    TextField {
                        id: nameField
                        objectName: "groupNameInput"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredWidth: 0
                        Layout.preferredHeight: Theme.controlHeight
                        placeholderText: qsTr("例如：一号机")
                        text: root.opsVm ? root.opsVm.draftName : ""
                        onTextEdited: if (root.opsVm) root.opsVm.updateDraft(text, dtuField.text, gcsProtoCombo.currentText, gcsField.text)
                        background: Rectangle {
                            radius: Theme.radiusField
                            color: Theme.field
                            border.width: (root.opsVm && root.opsVm.fieldErrors.name) || nameField.activeFocus ? 2 : 0
                            border.color: (root.opsVm && root.opsVm.fieldErrors.name) ? Theme.bad : Theme.primary
                        }
                    }
                    Text {
                        visible: Boolean(root.opsVm && root.opsVm.fieldErrors.name)
                        text: root.opsVm && root.opsVm.fieldErrors.name ? root.opsVm.fieldErrors.name : ""
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontXs
                        color: Theme.bad
                    }
                }

                // DTU Port (fixed UDP)
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text { text: qsTr("DTU 端口（固定 UDP）"); font.family: Theme.fontSans; font.pixelSize: Theme.fontSm; color: Theme.text2 }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Rectangle {
                            Layout.preferredWidth: 64
                            Layout.preferredHeight: Theme.controlHeight
                            radius: Theme.radiusField
                            color: Theme.idleBg
                            Text {
                                anchors.centerIn: parent
                                text: "UDP"
                                font.family: Theme.fontMono
                                font.pixelSize: Theme.fontSm
                                font.weight: Font.Medium
                                color: Theme.text2
                            }
                        }
                        TextField {
                            id: dtuField
                            objectName: "dtuPortInput"
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.preferredWidth: 0
                            Layout.preferredHeight: Theme.controlHeight
                            placeholderText: qsTr("1–65535，例如 5760")
                            font.family: Theme.fontMono
                            text: root.opsVm ? root.opsVm.draftDtuPort : ""
                            onTextEdited: if (root.opsVm) root.opsVm.updateDraft(nameField.text, text, gcsProtoCombo.currentText, gcsField.text)
                            background: Rectangle {
                                radius: Theme.radiusField
                                color: Theme.field
                                border.width: (root.opsVm && root.opsVm.fieldErrors.dtu_port) || dtuField.activeFocus ? 2 : 0
                                border.color: (root.opsVm && root.opsVm.fieldErrors.dtu_port) ? Theme.bad : Theme.primary
                            }
                        }
                    }
                    Text {
                        visible: Boolean(root.opsVm && root.opsVm.fieldErrors.dtu_port)
                        text: root.opsVm && root.opsVm.fieldErrors.dtu_port ? root.opsVm.fieldErrors.dtu_port : ""
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontXs
                        color: Theme.bad
                    }
                }

                // GCS Protocol + Port
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text { text: qsTr("地面站（GCS）协议与端口"); font.family: Theme.fontSans; font.pixelSize: Theme.fontSm; color: Theme.text2 }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        ComboBox {
                            id: gcsProtoCombo
                            objectName: "gcsProtocolCombo"
                            Layout.preferredWidth: 84
                            Layout.preferredHeight: Theme.controlHeight
                            model: ["tcp", "udp"]
                            currentIndex: root.opsVm && root.opsVm.draftGcsProtocol === "udp" ? 1 : 0
                            onActivated: if (root.opsVm) root.opsVm.updateDraft(nameField.text, dtuField.text, currentText, gcsField.text)
                        }
                        TextField {
                            id: gcsField
                            objectName: "gcsPortInput"
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.preferredWidth: 0
                            Layout.preferredHeight: Theme.controlHeight
                            placeholderText: qsTr("1–65535，例如 14552")
                            font.family: Theme.fontMono
                            text: root.opsVm ? root.opsVm.draftGcsPort : ""
                            onTextEdited: if (root.opsVm) root.opsVm.updateDraft(nameField.text, dtuField.text, gcsProtoCombo.currentText, text)
                            background: Rectangle {
                                radius: Theme.radiusField
                                color: Theme.field
                                border.width: (root.opsVm && root.opsVm.fieldErrors.gcs_port) || gcsField.activeFocus ? 2 : 0
                                border.color: (root.opsVm && root.opsVm.fieldErrors.gcs_port) ? Theme.bad : Theme.primary
                            }
                        }
                    }
                    Text {
                        visible: Boolean(root.opsVm && root.opsVm.fieldErrors.gcs_port)
                        text: root.opsVm && root.opsVm.fieldErrors.gcs_port ? root.opsVm.fieldErrors.gcs_port : ""
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontXs
                        color: Theme.bad
                    }
                }

                // Dry-run preview output (HTTP 200 preview, explicitly NOT applied)
                Rectangle {
                    objectName: "dryRunPreviewBox"
                    visible: Boolean(root.opsVm && root.opsVm.dryRunSummary.length > 0)
                    Layout.fillWidth: true
                    Layout.preferredHeight: dryLbl.implicitHeight + 14
                    radius: Theme.radiusTag
                    color: Theme.primaryContainer

                    Text {
                        id: dryLbl
                        anchors.fill: parent
                        anchors.margins: 7
                        wrapMode: Text.Wrap
                        text: root.opsVm ? root.opsVm.dryRunSummary : ""
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSm
                        color: Theme.textOnPrimaryContainer
                    }
                }

                // Form-level error banner
                Rectangle {
                    objectName: "groupFormErrorBanner"
                    visible: Boolean(root.opsVm && root.opsVm.formError.length > 0)
                    Layout.fillWidth: true
                    Layout.preferredHeight: formErrLbl.implicitHeight + 14
                    radius: Theme.radiusTag
                    color: Theme.badBg

                    Text {
                        id: formErrLbl
                        anchors.fill: parent
                        anchors.margins: 7
                        wrapMode: Text.Wrap
                        text: root.opsVm ? root.opsVm.formError : ""
                        font.family: Theme.fontSans
                        font.pixelSize: Theme.fontSm
                        color: Theme.bad
                    }
                }

                // Unsaved changes confirmation strip
                Rectangle {
                    objectName: "unsavedConfirmBox"
                    visible: Boolean(root.opsVm && root.opsVm.confirmDiscardOpen)
                    Layout.fillWidth: true
                    Layout.preferredHeight: discardRow.implicitHeight + 16
                    radius: Theme.radiusCard
                    color: Theme.warnBg

                    RowLayout {
                        id: discardRow
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8
                        Text {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            wrapMode: Text.Wrap
                            text: qsTr("有未保存的配置更改，确定放弃并关闭弹窗吗？")
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSm
                            color: Theme.warn
                        }
                        Button {
                            objectName: "keepEditingButton"
                            text: qsTr("继续编辑")
                            onClicked: if (root.opsVm) root.opsVm.cancelDiscardConfirmation()
                        }
                        Button {
                            objectName: "discardDraftButton"
                            text: qsTr("放弃更改")
                            onClicked: if (root.opsVm) root.opsVm.forceCloseDialog()
                        }
                    }
                }

                // Actions footer
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Button {
                        objectName: "dryRunButton"
                        visible: Boolean(root.opsVm && root.opsVm.dialogMode === "edit")
                        enabled: Boolean(root.opsVm && !root.opsVm.dryRunning && !root.opsVm.submitting)
                        text: root.opsVm && root.opsVm.dryRunning ? qsTr("预演中…") : qsTr("预演变更")
                        onClicked: if (root.opsVm) root.opsVm.runEditDryRun()
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        objectName: "cancelDialogButton"
                        enabled: !root.opsVm || !root.opsVm.submitting
                        text: qsTr("取消")
                        onClicked: if (root.opsVm) root.opsVm.requestCloseDialog()
                    }

                    Button {
                        id: submitBtn
                        objectName: "submitDialogButton"
                        enabled: !root.opsVm || !root.opsVm.submitting
                        text: root.opsVm && root.opsVm.submitting
                            ? qsTr("提交中…")
                            : (root.opsVm && root.opsVm.dialogMode === "edit" ? qsTr("提交变更") : qsTr("创建端口组"))
                        onClicked: if (root.opsVm) root.opsVm.submitDialog()
                        contentItem: Text {
                            text: submitBtn.text
                            font.family: Theme.fontSans
                            font.pixelSize: Theme.fontSm
                            font.weight: Font.Medium
                            color: Theme.textOnPrimary
                            leftPadding: 14; rightPadding: 14
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            radius: Theme.radiusPill
                            color: submitBtn.enabled ? Theme.primary : Theme.outline
                        }
                    }
                }
            }
        }
    }
}
