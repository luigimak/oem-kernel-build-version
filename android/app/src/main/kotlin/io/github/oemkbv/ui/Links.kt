package io.github.oemkbv.ui

import android.content.Context
import android.content.Intent
import androidx.core.net.toUri

/** Opens a web page in the browser; anything that is not https is ignored. */
internal fun openUrl(context: Context, url: String) {
  if (!url.startsWith("https://")) return
  runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, url.toUri()).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
}
