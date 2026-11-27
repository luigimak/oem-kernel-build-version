package io.github.oemkbv.ui

import android.Manifest
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.getBoundsInRoot
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import io.github.oemkbv.FakeApi
import io.github.oemkbv.MainActivity
import io.github.oemkbv.OemKbvApp
import io.github.oemkbv.TestApp
import io.github.oemkbv.TestWorld
import io.github.oemkbv.data.Brand
import io.github.oemkbv.data.DeviceId
import io.github.oemkbv.domain.Selection
import io.github.oemkbv.dto
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import org.junit.After
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@RunWith(AndroidJUnit4::class)
// a tall screen: a lazy list only composes the rows in view, and the tests look at all of them
@Config(application = TestApp::class, qualifiers = "w420dp-h3000dp-xxhdpi")
class AppUiTest {
  @get:Rule val rule = createEmptyComposeRule()
  private var scenario: ActivityScenario<MainActivity>? = null
  private val app get() = ApplicationProvider.getApplicationContext<OemKbvApp>()

  @Before
  fun setUp() {
    shadowOf(app).grantPermissions(Manifest.permission.POST_NOTIFICATIONS)
    TestWorld.api = FakeApi().apply {
      publish(
        Brand.ONEPLUS,
        dto("o1", "13", "CPH2655", "EU", "CPH2655_15.0.0.100(EX01)", "15", "6.6.30-android15-8-g1", "#1 SMP PREEMPT Wed Dec 10 04:46:02 UTC 2025"),
        dto("o2", "13", "PJZ110", "CN", "PJZ110_15.0.0.200(CN01)", "15", "6.6.50-android15-8-g2", "#1 SMP PREEMPT Wed Jan 14 04:46:02 UTC 2026"),
        dto("o3", "13", "CPH2655", "IN", "CPH2655_15.0.0.101(EX01)", ok = false),
        dto("o4", "13", "CPH2655", "EU", "CPH2655_16.0.0.200(EX01)", "16", "6.6.50-android15-8-g7", "#1 SMP PREEMPT Mon Mar 30 10:41:25 UTC 2026"),
      )
      publish(Brand.OPPO, dto("p1", "Find X8", "CPH2651", "EU", "CPH2651_15.0.0.50(EX01)", "15", "6.6.30-android15-8-g4"))
      publish(Brand.REALME, dto("r1", "10", "RMX3630", "TH", "RMX3630_14.0.0.200(EX01)", "14", "5.10.198-android12-9-g5"))
    }
  }

  @After
  fun tearDown() {
    scenario?.close()
  }

  /** Most tests look at the classic list of everything; the ones about choosing a device start from [Selection.None]. */
  private fun launch(selection: Selection = Selection.All) {
    app.container.prefs.setSelection(selection)
    scenario = ActivityScenario.launch(MainActivity::class.java)
  }

  private fun waitForList() = rule.waitUntil(10_000) { rule.onAllNodesWithTag("list").fetchSemanticsNodes().isNotEmpty() }

  private fun waitForTag(tag: String) = rule.waitUntil(10_000) { rule.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() }

  private fun back() = scenario!!.onActivity { it.onBackPressedDispatcher.onBackPressed() }

  private fun chooseOp13Eu() {
    rule.onNodeWithTag("device-bar").performClick()
    rule.onNodeWithTag("pick-brand-oneplus").performClick()
    rule.onNodeWithTag("pick-device-13").performClick()
    rule.onNodeWithTag("pick-region-EU").performClick()
    waitForList()
  }

  // ---- the list of everything

  @Test
  fun `lists the firmware and hides the failed ones`() {
    launch()
    waitForList()
    rule.onNodeWithText("5 of 5 firmware").assertIsDisplayed()
    rule.onAllNodesWithTag("row-oneplus:o3").assertCountEquals(0)
    rule.onNodeWithTag("row-oneplus:o2").assertIsDisplayed()
    rule.onNodeWithText("6.6.50-android15-8-g2").assertIsDisplayed()
  }

