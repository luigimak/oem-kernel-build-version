package io.github.oemkbv.domain

import io.github.oemkbv.data.Brand
import io.github.oemkbv.data.Firmware
import io.github.oemkbv.data.toFirmware
import io.github.oemkbv.dto
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class FirmwareQueryTest {
  private val rows: List<Firmware> = listOf(
    dto("1", "OP 13", "CPH2655", "EU", "CPH2655_15.0.0.100(EX01)", "15", "6.6.30-android15-8-g1", "#1 SMP PREEMPT Wed Dec 10 04:46:02 UTC 2025").toFirmware(Brand.ONEPLUS),
    dto("2", "OP 13", "PJZ110", "CN", "PJZ110_15.0.0.200(CN01)", "15", "6.6.50-android15-8-g2", "#1 SMP PREEMPT Wed Jan 14 04:46:02 UTC 2026").toFirmware(Brand.ONEPLUS),
    dto("3", "OP 10 Pro", "NE2210", "GLO", "NE2210_14.0.0.9(EX01)", "14", "5.10.209-android12-9-g3", "#1 SMP PREEMPT Mon Dec 25 12:31:09 UTC 2023").toFirmware(Brand.ONEPLUS),
    dto("4", "Find X8", "CPH2651", "EU", "CPH2651_15.0.0.50(EX01)", "15", "6.6.30-android15-8-g4", "#1 SMP PREEMPT Wed Dec 10 05:00:00 UTC 2025").toFirmware(Brand.OPPO),
    dto("5", "Realme 10", "RMX3630", "TH", "RMX3630_14.0.0.200(EX01)", "14", "5.10.198-android12-9-g5", "#1 SMP PREEMPT Wed Sep 20 05:00:00 UTC 2023").toFirmware(Brand.REALME),
    dto("6", "OP 13", "CPH2655", "IN", "CPH2655_15.0.0.101(EX01)", ok = false).toFirmware(Brand.ONEPLUS),
  )

  private fun run(filters: Filters = Filters(), sort: Sort = Sort(), followed: Set<String> = emptySet()) =
    FirmwareQuery.run(rows, filters, sort, followed)

  private fun ids(r: QueryResult) = r.rows.map { it.uid.substringAfter(':') }

  @Test
  fun `failed rows are hidden unless asked for`() {
    assertEquals(5, run().rows.size)
    assertEquals(5, run().total)
    assertEquals(6, run(Filters(showFailed = true)).rows.size)
  }

  @Test
  fun `newest kernel build first by default, rows without a date last`() {
    assertEquals(listOf("2", "4", "1", "3", "5"), ids(run()))
    assertEquals("6", ids(run(Filters(showFailed = true))).last())
  }

  @Test
  fun `sort ascending and descending keep rows without a value last`() {
    assertEquals(listOf("5", "3", "1", "4", "2", "6"), ids(run(Filters(showFailed = true), Sort(SortKey.BUILT, descending = false))))
    assertEquals(listOf("2", "4", "1", "3", "5", "6"), ids(run(Filters(showFailed = true), Sort(SortKey.BUILT, descending = true))))
  }

  @Test
  fun `kernel sort is natural`() {
    assertEquals(listOf("5", "3", "1", "4", "2"), ids(run(sort = Sort(SortKey.KERNEL, descending = false))))
  }

  @Test
  fun `device sort is natural, not alphabetical`() {
    val devices = run(sort = Sort(SortKey.DEVICE, descending = false)).rows.map { it.device }.distinct()
    assertEquals(listOf("Find X8", "OP 10 Pro", "OP 13", "Realme 10"), devices)
  }

  @Test
  fun `search needs every word, in any column`() {
    assertEquals(listOf("2", "1"), ids(run(Filters(query = "op 13"))))
    assertEquals(listOf("2"), ids(run(Filters(query = "pjz110 6.6.50"))))
    assertEquals(listOf("1", "4"), ids(run(Filters(query = "6.6.30"))).sorted())
    assertTrue(run(Filters(query = "nothing like this")).rows.isEmpty())
  }

  @Test
  fun `selections narrow the rows`() {
    val r = run(Filters().with(FilterField.BRAND, "OnePlus").with(FilterField.ANDROID, "15"))
    assertEquals(setOf("1", "2"), ids(r).toSet())
    assertEquals(setOf("1", "4"), ids(run(Filters().with(FilterField.BRANCH, "6.6").with(FilterField.REGION, "EU"))).toSet())
  }

  @Test
  fun `each list offers only what exists with the other selections`() {
    val r = run(Filters().with(FilterField.BRAND, "OnePlus"))
    assertEquals(listOf("OP 10 Pro", "OP 13"), r.options.getValue(FilterField.DEVICE))
    assertEquals(listOf("CN", "EU", "GLO"), r.options.getValue(FilterField.REGION))
    // the brand list itself ignores the brand selection, so it can be changed
    assertEquals(listOf("OnePlus", "OPPO", "Realme"), r.options.getValue(FilterField.BRAND))
    assertEquals(listOf("5.10", "6.6"), r.options.getValue(FilterField.BRANCH))
  }

  @Test
  fun `a selection that no longer exists is dropped`() {
    // "Find X8" is an OPPO device: with Realme selected the brand is dropped, the device stays
    val r = run(Filters().with(FilterField.DEVICE, "Find X8").with(FilterField.BRAND, "Realme"))
    assertEquals(mapOf(FilterField.DEVICE to "Find X8"), r.filters.selected)
    assertEquals(listOf("4"), ids(r))
  }

  @Test
  fun `selections that cannot hold together are dropped one by one`() {
    val r = run(Filters().with(FilterField.REGION, "EU").with(FilterField.ANDROID, "14").with(FilterField.BRAND, "OnePlus"))
    assertEquals(mapOf(FilterField.ANDROID to "14"), r.filters.selected)
    assertEquals(setOf("3", "5"), ids(r).toSet())
  }

  @Test
  fun `followed only shows the followed models`() {
    val r = run(Filters(followedOnly = true), followed = setOf("oneplus:CPH2655"))
    assertEquals(listOf("1"), ids(r))
    assertEquals(1, r.total)
    assertTrue(run(Filters(followedOnly = true)).rows.isEmpty())
  }

  @Test
  fun `natural compare orders numbers by value and ignores case`() {
    assertTrue(naturalCompare("A2", "A10") < 0)
    assertTrue(naturalCompare("5.10.9", "5.10.100") < 0)
    assertTrue(naturalCompare("abc", "ABD") < 0)
    assertEquals(0, naturalCompare("Op 13", "oP 13"))
    assertTrue(naturalCompare("OP 13", "OP 13R") < 0)
    assertTrue(naturalCompare("007", "7") == 0)
  }

  @Test
  fun `new firmware are the unseen ones of followed models with a kernel`() {
    val followed = setOf("oneplus:CPH2655")
    assertEquals(listOf("oneplus:1"), NewFirmware.find(rows, followed, emptySet()).map { it.uid }) // 6 has no kernel yet
    assertEquals(emptyList(), NewFirmware.find(rows, followed, setOf("oneplus:1")))
    assertEquals(emptyList(), NewFirmware.find(rows, emptySet(), emptySet()))
  }
}
