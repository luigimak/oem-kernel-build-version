package io.github.oemkbv.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import io.github.oemkbv.R
import io.github.oemkbv.data.Brand
import io.github.oemkbv.data.Firmware
import io.github.oemkbv.domain.naturalCompare

/**
 * The three steps that pick a device, each on its own screen (brand, then device, then region).
 * [rows] are the firmware the list could show: the picker never offers a choice that would lead to an empty list.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PickerScaffold(title: String, onBack: () -> Unit, content: @Composable () -> Unit) {
  Scaffold(
    topBar = {
      TopAppBar(
        title = { Text(title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
        navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) } },
      )
    },
  ) { padding ->
    Column(Modifier.padding(padding).fillMaxSize()) { content() }
  }
}

@Composable
fun PickBrandScreen(rows: List<Firmware>, onBack: () -> Unit, onAll: () -> Unit, onBrand: (Brand) -> Unit) {
  val devices = remember(rows) { rows.groupBy { it.brand }.mapValues { (_, r) -> r.map { it.device }.toSet().size } }
  PickerScaffold(stringResource(R.string.picker_title), onBack) {
    LazyColumn(Modifier.fillMaxSize()) {
      item {
        ListItem(
          headlineContent = { Text(stringResource(R.string.all_devices)) },
          supportingContent = { Text(stringResource(R.string.picker_all_hint)) },
          modifier = Modifier.clickable(onClick = onAll).testTag("pick-all"),
        )
        HorizontalDivider()
      }
      items(Brand.entries.filter { it in devices }, key = { it.key }) { brand ->
        val count = devices.getValue(brand)
        ListItem(
          headlineContent = { Text(brand.label) },
          supportingContent = { Text(pluralStringResource(R.plurals.devices_count, count, count)) },
          modifier = Modifier.clickable { onBrand(brand) }.testTag("pick-brand-${brand.key}"),
        )
      }
    }
  }
}

@Composable
fun PickDeviceScreen(brand: Brand, rows: List<Firmware>, onBack: () -> Unit, onDevice: (String) -> Unit) {
  var text by rememberSaveable { mutableStateOf("") }
  val regions = remember(rows, brand) {
    rows.filter { it.brand == brand }.groupBy { it.deviceId.device }.mapValues { (_, r) -> r.map { it.region }.toSet().size }
  }
  val shown = remember(regions, text) {
    val terms = text.trim().lowercase().split(Regex("\\s+")).filter { it.isNotEmpty() }
    regions.keys.filter { d -> terms.all { d.lowercase().contains(it) } }.sortedWith(::naturalCompare)
  }
  PickerScaffold(brand.label, onBack) {
    OutlinedTextField(
      value = text,
      onValueChange = { text = it },
      modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp).testTag("pick-search"),
      singleLine = true,
      placeholder = { Text(stringResource(R.string.picker_search), maxLines = 1, overflow = TextOverflow.Ellipsis) },
      leadingIcon = { Icon(Icons.Default.Search, null) },
      trailingIcon = {
        if (text.isNotEmpty()) IconButton(onClick = { text = "" }) { Icon(Icons.Default.Clear, stringResource(R.string.clear_search)) }
      },
    )
    if (shown.isEmpty()) {
      Text(stringResource(R.string.picker_no_match), Modifier.padding(24.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    LazyColumn(Modifier.fillMaxSize()) {
      items(shown, key = { it }) { device ->
        val count = regions.getValue(device)
        ListItem(
          headlineContent = { Text(device) },
          supportingContent = { Text(pluralStringResource(R.plurals.regions_count, count, count)) },
          modifier = Modifier.clickable { onDevice(device) }.testTag("pick-device-$device"),
        )
      }
    }
  }
}

@Composable
fun PickRegionScreen(brand: Brand, device: String, rows: List<Firmware>, onBack: () -> Unit, onRegion: (String) -> Unit) {
  val regions = remember(rows, brand, device) {
    rows.filter { it.brand == brand && it.deviceId.device == device }.groupBy { it.region }.mapValues { (_, r) -> r.size }
  }
  PickerScaffold("${brand.label} $device", onBack) {
    LazyColumn(Modifier.fillMaxSize()) {
      items(regions.keys.sortedWith(::naturalCompare), key = { it }) { region ->
        val count = regions.getValue(region)
        ListItem(
          headlineContent = { Text(region.ifEmpty { "—" }) },
          supportingContent = { Text(pluralStringResource(R.plurals.firmware_count, count, count)) },
          modifier = Modifier.clickable { onRegion(region) }.testTag("pick-region-$region"),
        )
      }
    }
  }
}