  @Test
  fun `search narrows the list and reset brings it back`() {
    launch()
    waitForList()
    rule.onNodeWithTag("search").performTextInput("rmx3630")
    rule.waitUntil(5_000) { rule.onAllNodesWithTag("row-oneplus:o1").fetchSemanticsNodes().isEmpty() }
    rule.onNodeWithText("1 of 5 firmware").assertIsDisplayed()
    rule.onNodeWithTag("row-realme:r1").assertIsDisplayed()

    rule.onNodeWithTag("chip-reset").performClick()
    rule.waitUntil(5_000) { rule.onAllNodesWithTag("row-oneplus:o1").fetchSemanticsNodes().isNotEmpty() }
    rule.onNodeWithText("5 of 5 firmware").assertIsDisplayed()
  }

  @Test
  fun `a brand filter limits the device list to that brand`() {
    launch()
    waitForList()
    rule.onNodeWithTag("chip-brand").performClick()
    rule.onNodeWithText("OPPO").performClick()
    rule.waitUntil(5_000) { rule.onAllNodesWithTag("row-oneplus:o1").fetchSemanticsNodes().isEmpty() }
    rule.onNodeWithTag("row-oppo:p1").assertIsDisplayed()

    rule.onNodeWithTag("chip-device").performClick()
    rule.onAllNodesWithText("OPPO Find X8").assertCountEquals(2) // the card and the OPPO device offered by the menu…
    rule.onAllNodesWithText("Realme 10").assertCountEquals(0) // …and not the Realme one, in the menu or in the list
  }

  @Test
  fun `show failed adds the rows without a kernel`() {
    launch()
    waitForList()
    rule.onNodeWithTag("chip-failed").performClick()
    rule.waitUntil(5_000) { rule.onAllNodesWithTag("row-oneplus:o3").fetchSemanticsNodes().isNotEmpty() }
    rule.onNodeWithText("6 of 6 firmware").assertIsDisplayed()
  }

  @Test
  fun `opening a row shows the full Linux version, making its device a favorite is remembered and listed in settings`() {
    launch()
    waitForList()
    rule.onNodeWithTag("row-oneplus:o1").performClick()
    rule.onNodeWithText("Linux version 6.6.30-android15-8-g1", substring = true).assertIsDisplayed()
    rule.onNodeWithTag("copy-linux").performScrollTo().assertIsDisplayed()

    rule.onNodeWithTag("favorite").performClick()
    rule.waitUntil(5_000) { app.container.prefs.favorites.value == setOf("oneplus|13|EU") }
    // what exists at the moment of becoming a favorite is not "new"; 13 CN is another device
    assertEquals(setOf("oneplus:o1", "oneplus:o4"), app.container.prefs.seen)

    back()
    rule.waitUntil(5_000) { rule.onAllNodesWithTag("list").fetchSemanticsNodes().isNotEmpty() }
    rule.onNodeWithTag("chip-favorites").performClick()
    rule.waitUntil(5_000) { rule.onAllNodesWithTag("row-oppo:p1").fetchSemanticsNodes().isEmpty() }
    rule.onNodeWithText("2 of 2 firmware").assertIsDisplayed()

    rule.onNodeWithContentDescription("Settings").performClick()
    rule.onNodeWithText("OnePlus 13 EU").assertIsDisplayed()
  }

