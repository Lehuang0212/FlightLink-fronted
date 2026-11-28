import QtQuick
import QtTest
import "../../src/flightlink_desktop/qml/components"

Item {
    id: root
    width: 360
    height: 480

    Component {
        id: dialogComponent
        CloseConfirmDialog {
            anchors.fill: parent
            open: true
            authenticated: true
        }
    }

    SignalSpy { id: cancelSpy; signalName: "cancelRequested" }
    SignalSpy { id: bgSpy; signalName: "backgroundRequested" }
    SignalSpy { id: quitSpy; signalName: "quitRequested" }

    TestCase {
        name: "CloseConfirmDialog"
        when: windowShown

        function test_close_dialog_fits_compact_window_and_emits_actions() {
            let dlg = createTemporaryObject(dialogComponent, root)
            verify(!!dlg, "CloseConfirmDialog created")
            cancelSpy.target = dlg
            bgSpy.target = dlg
            quitSpy.target = dlg
            cancelSpy.clear()
            bgSpy.clear()
            quitSpy.clear()
            waitForRendering(dlg)

            let card = findChild(dlg, "closeConfirmCard")
            let cancelBtn = findChild(dlg, "cancelCloseButton")
            let bgBtn = findChild(dlg, "minimizeToTrayButton")
            let quitBtn = findChild(dlg, "confirmQuitButton")
            verify(!!card && !!cancelBtn && !!bgBtn && !!quitBtn)

            // Fits comfortably within 360x480 minimum login window with no horizontal overflow
            verify(card.width <= root.width - 16)
            verify(card.x >= 0 && card.x + card.width <= root.width)

            // Cancel button & Esc both emit cancelRequested
            mouseClick(cancelBtn)
            tryCompare(cancelSpy, "count", 1)
            dlg.forceActiveFocus()
            keyClick(Qt.Key_Escape)
            tryCompare(cancelSpy, "count", 2)

            // Background run button emits backgroundRequested
            mouseClick(bgBtn)
            tryCompare(bgSpy, "count", 1)

            // Full quit button emits quitRequested
            mouseClick(quitBtn)
            tryCompare(quitSpy, "count", 1)
        }
    }
}
