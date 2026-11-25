package io.github.oemkbv.background

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import io.github.oemkbv.MainActivity
import io.github.oemkbv.R
import io.github.oemkbv.data.Firmware

class NewFirmwareNotifier(private val context: Context) {
  fun canNotify(): Boolean {
    val allowed = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
      ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
    return allowed && NotificationManagerCompat.from(context).areNotificationsEnabled()
  }

  fun notifyNew(rows: List<Firmware>) {
    if (rows.isEmpty() || !canNotify()) return
    ensureChannel()
    val open = PendingIntent.getActivity(
      context,
      0,
      Intent(context, MainActivity::class.java)
        .putExtra(MainActivity.EXTRA_SHOW_FOLLOWED, true)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
      PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )
    val title = context.resources.getQuantityString(R.plurals.notification_title, rows.size, rows.size)
    val lines = rows.take(MAX_LINES).map { line(it) }
    val style = NotificationCompat.InboxStyle().also { s ->
      lines.forEach(s::addLine)
      if (rows.size > MAX_LINES) s.setSummaryText(context.getString(R.string.notification_more, rows.size - MAX_LINES))
    }
    val notification = NotificationCompat.Builder(context, CHANNEL_ID)
      .setSmallIcon(R.drawable.ic_notification)
      .setContentTitle(title)
      .setContentText(lines.first())
      .setStyle(style)
      .setContentIntent(open)
      .setAutoCancel(true)
      .setOnlyAlertOnce(true)
      .build()
    // canNotify() above is the permission check lint cannot see through
    @Suppress("MissingPermission")
    NotificationManagerCompat.from(context).notify(NOTIFICATION_ID, notification)
  }

  private fun line(row: Firmware): String {
    return "${row.name} · ${row.version} · ${row.kernel}"
  }

  private fun ensureChannel() {
    val channel = NotificationChannel(CHANNEL_ID, context.getString(R.string.channel_name), NotificationManager.IMPORTANCE_DEFAULT)
      .apply { description = context.getString(R.string.channel_description) }
    context.getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
  }

  private companion object {
    const val CHANNEL_ID = "new_firmware"
    const val NOTIFICATION_ID = 1
    const val MAX_LINES = 5
  }
}
