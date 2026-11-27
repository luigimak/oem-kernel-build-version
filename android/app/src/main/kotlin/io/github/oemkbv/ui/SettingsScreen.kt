package io.github.oemkbv.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.text.format.DateFormat
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.net.toUri
import androidx.lifecycle.compose.LifecycleResumeEffect
import io.github.oemkbv.BuildConfig
import io.github.oemkbv.R
import io.github.oemkbv.data.DeviceId
import io.github.oemkbv.domain.naturalCompare
import io.github.oemkbv.background.NewFirmwareNotifier
import java.util.Date

private const val REPO_URL = "https://github.com/luigimak/oem-kernel-build-version"

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
  state: UiState,
  onBack: () -> Unit,
  onNotifications: (Boolean) -> Unit,
  onRemoveFavorite: (String) -> Unit,
  modifier: Modifier = Modifier,
) {
  val context = LocalContext.current
  // the user can switch notifications off in the system settings and come back: look again every time the screen resumes
  var resumes by remember { mutableIntStateOf(0) }
  LifecycleResumeEffect(Unit) {
    resumes++
    onPauseOrDispose {}
  }
  val preview = LocalInspectionMode.current // no system services in an IDE preview
  val favoriteLabels = remember(state.favorites) {
    state.favorites.map { it to (DeviceId.parse(it)?.label ?: it) }.sortedWith { a, b -> naturalCompare(a.second, b.second) }
  }
  val blocked = remember(resumes, state.notifications) { !preview && state.notifications && !NewFirmwareNotifier(context).canNotify() }

  Scaffold(
    modifier = modifier,
    topBar = {
      TopAppBar(
        title = { Text(stringResource(R.string.settings)) },
        navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) } },
      )
    },
  ) { padding ->
    Column(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 8.dp)) {
      Row(
        Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(16.dp),
      ) {
        Column(Modifier.weight(1f)) {
          Text(stringResource(R.string.settings_notifications), style = MaterialTheme.typography.titleMedium)
          Text(stringResource(R.string.settings_notifications_summary), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
          if (blocked) {
            Text(
              stringResource(R.string.settings_notifications_denied),
              style = MaterialTheme.typography.bodySmall,
              color = MaterialTheme.colorScheme.error,
              modifier = Modifier.testTag("notifications-blocked").clickable { openNotificationSettings(context) },
            )
          }
        }
        Switch(checked = state.notifications, onCheckedChange = onNotifications, modifier = Modifier.testTag("notifications-switch"))
      }

      Section(R.string.settings_favorites)
      if (state.favorites.isEmpty()) {
        Text(
          stringResource(R.string.settings_favorites_empty),
          style = MaterialTheme.typography.bodyMedium,
          color = MaterialTheme.colorScheme.onSurfaceVariant,
          modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
        )
      }
      for ((key, label) in favoriteLabels) {
        Row(Modifier.fillMaxWidth().padding(start = 16.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
          Text(label, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
          IconButton(onClick = { onRemoveFavorite(key) }, modifier = Modifier.testTag("remove-$key")) { Icon(Icons.Default.Clear, stringResource(R.string.favorite_remove, label)) }
        }
      }

      if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        HorizontalDivider(Modifier.padding(vertical = 8.dp))
        Column(Modifier.fillMaxWidth().clickable { openLanguageSettings(context) }.padding(horizontal = 16.dp, vertical = 8.dp)) {
          Text(stringResource(R.string.settings_language), style = MaterialTheme.typography.titleMedium)
          Text(stringResource(R.string.settings_language_summary), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
      }

      HorizontalDivider(Modifier.padding(vertical = 8.dp))
      Section(R.string.settings_data)
      val checked = state.lastChecked?.let { DateFormat.getMediumDateFormat(context).format(Date(it)) + " " + DateFormat.getTimeFormat(context).format(Date(it)) }
      Text(
        checked?.let { stringResource(R.string.settings_last_checked, it) } ?: stringResource(R.string.settings_never_checked),
        style = MaterialTheme.typography.bodyMedium,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp).testTag("last-checked"),
      )
      Text(
        stringResource(R.string.settings_data_source),
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
      )

      HorizontalDivider(Modifier.padding(vertical = 8.dp))
      Section(R.string.settings_about)
      Text(stringResource(R.string.app_name) + " · " + stringResource(R.string.settings_version, BuildConfig.VERSION_NAME), Modifier.padding(horizontal = 16.dp, vertical = 4.dp))
      Text(
        stringResource(R.string.settings_source_code),
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.clickable { openUrl(context, REPO_URL) }.padding(horizontal = 16.dp, vertical = 8.dp),
      )
      Text(stringResource(R.string.settings_license), Modifier.padding(horizontal = 16.dp, vertical = 4.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
  }
}

@Composable
private fun Section(title: Int) {
  Text(
    stringResource(title),
    style = MaterialTheme.typography.titleSmall,
    color = MaterialTheme.colorScheme.primary,
    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
  )
}

private fun openNotificationSettings(context: Context) {
  val intent = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
  runCatching { context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
}

private fun openLanguageSettings(context: Context) {
  if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
  val intent = Intent(Settings.ACTION_APP_LOCALE_SETTINGS, Uri.fromParts("package", context.packageName, null))
  runCatching { context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
}

private fun openUrl(context: Context, url: String) {
  runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, url.toUri()).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
}
