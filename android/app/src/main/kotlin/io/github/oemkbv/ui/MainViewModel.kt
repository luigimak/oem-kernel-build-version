package io.github.oemkbv.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.CreationExtras
import io.github.oemkbv.AppContainer
import io.github.oemkbv.OemKbvApp
import io.github.oemkbv.data.AppUpdate
import io.github.oemkbv.data.Brand
import io.github.oemkbv.data.DeviceId
import io.github.oemkbv.data.Firmware
import io.github.oemkbv.data.UpdateChecker
import io.github.oemkbv.domain.FilterField
import io.github.oemkbv.domain.Filters
import io.github.oemkbv.domain.FirmwareQuery
import io.github.oemkbv.domain.QueryResult
import io.github.oemkbv.domain.Selection
import io.github.oemkbv.domain.Sort
import io.github.oemkbv.domain.SortKey
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** What the settings screen says about the last "Check now". */
enum class UpdateStatus { IDLE, CHECKING, UP_TO_DATE, FAILED }

data class UiState(
  /** `false` until the cached copy has been read: the very first run shows a spinner, later runs the cached list at once. */
  val loaded: Boolean = false,
  val refreshing: Boolean = false,
  val result: QueryResult = QueryResult(Filters(), emptyList(), emptyMap(), 0),
  /** The sort in use: the one the user picked, or the default of the current selection. */
  val sort: Sort = Sort.ForAll,
  val defaultSort: Sort = Sort.ForAll,
  val selection: Selection = Selection.None,
  val allRows: List<Firmware> = emptyList(),
  val failedBrands: Set<Brand> = emptySet(),
  /** Keys of the favorite devices, see [DeviceId.key]. */
  val favorites: Set<String> = emptySet(),
  val notifications: Boolean = true,
  val lastChecked: Long? = null,
  /** Grows every time the user's search and filters are wiped (a new device, "Reset"): screens drop their own copies of them. */
  val epoch: Int = 0,
  /** A published release newer than this app, `null` when there is none (or it is not known yet). */
  val update: AppUpdate? = null,
  /** The user closed the banner of [update]; the settings still show it. */
  val updateDismissed: Boolean = false,
  val updateChecks: Boolean = true,
  val updateStatus: UpdateStatus = UpdateStatus.IDLE,
) {
  val filters: Filters get() = result.filters
}

class MainViewModel(private val container: AppContainer) : ViewModel() {
  private val prefs = container.prefs

  private val rows = MutableStateFlow<List<Firmware>>(emptyList())
  private val loaded = MutableStateFlow(false)
  private val refreshing = MutableStateFlow(false)
  private val failedBrands = MutableStateFlow<Set<Brand>>(emptySet())
  private val filters = MutableStateFlow(Filters())
  /** `null`: the default sort of the selection (newest version for one device, newest kernel build for all). */
  private val sortChoice = MutableStateFlow<Sort?>(null)

  private val query =
    combine(rows, filters, sortChoice, prefs.favorites, prefs.selection) { rows, filters, choice, favorites, selection ->
      val default = defaultSort(selection)
      val sort = choice ?: default
      val device = (selection as? Selection.Device)?.id
      // before the first choice nothing is listed: the home asks for a device
      val result = if (selection is Selection.None) {
        QueryResult(filters, emptyList(), emptyMap(), 0)
      } else {
        FirmwareQuery.run(rows, filters.copy(device = device), sort, favorites)
      }
      Query(rows, result, sort, default, selection, favorites)
    }.flowOn(Dispatchers.Default)

  private val epoch = MutableStateFlow(0)

  /** Read right away, unlike [UiState.epoch] which arrives with the next state: lets a screen tell its saved text is stale. */
  val currentEpoch: Int get() = epoch.value

  private val updateStatus = MutableStateFlow(UpdateStatus.IDLE)

  private class UpdateInfo(val update: AppUpdate?, val dismissed: Boolean, val checks: Boolean, val status: UpdateStatus)

  private val updateInfo = combine(prefs.availableUpdate, prefs.dismissedUpdate, prefs.updateChecks, updateStatus) { available, dismissed, checks, status ->
    // the app may have been updated since the check: a release that is not newer than the running app is nothing to offer
    val update = available?.takeIf { it.isNewerThan(container.appVersion) }
    UpdateInfo(update, update != null && update.version == dismissed, checks, status)
  }

  private class Extras(val notifications: Boolean, val lastChecked: Long?, val epoch: Int, val updates: UpdateInfo)

  private val extras = combine(prefs.notifications, prefs.lastRefresh, epoch, updateInfo, ::Extras)

