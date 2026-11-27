package io.github.oemkbv.ui

import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import io.github.oemkbv.data.AppUpdate
import io.github.oemkbv.data.Brand
import io.github.oemkbv.data.FirmwareDto
import io.github.oemkbv.data.toFirmware
import io.github.oemkbv.data.DeviceId
import io.github.oemkbv.domain.FilterField
import io.github.oemkbv.domain.Filters
import io.github.oemkbv.domain.FirmwareQuery
import io.github.oemkbv.domain.Selection
import io.github.oemkbv.domain.Sort
import io.github.oemkbv.ui.theme.OEMKernelBuildVersionTheme

private val sample = listOf(
  FirmwareDto(
    id = "1", device = "13", region = "EU", model = "CPH2655", version = "CPH2655_15.0.0.840(EX01)", androidVersion = "15", ok = true,
    kernelRelease = "6.6.30-android15-8-g1d2c3b4a5f6e", build = "#1 SMP PREEMPT Wed Dec 10 04:46:02 UTC 2025", source = "payload.bin", size = 7482806174, md5 = "bec15bb89e84487b104728993feab7df",
    linuxVersion = "Linux version 6.6.30-android15-8-g1d2c3b4a5f6e (build-user@build-host) (Android clang version 18.0.1) #1 SMP PREEMPT Wed Dec 10 04:46:02 UTC 2025",
    compiler = "Android (11368308, +pgo, +bolt, +lto, -mlgo, based on r510928) clang version 18.0.1",
  ).toFirmware(Brand.ONEPLUS),
  FirmwareDto(
    id = "2", device = "Find X8", region = "CN", model = "PKB110", version = "PKB110_15.0.0.401(CN01)", androidVersion = "15", ok = true,
    kernelRelease = "6.6.46-android15-8-g9a8b7c6d5e4f", build = "#1 SMP PREEMPT Thu Jan 14 08:12:44 CST 2026",
  ).toFirmware(Brand.OPPO),
  FirmwareDto(
    id = "3", device = "10", region = "TH", model = "RMX3630", version = "RMX3630_14.0.0.200(EX01)", androidVersion = "14", ok = true,
    kernelRelease = "5.10.198-android12-9-gf7a7af5fc933", build = "#1 SMP PREEMPT Wed Sep 20 05:00:00 UTC 2023",
  ).toFirmware(Brand.REALME),
  FirmwareDto(id = "4", device = "13", region = "IN", model = "CPH2655", version = "CPH2655_15.0.0.101(EX01)", androidVersion = "15", ok = false, error = "link expired")
    .toFirmware(Brand.ONEPLUS),
)

private fun sampleState(selection: Selection = Selection.All, filters: Filters = Filters(showFailed = true)): UiState {
  val device = (selection as? Selection.Device)?.id
  val sort = if (device != null) Sort.ForDevice else Sort.ForAll
  val result = FirmwareQuery.run(sample, filters.copy(device = device), sort, setOf("oneplus|13|EU"))
  return UiState(
    loaded = true, result = result, sort = sort, defaultSort = sort, selection = selection, allRows = sample,
    favorites = setOf("oneplus|13|EU", "oppo|Find X8|CN"), lastChecked = 1_764_000_000_000,
    update = AppUpdate("1.1.0", "https://github.com/luigimak/oem-kernel-build-version/releases/tag/app-v1.1.0"),
  )
}

private val noCallbacks = ListCallbacks({}, { _, _ -> }, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, { 0 })

@Preview(name = "list light", showBackground = true, widthDp = 400, heightDp = 800)
@Composable
private fun ListLight() = OEMKernelBuildVersionTheme(darkTheme = false, dynamicColor = false) { ListScreen(sampleState(Selection.Device(DeviceId(Brand.ONEPLUS, "13", "EU")), Filters()), noCallbacks) }

@Preview(name = "list dark it", showBackground = true, widthDp = 400, heightDp = 800, locale = "it")
@Composable
private fun ListDarkItalian() = OEMKernelBuildVersionTheme(darkTheme = true, dynamicColor = false) {
  ListScreen(sampleState(Selection.All, Filters().with(FilterField.BRAND, "OnePlus")), noCallbacks)
}

@Preview(name = "first run", showBackground = true, widthDp = 400, heightDp = 500)
@Composable
private fun FirstRun() = OEMKernelBuildVersionTheme(darkTheme = false, dynamicColor = false) {
  ListScreen(sampleState(Selection.None, Filters()), noCallbacks)
}

@Preview(name = "detail", showBackground = true, widthDp = 400, heightDp = 900)
@Composable
private fun DetailLight() = OEMKernelBuildVersionTheme(darkTheme = false, dynamicColor = false) {
  DetailScreen(sample.first(), favorite = true, onBack = {}, onToggleFavorite = {})
}

@Preview(name = "settings", showBackground = true, widthDp = 400, heightDp = 800)
@Composable
private fun SettingsLight() = OEMKernelBuildVersionTheme(darkTheme = false, dynamicColor = false) {
  SettingsScreen(sampleState(), onBack = {}, onNotifications = {}, onRemoveFavorite = {}, onUpdateChecks = {}, onCheckUpdates = {})
}
