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
      publish(Brand.ONEPLUS, dto("o1", "OP 13", "CPH2655", version = "CPH2655_15.0.0.100(EX01)"))
      publish(Brand.OPPO, dto("p1", "Find X8", "CPH2651"))
      publish(Brand.REALME)
    }
  }

  private fun run(): Result = runBlocking { TestListenableWorkerBuilder<CheckNewFirmwareWorker>(app).build().doWork() }

  /** The user follows OP 13 while its first firmware is already known. */
  private fun followOp13() = runBlocking {
    val c = app.container
    val rows = c.repository.refresh().rows
    c.prefs.markSeen(rows.filter { it.followKey == "oneplus:CPH2655" }.map { it.uid })
    c.prefs.setFollowed("oneplus:CPH2655", true)
  }

  @Test
  fun `nothing followed means no network and no notification`() {
    assertEquals(Result.success(), run())
    assertTrue(TestWorld.api.calls.isEmpty())
    assertTrue(notifications.isEmpty())
  }

  @Test
  fun `a new firmware of a followed model is notified once`() {
    followOp13()
    TestWorld.api.publish(
      Brand.ONEPLUS,
      dto("o1", "OP 13", "CPH2655"),
      dto("o9", "OP 13", "CPH2655", version = "CPH2655_15.0.0.200(EX01)", kernel = "6.6.50-android15-8-g9"),
    )
    assertEquals(Result.success(), run())
    val n = notifications.single()
    assertEquals("1 new firmware", n.extras.getString("android.title"))
    assertTrue(n.extras.getString("android.text")!!.contains("CPH2655_15.0.0.200(EX01)"))

    manager.cancelAll()
    assertEquals(Result.success(), run())
    assertTrue(notifications.isEmpty(), "already notified")
  }

  @Test
  fun `other models and failed rows do not notify`() {
    followOp13()
    TestWorld.api.publish(Brand.OPPO, dto("p1", "Find X8", "CPH2651"), dto("p2", "Find X8", "CPH2651", version = "CPH2651_15.0.0.99(EX01)"))
    TestWorld.api.publish(Brand.ONEPLUS, dto("o1", "OP 13", "CPH2655"), dto("o8", "OP 13", "CPH2655", ok = false))
    assertEquals(Result.success(), run())
    assertTrue(notifications.isEmpty())
  }

  @Test
  fun `without the notification permission nothing is lost, it is reported later`() {
    followOp13()
    TestWorld.api.publish(Brand.ONEPLUS, dto("o1", "OP 13", "CPH2655"), dto("o9", "OP 13", "CPH2655", version = "CPH2655_15.0.0.200(EX01)"))
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
