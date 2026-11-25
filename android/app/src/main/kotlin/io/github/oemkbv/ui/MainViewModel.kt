package io.github.oemkbv.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.CreationExtras
import io.github.oemkbv.AppContainer
import io.github.oemkbv.OemKbvApp
import io.github.oemkbv.data.Brand
import io.github.oemkbv.data.Firmware
import io.github.oemkbv.domain.FilterField
import io.github.oemkbv.domain.Filters
import io.github.oemkbv.domain.FirmwareQuery
import io.github.oemkbv.domain.QueryResult
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

data class UiState(
  /** `false` until the cached copy has been read: the very first run shows a spinner, later runs the cached list at once. */
  val loaded: Boolean = false,
  val refreshing: Boolean = false,
  val result: QueryResult = QueryResult(Filters(), emptyList(), emptyMap(), 0),
  val sort: Sort = Sort(),
  val allRows: List<Firmware> = emptyList(),
  val failedBrands: Set<Brand> = emptySet(),
  val followed: Set<String> = emptySet(),
  val notifications: Boolean = true,
  val lastChecked: Long? = null,
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
  private val sort = MutableStateFlow(Sort())

  private val query =
    combine(rows, filters, sort, prefs.followed) { rows, filters, sort, followed ->
      Query(rows, FirmwareQuery.run(rows, filters, sort, followed), sort, followed)
    }.flowOn(Dispatchers.Default)

  private val prefsState = combine(prefs.notifications, prefs.lastRefresh) { notifications, lastChecked -> notifications to lastChecked }

  val state: StateFlow<UiState> =
    combine(query, loaded, refreshing, failedBrands, prefsState) { q, loaded, refreshing, failed, (notifications, lastChecked) ->
      UiState(
        loaded = loaded,
        refreshing = refreshing,
        result = q.result,
        sort = q.sort,
        allRows = q.rows,
        failedBrands = failed,
        followed = q.followed,
        notifications = notifications,
        lastChecked = lastChecked,
      )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), UiState())

  private class Query(val rows: List<Firmware>, val result: QueryResult, val sort: Sort, val followed: Set<String>)

  init {
    viewModelScope.launch {
      rows.value = container.repository.loadCached().rows
      loaded.value = true
      refresh()
    }
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

  fun setFollowedOnly(on: Boolean) = edit { it.copy(followedOnly = on) }

  fun sortBy(key: SortKey) = sort.update { if (it.key == key) it.copy(descending = !it.descending) else Sort(key, descending = key == SortKey.BUILT) }

  fun reset() {
    filters.value = Filters()
    sort.value = Sort()
  }

  fun toggleFollow(row: Firmware) = setFollowed(row.followKey, row.followKey !in prefs.followed.value)

  fun setFollowed(key: String, follow: Boolean) {
    // what exists now is not "new": only firmware that appears after the follow is reported
    if (follow) prefs.markSeen(rows.value.filter { it.followKey == key && it.ok }.map { it.uid })
    prefs.setFollowed(key, follow)
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
