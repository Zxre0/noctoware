// Noctoware SDDM greeter (Qt 6). MIT licensed code; artwork CC-BY-SA-4.0.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: root
    width: 1920
    height: 1080
    color: "#07040c"

    readonly property color accent: config.accent || "#9b6bff"
    readonly property color fg: "#efe6ff"
    readonly property color muted: "#a493c4"
    readonly property color field: "#1a1228"
    readonly property string fontFamily: config.font || "Noto Sans"

    function doLogin() {
        errorText.text = ""
        sddm.login(userField.text, passwordField.text, sessionBox.currentIndex)
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            errorText.text = "Login failed. Check your password and try again."
            passwordField.text = ""
            passwordField.forceActiveFocus()
        }
    }

    Image {
        anchors.fill: parent
        source: config.background
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        smooth: true
    }
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "#e607040c" }
            GradientStop { position: 0.55; color: "#8007040c" }
            GradientStop { position: 1.0; color: "#0007040c" }
        }
    }

    ColumnLayout {
        id: panel
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        anchors.leftMargin: Math.max(48, root.width * 0.08)
        width: Math.min(420, root.width - 96)
        spacing: 14

        Image {
            source: config.logo
            sourceSize.width: 96
            sourceSize.height: 96
            Layout.preferredWidth: 96
            Layout.preferredHeight: 96
        }
        Text {
            id: clock
            color: root.fg
            font.family: root.fontFamily
            font.pixelSize: 64
            font.weight: Font.Light
            text: Qt.formatTime(new Date(), "hh:mm")
            Timer {
                interval: 1000; running: true; repeat: true
                onTriggered: {
                    clock.text = Qt.formatTime(new Date(), "hh:mm")
                    dateText.text = Qt.formatDate(new Date(), "dddd, d MMMM")
                }
            }
        }
        Text {
            id: dateText
            color: root.muted
            font.family: root.fontFamily
            font.pixelSize: 18
            text: Qt.formatDate(new Date(), "dddd, d MMMM")
            Layout.bottomMargin: 18
        }

        TextField {
            id: userField
            Layout.fillWidth: true
            placeholderText: "Username"
            text: userModel.lastUser
            color: root.fg
            placeholderTextColor: root.muted
            font.family: root.fontFamily
            font.pixelSize: 16
            padding: 12
            background: Rectangle { radius: 10; color: root.field; border.color: userField.activeFocus ? root.accent : "#33264d"; border.width: 1 }
            KeyNavigation.tab: passwordField
            onAccepted: passwordField.forceActiveFocus()
        }
        TextField {
            id: passwordField
            Layout.fillWidth: true
            placeholderText: keyboard.capsLock ? "Password (Caps Lock is on)" : "Password"
            echoMode: TextInput.Password
            color: root.fg
            placeholderTextColor: root.muted
            font.family: root.fontFamily
            font.pixelSize: 16
            padding: 12
            focus: true
            background: Rectangle { radius: 10; color: root.field; border.color: passwordField.activeFocus ? root.accent : "#33264d"; border.width: 1 }
            KeyNavigation.tab: sessionBox
            onAccepted: root.doLogin()
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            ComboBox {
                id: sessionBox
                Layout.fillWidth: true
                model: sessionModel
                textRole: "name"
                currentIndex: sessionModel.lastIndex
                font.family: root.fontFamily
                contentItem: Text {
                    leftPadding: 12
                    text: sessionBox.displayText
                    color: root.fg
                    font: sessionBox.font
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                background: Rectangle { implicitHeight: 44; radius: 10; color: root.field; border.color: sessionBox.activeFocus ? root.accent : "#33264d" }
                delegate: ItemDelegate {
                    width: sessionBox.width
                    contentItem: Text { text: model.name; color: root.fg; font: sessionBox.font }
                    background: Rectangle { color: highlighted ? "#3b2366" : root.field }
                    highlighted: sessionBox.highlightedIndex === index
                }
                popup.background: Rectangle { color: root.field; radius: 8; border.color: "#33264d" }
                KeyNavigation.tab: loginButton
            }
            Button {
                id: loginButton
                text: "Log in"
                font.family: root.fontFamily
                font.pixelSize: 15
                implicitHeight: 44
                contentItem: Text { text: loginButton.text; font: loginButton.font; color: "#0b0612"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                background: Rectangle { radius: 10; color: loginButton.down ? "#7c4dff" : root.accent; implicitWidth: 110 }
                onClicked: root.doLogin()
                Keys.onReturnPressed: root.doLogin()
            }
        }
        Text {
            id: errorText
            color: "#ff8fa3"
            font.family: root.fontFamily
            font.pixelSize: 14
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }
    }

    Row {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 32
        spacing: 18
        Repeater {
            model: [
                { label: "Suspend", enabled: sddm.canSuspend, act: function() { sddm.suspend() } },
                { label: "Restart", enabled: sddm.canReboot, act: function() { sddm.reboot() } },
                { label: "Shut down", enabled: sddm.canPowerOff, act: function() { sddm.powerOff() } }
            ]
            delegate: Text {
                required property var modelData
                visible: modelData.enabled
                text: modelData.label
                color: hover.hovered ? root.fg : root.muted
                font.family: root.fontFamily
                font.pixelSize: 15
                HoverHandler { id: hover }
                TapHandler { onTapped: modelData.act() }
            }
        }
    }
    Text {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 32
        text: "Noctoware Linux"
        color: "#6d5a91"
        font.family: root.fontFamily
        font.pixelSize: 13
        font.letterSpacing: 2
    }

    Component.onCompleted: {
        if (userField.text.length === 0) userField.forceActiveFocus()
        else passwordField.forceActiveFocus()
    }
}
