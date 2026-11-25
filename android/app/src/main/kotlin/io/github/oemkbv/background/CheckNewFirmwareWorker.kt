package io.github.oemkbv.background

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import io.github.oemkbv.OemKbvApp
import io.github.oemkbv.data.Brand
import io.github.oemkbv.domain.NewFirmware

/** Refreshes the data in the background and tells the user about firmware of the followed models that are new. */
class CheckNewFirmwareWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
  override suspend fun doWork(): Result {
    val container = (applicationContext as OemKbvApp).container
    val prefs = container.prefs
    val followed = prefs.followed.value
    if (!prefs.notifications.value || followed.isEmpty()) return Result.success()

    val result = container.repository.refresh()
    if (result.failedBrands.size == Brand.entries.size) return Result.retry()
    prefs.setLastRefresh(System.currentTimeMillis())

    val fresh = NewFirmware.find(result.rows, followed, prefs.seen)
    if (fresh.isEmpty()) return Result.success()
    // not allowed to notify (yet): keep them unseen, they are reported as soon as notifications are allowed
    if (!container.notifier.canNotify()) return Result.success()

    container.notifier.notifyNew(fresh)
    prefs.markSeen(fresh.map { it.uid })
    return Result.success()
  }
}
