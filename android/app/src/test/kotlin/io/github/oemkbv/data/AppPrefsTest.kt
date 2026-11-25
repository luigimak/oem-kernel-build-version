package io.github.oemkbv.data

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class AppPrefsTest {
  private fun prefs() = AppPrefs(ApplicationProvider.getApplicationContext<Context>().getSharedPreferences("test", Context.MODE_PRIVATE))

  @Test
  fun `defaults, then follow and unfollow are kept across instances`() {
    val p = prefs()
    assertTrue(p.followed.value.isEmpty())
    assertTrue(p.notifications.value)
    assertNull(p.lastRefresh.value)

    p.setFollowed("oneplus:CPH2655", true)
    p.setFollowed("oppo:CPH2651", true)
    assertEquals(setOf("oneplus:CPH2655", "oppo:CPH2651"), prefs().followed.value)

    p.setFollowed("oppo:CPH2651", false)
    assertEquals(setOf("oneplus:CPH2655"), prefs().followed.value)
  }

  @Test
  fun `seen ids only grow`() {
    val p = prefs()
    p.markSeen(listOf("a", "b"))
    p.markSeen(listOf("b", "c"))
    p.markSeen(emptyList())
    assertEquals(setOf("a", "b", "c"), prefs().seen)
  }

  @Test
  fun `notifications switch and last refresh are kept`() {
    val p = prefs()
    p.setNotifications(false)
    p.setLastRefresh(1234L)
    val again = prefs()
    assertEquals(false, again.notifications.value)
    assertEquals(1234L, again.lastRefresh.value)
  }
}
