package io.github.oemkbv

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import io.github.oemkbv.data.DeviceId
import io.github.oemkbv.domain.Selection
import io.github.oemkbv.ui.AppNavigation
import io.github.oemkbv.ui.MainViewModel
import io.github.oemkbv.ui.theme.OEMKernelBuildVersionTheme

class MainActivity : ComponentActivity() {
  private val viewModel by viewModels<MainViewModel> { MainViewModel.Factory }

  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    enableEdgeToEdge()
    if (savedInstanceState == null) handle(intent)
    setContent {
      OEMKernelBuildVersionTheme {
        Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) { AppNavigation(viewModel) }
      }
    }
  }

  override fun onNewIntent(intent: Intent) {
    super.onNewIntent(intent)
    handle(intent)
  }

  /** A tap on the "new firmware" notification opens the device it is about, or the firmware of all the favorites. */
  private fun handle(intent: Intent) {
    val device = intent.getStringExtra(EXTRA_DEVICE)?.let(DeviceId::parse)
    if (device != null) {
      viewModel.choose(Selection.Device(device))
    } else if (intent.getBooleanExtra(EXTRA_SHOW_FAVORITES, false)) {
      viewModel.choose(Selection.All)
      viewModel.setFavoritesOnly(true)
    }
  }

  companion object {
    const val EXTRA_DEVICE = "device"
    const val EXTRA_SHOW_FAVORITES = "show_favorites"
  }
}
