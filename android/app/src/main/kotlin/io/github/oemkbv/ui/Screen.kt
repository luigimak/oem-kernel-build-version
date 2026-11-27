package io.github.oemkbv.ui

import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.runtime.toMutableStateList
import io.github.oemkbv.data.Brand

/** Where the user is. Kept as a plain list so it survives rotation and process death without reflection. */
sealed interface Screen {
  data object Main : Screen

  data object Settings : Screen

  data class Detail(val uid: String) : Screen

  /** Choosing a device takes three screens: brand, device, region. Each one is a step the back button undoes. */
  sealed interface Pick : Screen

  data object PickBrand : Pick

  data class PickDevice(val brand: Brand) : Pick

  data class PickRegion(val brand: Brand, val device: String) : Pick

  companion object {
    private const val DETAIL = "detail:"
    private const val DEVICE = "pick-device:"
    private const val REGION = "pick-region:"

    private fun store(screen: Screen): String =
      when (screen) {
        Main -> "main"
        Settings -> "settings"
        PickBrand -> "pick-brand"
        is Detail -> DETAIL + screen.uid
        is PickDevice -> DEVICE + screen.brand.key
        is PickRegion -> REGION + screen.brand.key + "|" + screen.device
      }

    private fun restore(saved: String): Screen {
      fun brand(key: String) = Brand.entries.firstOrNull { it.key == key }
      return when {
        saved == "settings" -> Settings
        saved == "pick-brand" -> PickBrand
        saved.startsWith(DETAIL) -> Detail(saved.removePrefix(DETAIL))
        saved.startsWith(DEVICE) -> brand(saved.removePrefix(DEVICE))?.let(::PickDevice) ?: Main
        saved.startsWith(REGION) -> {
          val rest = saved.removePrefix(REGION)
          val brand = brand(rest.substringBefore('|'))
          if (brand == null) Main else PickRegion(brand, rest.substringAfter('|'))
        }
        else -> Main
      }
    }

    val StackSaver: Saver<SnapshotStateList<Screen>, List<String>> = Saver(
      save = { stack -> stack.map(::store) },
      restore = { saved -> saved.map(::restore).ifEmpty { listOf(Main) }.toMutableStateList() },
    )
  }
}
