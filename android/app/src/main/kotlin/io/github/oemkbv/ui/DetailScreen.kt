package io.github.oemkbv.ui

import android.content.ClipData
import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.Star
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.ClipEntry
import androidx.compose.ui.platform.LocalClipboard
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import io.github.oemkbv.R
import io.github.oemkbv.data.Firmware
import java.util.Locale
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DetailScreen(row: Firmware?, followed: Boolean, onBack: () -> Unit, onToggleFollow: (Firmware) -> Unit, modifier: Modifier = Modifier) {
  val snackbar = remember { SnackbarHostState() }
  val scope = rememberCoroutineScope()
  val clipboard = LocalClipboard.current
  val context = LocalContext.current
  val copied = stringResource(R.string.copied)
  val name = row?.let { it.device.ifEmpty { it.model } }.orEmpty()

  fun copy(label: String, text: String) {
    scope.launch {
      clipboard.setClipEntry(ClipEntry(ClipData.newPlainText(label, text)))
      snackbar.showSnackbar(copied)
    }
  }

  Scaffold(
    modifier = modifier,
    snackbarHost = { SnackbarHost(snackbar) },
    topBar = {
      TopAppBar(
        title = { Text(name) },
        navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) } },
        actions = {
          if (row != null) {
            val label = stringResource(if (followed) R.string.unfollow else R.string.follow, row.model.ifEmpty { name })
            IconButton(onClick = { onToggleFollow(row) }, modifier = Modifier.testTag("follow")) {
              Icon(if (followed) Icons.Default.Star else Icons.Outlined.Star, label)
            }
          }
        },
      )
    },
  ) { padding ->
    if (row == null) {
      Column(Modifier.padding(padding).fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(stringResource(R.string.firmware_not_found))
      }
      return@Scaffold
    }
    SelectionContainer {
      Column(
        Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
      ) {
        Field(R.string.field_brand, row.brand.label)
        Field(R.string.field_device, row.device)
        Field(R.string.field_model, row.model)
        Field(R.string.field_region, row.region)
        Field(R.string.field_android, row.android)
        Field(R.string.field_firmware, row.version)
        Field(R.string.field_kernel, row.kernel, mono = true)
        Field(R.string.field_build, row.build, mono = true)
        Field(R.string.field_ota_version, row.otaVersion)
        Field(R.string.field_ota_built, row.otaBuilt)
        Field(R.string.field_linux_version, row.linuxVersion, mono = true)
        Field(R.string.field_compiler, row.compiler, mono = true)
        Field(R.string.field_source, row.source)
        Field(R.string.field_size, if (row.size > 0) stringResource(R.string.size_gib, String.format(Locale.getDefault(), "%.2f", row.size / GIB)) else "")
        Field(R.string.field_md5, row.md5, mono = true)
        Field(R.string.field_error, row.error, mono = true, error = true)

        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
          if (row.linuxVersion.isNotEmpty()) {
            OutlinedButton(onClick = { copy("Linux version", row.linuxVersion) }, modifier = Modifier.testTag("copy-linux")) {
              Text(stringResource(R.string.copy_linux_version))
            }
          }
          if (row.kernel.isNotEmpty()) {
            OutlinedButton(onClick = { copy("Kernel", row.kernel) }, modifier = Modifier.testTag("copy-kernel")) {
              Text(stringResource(R.string.copy_kernel))
            }
          }
          OutlinedButton(onClick = { share(context, row) }, modifier = Modifier.testTag("share")) {
            Icon(Icons.Default.Share, null, Modifier.padding(end = 8.dp))
            Text(stringResource(R.string.share))
          }
        }
      }
    }
  }
}

private const val GIB = 1024.0 * 1024 * 1024

@Composable
private fun Field(label: Int, value: String, mono: Boolean = false, error: Boolean = false) {
  if (value.isEmpty()) return
  Column {
    Text(stringResource(label), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    Text(
      value,
      style = MaterialTheme.typography.bodyMedium,
      fontFamily = if (mono) FontFamily.Monospace else null,
      color = if (error) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
    )
  }
}

private fun share(context: android.content.Context, row: Firmware) {
  val text = buildString {
    append(row.device.ifEmpty { row.model }).append(" (").append(row.model).append(") ").append(row.version)
    if (row.linuxVersion.isNotEmpty()) append('\n').append(row.linuxVersion) else if (row.kernel.isNotEmpty()) append('\n').append(row.kernel)
  }
  val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text)
  context.startActivity(Intent.createChooser(send, null).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
}
