import QtQuick
import QtQuick.Controls.Basic
import theme

Button {
    id: control

    // Variants: "secondary" | "primary" | "danger" | "dangerFilled" | "subtle" | "ghost"
    property string variant: "secondary"
    property bool compact: false
    property bool active: false
    property bool pill: variant === "primary" || variant === "dangerFilled"

    activeFocusOnTab: true
    implicitHeight: compact ? 28 : 34
    implicitWidth: Math.max(compact ? 28 : 44, labelItem.implicitWidth + (compact ? 18 : 24))

    HoverHandler {
        cursorShape: control.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
    }

    contentItem: Text {
        id: labelItem
        text: control.text
        font.family: Theme.fontSans
        font.pixelSize: control.compact ? Theme.fontXs : Theme.fontSm
        font.weight: (control.variant === "primary" || control.variant === "dangerFilled" || control.active)
            ? Font.Medium
            : Font.Normal
        color: {
            if (!control.enabled)
                return Theme.text3
            if (control.variant === "primary" || control.variant === "dangerFilled")
                return Theme.textOnPrimary
            if (control.variant === "danger")
                return Theme.bad
            if (control.variant === "subtle")
                return Theme.primary
            if (control.active)
                return Theme.textOnPrimaryContainer
            return Theme.text
        }
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: control.pill ? Theme.radiusPill : Theme.radiusField
        color: {
            if (!control.enabled)
                return (control.variant === "primary" || control.variant === "dangerFilled") ? Theme.outline : Theme.idleBg
            if (control.variant === "primary")
                return control.down ? Theme.primaryHover : (control.hovered ? Theme.primaryHover : Theme.primary)
            if (control.variant === "dangerFilled")
                return control.down ? "#8C1D18" : (control.hovered ? "#991F1A" : Theme.bad)
            if (control.variant === "danger")
                return control.down ? "#F2C6C3" : (control.hovered ? Theme.badBg : Theme.surface)
            if (control.variant === "subtle")
                return control.down ? Theme.primaryContainer : (control.hovered ? Theme.primaryContainer : Theme.surfaceTint)
            if (control.variant === "ghost")
                return control.down ? Theme.divider : (control.hovered ? Theme.surfaceTint : "#00000000")
            if (control.active)
                return Theme.primaryContainer
            return control.down ? Theme.field : (control.hovered ? Theme.surfaceTint : Theme.surface)
        }
        border.width: {
            if (control.activeFocus)
                return 2
            if (control.variant === "primary" || control.variant === "dangerFilled" || control.variant === "ghost")
                return 0
            return 1
        }
        border.color: {
            if (control.activeFocus)
                return (control.variant === "primary" || control.variant === "dangerFilled")
                    ? Theme.textOnPrimaryContainer
                    : Theme.primary
            if (control.variant === "danger" && control.enabled)
                return "#E6B4B1"
            if (control.active)
                return Theme.primary
            return Theme.divider
        }
    }
}
