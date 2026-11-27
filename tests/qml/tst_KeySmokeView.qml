import QtQuick
import QtTest
import "../../src/flightlink_desktop/qml/components"

Item {
    id: root
    width: 480
    height: 320

    Component {
        id: viewComponent
        KeySmokeView {
            width: root.width
            height: root.height
        }
    }

    SignalSpy {
        id: shortcutSpy
        signalName: "shortcutTriggered"
    }

    TestCase {
        name: "KeySmokeView"
        when: windowShown

        function test_ctrl_k_focuses_search_and_emits_shortcut() {
            let view = createTemporaryObject(viewComponent, root)
            verify(!!view, "Component exists")

            let searchInput = findChild(view, "searchInput")
            verify(!!searchInput, "Object exists")

            shortcutSpy.target = view
            shortcutSpy.clear()

            view.focus = true
            keyClick(Qt.Key_K, Qt.ControlModifier)

            tryCompare(shortcutSpy, "count", 1)
            compare(view.shortcutCount, 1)
            compare(view.lastShortcut, "Ctrl+K")
            tryCompare(searchInput, "activeFocus", true)
        }

        function test_escape_clears_search_and_emits_shortcut() {
            let view = createTemporaryObject(viewComponent, root)
            verify(!!view, "Component exists")

            let searchInput = findChild(view, "searchInput")
            verify(!!searchInput, "Object exists")

            searchInput.text = "5760"
            searchInput.forceActiveFocus()
            tryCompare(searchInput, "activeFocus", true)

            shortcutSpy.target = view
            shortcutSpy.clear()

            keyClick(Qt.Key_Escape)

            tryCompare(shortcutSpy, "count", 1)
            compare(searchInput.text, "")
            compare(view.lastShortcut, "Esc")
        }
    }
}
