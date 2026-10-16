/* Noctoware installer slideshow (Calamares slideshowAPI 2). MIT. */
import QtQuick
import calamares.slideshow 1.0

Presentation {
    id: presentation

    function onActivate() { timer.running = true }
    function onLeave() { timer.running = false }

    Timer {
        id: timer
        interval: 9000
        repeat: true
        onTriggered: presentation.goToNextSlide()
    }

    Repeater {
        model: [
            { t: "Welcome to Noctoware", b: "An Arch-based rolling release with the CachyOS kernel, Hyprland and HyDE." },
            { t: "Always up to date", b: "One command updates everything — Noctoware, Arch and CachyOS packages:\n\nsudo pacman -Syu" },
            { t: "Snapshots before every update", b: "On Btrfs, snapper saves the system before and after each pacman transaction.\nRoll back any time with noctoware-rollback." },
            { t: "Ready to play", b: "Steam, Proton, Gamescope, GameMode and MangoHud are preinstalled,\nwith drivers chosen for your GPU." },
            { t: "Built for developers", b: "Git, Node.js, Python and the Codex CLI are included.\nThe Welcome app sets up Claude Code with your own account." },
            { t: "Two desktops, one login screen", b: "Hyprland + HyDE by default. Add KDE Plasma any time:\n\nsudo pacman -S noctoware-plasma" }
        ]
        delegate: Slide {
            required property var modelData
            Rectangle {
                anchors.fill: parent
                color: "#0b0712"
                Image {
                    anchors.fill: parent
                    source: "slide-bg.png"
                    fillMode: Image.PreserveAspectCrop
                    opacity: 0.55
                }
                Column {
                    anchors.centerIn: parent
                    width: parent.width * 0.8
                    spacing: 18
                    Text {
                        width: parent.width
                        text: modelData.t
                        color: "#e9ddff"
                        font.pixelSize: 30
                        font.weight: Font.Light
                        horizontalAlignment: Text.AlignHCenter
                    }
                    Text {
                        width: parent.width
                        text: modelData.b
                        color: "#c4a7ff"
                        font.pixelSize: 16
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }
        }
    }
}
