package io.github.oemkbv.data

import java.time.DateTimeException
import java.time.LocalDateTime
import java.time.ZoneOffset
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** One data file per brand, as published next to the web table (`<key>.json`). */
enum class Brand(val key: String, val label: String) {
  ONEPLUS("oneplus", "OnePlus"),
  OPPO("oppo", "OPPO"),
  REALME("realme", "Realme"),
}

/** A row of `data/<brand>.json`. Every field is optional so a new or missing field never breaks the whole file. */
@Serializable
data class FirmwareDto(
  val id: String = "",
  val device: String? = null,
  val region: String? = null,
  val model: String? = null,
  val version: String? = null,
  @SerialName("ota_version") val otaVersion: String? = null,
  @SerialName("build_timestamp") val buildTimestamp: String? = null,
  val md5: String? = null,
  val size: Long? = null,
  val ok: Boolean = false,
  @SerialName("android_version") val androidVersion: String? = null,
  @SerialName("linux_version") val linuxVersion: String? = null,
  @SerialName("kernel_release") val kernelRelease: String? = null,
  val build: String? = null,
  val compiler: String? = null,
  val source: String? = null,
  val error: String? = null,
)

/**
 * What a user means by "my device": brand + device + region, e.g. `OnePlus 13 EU`.
 * Two regional variants of the same phone are different devices: they get different firmware.
 */
data class DeviceId(val brand: Brand, val device: String, val region: String) {
  /** Stable text form for storage: `oneplus|13|EU`. */
  val key: String get() = "${brand.key}|$device|$region"

  /** `OnePlus 13 EU` */
  val label: String get() = "${brand.label} $device $region".trim()

  companion object {
    /** The inverse of [key]; `null` for anything else. The device may itself contain `|`, brand and region cannot. */
    fun parse(key: String): DeviceId? {
      val first = key.indexOf('|')
      val last = key.lastIndexOf('|')
      if (first <= 0 || last <= first) return null
      val brand = Brand.entries.firstOrNull { it.key == key.substring(0, first) } ?: return null
      return DeviceId(brand, key.substring(first + 1, last), key.substring(last + 1))
    }
  }
}

/** A firmware row prepared for display, search and sorting. */
data class Firmware(
  val uid: String,
  val brand: Brand,
  val device: String,
  val model: String,
  val region: String,
  val android: String,
  val version: String,
  val otaVersion: String,
  val otaBuilt: String,
  val kernel: String,
  /** `5.10`, `6.6`…: the leading `major.minor` of the kernel release. */
  val branch: String,
  val build: String,
  /** Epoch millis of the kernel build, `null` when the build string has no readable date. */
  val builtMs: Long?,
  val linuxVersion: String,
  val compiler: String,
  val source: String,
  val size: Long,
  val md5: String,
  val error: String,
  val ok: Boolean,
  val haystack: String,
) {
  /** What "follow" refers to: a model code of a brand (the device label is shared by several regional models). */
  val followKey: String get() = followKey(brand, model.ifEmpty { device })

  /** Brand and device as one label ("OnePlus 13R"): the device alone is ambiguous, OnePlus 11 and Realme 11 are both "11". */
  val name: String get() = "${brand.label} ${device.ifEmpty { model }}".trim()

  /** Brand, device and region: the "device" the user picks and follows. */
  val deviceId: DeviceId get() = DeviceId(brand, device.ifEmpty { model }, region)

  companion object {
    fun followKey(brand: Brand, model: String): String = "${brand.key}:$model"
  }
}

private val BRANCH = Regex("""^\d+\.\d+""")

fun FirmwareDto.toFirmware(brand: Brand): Firmware {
  val kernel = kernelRelease.orEmpty()
  val build = build.orEmpty()
  return Firmware(
    uid = "${brand.key}:$id",
    brand = brand,
    device = device.orEmpty(),
    model = model.orEmpty(),
    region = region.orEmpty(),
    android = androidVersion.orEmpty(),
    version = version.orEmpty(),
    otaVersion = otaVersion.orEmpty(),
    otaBuilt = buildTimestamp.orEmpty(),
    kernel = kernel,
    branch = BRANCH.find(kernel)?.value.orEmpty(),
    build = build,
    builtMs = BuildTime.parse(build),
    linuxVersion = linuxVersion.orEmpty(),
    compiler = compiler.orEmpty(),
    source = source.orEmpty(),
    size = size ?: 0L,
    md5 = md5.orEmpty(),
    error = error.orEmpty(),
    ok = ok,
    haystack = listOf(brand.label, device, model, region, version, otaVersion, kernel, build)
      .joinToString(" ") { it.orEmpty() }
      .lowercase(),
  )
}

/** Reads the date of `#1 SMP PREEMPT Mon Dec 25 12:31:09 UTC 2023`, the same way the web table does. */
object BuildTime {
  private val PATTERN = Regex("""([A-Z][a-z]{2}) +(\d{1,2}) (\d\d:\d\d:\d\d) ([A-Z]{2,4}) (\d{4})""")
  private val MONTHS = listOf("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

  // CST: China Standard Time, as in the CN builds
  private val ZONES = mapOf("UTC" to ZoneOffset.UTC, "CST" to ZoneOffset.ofHours(8))

  fun parse(build: String): Long? {
    val m = PATTERN.find(build) ?: return null
    val (month, day, time, zone, year) = m.destructured
    val offset = ZONES[zone] ?: return null
    val monthIndex = MONTHS.indexOf(month).takeIf { it >= 0 } ?: return null
    val (h, min, s) = time.split(':').map { it.toInt() }
    return try {
      LocalDateTime.of(year.toInt(), monthIndex + 1, day.toInt(), h, min, s).toInstant(offset).toEpochMilli()
    } catch (_: DateTimeException) {
      null
    }
  }
}
