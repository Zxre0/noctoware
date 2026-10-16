// Noctoware default Plasma layout: one bottom panel, Noctoware wallpaper.
// Only applied to new users / when the user explicitly applies the layout.
var panel = new Panel;
panel.location = "bottom";
panel.height = 2 * Math.ceil(gridUnit * 2.5 / 2);
panel.addWidget("org.kde.plasma.kickoff").currentConfigGroup = ["General"];
panel.addWidget("org.kde.plasma.pager");
var tasks = panel.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", ["applications:org.kde.dolphin.desktop", "applications:org.kde.konsole.desktop",
                                "applications:firefox.desktop", "applications:steam.desktop",
                                "applications:noctoware-welcome.desktop"]);
panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.kde.plasma.systemtray");
panel.addWidget("org.kde.plasma.digitalclock");
panel.addWidget("org.kde.plasma.showdesktop");

desktopsArray = desktopsForActivity(currentActivity());
for (var j = 0; j < desktopsArray.length; j++) {
    var d = desktopsArray[j];
    d.wallpaperPlugin = "org.kde.image";
    d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    d.writeConfig("Image", "file:///usr/share/wallpapers/Noctoware-Nocturne/");
}