  @Test
  fun `the star next to the device makes it a favorite, and favorites are one-tap shortcuts`() {
    launch(Selection.Device(DeviceId(Brand.ONEPLUS, "13", "EU")))
    waitForList()
    rule.onAllNodesWithTag("favorite-oneplus|13|EU").assertCountEquals(0)
    rule.onNodeWithTag("favorite-current").performClick()
    rule.waitUntil(5_000) { app.container.prefs.favorites.value == setOf("oneplus|13|EU") }
    waitForTag("favorite-oneplus|13|EU")

    // another device: the shortcut of the first is still there, one tap away
    rule.onNodeWithTag("device-bar").performClick()
    rule.onNodeWithTag("pick-brand-oneplus").performClick()
    rule.onNodeWithTag("pick-device-13").performClick()
    rule.onNodeWithTag("pick-region-CN").performClick()
    waitForTag("row-oneplus:o2")
    rule.onNodeWithTag("favorite-current").performClick() // now 13 CN is a favorite too
    rule.waitUntil(5_000) { app.container.prefs.favorites.value == setOf("oneplus|13|EU", "oneplus|13|CN") }
    waitForTag("favorite-oneplus|13|CN")

    rule.onNodeWithTag("favorite-oneplus|13|EU").performClick()
    waitForTag("row-oneplus:o4")
    rule.onNodeWithTag("device-bar").assertTextContains("OnePlus 13 EU")
    rule.onAllNodesWithTag("row-oneplus:o2").assertCountEquals(0)
    assertEquals(Selection.Device(DeviceId(Brand.ONEPLUS, "13", "EU")), app.container.prefs.selection.value)

    // settings lists both, and removing one takes its shortcut away
    rule.onNodeWithContentDescription("Settings").performClick()
    rule.onNodeWithText("OnePlus 13 CN").assertIsDisplayed()
    rule.onNodeWithTag("remove-oneplus|13|CN").performClick()
    rule.waitUntil(5_000) { app.container.prefs.favorites.value == setOf("oneplus|13|EU") }
    rule.onAllNodesWithText("OnePlus 13 CN").assertCountEquals(0)
  }

  @Test
  fun `the star takes a favorite out again`() {
    app.container.prefs.setFavorite("oneplus|13|EU", true)
    launch(Selection.Device(DeviceId(Brand.ONEPLUS, "13", "EU")))
    waitForTag("favorite-oneplus|13|EU")
    rule.onNodeWithTag("favorite-current").performClick()
    rule.waitUntil(5_000) { app.container.prefs.favorites.value.isEmpty() }
    rule.onAllNodesWithTag("favorite-oneplus|13|EU").assertCountEquals(0)
  }

  @Test
  fun `a tap on the notification of one device opens that device`() {
    app.container.prefs.setSelection(Selection.All)
    scenario = ActivityScenario.launch(
      android.content.Intent(app, MainActivity::class.java).putExtra(MainActivity.EXTRA_DEVICE, DeviceId(Brand.ONEPLUS, "13", "CN").key),
    )
    waitForTag("row-oneplus:o2")
    rule.onNodeWithTag("device-bar").assertTextContains("OnePlus 13 CN")
    rule.onAllNodesWithTag("row-oneplus:o4").assertCountEquals(0)
  }

  @Test
  fun `a tap on the notification of several devices opens the firmware of the favorites`() {
    app.container.prefs.setFavorite("oneplus|13|CN", true)
    app.container.prefs.setSelection(Selection.Device(DeviceId(Brand.OPPO, "Find X8", "EU")))
    scenario = ActivityScenario.launch(android.content.Intent(app, MainActivity::class.java).putExtra(MainActivity.EXTRA_SHOW_FAVORITES, true))
    waitForTag("row-oneplus:o2")
    rule.onNodeWithTag("device-bar").assertTextContains("All devices")
    rule.onNodeWithText("1 of 1 firmware").assertIsDisplayed()
  }

  @Test
  fun `first run without network says so and works after a retry`() {
    TestWorld.api.failing = Brand.entries.toSet()
    launch()
    rule.waitUntil(10_000) { rule.onAllNodesWithTag("load-failed").fetchSemanticsNodes().isNotEmpty() }

    TestWorld.api.failing = emptySet()
    rule.onNodeWithText("Try again").performClick()
    waitForList()
    rule.onNodeWithText("5 of 5 firmware").assertIsDisplayed()
  }

  @Test
  fun `one brand down shows the list and a warning`() {
    TestWorld.api.failing = setOf(Brand.REALME)
    launch()
    waitForList()
    rule.waitUntil(5_000) { rule.onAllNodesWithTag("partial-failure").fetchSemanticsNodes().isNotEmpty() }
    rule.onNodeWithText("4 of 4 firmware").assertIsDisplayed()
  }

