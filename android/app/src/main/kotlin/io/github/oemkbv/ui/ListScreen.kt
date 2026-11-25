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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
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
import io.github.oemkbv.data.Firmware
import io.github.oemkbv.domain.FilterField
import io.github.oemkbv.domain.Sort
import io.github.oemkbv.domain.SortKey

class ListCallbacks(
  val onQuery: (String) -> Unit,
  val onSelect: (FilterField, String) -> Unit,
  val onShowFailed: (Boolean) -> Unit,
  val onFollowedOnly: (Boolean) -> Unit,
  val onSort: (SortKey) -> Unit,
  val onReset: () -> Unit,
  val onRefresh: () -> Unit,
  val onOpen: (Firmware) -> Unit,
  val onSettings: () -> Unit,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ListScreen(state: UiState, callbacks: ListCallbacks, modifier: Modifier = Modifier) {
  // the text lives here, not in the asynchronous query state, so typing never lags or jumps
  var text by rememberSaveable { mutableStateOf(state.filters.query) }
  // after process death the text comes back but the ViewModel is new: hand it the restored text (a no-op otherwise)
  LaunchedEffect(Unit) { if (text.isNotEmpty()) callbacks.onQuery(text) }
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
      OutlinedTextField(
        value = text,
        onValueChange = {
          text = it
          callbacks.onQuery(it)
        },
        modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp).testTag("search"),
        singleLine = true,
        placeholder = { Text(stringResource(R.string.search_hint), maxLines = 1, overflow = TextOverflow.Ellipsis) },
        leadingIcon = { Icon(Icons.Default.Search, null) },
        trailingIcon = {
          if (text.isNotEmpty()) {
            IconButton(onClick = {
              text = ""
              callbacks.onQuery("")
            }) { Icon(Icons.Default.Clear, stringResource(R.string.clear_search)) }
          }
        },
      )
      FilterRow(state, callbacks, onReset = {
        text = ""
        callbacks.onReset()
      })
      Banner(state)
      Content(state, callbacks)
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
    if (!filters.isDefault || state.sort != Sort()) {
      AssistChip(onClick = onReset, label = { Text(stringResource(R.string.reset)) }, modifier = Modifier.testTag("chip-reset"))
    }
    FilterChip(
      selected = filters.followedOnly,
      onClick = { callbacks.onFollowedOnly(!filters.followedOnly) },
      label = { Text(stringResource(R.string.filter_followed)) },
      leadingIcon = { Icon(Icons.Default.Star, null) },
      modifier = Modifier.testTag("chip-followed"),
    )
    for (field in FilterField.entries) {
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
  if (state.loaded && state.allRows.isNotEmpty()) {
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
    else -> PullToRefreshBox(isRefreshing = state.refreshing, onRefresh = callbacks.onRefresh, modifier = Modifier.fillMaxSize()) {
      if (state.result.rows.isEmpty()) {
        val none = if (state.filters.followedOnly && state.followed.isEmpty()) R.string.no_followed else R.string.no_match
        Centered { Text(stringResource(none), modifier = Modifier.testTag("no-match")) }
      } else {
        LazyColumn(
          modifier = Modifier.fillMaxSize().testTag("list"),
          contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
          verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
          items(state.result.rows, key = { it.uid }) { row ->
            FirmwareCard(row, followed = row.followKey in state.followed, onClick = { callbacks.onOpen(row) })
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
fun FirmwareCard(row: Firmware, followed: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
  Card(onClick = onClick, modifier = modifier.fillMaxWidth().testTag("row-${row.uid}")) {
    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
      Row(verticalAlignment = Alignment.CenterVertically) {
        Text(row.name, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
        if (followed) Icon(Icons.Default.Star, null, tint = MaterialTheme.colorScheme.primary)
      }
      Text(
        listOf(row.model, row.region).filter { it.isNotEmpty() }.joinToString(" · ") +
          if (row.android.isNotEmpty()) " · " + stringResource(R.string.android_version, row.android) else "",
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
