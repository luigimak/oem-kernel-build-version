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

  /** A tap on the "new firmware" notification opens the list of the followed models. */
  private fun handle(intent: Intent) {
    if (intent.getBooleanExtra(EXTRA_SHOW_FOLLOWED, false)) viewModel.setFollowedOnly(true)
  }

  companion object {
    const val EXTRA_SHOW_FOLLOWED = "show_followed"
  }
}
