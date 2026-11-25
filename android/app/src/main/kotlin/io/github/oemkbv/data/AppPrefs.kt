package io.github.oemkbv.data

import android.content.SharedPreferences
import androidx.core.content.edit
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/** What the user chose (followed models, notifications) and what was already notified, kept in plain SharedPreferences. */
class AppPrefs(private val sp: SharedPreferences) {
  private val followedState = MutableStateFlow(sp.getStringSet(FOLLOWED, null).orEmpty().toSet())
  private val notifyState = MutableStateFlow(sp.getBoolean(NOTIFY, true))
  private val refreshedState = MutableStateFlow(sp.getLong(REFRESHED, 0L).takeIf { it > 0 })

  /** Follow keys (`brand:model`), see [Firmware.followKey]. */
  val followed: StateFlow<Set<String>> = followedState
  val notifications: StateFlow<Boolean> = notifyState

  /** Epoch millis of the last successful refresh of any brand, `null` before the first one. */
  val lastRefresh: StateFlow<Long?> = refreshedState

  val seen: Set<String> get() = sp.getStringSet(SEEN, null).orEmpty().toSet()

  fun setFollowed(key: String, follow: Boolean) {
    val next = if (follow) followedState.value + key else followedState.value - key
    sp.edit { putStringSet(FOLLOWED, next) }
    followedState.value = next
  }

  fun setNotifications(on: Boolean) {
    sp.edit { putBoolean(NOTIFY, on) }
    notifyState.value = on
  }

  fun markSeen(uids: Collection<String>) {
    if (uids.isEmpty()) return
    sp.edit { putStringSet(SEEN, seen + uids) }
  }

  fun setLastRefresh(millis: Long) {
    sp.edit { putLong(REFRESHED, millis) }
    refreshedState.value = millis
  }

  private companion object {
    const val FOLLOWED = "followed"
    const val NOTIFY = "notifications"
    const val SEEN = "seen"
    const val REFRESHED = "refreshed"
  }
}
