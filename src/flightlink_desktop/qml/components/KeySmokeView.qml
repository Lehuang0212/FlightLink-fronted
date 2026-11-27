import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    objectName: "keySmokeView"

    property int shortcutCount: 0
    property string lastShortcut: ""

    signal shortcutTriggered(string name)

    Shortcut {
        sequences: ["Ctrl+K"]
        context: Qt.WindowShortcut
        onActivated: {
            root.shortcutCount += 1
            root.lastShortcut = "Ctrl+K"
            searchInput.forceActiveFocus()
            root.shortcutTriggered("Ctrl+K")
        }
    }

    Shortcut {
        sequences: [StandardKey.Cancel]
        context: Qt.WindowShortcut
        onActivated: {
            searchInput.text = ""
            root.lastShortcut = "Esc"
            root.shortcutTriggered("Esc")
        }
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 12
        width: 360

        Label {
            objectName: "headlineLabel"
            text: qsTr("FlightLink Desktop 1.0")
            font.pixelSize: 22
            color: "#1F1F1F"
        }

        Label {
            objectName: "statusLabel"
            text: root.lastShortcut.length > 0
                ? qsTr("Last shortcut: %1").arg(root.lastShortcut)
                : qsTr("Ready")
            font.pixelSize: 13
            color: "#444746"
        }

        TextField {
            id: searchInput
            objectName: "searchInput"
            Layout.fillWidth: true
            placeholderText: qsTr("Press Ctrl+K to focus search")
        }
    }
}
