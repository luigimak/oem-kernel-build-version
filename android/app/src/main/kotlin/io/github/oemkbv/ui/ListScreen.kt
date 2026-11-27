package io.github.oemkbv.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.Star
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.listSaver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import io.github.oemkbv.R
import io.github.oemkbv.data.DeviceId
import io.github.oemkbv.data.Firmware
import io.github.oemkbv.domain.FilterField
import io.github.oemkbv.domain.Selection
import io.github.oemkbv.domain.Sort
import io.github.oemkbv.domain.SortKey
import io.github.oemkbv.domain.naturalCompare

class ListCallbacks(
  val onQuery: (String) -> Unit,
  val onSelect: (FilterField, String) -> Unit,
  val onShowFailed: (Boolean) -> Unit,
  val onFavoritesOnly: (Boolean) -> Unit,
  val onSort: (SortKey) -> Unit,
  val onReset: () -> Unit,
  val onRefresh: () -> Unit,
  val onOpen: (Firmware) -> Unit,
  val onSettings: () -> Unit,
  val onPickDevice: () -> Unit,
  val onChoose: (Selection) -> Unit,
  val onToggleFavorite: (DeviceId) -> Unit,
  /** The ViewModel's current epoch, see [UiState.epoch]. */
  val epoch: () -> Int,
)

private data class SearchText(val epoch: Int, val text: String) {
  companion object {
    val Saver = listSaver<SearchText, Any>(save = { listOf(it.epoch, it.text) }, restore = { SearchText(it[0] as Int, it[1] as String) })
  }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ListScreen(state: UiState, callbacks: ListCallbacks, modifier: Modifier = Modifier) {
  // The search text lives here, not in the asynchronous query state, so typing never lags or jumps. It is tagged with the
  // epoch it was typed in: after a new device or a reset the saved text is stale and reads as empty (a process death
  // starts a new epoch counter, so it empties the search too, which is what the new ViewModel has).
  var typed by rememberSaveable(stateSaver = SearchText.Saver) { mutableStateOf(SearchText(callbacks.epoch(), "")) }
  val text = if (typed.epoch == callbacks.epoch()) typed.text else ""
  Scaffold(
    modifier = modifier,
    topBar = {
      TopAppBar(
        title = { Text(stringResource(R.string.title), maxLines = 1, overflow = TextOverflow.Ellipsis) },
        actions = {
          IconButton(onClick = callbacks.onRefresh) { Icon(Icons.Default.Refresh, stringResource(R.string.refresh)) }
          IconButton(onClick = callbacks.onSettings) { Icon(Icons.Default.Settings, stringResource(R.string.settings)) }
        },
      )
    },
  ) { padding ->
    Column(Modifier.padding(padding).fillMaxSize()) {
      if (state.refreshing) LinearProgressIndicator(Modifier.fillMaxWidth().testTag("refreshing"))
      DeviceBar(state.selection, state.favorites, callbacks.onPickDevice, callbacks.onToggleFavorite)
      FavoriteShortcuts(state.selection, state.favorites, callbacks.onChoose)
      if (state.selection != Selection.None) OutlinedTextField(
        value = text,
        onValueChange = {
          typed = SearchText(callbacks.epoch(), it)
          callbacks.onQuery(it)
        },
        modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp).testTag("search"),
        singleLine = true,
        placeholder = { Text(stringResource(R.string.search_hint), maxLines = 1, overflow = TextOverflow.Ellipsis) },
        leadingIcon = { Icon(Icons.Default.Search, null) },
        trailingIcon = {
          if (text.isNotEmpty()) {
            IconButton(onClick = {
              typed = SearchText(callbacks.epoch(), "")
              callbacks.onQuery("")
            }) { Icon(Icons.Default.Clear, stringResource(R.string.clear_search)) }
          }
        },
      )
      if (state.selection != Selection.None) FilterRow(state, callbacks, onReset = callbacks.onReset)
      Banner(state)
      Content(state, callbacks)
    }
  }
}

/** The device whose firmware the list shows; tap to change it. */
@Composable
private fun DeviceBar(selection: Selection, favorites: Set<String>, onClick: () -> Unit, onToggleFavorite: (DeviceId) -> Unit) {
  val name = when (selection) {
    Selection.None -> stringResource(R.string.choose_device)
    Selection.All -> stringResource(R.string.all_devices)
    is Selection.Device -> selection.id.label
  }
  Card(onClick = onClick, modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp).testTag("device-bar")) {
    Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
      Column(Modifier.weight(1f)) {
        Text(stringResource(R.string.filter_device), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(name, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
      }
      if (selection is Selection.Device) {
        val favorite = selection.id.key in favorites
        IconButton(onClick = { onToggleFavorite(selection.id) }, modifier = Modifier.testTag("favorite-current")) {
          Icon(
            if (favorite) Icons.Default.Star else Icons.Outlined.Star,
            stringResource(if (favorite) R.string.favorite_remove else R.string.favorite_add, selection.id.label),
            tint = if (favorite) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
          )
        }
      }
      Icon(Icons.Default.ArrowDropDown, null)
    }
  }
}

