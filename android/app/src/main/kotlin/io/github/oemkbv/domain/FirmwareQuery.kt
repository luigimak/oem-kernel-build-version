package io.github.oemkbv.domain

import io.github.oemkbv.data.DeviceId
import io.github.oemkbv.data.Firmware

enum class FilterField(val value: (Firmware) -> String) {
  BRAND({ it.brand.label }),
  DEVICE({ it.name }),
  REGION({ it.region }),
  ANDROID({ it.android }),
  BRANCH({ it.branch }),
}

enum class SortKey { BRAND, DEVICE, MODEL, REGION, ANDROID, VERSION, KERNEL, BUILT }

data class Sort(val key: SortKey = SortKey.BUILT, val descending: Boolean = true) {
  companion object {
    /** All firmware of one device: newest firmware version first. */
    val ForDevice = Sort(SortKey.VERSION, descending = true)

    /** Across devices a version number means little: newest kernel build first. */
    val ForAll = Sort(SortKey.BUILT, descending = true)
  }
}

data class Filters(
  val query: String = "",
  val selected: Map<FilterField, String> = emptyMap(),
  val showFailed: Boolean = false,
  val followedOnly: Boolean = false,
  /** Only the firmware of this device (brand + device + region); `null` = all of them. */
  val device: DeviceId? = null,
) {
  operator fun get(field: FilterField): String = selected[field].orEmpty()

  fun with(field: FilterField, value: String): Filters =
    copy(selected = if (value.isEmpty()) selected - field else selected + (field to value))

  /** Nothing narrowed down by the user (the device of the home selection does not count). */
  val isDefault: Boolean get() = copy(device = null) == Filters()
}

data class QueryResult(
  /** The filters actually applied: a selection that no longer exists with the others is dropped. */
  val filters: Filters,
  val rows: List<Firmware>,
  /** For each list, only the values that exist with the *other* filters applied (brand -> its devices, …). */
  val options: Map<FilterField, List<String>>,
  /** Rows before search and selections: what "N of M" counts against. */
  val total: Int,
)

object FirmwareQuery {
  fun run(all: List<Firmware>, filters: Filters, sort: Sort, followed: Set<String>): QueryResult {
    val base = all.filter {
      (filters.showFailed || it.ok) &&
        (!filters.followedOnly || it.followKey in followed) &&
        (filters.device == null || it.deviceId == filters.device)
    }
    val applied = normalize(base, filters)
    val options = FilterField.entries.associateWith { field ->
      base.asSequence()
        .filter { matches(it, applied, except = field) }
        .map(field.value)
        .filter { it.isNotEmpty() }
        .distinct()
        .sortedWith(::naturalCompare)
        .toList()
    }
    val terms = applied.query.trim().lowercase().split(Regex("\\s+")).filter { it.isNotEmpty() }
    val rows = base
      .filter { row -> matches(row, applied, except = null) && terms.all { row.haystack.contains(it) } }
      .sortedWith(comparator(sort))
    return QueryResult(applied, rows, options, base.size)
  }

  private fun matches(row: Firmware, filters: Filters, except: FilterField?): Boolean =
    filters.selected.all { (field, value) -> field == except || field.value(row) == value }

  /** Drops the selections that no row satisfies together with the other ones (e.g. a device of another brand). */
  private fun normalize(base: List<Firmware>, filters: Filters): Filters {
    var current = filters
    repeat(FilterField.entries.size) {
      var changed = false
      for (field in FilterField.entries) {
        val value = current[field]
        if (value.isEmpty()) continue
        if (base.none { field.value(it) == value && matches(it, current, except = field) }) {
          current = current.with(field, "")
          changed = true
        }
      }
      if (!changed) return current
    }
    return current
  }

  fun comparator(sort: Sort): Comparator<Firmware> = Comparator { a, b ->
    val keyA = sortKey(a, sort.key)
    val keyB = sortKey(b, sort.key)
    // rows without a value go last, whatever the direction
    if (keyA == null || keyB == null) return@Comparator if (keyA == keyB) 0 else if (keyA == null) 1 else -1
    val c = when {
      keyA is Long && keyB is Long -> keyA.compareTo(keyB)
      else -> naturalCompare(keyA.toString(), keyB.toString())
    }
    val directed = if (sort.descending) -c else c
    if (directed != 0) directed else naturalCompare(a.version, b.version)
  }

  private fun sortKey(row: Firmware, key: SortKey): Any? =
    when (key) {
      SortKey.BRAND -> row.brand.label
      SortKey.DEVICE -> row.name
      SortKey.MODEL -> row.model
      SortKey.REGION -> row.region
      SortKey.ANDROID -> row.android
      SortKey.VERSION -> versionNumber(row.version)
      SortKey.KERNEL -> row.kernel
      SortKey.BUILT -> row.builtMs
    }?.takeIf { it != "" }
}

/** `CPH2653_16.0.9.401(EX01)` -> `16.0.9.401(EX01)`: the model code in front says nothing about which firmware is newer. */
fun versionNumber(version: String): String = version.substringAfter('_', version)

/** Case-insensitive, digit runs compared as numbers: `A2` < `A10`, `5.10.9` < `5.10.100`. */
fun naturalCompare(a: String, b: String): Int {
  var i = 0
  var j = 0
  while (i < a.length && j < b.length) {
    val ca = a[i]
    val cb = b[j]
    if (ca.isDigit() && cb.isDigit()) {
      var ei = i
      while (ei < a.length && a[ei].isDigit()) ei++
      var ej = j
      while (ej < b.length && b[ej].isDigit()) ej++
      val na = a.substring(i, ei).trimStart('0')
      val nb = b.substring(j, ej).trimStart('0')
      if (na.length != nb.length) return na.length.compareTo(nb.length)
      val c = na.compareTo(nb)
      if (c != 0) return c
      i = ei
      j = ej
    } else {
      val c = ca.lowercaseChar().compareTo(cb.lowercaseChar())
      if (c != 0) return c
      i++
      j++
    }
  }
  return (a.length - i).compareTo(b.length - j)
}

/** Firmware of followed models that were never seen before and now have a kernel string. */
object NewFirmware {
  fun find(rows: List<Firmware>, followed: Set<String>, seen: Set<String>): List<Firmware> =
    rows.filter { it.ok && it.followKey in followed && it.uid !in seen }
}
