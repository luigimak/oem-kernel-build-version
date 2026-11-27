package io.github.oemkbv.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation3.runtime.entryProvider
import androidx.navigation3.ui.NavDisplay
import io.github.oemkbv.data.DeviceId
import io.github.oemkbv.data.Firmware
import io.github.oemkbv.domain.Selection

@Composable
fun AppNavigation(viewModel: MainViewModel) {
  val state by viewModel.state.collectAsStateWithLifecycle()
  val stack = rememberSaveable(saver = Screen.StackSaver) { mutableStateListOf<Screen>(Screen.Main) }
  val context = LocalContext.current
  val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }

  // Android 13+ asks before an app may notify: ask when notifying becomes useful, not at first launch
  fun askToNotify() {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
      ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
    ) {
      permission.launch(Manifest.permission.POST_NOTIFICATIONS)
    }
  }

  fun toggleFavorite(device: DeviceId) {
    if (viewModel.toggleFavorite(device) && viewModel.state.value.notifications) askToNotify()
  }

  val callbacks = remember(viewModel) {
    ListCallbacks(
      onQuery = viewModel::setQuery,
      onSelect = viewModel::select,
      onShowFailed = viewModel::setShowFailed,
      onFavoritesOnly = viewModel::setFavoritesOnly,
      onSort = viewModel::sortBy,
      onReset = viewModel::reset,
      onRefresh = viewModel::refresh,
      onOpen = { stack.add(Screen.Detail(it.uid)) },
      onSettings = { stack.add(Screen.Settings) },
      onPickDevice = { stack.add(Screen.PickBrand) },
      onChoose = viewModel::choose,
      onToggleFavorite = ::toggleFavorite,
      onDismissUpdate = viewModel::dismissUpdate,
      epoch = { viewModel.currentEpoch },
    )
  }

  // what the picker may offer: the firmware the list could show, so no choice ends in an empty list
  val pickable = remember(state.allRows, state.filters.showFailed) { state.allRows.filter { state.filters.showFailed || it.ok } }
  fun back() {
    if (stack.size > 1) stack.removeAt(stack.lastIndex)
  }
  fun choose(selection: Selection) {
    viewModel.choose(selection)
    stack.removeAll { it is Screen.Pick }
  }

  NavDisplay(
    backStack = stack,
    onBack = ::back,
    entryProvider = entryProvider<Screen> {
      entry<Screen.Main> { ListScreen(state, callbacks) }
      entry<Screen.Detail> { key ->
        val row: Firmware? = remember(key.uid, state.allRows) { state.allRows.firstOrNull { it.uid == key.uid } }
        DetailScreen(
          row = row,
          favorite = row != null && row.deviceId.key in state.favorites,
          onBack = ::back,
          onToggleFavorite = ::toggleFavorite,
        )
      }
      entry<Screen.PickBrand> {
        PickBrandScreen(pickable, onBack = ::back, onAll = { choose(Selection.All) }, onBrand = { stack.add(Screen.PickDevice(it)) })
      }
      entry<Screen.PickDevice> { key ->
        PickDeviceScreen(key.brand, pickable, onBack = ::back, onDevice = { stack.add(Screen.PickRegion(key.brand, it)) })
      }
      entry<Screen.PickRegion> { key ->
        PickRegionScreen(key.brand, key.device, pickable, onBack = ::back, onRegion = { choose(Selection.Device(DeviceId(key.brand, key.device, it))) })
      }
      entry<Screen.Settings> {
        SettingsScreen(
          state = state,
          onBack = ::back,
          onNotifications = {
            viewModel.setNotifications(it)
            if (it) askToNotify()
          },
          onRemoveFavorite = { viewModel.setFavorite(it, false) },
          onUpdateChecks = viewModel::setUpdateChecks,
          onCheckUpdates = viewModel::checkForAppUpdate,
        )
      }
    },
  )
}
