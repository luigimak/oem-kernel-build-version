package io.github.oemkbv.domain

import io.github.oemkbv.data.Brand
import io.github.oemkbv.data.DeviceId
import io.github.oemkbv.data.Firmware
import io.github.oemkbv.data.toFirmware
import io.github.oemkbv.dto
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class FirmwareQueryTest {
  private val rows: List<Firmware> = listOf(
    dto("1", "13", "CPH2655", "EU", "CPH2655_15.0.0.100(EX01)", "15", "6.6.30-android15-8-g1", "#1 SMP PREEMPT Wed Dec 10 04:46:02 UTC 2025").toFirmware(Brand.ONEPLUS),
    dto("2", "13", "PJZ110", "CN", "PJZ110_15.0.0.200(CN01)", "15", "6.6.50-android15-8-g2", "#1 SMP PREEMPT Wed Jan 14 04:46:02 UTC 2026").toFirmware(Brand.ONEPLUS),
    dto("3", "10 Pro", "NE2210", "GLO", "NE2210_14.0.0.9(EX01)", "14", "5.10.209-android12-9-g3", "#1 SMP PREEMPT Mon Dec 25 12:31:09 UTC 2023").toFirmware(Brand.ONEPLUS),
    dto("4", "Find X8", "CPH2651", "EU", "CPH2651_15.0.0.50(EX01)", "15", "6.6.30-android15-8-g4", "#1 SMP PREEMPT Wed Dec 10 05:00:00 UTC 2025").toFirmware(Brand.OPPO),
    dto("5", "10", "RMX3630", "TH", "RMX3630_14.0.0.200(EX01)", "14", "5.10.198-android12-9-g5", "#1 SMP PREEMPT Wed Sep 20 05:00:00 UTC 2023").toFirmware(Brand.REALME),
    dto("6", "13", "CPH2655", "IN", "CPH2655_15.0.0.101(EX01)", ok = false).toFirmware(Brand.ONEPLUS),
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
    val devices = run(sort = Sort(SortKey.DEVICE, descending = false)).rows.map { it.name }.distinct()
    assertEquals(listOf("OnePlus 10 Pro", "OnePlus 13", "OPPO Find X8", "Realme 10"), devices)
  }

  @Test
  fun `search needs every word, in any column`() {
    assertEquals(listOf("2", "1"), ids(run(Filters(query = "oneplus 13"))))
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
    assertEquals(listOf("OnePlus 10 Pro", "OnePlus 13"), r.options.getValue(FilterField.DEVICE))
    assertEquals(listOf("CN", "EU", "GLO"), r.options.getValue(FilterField.REGION))
    // the brand list itself ignores the brand selection, so it can be changed
    assertEquals(listOf("OnePlus", "OPPO", "Realme"), r.options.getValue(FilterField.BRAND))
    assertEquals(listOf("5.10", "6.6"), r.options.getValue(FilterField.BRANCH))
  }

  @Test
  fun `the same device name under two brands stays two devices`() {
    val both = listOf(
      dto("1", "11", "CPH2447").toFirmware(Brand.ONEPLUS),
      dto("2", "11", "RMX3780", version = "RMX3780_14.0.0.100(EX01)").toFirmware(Brand.REALME),
    )
    val all = FirmwareQuery.run(both, Filters(), Sort(), emptySet())
    assertEquals(listOf("OnePlus 11", "Realme 11"), all.options.getValue(FilterField.DEVICE))
    assertEquals(listOf("2"), ids(FirmwareQuery.run(both, Filters().with(FilterField.DEVICE, "Realme 11"), Sort(), emptySet())))
  }

  @Test
  fun `a selection that no longer exists is dropped`() {
    // "OPPO Find X8" is an OPPO device: with Realme selected the brand is dropped, the device stays
    val r = run(Filters().with(FilterField.DEVICE, "OPPO Find X8").with(FilterField.BRAND, "Realme"))
    assertEquals(mapOf(FilterField.DEVICE to "OPPO Find X8"), r.filters.selected)
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

  @Test
  fun `one device lists only its own firmware and offers only what varies inside it`() {
    val op13eu = DeviceId(Brand.ONEPLUS, "13", "EU")
    val r = run(Filters(device = op13eu))
    assertEquals(listOf("1"), ids(r))
    assertEquals(1, r.total)
    assertEquals(listOf("15"), r.options.getValue(FilterField.ANDROID))
    assertEquals(listOf("6.6"), r.options.getValue(FilterField.BRANCH))
    // the same device in another region is another device
    assertEquals(listOf("2"), ids(run(Filters(device = DeviceId(Brand.ONEPLUS, "13", "CN")))))
    assertEquals(listOf("1"), ids(run(Filters(device = op13eu, showFailed = true))))
    assertEquals(listOf("6"), ids(run(Filters(device = DeviceId(Brand.ONEPLUS, "13", "IN"), showFailed = true))))
  }

  @Test
  fun `a device with several models lists them together, newest firmware version first`() {
    val twoModels = listOf(
      dto("a", "12", "CPH2573", "IN", "CPH2573_16.0.2.1(IN01)", "16").toFirmware(Brand.ONEPLUS),
      dto("b", "12", "CPH2581", "IN", "CPH2581_16.0.1.5(IN01)", "16").toFirmware(Brand.ONEPLUS),
      dto("c", "12", "CPH2581", "IN", "CPH2581_15.0.0.9(IN01)", "15").toFirmware(Brand.ONEPLUS),
    )
    val r = FirmwareQuery.run(twoModels, Filters(device = DeviceId(Brand.ONEPLUS, "12", "IN")), Sort.ForDevice, emptySet())
    // 16.0.2.1 is newer than 16.0.1.5 although CPH2573 sorts before CPH2581
    assertEquals(listOf("a", "b", "c"), r.rows.map { it.uid.substringAfter(':') })
    assertEquals(listOf("15", "16"), r.options.getValue(FilterField.ANDROID))
    assertEquals(listOf("b", "a"), FirmwareQuery.run(twoModels, Filters(device = DeviceId(Brand.ONEPLUS, "12", "IN")).with(FilterField.ANDROID, "16"), Sort(SortKey.VERSION, descending = false), emptySet()).rows.map { it.uid.substringAfter(':') })
  }

  @Test
  fun `the version number is what comes after the model code`() {
    assertEquals("16.0.9.401(EX01)", versionNumber("CPH2653_16.0.9.401(EX01)"))
    assertEquals("whatever", versionNumber("whatever"))
  }

  @Test
  fun `default sorts, and reset ignores the chosen device`() {
    assertEquals(Sort(SortKey.VERSION, descending = true), Sort.ForDevice)
    assertEquals(Sort(SortKey.BUILT, descending = true), Sort.ForAll)
    assertTrue(Filters(device = DeviceId(Brand.OPPO, "Find X8", "EU")).isDefault)
    assertTrue(!Filters(query = "x", device = DeviceId(Brand.OPPO, "Find X8", "EU")).isDefault)
  }

  @Test
  fun `device ids and selections survive being stored`() {
    val id = DeviceId(Brand.ONEPLUS, "10T/ACE PRO", "CN")
    assertEquals("OnePlus 10T/ACE PRO CN", id.label)
    assertEquals(id, DeviceId.parse(id.key))
    assertEquals(DeviceId(Brand.OPPO, "a|b", "EU"), DeviceId.parse(DeviceId(Brand.OPPO, "a|b", "EU").key))
    assertEquals(null, DeviceId.parse("nothing"))
    assertEquals(null, DeviceId.parse("unknown|13|EU"))
    for (s in listOf(Selection.None, Selection.All, Selection.Device(id))) assertEquals(s, Selection.parse(s.stored))
    assertEquals(Selection.None, Selection.parse(null))
    assertEquals(Selection.None, Selection.parse("device:garbage"))
  }
}
