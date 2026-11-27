package io.github.oemkbv.background

import android.Manifest
import android.app.NotificationManager
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.work.ListenableWorker.Result
import androidx.work.testing.TestListenableWorkerBuilder
import io.github.oemkbv.FakeApi
import io.github.oemkbv.OemKbvApp
import io.github.oemkbv.TestApp
import io.github.oemkbv.TestWorld
import io.github.oemkbv.data.Brand
import io.github.oemkbv.data.DeviceId
import io.github.oemkbv.dto
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlinx.coroutines.runBlocking
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@RunWith(AndroidJUnit4::class)
@Config(application = TestApp::class)
class CheckNewFirmwareWorkerTest {
  private val app get() = ApplicationProvider.getApplicationContext<OemKbvApp>()
  private val manager get() = app.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
  private val notifications get() = shadowOf(manager).allNotifications

  @Before
  fun setUp() {
    shadowOf(app).grantPermissions(Manifest.permission.POST_NOTIFICATIONS)
    TestWorld.api = FakeApi().apply {
      publish(Brand.ONEPLUS, dto("o1", "13", "CPH2655", version = "CPH2655_15.0.0.100(EX01)"))
      publish(Brand.OPPO, dto("p1", "Find X8", "CPH2651"))
      publish(Brand.REALME)
    }
  }

  private fun run(): Result = runBlocking { TestListenableWorkerBuilder<CheckNewFirmwareWorker>(app).build().doWork() }

  private val op13 = DeviceId(Brand.ONEPLUS, "13", "EU")

  /** The user makes OnePlus 13 EU a favorite while its first firmware is already known. */
  private fun followOp13() = favorite(op13)

  private fun favorite(device: DeviceId) = runBlocking {
    val c = app.container
    val rows = c.repository.refresh().rows
    c.prefs.markSeen(rows.filter { it.deviceId == device }.map { it.uid })
    c.prefs.setFavorite(device.key, true)
  }

  @Test
  fun `no favorites means no network and no notification`() {
    assertEquals(Result.success(), run())
    assertTrue(TestWorld.api.calls.isEmpty())
    assertTrue(notifications.isEmpty())
  }

  @Test
  fun `a new firmware of a favorite device is notified once`() {
    followOp13()
    TestWorld.api.publish(
      Brand.ONEPLUS,
      dto("o1", "13", "CPH2655"),
      dto("o9", "13", "CPH2655", version = "CPH2655_15.0.0.200(EX01)", kernel = "6.6.50-android15-8-g9"),
    )
    assertEquals(Result.success(), run())
    val n = notifications.single()
    assertEquals("1 new firmware", n.extras.getString("android.title"))
    assertTrue(n.extras.getString("android.text")!!.contains("CPH2655_15.0.0.200(EX01)"))
    // a tap opens that device
    assertEquals(op13.key, shadowOf(n.contentIntent).savedIntent.getStringExtra("device"))

    manager.cancelAll()
    assertEquals(Result.success(), run())
    assertTrue(notifications.isEmpty(), "already notified")
  }

  @Test
  fun `the same phone in another region is another device`() {
    followOp13() // OP 13 EU
    TestWorld.api.publish(
      Brand.ONEPLUS,
      dto("o1", "13", "CPH2655", version = "CPH2655_15.0.0.100(EX01)"),
      dto("o7", "13", "CPH2655", region = "IN", version = "CPH2655_15.0.0.300(IN01)"),
    )
    assertEquals(Result.success(), run())
    assertTrue(notifications.isEmpty())
  }

  @Test
  fun `several devices with news make one notification that opens the favorites`() {
    followOp13()
    favorite(DeviceId(Brand.OPPO, "Find X8", "EU"))
    TestWorld.api.publish(Brand.ONEPLUS, dto("o1", "13", "CPH2655"), dto("o9", "13", "CPH2655", version = "CPH2655_15.0.0.200(EX01)"))
    TestWorld.api.publish(Brand.OPPO, dto("p1", "Find X8", "CPH2651"), dto("p9", "Find X8", "CPH2651", version = "CPH2651_15.0.0.99(EX01)"))
    assertEquals(Result.success(), run())
    val n = notifications.single()
    assertEquals("2 new firmware", n.extras.getString("android.title"))
    val intent = shadowOf(n.contentIntent).savedIntent
    assertEquals(null, intent.getStringExtra("device"))
    assertTrue(intent.getBooleanExtra("show_favorites", false))
  }

  @Test
  fun `other devices and failed rows do not notify`() {
    followOp13()
    TestWorld.api.publish(Brand.OPPO, dto("p1", "Find X8", "CPH2651"), dto("p2", "Find X8", "CPH2651", version = "CPH2651_15.0.0.99(EX01)"))
    TestWorld.api.publish(Brand.ONEPLUS, dto("o1", "13", "CPH2655"), dto("o8", "13", "CPH2655", ok = false))
    assertEquals(Result.success(), run())
    assertTrue(notifications.isEmpty())
  }

  @Test
  fun `without the notification permission nothing is lost, it is reported later`() {
    followOp13()
    TestWorld.api.publish(Brand.ONEPLUS, dto("o1", "13", "CPH2655"), dto("o9", "13", "CPH2655", version = "CPH2655_15.0.0.200(EX01)"))
    shadowOf(app).denyPermissions(Manifest.permission.POST_NOTIFICATIONS)
    assertEquals(Result.success(), run())
    assertTrue(notifications.isEmpty())

    shadowOf(app).grantPermissions(Manifest.permission.POST_NOTIFICATIONS)
    assertEquals(Result.success(), run())
    assertEquals(1, notifications.size)
  }

  @Test
  fun `notifications switched off in the app means no check`() {
    followOp13()
    app.container.prefs.setNotifications(false)
    TestWorld.api.calls.clear()
    assertEquals(Result.success(), run())
    assertTrue(TestWorld.api.calls.isEmpty())
  }

  @Test
  fun `no network anywhere asks to retry`() {
    followOp13()
    TestWorld.api.failing = Brand.entries.toSet()
    assertEquals(Result.retry(), run())
  }
}
