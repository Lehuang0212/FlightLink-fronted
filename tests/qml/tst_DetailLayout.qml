import QtQuick
import QtTest
import "../../src/flightlink_desktop/qml/pages"
import "../../src/flightlink_desktop/qml/components"

Item {
    id: root
    width: 1600
    height: 1000

    QtObject {
        id: fakeSession
        property bool authenticated: true
        property bool isAdmin: true
        property string healthStatus: "ok"
        property int healthRttMs: 18
        property string currentDisplayName: "运维管理员"
        property string currentRoleLabel: "系统管理员"
        property string serverUrl: "http://127.0.0.1:8000"
        property string ecsInstanceId: "ecs_demo_01"
        function logout() {}
        function copyToClipboard(txt) {}
    }

    QtObject {
        id: fakeWorkspace
        property string route: "overview"
        property string activeGroupId: "grp_1"
        property string historyGroupId: ""
        property bool liveUpdatesEnabled: true
        property string lastSyncText: "12:00:00"
        property bool overviewStale: false
        property string overviewObservedAt: "12:00:00"
        property var components: []
        property int componentsOkCount: 3
        property int componentsTotalCount: 3
        property string diskStatus: "ok"
        property string diskSummary: "ok"
        property var overviewMetrics: ({ group_count: 1, max_groups: 5, online_fc_count: 1 })
        property var overviewGroupsModel: null
        property var groupListModel: null
        property string groupQuery: ""
        property string groupFilter: "all"
        property int groupsTotal: 1
        property int maxGroups: 5
        property bool atGroupLimit: false

        property string detailName: "一号机"
        property string detailLifecycleState: "running"
        property string detailLifecycleLabel: "运行中"
        property string detailLifecycleTone: "ok"
        property int detailDtuPort: 5760
        property string detailGcsProtocol: "tcp"
        property int detailGcsPort: 14552
        property string detailDtuPeer: "172.22.11.8"
        property string detailGcsPeer: "10.0.3.21"
        property string detailFcState: "online"
        property string detailGcsState: "connected"
        property bool detailStale: false
        property string detailObservedAt: "12:00:00"
        property var detailServices: [
            { key: "router", title: "Router", state: "running", stateLabel: "运行中", tone: "ok", meta: "PID 4821", observedAt: "12:00:00", stale: false },
            { key: "mavproxy", title: "MAVProxy 会话", state: "connected", stateLabel: "已连接", tone: "ok", meta: "00:05:00", observedAt: "12:00:00", stale: false },
            { key: "security_group", title: "安全组", state: "synced", stateLabel: "已同步", tone: "ok", meta: "2 条入方向规则", observedAt: "12:00:00", stale: true }
        ]
        property var detailTelemetryCards: [
            { key: "flight_mode", label: "飞行模式", value: "LOITER", sub: "SYSID 1", tone: "default", empty: false },
            { key: "armed", label: "解锁状态", value: "未解锁", sub: "", tone: "default", empty: false },
            { key: "battery_remaining_pct", label: "电量", value: "86%", sub: "", tone: "default", empty: false },
            { key: "battery_voltage_v", label: "电池电压", value: "24.6 V", sub: "4.10 V / cell", tone: "default", empty: false },
            { key: "gps_satellites", label: "GPS 卫星数", value: "17", sub: "", tone: "default", empty: false },
            { key: "gps_fix_type", label: "GPS 定位类型", value: "RTK Fixed", sub: "HDOP 0.62", tone: "default", empty: false },
            { key: "altitude_msl_m", label: "海拔", value: "512.5 m", sub: "MSL 高度", tone: "default", empty: false },
            { key: "relative_altitude_m", label: "相对高度", value: "0.0 m", sub: "相对起飞点", tone: "default", empty: false },
            { key: "ground_speed_mps", label: "地速", value: "0.0 m/s", sub: "0.0 km/h", tone: "default", empty: false },
            { key: "rx_rate_kbps", label: "飞控接收速率", value: "4.74 KB/s", sub: "从 DTU 到 ECS", tone: "default", empty: false },
            { key: "tx_rate_kbps", label: "地面站发送速率", value: "3.95 KB/s", sub: "从 ECS 到地面站", tone: "default", empty: false },
            { key: "packets", label: "丢包 / 收包", value: "0 / 441", sub: "丢包率 0.0%", tone: "default", empty: false }
        ]
        property string detailTelemetryNote: "观测于 12:00:00"
        property var detailGcsCommands: []
        property string detailLogTab: "router"
        property var detailRouterLogsModel: null
        property var detailMavproxyLogsModel: null
        property var liveLogsModel: null
        property string logsGroupFilter: ""
        property string logsSourceFilter: "all"
        property string logsLevelFilter: "all"
        property string logsQueryFilter: ""
        property var archiveGroupsModel: null
        property var archiveSessionsModel: null
        property var historyGroupMeta: ({})
        property string globalSearchQuery: ""
        property var globalSearchResults: []
        property string archiveLocalRoot: ""
        property int archiveFailedCount: 0
        property string archiveFailedGroupId: ""
        property string archiveFailedSessionId: ""
        property string archiveFailedMessage: ""
        property string archiveStatusText: "自动归档就绪"
        property string archiveRetentionGapNote: ""
        property string toastMessage: ""
        property string toastTone: "info"
        property bool toastVisible: false

        function navigate(target) { route = target }
        function setDetailLogTab(src) { detailLogTab = src }
        function toggleLiveUpdates() { liveUpdatesEnabled = !liveUpdatesEnabled }
        function clearGlobalSearch() { globalSearchQuery = ""; globalSearchResults = [] }
        function loadArchiveGroups() {}
    }

    Component {
        id: detailComponent
        GroupDetailPage {
            workspaceVm: fakeWorkspace
            sessionVm: fakeSession
        }
    }

    Component {
        id: shellComponent
        AppShell {
            sessionVm: fakeSession
            workspaceVm: fakeWorkspace
        }
    }

    TestCase {
        name: "DetailAndShellResponsive"
        when: windowShown

        function test_detail_1280_shows_services_12_cards_and_tabbed_logs() {
            fakeWorkspace.detailLogTab = "router"
            let page = createTemporaryObject(detailComponent, root, { width: 1088, height: 736, compact: true })
            verify(!!page, "Component exists")
            waitForRendering(page)

            let servicesPanel = findChild(page, "detailServicesPanel")
            let telemetryPanel = findChild(page, "detailTelemetryPanel")
            let logTabs = findChild(page, "detailLogTabs")
            let routerPane = findChild(page, "detailRouterLogPane")
            let mavPane = findChild(page, "detailMavproxyLogPane")
            let mavTabBtn = findChild(page, "detailMavproxyTabButton")
            let sgStaleTag = findChild(page, "serviceStaleTag_security_group")

            verify(!!servicesPanel, "Object exists")
            verify(!!telemetryPanel, "Object exists")
            verify(!!logTabs, "Object exists")
            verify(!!routerPane, "Object exists")
            verify(!!mavPane, "Object exists")
            verify(!!mavTabBtn, "Object exists")
            verify(!!sgStaleTag, "Object exists")

            compare(logTabs.visible, true)
            compare(routerPane.visible, true)
            compare(mavPane.visible, false)
            compare(sgStaleTag.visible, true)
            // Three services + 12 telemetry cards visible on first screen of 1280x800 (viewport height 736)
            verify(telemetryPanel.y + telemetryPanel.height <= 736)
            // No horizontal overflow
            verify(telemetryPanel.x + telemetryPanel.width <= page.width)

            // Switch to MAVProxy tab
            mouseClick(mavTabBtn)
            tryCompare(fakeWorkspace, "detailLogTab", "mavproxy")
            compare(routerPane.visible, false)
            compare(mavPane.visible, true)
        }

        function test_detail_1440_and_1600_show_dual_pane_logs() {
            let page = createTemporaryObject(detailComponent, root, { width: 1232, height: 836, compact: false })
            verify(!!page, "Component exists")
            waitForRendering(page)

            let logTabs = findChild(page, "detailLogTabs")
            let routerPane = findChild(page, "detailRouterLogPane")
            let mavPane = findChild(page, "detailMavproxyLogPane")

            verify(!!logTabs, "Object exists")
            verify(!!routerPane, "Object exists")
            verify(!!mavPane, "Object exists")

            compare(logTabs.visible, false)
            compare(routerPane.visible, true)
            compare(mavPane.visible, true)
            compare(mavPane.title, "MAVProxy 会话日志")
            verify(mavPane.x > routerPane.x)
            verify(mavPane.x + mavPane.width <= page.width)
        }

        function test_shell_sidebar_narrows_at_1280_and_shortcuts_navigate() {
            fakeWorkspace.route = "overview"
            let shell = createTemporaryObject(shellComponent, root, { width: 1280, height: 760 })
            verify(!!shell, "Component exists")
            waitForRendering(shell)

            let sidebar = findChild(shell, "appSidebar")
            let statusInst = findChild(shell, "statusBarInstanceId")
            let overviewInst = findChild(shell, "overviewInstanceId")
            verify(!!sidebar, "Object exists")
            verify(!!statusInst, "Status bar instance ID exists")
            verify(!!overviewInst, "Overview instance ID exists")
            compare(statusInst.visible, true)
            compare(statusInst.text, "ecs_demo_01")
            compare(overviewInst.visible, true)
            verify(overviewInst.text.indexOf("ecs_demo_01") >= 0)
            compare(sidebar.width, 192)

            shell.width = 1440
            tryCompare(sidebar, "width", 208)

            shell.forceActiveFocus()
            keyClick(Qt.Key_2, Qt.ControlModifier)
            tryCompare(fakeWorkspace, "route", "groups")
            keyClick(Qt.Key_3, Qt.ControlModifier)
            tryCompare(fakeWorkspace, "route", "logs")
            keyClick(Qt.Key_4, Qt.ControlModifier)
            tryCompare(fakeWorkspace, "route", "history")
            keyClick(Qt.Key_1, Qt.ControlModifier)
            tryCompare(fakeWorkspace, "route", "overview")
        }
    }
}
