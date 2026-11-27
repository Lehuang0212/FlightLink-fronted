import QtQuick
import QtTest
import "../../src/flightlink_desktop/qml/pages"

Item {
    id: root
    width: 1100
    height: 760

    ListModel {
        id: mockSessions
        ListElement {
            sessionId: "sess_saved"
            statusLabel: "已封存"
            closeReason: "fc_heartbeat_timeout"
            timeRange: "2026-11-27 10:00:00 至 2026-11-27 10:25:00"
            expiresAt: "2026-12-04 10:25:00"
            sysidText: "SYSID 1"
            expanded: false
            localStatus: "saved"
            localStatusLabel: "已自动保存"
            localStatusTone: "ok"
            localDetail: ""
            showRetryAction: false
            activeSource: "router"
            entriesLoading: false
            entriesHasMore: false
            entriesText: ""
            entriesCount: 0
        }
        ListElement {
            sessionId: "sess_gap"
            statusLabel: "已封存"
            closeReason: "fc_heartbeat_timeout"
            timeRange: "2026-11-27 09:00:00 至 2026-11-27 09:15:00"
            expiresAt: "2026-12-04 09:15:00"
            sysidText: "SYSID 1"
            expanded: false
            localStatus: "saved_with_source_gaps"
            localStatusLabel: "已保存（云端缺源）"
            localStatusTone: "warn"
            localDetail: "云端缺少或仅含部分来源：mavproxy（mavproxy_not_running）"
            showRetryAction: false
            activeSource: "router"
            entriesLoading: false
            entriesHasMore: false
            entriesText: ""
            entriesCount: 0
        }
        ListElement {
            sessionId: "sess_fail"
            statusLabel: "已封存"
            closeReason: "fc_heartbeat_timeout"
            timeRange: "2026-11-27 08:00:00 至 2026-11-27 08:10:00"
            expiresAt: "2026-12-04 08:10:00"
            sysidText: "SYSID 1"
            expanded: false
            localStatus: "failed"
            localStatusLabel: "本机保存失败"
            localStatusTone: "bad"
            localDetail: "下载 mavproxy.log 时网络中断，请恢复后重试"
            showRetryAction: true
            activeSource: "router"
            entriesLoading: false
            entriesHasMore: false
            entriesText: ""
            entriesCount: 0
        }
    }

    QtObject {
        id: fakeWorkspace
        property var archiveSessionsModel: mockSessions
        property var historyGroupMeta: ({
            groupId: "grp_1",
            nameSnapshot: "一号机",
            dtuPort: 5760,
            gcsProtocol: "TCP",
            gcsPort: 14552,
            deleted: false
        })
        property string lastRetrySessionId: ""
        function navigate(t) {}
        function toggleHistorySlice(sid) {}
        function selectHistorySliceSource(sid, src) {}
        function loadMoreSliceEntries(sid) {}
        function requestManualArchiveRetry(sid) { lastRetrySessionId = sid }
    }

    Component {
        id: historyDetailComp
        HistoryDetailPage {
            width: root.width
            height: root.height
            workspaceVm: fakeWorkspace
        }
    }

    TestCase {
        name: "HistorySaveStates"
        when: windowShown

        function test_retry_button_only_visible_for_failed_and_hidden_for_saved_and_source_gaps() {
            fakeWorkspace.lastRetrySessionId = ""
            let page = createTemporaryObject(historyDetailComp, root)
            verify(!!page, "Component exists")
            waitForRendering(page)

            let savedRetry = findChild(page, "retrySliceDownloadBtn_sess_saved")
            let gapRetry = findChild(page, "retrySliceDownloadBtn_sess_gap")
            let failRetry = findChild(page, "retrySliceDownloadBtn_sess_fail")

            verify(!!savedRetry, "Object exists")
            verify(!!gapRetry, "Object exists")
            verify(!!failRetry, "Object exists")

            // saved & saved_with_source_gaps MUST NOT show download/retry button
            compare(savedRetry.visible, false)
            compare(gapRetry.visible, false)
            // failed shows 「重新下载日志」 and triggers manual retry for exact slice
            compare(failRetry.visible, true)
            mouseClick(failRetry)
            tryCompare(fakeWorkspace, "lastRetrySessionId", "sess_fail")
        }
    }
}
