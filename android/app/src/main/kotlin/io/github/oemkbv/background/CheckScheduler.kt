package io.github.oemkbv.background

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

object CheckScheduler {
  const val UNIQUE_NAME = "check-new-firmware"

  /** The data is regenerated once a day: twice a day is enough to notice it within hours. */
  private const val PERIOD_HOURS = 12L

  fun sync(context: Context, enabled: Boolean) {
    val wm = WorkManager.getInstance(context)
    if (!enabled) {
      wm.cancelUniqueWork(UNIQUE_NAME)
      return
    }
    val request = PeriodicWorkRequestBuilder<CheckNewFirmwareWorker>(PERIOD_HOURS, TimeUnit.HOURS)
      .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
      .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.MINUTES)
      .build()
    wm.enqueueUniquePeriodicWork(UNIQUE_NAME, ExistingPeriodicWorkPolicy.KEEP, request)
  }
}
