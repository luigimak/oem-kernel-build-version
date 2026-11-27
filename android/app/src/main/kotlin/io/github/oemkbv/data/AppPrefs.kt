package io.github.oemkbv.data

import android.content.SharedPreferences
import androidx.core.content.edit
import io.github.oemkbv.domain.Selection
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/** What the user chose (favorite devices, notifications, update checks) and what was already notified, kept in plain SharedPreferences. */
class AppPrefs(private val sp: SharedPreferences) {
  private val favoritesState = MutableStateFlow(sp.getStringSet(FAVORITES, null).orEmpty().toSet())
  private val notifyState = MutableStateFlow(sp.getBoolean(NOTIFY, true))
  private val refreshedState = MutableStateFlow(sp.getLong(REFRESHED, 0L).takeIf { it > 0 })
  private val selectionState = MutableStateFlow(Selection.parse(sp.getString(SELECTION, null)))
  private val updateChecksState = MutableStateFlow(sp.getBoolean(UPDATE_CHECKS, true))
  private val availableUpdateState = MutableStateFlow(sp.getString(UPDATE_AVAILABLE, null)?.let(::parseUpdate))
  private val dismissedUpdateState = MutableStateFlow(sp.getString(UPDATE_DISMISSED, null))

  /** Keys (`brand|device|region`, see [DeviceId.key]) of the favorite devices: the ones notified about. */
  val favorites: StateFlow<Set<String>> = favoritesState
  val notifications: StateFlow<Boolean> = notifyState

  /** Epoch millis of the last successful refresh of any brand, `null` before the first one. */
  val lastRefresh: StateFlow<Long?> = refreshedState

  /** What the home screen shows; remembered between runs. */
  val selection: StateFlow<Selection> = selectionState

  /** Whether the app may ask GitHub, once a day, for a newer release of itself. */
  val updateChecks: StateFlow<Boolean> = updateChecksState

  /** The newer release found by the last check, if any (it may be older than the running app by now: compare before showing). */
  val availableUpdate: StateFlow<AppUpdate?> = availableUpdateState

  /** The version whose banner the user closed. */
  val dismissedUpdate: StateFlow<String?> = dismissedUpdateState

  /** Epoch millis of the last answered update check, `0` before the first. */
  val lastUpdateCheck: Long get() = sp.getLong(UPDATE_LAST_CHECK, 0L)

  val seen: Set<String> get() = sp.getStringSet(SEEN, null).orEmpty().toSet()

  fun setFavorite(key: String, favorite: Boolean) {
    val next = if (favorite) favoritesState.value + key else favoritesState.value - key
    sp.edit { putStringSet(FAVORITES, next) }
    favoritesState.value = next
  }

  fun setSelection(selection: Selection) {
    sp.edit { putString(SELECTION, selection.stored) }
    selectionState.value = selection
  }

  fun setNotifications(on: Boolean) {
    sp.edit { putBoolean(NOTIFY, on) }
    notifyState.value = on
  }

  fun setUpdateChecks(on: Boolean) {
    sp.edit { putBoolean(UPDATE_CHECKS, on) }
    updateChecksState.value = on
  }

  fun setAvailableUpdate(update: AppUpdate?) {
    sp.edit { if (update == null) remove(UPDATE_AVAILABLE) else putString(UPDATE_AVAILABLE, update.version + "|" + update.url) }
    availableUpdateState.value = update
  }

  fun dismissUpdate(version: String) {
    sp.edit { putString(UPDATE_DISMISSED, version) }
    dismissedUpdateState.value = version
  }

  fun setLastUpdateCheck(millis: Long) {
    sp.edit { putLong(UPDATE_LAST_CHECK, millis) }
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
    const val FAVORITES = "favorites"
    const val NOTIFY = "notifications"
    const val SEEN = "seen"
    const val REFRESHED = "refreshed"
    const val SELECTION = "selection"
    const val UPDATE_CHECKS = "update_checks"
    const val UPDATE_AVAILABLE = "update_available"
    const val UPDATE_DISMISSED = "update_dismissed"
    const val UPDATE_LAST_CHECK = "update_last_check"

    fun parseUpdate(stored: String): AppUpdate? = stored.substringBefore('|', "").takeIf { it.isNotEmpty() }?.let { AppUpdate(it, stored.substringAfter('|')) }
  }
}