/** The favorites as one-tap choices: switching between the devices one follows should not take three screens. */
@Composable
private fun FavoriteShortcuts(selection: Selection, favorites: Set<String>, onChoose: (Selection) -> Unit) {
  if (favorites.isEmpty()) return
  val devices = remember(favorites) { favorites.mapNotNull(DeviceId::parse).sortedWith { a, b -> naturalCompare(a.label, b.label) } }
  Row(
    Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp),
    horizontalArrangement = Arrangement.spacedBy(8.dp),
  ) {
    for (id in devices) {
      FilterChip(
        selected = selection == Selection.Device(id),
        onClick = { onChoose(Selection.Device(id)) },
        label = { Text(id.label, maxLines = 1) },
        leadingIcon = { Icon(Icons.Default.Star, null) },
        modifier = Modifier.testTag("favorite-${id.key}"),
      )
    }
  }
}

@Composable
private fun FilterRow(state: UiState, callbacks: ListCallbacks, onReset: () -> Unit) {
  val filters = state.filters
  Row(
    Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp),
    horizontalArrangement = Arrangement.spacedBy(8.dp),
    verticalAlignment = Alignment.CenterVertically,
  ) {
    // first, so it is in view as soon as something is filtered
    if (!filters.isDefault || state.sort != state.defaultSort) {
      AssistChip(onClick = onReset, label = { Text(stringResource(R.string.reset)) }, modifier = Modifier.testTag("chip-reset"))
    }
    // one device: brand, device and region are the choice itself, only what varies inside it is offered
    val all = state.selection == Selection.All
    if (all) {
      FilterChip(
        selected = filters.favoritesOnly,
        onClick = { callbacks.onFavoritesOnly(!filters.favoritesOnly) },
        label = { Text(stringResource(R.string.filter_favorites)) },
        leadingIcon = { Icon(Icons.Default.Star, null) },
        modifier = Modifier.testTag("chip-favorites"),
      )
    }
    for (field in if (all) FilterField.entries else listOf(FilterField.ANDROID, FilterField.BRANCH)) {
      DropdownChip(
        label = stringResource(field.label()),
        allLabel = stringResource(field.allLabel()),
        value = filters[field],
        options = state.result.options[field].orEmpty(),
        onSelect = { callbacks.onSelect(field, it) },
        tag = "chip-${field.name.lowercase()}",
      )
    }
    FilterChip(
      selected = filters.showFailed,
      onClick = { callbacks.onShowFailed(!filters.showFailed) },
      label = { Text(stringResource(R.string.filter_failed)) },
      modifier = Modifier.testTag("chip-failed"),
    )
    SortChip(state.sort, callbacks.onSort)
  }
}

@Composable
private fun DropdownChip(label: String, allLabel: String, value: String, options: List<String>, onSelect: (String) -> Unit, tag: String) {
  var open by remember { mutableStateOf(false) }
  Box {
    FilterChip(
      selected = value.isNotEmpty(),
      onClick = { open = true },
      label = { Text(value.ifEmpty { label }, maxLines = 1) },
      trailingIcon = { Icon(Icons.Default.ArrowDropDown, null) },
      modifier = Modifier.testTag(tag),
    )
    DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
      DropdownMenuItem(text = { Text(allLabel) }, onClick = { onSelect(""); open = false })
      for (option in options) {
        DropdownMenuItem(
          text = { Text(option) },
          onClick = { onSelect(option); open = false },
          trailingIcon = { if (option == value) Icon(Icons.Default.Check, null) },
        )
      }
    }
  }
}

@Composable
private fun SortChip(sort: Sort, onSort: (SortKey) -> Unit) {
  var open by remember { mutableStateOf(false) }
  val direction = stringResource(if (sort.descending) R.string.sort_descending else R.string.sort_ascending)
  Box {
    AssistChip(
      onClick = { open = true },
      label = { Text("${stringResource(R.string.sort)}: ${stringResource(sort.key.label())} ($direction)", maxLines = 1) },
      modifier = Modifier.testTag("chip-sort"),
    )
    DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
      for (key in SortKey.entries) {
        DropdownMenuItem(
          text = { Text(stringResource(key.label())) },
          onClick = { onSort(key); open = false },
          trailingIcon = { if (key == sort.key) Icon(Icons.Default.Check, null) },
        )
      }
    }
  }
}

