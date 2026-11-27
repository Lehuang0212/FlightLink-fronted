import QtQuick
import QtQuick.Controls.Basic
import theme

ComboBox {
    id: control

    activeFocusOnTab: true
    implicitHeight: Theme.controlHeight
    leftPadding: 12
    rightPadding: 28
    font.family: Theme.fontSans
    font.pixelSize: Theme.fontSm

    HoverHandler {
        cursorShape: control.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
    }

    indicator: Text {
        x: control.width - width - 10
        y: (control.height - height) / 2
        text: "▾"
        font.family: Theme.fontSans
        font.pixelSize: Theme.fontSm
        color: control.enabled ? Theme.text2 : Theme.text3
    }

    contentItem: Text {
        leftPadding: 0
        rightPadding: 0
        text: control.displayText
        font: control.font
        color: control.enabled ? Theme.text : Theme.text3
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: Theme.radiusField
        color: control.hovered ? Theme.surfaceTint : Theme.field
        border.width: control.activeFocus || control.popup.visible ? 2 : 1
        border.color: control.activeFocus || control.popup.visible ? Theme.primary : Theme.divider
    }

    delegate: ItemDelegate {
        id: delItem
        width: control.width
        height: 32
        highlighted: control.highlightedIndex === index
        contentItem: Text {
            text: modelData
            color: delItem.highlighted ? Theme.textOnPrimaryContainer : Theme.text
            font.family: Theme.fontSans
            font.pixelSize: Theme.fontSm
            font.weight: control.currentIndex === index ? Font.Medium : Font.Normal
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle {
            radius: Theme.radiusTag
            color: delItem.highlighted ? Theme.primaryContainer : (delItem.hovered ? Theme.surfaceTint : "#00000000")
        }
    }

    popup: Popup {
        y: control.height + 4
        width: control.width
        implicitHeight: Math.min(220, contentItem.implicitHeight + 8)
        padding: 4

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator { }
        }

        background: Rectangle {
            radius: Theme.radiusCard
            color: Theme.surface
            border.width: 1
            border.color: Theme.divider
        }
    }
}
