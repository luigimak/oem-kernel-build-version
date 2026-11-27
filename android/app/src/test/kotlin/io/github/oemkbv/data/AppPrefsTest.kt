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
  fun `defaults, then adding and removing favorites is kept across instances`() {
    val p = prefs()
    assertTrue(p.favorites.value.isEmpty())
    assertTrue(p.notifications.value)
    assertNull(p.lastRefresh.value)

    p.setFavorite("oneplus|13|EU", true)
    p.setFavorite("oppo|Find X8|CN", true)
    assertEquals(setOf("oneplus|13|EU", "oppo|Find X8|CN"), prefs().favorites.value)

    p.setFavorite("oppo|Find X8|CN", false)
    assertEquals(setOf("oneplus|13|EU"), prefs().favorites.value)
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
