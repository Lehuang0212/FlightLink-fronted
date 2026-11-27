pragma Singleton
import QtQuick

QtObject {
    id: theme

    // Surface & canvas palette (1:1 with FLightLink1.0-preview/styles.css)
    readonly property color bg: "#F8FAFD"
    readonly property color surface: "#FFFFFF"
    readonly property color surfaceTint: "#F0F4F9"
    readonly property color field: "#E9EEF6"
    readonly property color divider: "#E1E5EA"
    readonly property color outline: "#C4C7C5"

    // Brand & container colors
    readonly property color primary: "#0B57D0"
    readonly property color primaryHover: "#0842A0"
    readonly property color textOnPrimary: "#FFFFFF"
    readonly property color primaryContainer: "#D3E3FD"
    readonly property color textOnPrimaryContainer: "#041E49"
    readonly property color fab: "#C2E7FF"
    readonly property color fabHover: "#A8D8FB"

    // Text hierarchy
    readonly property color text: "#1F1F1F"
    readonly property color text2: "#444746"
    readonly property color text3: "#747775"

    // Semantic status colors
    readonly property color ok: "#146C2E"
    readonly property color okBg: "#C4EED0"
    readonly property color warn: "#8A5300"
    readonly property color warnBg: "#FFE7B8"
    readonly property color bad: "#B3261E"
    readonly property color badBg: "#F9DEDC"
    readonly property color badRow: "#0AB3261E"
    readonly property color idle: "#444746"
    readonly property color idleBg: "#EEF0F2"
    readonly property color scrim: "#521F1F1F"

    // Link wire glow (strictly reserved for active link pulse)
    readonly property color flowStart: "#4285F4"
    readonly property color flowMiddle: "#9B72CB"
    readonly property color flowEnd: "#D96570"

    // Font families
    readonly property string fontSans: "Microsoft YaHei UI"
    readonly property string fontMono: "Cascadia Mono"

    // 7 exact type scales: 11/16, 12/18, 13/20, 14/20, 16/24, 22/28, 24/28
    readonly property int fontXs: 11
    readonly property int lineXs: 16
    readonly property int fontSm: 12
    readonly property int lineSm: 18
    readonly property int fontBody: 13
    readonly property int lineBody: 20
    readonly property int fontMd: 14
    readonly property int lineMd: 20
    readonly property int fontLg: 16
    readonly property int lineLg: 24
    readonly property int fontXl: 22
    readonly property int lineXl: 28
    readonly property int font2xl: 24
    readonly property int line2xl: 28

    // Radii
    readonly property int radiusPanel: 16
    readonly property int radiusCard: 12
    readonly property int radiusPill: 999
    readonly property int radiusTag: 8
    readonly property int radiusFab: 16
    readonly property int radiusField: 8
    readonly property int radiusDialog: 24

    // Layout metrics
    readonly property int titlebarHeight: 40
    readonly property int statusbarHeight: 24
    readonly property int sidebarWidthWide: 208
    readonly property int sidebarWidthCompact: 192
    readonly property int compactBreakpoint: 1360
    readonly property int contentMarginWide: 24
    readonly property int contentMarginCompact: 20
    readonly property int columnGapWide: 16
    readonly property int columnGapCompact: 12
    readonly property int controlHeight: 36
    readonly property int tagHeight: 24
    readonly property int panelPadding: 16
    readonly property int rowHeight: 40
    readonly property int logRowHeight: 20
    readonly property int loginCardWidth: 360

    // Motion & accessibility
    property bool reducedMotion: false
    readonly property int durationExpand: reducedMotion ? 0 : 180
    readonly property int durationFlow: 2400
}
