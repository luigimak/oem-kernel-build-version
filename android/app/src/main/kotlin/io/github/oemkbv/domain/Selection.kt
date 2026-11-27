package io.github.oemkbv.domain

import io.github.oemkbv.data.DeviceId

/** What the home screen shows: nothing yet, one device (brand + device + region), or everything. */
sealed interface Selection {
  /** First run: the home asks to pick a device before listing anything. */
  data object None : Selection

  /** The classic table with all firmware, for searches across devices (e.g. "who has kernel 6.6.89?"). */
  data object All : Selection

  data class Device(val id: DeviceId) : Selection

  /** Text form for storage. */
  val stored: String
    get() = when (this) {
      None -> "none"
      All -> "all"
      is Device -> "device:" + id.key
    }

  companion object {
    fun parse(stored: String?): Selection =
      when {
        stored == "all" -> All
        stored != null && stored.startsWith("device:") -> DeviceId.parse(stored.removePrefix("device:"))?.let(::Device) ?: None
        else -> None
      }
  }
}
