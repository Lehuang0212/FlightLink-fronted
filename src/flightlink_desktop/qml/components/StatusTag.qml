import QtQuick
import theme

Rectangle {
    id: root
    property string text: ""
    property string tone: "idle" // ok | warn | bad | idle

    implicitHeight: Theme.tagHeight
    implicitWidth: Math.max(40, labelItem.implicitWidth + 16)
    radius: Theme.radiusTag
    color: tone === "ok"
        ? Theme.okBg
        : tone === "warn"
            ? Theme.warnBg
            : tone === "bad"
                ? Theme.badBg
                : Theme.idleBg

    Text {
        id: labelItem
        anchors.centerIn: parent
        text: root.text
        font.family: Theme.fontSans
        font.pixelSize: Theme.fontSm
        font.weight: Font.Medium
        color: root.tone === "ok"
            ? Theme.ok
            : root.tone === "warn"
                ? Theme.warn
                : root.tone === "bad"
                    ? Theme.bad
                    : Theme.idle
    }
}
