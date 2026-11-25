package io.github.oemkbv.ui

import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.runtime.toMutableStateList

/** Where the user is. Kept as a plain list so it survives rotation and process death without reflection. */
sealed interface Screen {
  data object Main : Screen

  data object Settings : Screen

  data class Detail(val uid: String) : Screen

  companion object {
    private const val DETAIL = "detail:"

    val StackSaver: Saver<SnapshotStateList<Screen>, List<String>> = Saver(
      save = { stack ->
        stack.map {
          when (it) {
            Main -> "main"
            Settings -> "settings"
            is Detail -> DETAIL + it.uid
          }
        }
      },
      restore = { saved ->
        saved.map {
          when {
            it == "settings" -> Settings
            it.startsWith(DETAIL) -> Detail(it.removePrefix(DETAIL))
            else -> Main
          }
        }.ifEmpty { listOf(Main) }.toMutableStateList()
      },
    )
  }
}
