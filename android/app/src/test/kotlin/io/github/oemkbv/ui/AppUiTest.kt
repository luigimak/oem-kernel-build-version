package io.github.oemkbv.ui

import android.Manifest
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
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
      )
      publish(Brand.OPPO, dto("p1", "Find X8", "CPH2651", "EU", "CPH2651_15.0.0.50(EX01)", "15", "6.6.30-android15-8-g4"))
      publish(Brand.REALME, dto("r1", "10", "RMX3630", "TH", "RMX3630_14.0.0.200(EX01)", "14", "5.10.198-android12-9-g5"))
    }
  }

  @After
  fun tearDown() {
    scenario?.close()
  }

  private fun launch() {
    scenario = ActivityScenario.launch(MainActivity::class.java)
  }

  private fun waitForList() = rule.waitUntil(10_000) { rule.onAllNodesWithTag("list").fetchSemanticsNodes().isNotEmpty() }

  private fun back() = scenario!!.onActivity { it.onBackPressedDispatcher.onBackPressed() }

  @Test
  fun `lists the firmware newest first and hides the failed ones`() {
    launch()
    waitForList()
    rule.onNodeWithTag("count").assertIsDisplayed()
    rule.onNodeWithText("4 of 4 firmware").assertIsDisplayed()
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
    rule.onNodeWithText("1 of 4 firmware").assertIsDisplayed()
    rule.onNodeWithTag("row-realme:r1").assertIsDisplayed()

    rule.onNodeWithTag("chip-reset").performClick()
    rule.waitUntil(5_000) { rule.onAllNodesWithTag("row-oneplus:o1").fetchSemanticsNodes().isNotEmpty() }
    rule.onNodeWithText("4 of 4 firmware").assertIsDisplayed()
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
    rule.onNodeWithText("5 of 5 firmware").assertIsDisplayed()
  }

  @Test
  fun `opening a row shows the full Linux version, following it is remembered and listed in settings`() {
    launch()
    waitForList()
    rule.onNodeWithTag("row-oneplus:o1").performClick()
    rule.onNodeWithText("Linux version 6.6.30-android15-8-g1", substring = true).assertIsDisplayed()
    rule.onNodeWithTag("copy-linux").performScrollTo().assertIsDisplayed()

    rule.onNodeWithTag("follow").performClick()
    rule.waitUntil(5_000) { app.container.prefs.followed.value == setOf("oneplus:CPH2655") }
    // what exists at the moment of following is not "new"
    assertEquals(setOf("oneplus:o1"), app.container.prefs.seen)

    back()
    rule.waitUntil(5_000) { rule.onAllNodesWithTag("list").fetchSemanticsNodes().isNotEmpty() }
    rule.onNodeWithTag("chip-followed").performClick()
    rule.waitUntil(5_000) { rule.onAllNodesWithTag("row-oppo:p1").fetchSemanticsNodes().isEmpty() }
    rule.onNodeWithText("1 of 1 firmware").assertIsDisplayed()

    rule.onNodeWithContentDescription("Settings").performClick()
    rule.onNodeWithText("OnePlus 13 (CPH2655)").assertIsDisplayed()
  }

  @Test
  fun `first run without network says so and works after a retry`() {
    TestWorld.api.failing = Brand.entries.toSet()
    launch()
    rule.waitUntil(10_000) { rule.onAllNodesWithTag("load-failed").fetchSemanticsNodes().isNotEmpty() }

    TestWorld.api.failing = emptySet()
    rule.onNodeWithText("Try again").performClick()
    waitForList()
    rule.onNodeWithText("4 of 4 firmware").assertIsDisplayed()
  }

  @Test
  fun `one brand down shows the list and a warning`() {
    TestWorld.api.failing = setOf(Brand.REALME)
    launch()
    waitForList()
    rule.waitUntil(5_000) { rule.onAllNodesWithTag("partial-failure").fetchSemanticsNodes().isNotEmpty() }
    rule.onNodeWithText("3 of 3 firmware").assertIsDisplayed()
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
    rule.onNodeWithTag("follow").assertIsDisplayed()
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
    rule.onNodeWithTag("follow").assertIsDisplayed()

    scenario!!.recreate()
    rule.onNodeWithTag("follow").assertIsDisplayed() // still on the detail

    back()
    waitForList()
    rule.onNodeWithText("2 of 4 firmware").assertIsDisplayed() // and the filter is still there
  }
}