  val state: StateFlow<UiState> =
    combine(query, loaded, refreshing, failedBrands, extras) { q, loaded, refreshing, failed, extras ->
      UiState(
        loaded = loaded,
        refreshing = refreshing,
        result = q.result,
        sort = q.sort,
        defaultSort = q.defaultSort,
        selection = q.selection,
        allRows = q.rows,
        failedBrands = failed,
        favorites = q.favorites,
        notifications = extras.notifications,
        lastChecked = extras.lastChecked,
        epoch = extras.epoch,
        update = extras.updates.update,
        updateDismissed = extras.updates.dismissed,
        updateChecks = extras.updates.checks,
        updateStatus = extras.updates.status,
      )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), UiState())

  private class Query(val rows: List<Firmware>, val result: QueryResult, val sort: Sort, val defaultSort: Sort, val selection: Selection, val favorites: Set<String>)

  init {
    viewModelScope.launch {
      rows.value = container.repository.loadCached().rows
      loaded.value = true
      refresh()
    }
    // at most once a day, and never in the way of the list
    viewModelScope.launch { container.updates.checkIfDue() }
  }

  /** "Check now" in the settings. */
  fun checkForAppUpdate() {
    if (updateStatus.value == UpdateStatus.CHECKING) return
    updateStatus.value = UpdateStatus.CHECKING
    viewModelScope.launch {
      updateStatus.value = when (container.updates.check()) {
        UpdateChecker.Outcome.FAILED -> UpdateStatus.FAILED
        else -> if (prefs.availableUpdate.value?.isNewerThan(container.appVersion) == true) UpdateStatus.IDLE else UpdateStatus.UP_TO_DATE
      }
    }
  }

  fun setUpdateChecks(on: Boolean) = prefs.setUpdateChecks(on)

  fun dismissUpdate() {
    state.value.update?.let { prefs.dismissUpdate(it.version) }
  }

  fun refresh() {
    if (refreshing.value) return
    refreshing.value = true
    viewModelScope.launch {
      try {
        val result = container.repository.refresh()
        rows.value = result.rows
        failedBrands.value = result.failedBrands
        if (result.failedBrands.size < Brand.entries.size) prefs.setLastRefresh(System.currentTimeMillis())
      } finally {
        refreshing.value = false
      }
    }
  }

  // edits start from the selections actually applied (one that no longer exists was already dropped),
  // but keep the newest text and switches, which the asynchronous query may not have caught up with yet
  private fun edit(block: (Filters) -> Filters) = filters.update { raw -> block(raw.copy(selected = state.value.filters.selected)) }

  fun setQuery(query: String) = edit { it.copy(query = query) }

  fun select(field: FilterField, value: String) = edit { it.with(field, value) }

  fun setShowFailed(on: Boolean) = edit { it.copy(showFailed = on) }

  fun setFavoritesOnly(on: Boolean) = edit { it.copy(favoritesOnly = on) }

  fun sortBy(key: SortKey) = sortChoice.update { choice ->
    val current = choice ?: defaultSort(prefs.selection.value)
    if (current.key == key) current.copy(descending = !current.descending) else Sort(key, descending = key == SortKey.BUILT || key == SortKey.VERSION)
  }

  /** Back to the plain list of the current selection: no search, filters or sort of the user. */
  fun reset() {
    filters.value = Filters()
    sortChoice.value = null
    epoch.update { it + 1 }
  }

  /** A new device (or "all"): what was narrowed down for the previous one does not carry over. */
  fun choose(selection: Selection) {
    filters.update { Filters(showFailed = it.showFailed) }
    sortChoice.value = null
    epoch.update { it + 1 }
    prefs.setSelection(selection)
  }

  private fun defaultSort(selection: Selection) = if (selection is Selection.Device) Sort.ForDevice else Sort.ForAll

  /** Adds the device to the favorites or takes it out; `true` when it is a favorite now. */
  fun toggleFavorite(device: DeviceId): Boolean {
    val add = device.key !in prefs.favorites.value
    setFavorite(device.key, add)
    return add
  }

  fun setFavorite(key: String, favorite: Boolean) {
    // what exists now is not "new": only firmware that appears after it became a favorite is reported
    if (favorite) prefs.markSeen(rows.value.filter { it.deviceId.key == key && it.ok }.map { it.uid })
    prefs.setFavorite(key, favorite)
  }

  fun setNotifications(on: Boolean) = prefs.setNotifications(on)

  companion object {
    val Factory = object : ViewModelProvider.Factory {
      @Suppress("UNCHECKED_CAST")
      override fun <T : ViewModel> create(modelClass: Class<T>, extras: CreationExtras): T {
        val app = extras[ViewModelProvider.AndroidViewModelFactory.APPLICATION_KEY] as OemKbvApp
        return MainViewModel(app.container) as T
      }
    }
  }
}
