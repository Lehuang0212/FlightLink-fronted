import QtQuick
import QtQuick.Controls
import "components"

ApplicationWindow {
    id: root
    objectName: "flightlinkMainWindow"
    width: 1280
    height: 800
    minimumWidth: 1024
    minimumHeight: 640
    visible: true
    title: qsTr("FlightLink Desktop 1.0")
    color: "#F8FAFD"

    KeySmokeView {
        id: smokeView
        objectName: "smokeView"
        anchors.fill: parent
    }
}
