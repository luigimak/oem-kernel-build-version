package io.github.oemkbv.data

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import io.github.oemkbv.TestApp
import io.github.oemkbv.FakeUpdateApi
import io.github.oemkbv.release
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlinx.coroutines.test.runTest
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

@RunWith(AndroidJUnit4::class)
// the test application: the real one starts WorkManager, which Robolectric does not provide
@Config(application = TestApp::class)
class UpdateCheckerTest {
  private val api = FakeUpdateApi()
  private var clock = 1_000_000_000_000L
  private val prefs = AppPrefs(ApplicationProvider.getApplicationContext<Context>().getSharedPreferences("updates-test", Context.MODE_PRIVATE))
  private fun checker(current: String = "1.0.0") = UpdateChecker(api, prefs, current) { clock }

  @Test
  fun `a newer release is remembered, an equal or older one is not`() = runTest {
    api.releases = listOf(release("1.1.0"), release("1.0.0"))
    assertEquals(UpdateChecker.Outcome.CHECKED, checker("1.0.0").check())
    assertEquals("1.1.0", prefs.availableUpdate.value?.version)

    assertEquals(UpdateChecker.Outcome.CHECKED, checker("1.1.0").check())
    assertNull(prefs.availableUpdate.value) // the app was updated: nothing to offer any more
  }

  @Test
  fun `the check on start runs once a day`() = runTest {
    api.releases = listOf(release("1.1.0"))
    val c = checker()
    assertEquals(UpdateChecker.Outcome.CHECKED, c.checkIfDue())
    assertEquals(1, api.calls)

    clock += 23L * 60 * 60 * 1000
    assertEquals(UpdateChecker.Outcome.SKIPPED, c.checkIfDue())
    assertEquals(1, api.calls)

    clock += 2L * 60 * 60 * 1000
    assertEquals(UpdateChecker.Outcome.CHECKED, c.checkIfDue())
    assertEquals(2, api.calls)
  }

  @Test
  fun `switched off means no request on start, but the button still asks`() = runTest {
    prefs.setUpdateChecks(false)
    api.releases = listOf(release("1.1.0"))
    assertEquals(UpdateChecker.Outcome.SKIPPED, checker().checkIfDue())
    assertEquals(0, api.calls)

    assertEquals(UpdateChecker.Outcome.CHECKED, checker().check())
    assertEquals(1, api.calls)
    assertEquals("1.1.0", prefs.availableUpdate.value?.version)
  }

  @Test
  fun `a failed check keeps what was known and is retried at the next start`() = runTest {
    api.releases = listOf(release("1.1.0"))
    checker().checkIfDue()
    clock += 25L * 60 * 60 * 1000

    api.failing = true
    assertEquals(UpdateChecker.Outcome.FAILED, checker().checkIfDue())
    assertEquals("1.1.0", prefs.availableUpdate.value?.version)

    api.failing = false
    assertEquals(UpdateChecker.Outcome.CHECKED, checker().checkIfDue()) // the failure did not count as a check
  }

  @Test
  fun `the choice and the dismissed banner are kept`() {
    prefs.setUpdateChecks(false)
    prefs.dismissUpdate("1.1.0")
    prefs.setAvailableUpdate(AppUpdate("1.1.0", "https://github.com/luigimak/oem-kernel-build-version/releases/tag/app-v1.1.0"))
    val again = AppPrefs(ApplicationProvider.getApplicationContext<Context>().getSharedPreferences("updates-test", Context.MODE_PRIVATE))
    assertEquals(false, again.updateChecks.value)
    assertEquals("1.1.0", again.dismissedUpdate.value)
    assertEquals("1.1.0", again.availableUpdate.value?.version)
  }
}
