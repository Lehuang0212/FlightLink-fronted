import QtQuick
import QtQuick.Controls.Basic
import theme

Item {
    id: root
    objectName: "marqueeText"

    property string text: ""
    property color color: Theme.text2
    property string fontFamily: Theme.fontSans
    property int pixelSize: Theme.fontSm
    property int fontWeight: Font.Normal
    property int pixelsPerSecond: 44
    property int pauseMs: 1100

    readonly property real overflowDistance: Math.max(0, labelItem.implicitWidth - root.width)
    readonly property bool isOverflowing: root.overflowDistance > 2
    readonly property bool scrollingActive: root.visible && root.isOverflowing && !Theme.reducedMotion && !hoverHandler.hovered

    implicitHeight: Math.max(18, labelItem.implicitHeight)
    implicitWidth: labelItem.implicitWidth
    clip: true

    onTextChanged: {
        scrollAnim.restart()
        labelItem.x = 0
    }

    onIsOverflowingChanged: {
        if (!isOverflowing)
            labelItem.x = 0
    }

    HoverHandler {
        id: hoverHandler
    }

    ToolTip.visible: hoverHandler.hovered && root.isOverflowing
    ToolTip.text: root.text
    ToolTip.delay: 300

    Text {
        id: labelItem
        objectName: "marqueeInnerText"
        x: 0
        anchors.verticalCenter: parent.verticalCenter
        text: root.text
        color: root.color
        font.family: root.fontFamily
        font.pixelSize: root.pixelSize
        font.weight: root.fontWeight
    }

    SequentialAnimation {
        id: scrollAnim
        running: root.scrollingActive
        loops: Animation.Infinite

        PauseAnimation {
            duration: root.pauseMs
        }

        NumberAnimation {
            target: labelItem
            property: "x"
            from: 0
            to: -root.overflowDistance
            duration: Math.max(900, Math.round((root.overflowDistance * 1000) / Math.max(10, root.pixelsPerSecond)))
            easing.type: Easing.Linear
        }

        PauseAnimation {
            duration: root.pauseMs
        }

        NumberAnimation {
            target: labelItem
            property: "x"
            to: 0
            duration: 380
            easing.type: Easing.InOutQuad
        }
    }
}
