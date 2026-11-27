package io.github.oemkbv.data

import android.content.SharedPreferences
import androidx.core.content.edit
import io.github.oemkbv.domain.Selection
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/** What the user chose (favorite devices, notifications) and what was already notified, kept in plain SharedPreferences. */
class AppPrefs(private val sp: SharedPreferences) {
  private val favoritesState = MutableStateFlow(sp.getStringSet(FAVORITES, null).orEmpty().toSet())
  private val notifyState = MutableStateFlow(sp.getBoolean(NOTIFY, true))
  private val refreshedState = MutableStateFlow(sp.getLong(REFRESHED, 0L).takeIf { it > 0 })
  private val selectionState = MutableStateFlow(Selection.parse(sp.getString(SELECTION, null)))

  /** Keys (`brand|device|region`, see [DeviceId.key]) of the favorite devices: the ones notified about. */
  val favorites: StateFlow<Set<String>> = favoritesState
  val notifications: StateFlow<Boolean> = notifyState

  /** Epoch millis of the last successful refresh of any brand, `null` before the first one. */
  val lastRefresh: StateFlow<Long?> = refreshedState

  /** What the home screen shows; remembered between runs. */
  val selection: StateFlow<Selection> = selectionState

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
  }
}
