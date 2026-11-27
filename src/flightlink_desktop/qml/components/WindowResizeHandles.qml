import QtQuick
import QtQuick.Window

Item {
    id: root
    objectName: "windowResizeHandles"

    required property Window targetWindow
    property int edgeSize: 6
    property int cornerSize: 10

    readonly property bool active: Boolean(
        targetWindow
        && targetWindow.visibility !== Window.Maximized
        && targetWindow.visibility !== Window.FullScreen
    )

    visible: root.active

    // Top edge
    MouseArea {
        objectName: "resizeTop"
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: root.cornerSize
        anchors.rightMargin: root.cornerSize
        height: root.edgeSize
        cursorShape: Qt.SizeVerCursor
        onPressed: root.targetWindow.startSystemResize(Qt.TopEdge)
    }

    // Bottom edge
    MouseArea {
        objectName: "resizeBottom"
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: root.cornerSize
        anchors.rightMargin: root.cornerSize
        height: root.edgeSize
        cursorShape: Qt.SizeVerCursor
        onPressed: root.targetWindow.startSystemResize(Qt.BottomEdge)
    }

    // Left edge
    MouseArea {
        objectName: "resizeLeft"
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.topMargin: root.cornerSize
        anchors.bottomMargin: root.cornerSize
        width: root.edgeSize
        cursorShape: Qt.SizeHorCursor
        onPressed: root.targetWindow.startSystemResize(Qt.LeftEdge)
    }

    // Right edge
    MouseArea {
        objectName: "resizeRight"
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.topMargin: root.cornerSize
        anchors.bottomMargin: root.cornerSize
        width: root.edgeSize
        cursorShape: Qt.SizeHorCursor
        onPressed: root.targetWindow.startSystemResize(Qt.RightEdge)
    }

    // Top-left corner
    MouseArea {
        objectName: "resizeTopLeft"
        anchors.top: parent.top
        anchors.left: parent.left
        width: root.cornerSize
        height: root.cornerSize
        cursorShape: Qt.SizeFDiagCursor
        onPressed: root.targetWindow.startSystemResize(Qt.TopEdge | Qt.LeftEdge)
    }

    // Top-right corner
    MouseArea {
        objectName: "resizeTopRight"
        anchors.top: parent.top
        anchors.right: parent.right
        width: root.cornerSize
        height: root.cornerSize
        cursorShape: Qt.SizeBDiagCursor
        onPressed: root.targetWindow.startSystemResize(Qt.TopEdge | Qt.RightEdge)
    }

    // Bottom-left corner
    MouseArea {
        objectName: "resizeBottomLeft"
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        width: root.cornerSize
        height: root.cornerSize
        cursorShape: Qt.SizeBDiagCursor
        onPressed: root.targetWindow.startSystemResize(Qt.BottomEdge | Qt.LeftEdge)
    }

    // Bottom-right corner
    MouseArea {
        objectName: "resizeBottomRight"
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        width: root.cornerSize
        height: root.cornerSize
        cursorShape: Qt.SizeFDiagCursor
        onPressed: root.targetWindow.startSystemResize(Qt.BottomEdge | Qt.RightEdge)
    }
}