  @Test
  fun `the second start shows the cached list before any network answer`() {
    launch()
    waitForList()
    scenario!!.close()

    TestWorld.api.failing = Brand.entries.toSet() // offline now: the cache of the same app instance is still there
    launch()
    waitForList()
    rule.onNodeWithTag("row-oneplus:o1").assertIsDisplayed()
  }

  @Test
  fun `back on the list leaves the app, back on a detail returns to the list`() {
    launch()
    waitForList()
    rule.onNodeWithTag("row-oneplus:o1").performClick()
    rule.onNodeWithTag("favorite").assertIsDisplayed()
    back()
    waitForList()
    rule.onNodeWithTag("search").assertIsDisplayed()

    // nothing left to go back to: the system must be allowed to close the app
    back()
    var finishing = false
    scenario!!.onActivity { finishing = it.isFinishing }
    assertTrue(finishing, "back at the root of the app was swallowed")
  }

  @Test
  fun `rotation keeps the open detail and the search`() {
    launch()
    waitForList()
    rule.onNodeWithTag("search").performTextInput("oneplus 13")
    rule.waitUntil(5_000) { rule.onAllNodesWithTag("row-oppo:p1").fetchSemanticsNodes().isEmpty() }
    rule.onNodeWithTag("row-oneplus:o1").performClick()
    rule.onNodeWithTag("favorite").assertIsDisplayed()

    scenario!!.recreate()
    rule.onNodeWithTag("favorite").assertIsDisplayed() // still on the detail

    back()
    waitForList()
    rule.onNodeWithText("3 of 5 firmware").assertIsDisplayed() // and the filter is still there
  }

  // ---- choosing a device

  @Test
  fun `first run asks for a device and lists nothing`() {
    launch(Selection.None)
    waitForTag("choose-device")
    rule.onNodeWithTag("device-bar").assertTextContains("Choose a device")
    rule.onAllNodesWithTag("list").assertCountEquals(0)
    rule.onAllNodesWithTag("search").assertCountEquals(0)
  }

  @Test
  fun `brand, device and region lead to that device, newest firmware version first`() {
    launch(Selection.None)
    waitForTag("choose-device")
    chooseOp13Eu()

    rule.onNodeWithTag("device-bar").assertTextContains("OnePlus 13 EU")
    rule.onNodeWithText("2 of 2 firmware").assertIsDisplayed()
    rule.onAllNodesWithTag("row-oneplus:o2").assertCountEquals(0) // 13 CN is another device
    rule.onAllNodesWithTag("row-oneplus:o3").assertCountEquals(0) // 13 IN, and it failed
    val newer = rule.onNodeWithTag("row-oneplus:o4").getBoundsInRoot().top // 16.0.0.200…
    val older = rule.onNodeWithTag("row-oneplus:o1").getBoundsInRoot().top // …before 15.0.0.100
    assertTrue(newer < older, "newest version first")

    // brand, device and region are the choice itself: not offered again as filters
    for (tag in listOf("chip-brand", "chip-device", "chip-region", "chip-favorites")) rule.onAllNodesWithTag(tag).assertCountEquals(0)

    // inside the device, the Android version narrows the list
    rule.onNodeWithTag("chip-android").performClick()
    rule.onNodeWithText("16").performClick()
    rule.waitUntil(5_000) { rule.onAllNodesWithTag("row-oneplus:o1").fetchSemanticsNodes().isEmpty() }
    rule.onNodeWithText("1 of 2 firmware").assertIsDisplayed()
    rule.onNodeWithTag("row-oneplus:o4").assertIsDisplayed()
  }

  @Test
  fun `the picker offers only what the list could show`() {
    launch(Selection.None)
    waitForTag("choose-device")
    rule.onNodeWithTag("device-bar").performClick()
    rule.onNodeWithTag("pick-all").assertIsDisplayed()
    rule.onNodeWithTag("pick-brand-oneplus").performClick()
    rule.onNodeWithTag("pick-device-13").performClick()
    rule.onNodeWithTag("pick-region-EU").assertIsDisplayed()
    rule.onNodeWithTag("pick-region-CN").assertIsDisplayed()
    rule.onAllNodesWithTag("pick-region-IN").assertCountEquals(0) // only failed firmware there
  }