@Composable
private fun Banner(state: UiState) {
  if (state.failedBrands.isNotEmpty() && state.allRows.isNotEmpty()) {
    Text(
      stringResource(R.string.partial_failure, state.failedBrands.joinToString { it.label }),
      color = MaterialTheme.colorScheme.error,
      style = MaterialTheme.typography.bodySmall,
      modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp).testTag("partial-failure"),
    )
  }
  if (state.loaded && state.allRows.isNotEmpty() && state.selection != Selection.None) {
    Text(
      stringResource(R.string.count, state.result.rows.size, state.result.total),
      color = MaterialTheme.colorScheme.onSurfaceVariant,
      style = MaterialTheme.typography.bodySmall,
      modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp).testTag("count"),
    )
  }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Content(state: UiState, callbacks: ListCallbacks) {
  when {
    !state.loaded || (state.allRows.isEmpty() && state.refreshing) -> Centered { CircularProgressIndicator(Modifier.testTag("loading")); Text(stringResource(R.string.loading)) }
    state.allRows.isEmpty() -> Centered {
      Text(stringResource(R.string.load_failed), modifier = Modifier.testTag("load-failed"))
      TextButton(onClick = callbacks.onRefresh) { Text(stringResource(R.string.retry)) }
    }
    state.selection == Selection.None -> Centered {
      Text(stringResource(R.string.choose_device_hint), modifier = Modifier.testTag("choose-device"))
      TextButton(onClick = callbacks.onPickDevice) { Text(stringResource(R.string.choose_device)) }
    }
    else -> PullToRefreshBox(isRefreshing = state.refreshing, onRefresh = callbacks.onRefresh, modifier = Modifier.fillMaxSize()) {
      if (state.result.rows.isEmpty()) {
        val none = if (state.filters.favoritesOnly && state.favorites.isEmpty()) R.string.no_favorites else R.string.no_match
        Centered { Text(stringResource(none), modifier = Modifier.testTag("no-match")) }
      } else {
        LazyColumn(
          modifier = Modifier.fillMaxSize().testTag("list"),
          contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
          verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
          items(state.result.rows, key = { it.uid }) { row ->
            FirmwareCard(row, favorite = row.deviceId.key in state.favorites, onClick = { callbacks.onOpen(row) })
          }
        }
      }
    }
  }
}

@Composable
private fun Centered(content: @Composable () -> Unit) {
  Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
    content()
  }
}

@Composable
fun FirmwareCard(row: Firmware, favorite: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
  Card(onClick = onClick, modifier = modifier.fillMaxWidth().testTag("row-${row.uid}")) {
    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
      Row(verticalAlignment = Alignment.CenterVertically) {
        Text(row.deviceId.label, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
        if (favorite) Icon(Icons.Default.Star, null, tint = MaterialTheme.colorScheme.primary)
      }
      Text(
        // the title already says brand, device and region
        listOf(row.model, if (row.android.isNotEmpty()) stringResource(R.string.android_version, row.android) else "")
          .filter { it.isNotEmpty() }
          .joinToString(" · "),
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
      )
      Text(row.version, style = MaterialTheme.typography.bodyMedium)
      if (row.kernel.isNotEmpty()) {
        Text(row.kernel, style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace)
        if (row.build.isNotEmpty()) {
          Text(row.build, style = MaterialTheme.typography.labelSmall, fontFamily = FontFamily.Monospace, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
      } else {
        Text(stringResource(R.string.failed), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
      }
    }
  }
}

private fun FilterField.label() = when (this) {
  FilterField.BRAND -> R.string.filter_brand
  FilterField.DEVICE -> R.string.filter_device
  FilterField.REGION -> R.string.filter_region
  FilterField.ANDROID -> R.string.filter_android
  FilterField.BRANCH -> R.string.filter_kernel
}

private fun FilterField.allLabel() = when (this) {
  FilterField.BRAND -> R.string.all_brands
  FilterField.DEVICE -> R.string.all_devices
  FilterField.REGION -> R.string.all_regions
  FilterField.ANDROID -> R.string.all_android
  FilterField.BRANCH -> R.string.all_kernels
}

private fun SortKey.label() = when (this) {
  SortKey.BRAND -> R.string.sort_brand
  SortKey.DEVICE -> R.string.sort_device
  SortKey.MODEL -> R.string.sort_model
  SortKey.REGION -> R.string.sort_region
  SortKey.ANDROID -> R.string.sort_android
  SortKey.VERSION -> R.string.sort_firmware
  SortKey.KERNEL -> R.string.sort_kernel
  SortKey.BUILT -> R.string.sort_built
}
