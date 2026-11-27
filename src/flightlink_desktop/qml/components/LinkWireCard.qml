import QtQuick
import QtQuick.Layouts
import theme

Item {
    id: root

    property int dtuPort: 0
    property string gcsProtocol: "TCP"
    property int gcsPort: 0
    property string dtuPeer: "—"
    property string gcsPeer: "—"
    property bool fcOnline: false
    property bool routerRunning: false
    property string routerStatusText: ""
    property bool gcsConnected: false
    property bool liveActive: true

    implicitHeight: 68

    readonly property bool animateFlow: root.visible && root.liveActive && !Theme.reducedMotion && root.routerRunning && root.fcOnline

    ColumnLayout {
        anchors.fill: parent
        spacing: 6

        // Port labels row
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                elide: Text.ElideRight
                text: qsTr("UDP %1").arg(root.dtuPort)
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontSm
                font.weight: Font.Medium
                color: Theme.text2
            }

            Text {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                elide: Text.ElideRight
                text: qsTr("%1 %2").arg(root.gcsProtocol.toUpperCase()).arg(root.gcsPort)
                font.family: Theme.fontMono
                font.pixelSize: Theme.fontSm
                font.weight: Font.Medium
                color: Theme.text2
            }
        }

        // Wire line with optional link pulse dot (only gradient in entire app)
        Item {
            id: wireTrack
            Layout.fillWidth: true
            Layout.preferredHeight: 10

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                height: 2
                radius: 1
                color: root.routerRunning ? Theme.primary : Theme.outline
                opacity: root.routerRunning ? 0.85 : 0.45
            }

            // Animated flow pulse strictly confined within the wire track
            Rectangle {
                id: pulseDot
                visible: root.animateFlow
                width: 28
                height: 4
                radius: 2
                y: (wireTrack.height - height) / 2
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: Theme.flowStart }
                    GradientStop { position: 0.5; color: Theme.flowMiddle }
                    GradientStop { position: 1.0; color: Theme.flowEnd }
                }

                XAnimator {
                    target: pulseDot
                    from: 0
                    to: Math.max(0, wireTrack.width - pulseDot.width)
                    duration: Theme.durationFlow
                    loops: Animation.Infinite
                    running: root.animateFlow
                }
            }

            // Three endpoint dots: DTU, Router, GCS
            Rectangle {
                width: 8; height: 8; radius: 4
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                color: root.fcOnline ? Theme.primary : Theme.outline
            }
            Rectangle {
                width: 8; height: 8; radius: 4
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.verticalCenter: parent.verticalCenter
                color: root.routerRunning ? Theme.primary : Theme.outline
            }
            Rectangle {
                width: 8; height: 8; radius: 4
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                color: root.gcsConnected ? Theme.primary : Theme.outline
            }
        }

        // Endpoint titles & peer addresses
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2
                Text {
                    text: qsTr("DTU")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontMd
                    font.weight: Font.Medium
                    color: Theme.text
                }
                Text {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    elide: Text.ElideRight
                    text: root.dtuPeer
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontXs
                    color: Theme.text3
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: qsTr("Router")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontMd
                    font.weight: Font.Medium
                    color: Theme.text
                }
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: root.routerRunning ? qsTr("转发中") : (root.routerStatusText || qsTr("未启动"))
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontXs
                    color: Theme.text3
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2
                Text {
                    Layout.alignment: Qt.AlignRight
                    text: qsTr("GCS")
                    font.family: Theme.fontSans
                    font.pixelSize: Theme.fontMd
                    font.weight: Font.Medium
                    color: Theme.text
                }
                Text {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    horizontalAlignment: Text.AlignRight
                    elide: Text.ElideRight
                    text: root.gcsPeer
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.fontXs
                    color: Theme.text3
                }
            }
        }
    }
}