  @Test
  fun `back undoes the steps one by one`() {
    launch(Selection.None)
    waitForTag("choose-device")
    rule.onNodeWithTag("device-bar").performClick()
    rule.onNodeWithTag("pick-brand-oneplus").performClick()
    rule.onNodeWithTag("pick-device-13").performClick()
    rule.onNodeWithTag("pick-region-EU").assertIsDisplayed()

    back()
    rule.onNodeWithTag("pick-search").assertIsDisplayed() // devices of the brand
    back()
    rule.onNodeWithTag("pick-all").assertIsDisplayed() // brands
    back()
    rule.onNodeWithTag("choose-device").assertIsDisplayed() // home, nothing chosen
  }

  @Test
  fun `the picker's device search narrows the devices of a brand`() {
    launch(Selection.None)
    waitForTag("choose-device")
    rule.onNodeWithTag("device-bar").performClick()
    rule.onNodeWithTag("pick-brand-oppo").performClick()
    rule.onNodeWithTag("pick-device-Find X8").assertIsDisplayed()
    rule.onNodeWithTag("pick-search").performTextInput("zzz")
    rule.onNodeWithText("No device matches.").assertIsDisplayed()
    rule.onAllNodesWithTag("pick-device-Find X8").assertCountEquals(0)
  }

  @Test
  fun `all devices from the picker is the classic list`() {
    launch(Selection.None)
    waitForTag("choose-device")
    rule.onNodeWithTag("device-bar").performClick()
    rule.onNodeWithTag("pick-all").performClick()
    waitForList()
    rule.onNodeWithTag("device-bar").assertTextContains("All devices")
    rule.onNodeWithText("5 of 5 firmware").assertIsDisplayed()
    rule.onNodeWithTag("chip-brand").assertIsDisplayed()
  }

  @Test
  fun `the choice is remembered, and a new choice starts with a clean search`() {
    launch(Selection.Device(DeviceId(Brand.ONEPLUS, "13", "EU")))
    waitForList()
    rule.onNodeWithTag("device-bar").assertTextContains("OnePlus 13 EU")
    rule.onNodeWithTag("search").performTextInput("g7")
    rule.waitUntil(5_000) { rule.onAllNodesWithTag("row-oneplus:o1").fetchSemanticsNodes().isEmpty() }
    assertEquals(Selection.Device(DeviceId(Brand.ONEPLUS, "13", "EU")), app.container.prefs.selection.value)

    rule.onNodeWithTag("device-bar").performClick()
    rule.onNodeWithTag("pick-brand-oneplus").performClick()
    rule.onNodeWithTag("pick-device-13").performClick()
    rule.onNodeWithTag("pick-region-CN").performClick()
    waitForTag("row-oneplus:o2")
    rule.onNodeWithTag("device-bar").assertTextContains("OnePlus 13 CN")
    rule.onNodeWithText("1 of 1 firmware").assertIsDisplayed()
    assertEquals(Selection.Device(DeviceId(Brand.ONEPLUS, "13", "CN")), app.container.prefs.selection.value)
    assertEquals("", rule.onNodeWithTag("search").fetchSemanticsNode().config[androidx.compose.ui.semantics.SemanticsProperties.EditableText].text)
  }

  @Test
  fun `rotation keeps the picker step`() {
    launch(Selection.None)
    waitForTag("choose-device")
    rule.onNodeWithTag("device-bar").performClick()
    rule.onNodeWithTag("pick-brand-oneplus").performClick()
    rule.onNodeWithTag("pick-device-13").performClick()
    rule.onNodeWithTag("pick-region-EU").assertIsDisplayed()

    scenario!!.recreate()
    rule.onNodeWithTag("pick-region-EU").assertIsDisplayed()
    rule.onNodeWithTag("pick-region-EU").performClick()
    waitForList()
    rule.onNodeWithTag("device-bar").assertTextContains("OnePlus 13 EU")
  }
}
