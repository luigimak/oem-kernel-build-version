package io.github.oemkbv.data

import io.github.oemkbv.dto
import java.time.Instant
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json

class FirmwareTest {
  @Test
  fun `build time reads UTC and CST like the web table`() {
    assertEquals(Instant.parse("2025-12-10T04:46:02Z").toEpochMilli(), BuildTime.parse("#1 SMP PREEMPT Wed Dec 10 04:46:02 UTC 2025"))
    assertEquals(Instant.parse("2024-12-24T22:31:09Z").toEpochMilli(), BuildTime.parse("#1 SMP PREEMPT Wed Dec 25 06:31:09 CST 2024"))
    assertEquals(Instant.parse("2023-12-25T12:31:09Z").toEpochMilli(), BuildTime.parse("#2 SMP Mon Dec  25 12:31:09 UTC 2023"))
  }

  @Test
  fun `build time of Hong Kong is eight hours ahead of UTC`() {
    assertEquals(Instant.parse("2025-07-21T04:31:09Z").toEpochMilli(), BuildTime.parse("#1 SMP PREEMPT Mon Jul 21 12:31:09 HKT 2025"))
  }

  @Test
  fun `Motorola builds in US Central time, the other brands keep CST as China Standard Time`() {
    val cst = "#1 SMP PREEMPT Mon Dec 22 22:41:20 CST 2025"
    assertEquals(Instant.parse("2025-12-23T04:41:20Z").toEpochMilli(), BuildTime.parse(cst, Brand.MOTOROLA))
    assertEquals(Instant.parse("2025-12-22T14:41:20Z").toEpochMilli(), BuildTime.parse(cst, Brand.LENOVO))
    assertEquals(Instant.parse("2025-12-22T14:41:20Z").toEpochMilli(), BuildTime.parse(cst))
    assertEquals(Instant.parse("2025-07-21T17:31:09Z").toEpochMilli(), BuildTime.parse("#1 SMP PREEMPT Mon Jul 21 12:31:09 CDT 2025", Brand.MOTOROLA))
    assertNull(BuildTime.parse("#1 SMP PREEMPT Mon Jul 21 12:31:09 CDT 2025", Brand.NOTHING))        // CDT only means something in the US
  }

  @Test
  fun `row of a Motorola firmware is dated in US Central time`() {
    val row = dto("m", device = "AVR").copy(build = "#1 SMP PREEMPT Mon Dec 22 22:41:20 CST 2025").toFirmware(Brand.MOTOROLA)
    assertEquals(Instant.parse("2025-12-23T04:41:20Z").toEpochMilli(), row.builtMs)
  }

  @Test
  fun `every brand has the key of its data file and a distinct label`() {
    assertEquals(
      listOf("oneplus", "oppo", "realme", "xiaomi", "poco", "redmi", "nothing", "motorola", "lenovo"),
      Brand.entries.map { it.key },
    )
    assertEquals(Brand.entries.size, Brand.entries.map { it.label }.toSet().size)
    assertEquals(DeviceId(Brand.POCO, "F7 PRO", "GLO"), DeviceId.parse("poco|F7 PRO|GLO"))
    assertEquals("Nothing Phone (2a) GLO", DeviceId(Brand.NOTHING, "Phone (2a)", "GLO").label)
  }

  @Test
  fun `build time is null when it cannot be read`() {
    assertNull(BuildTime.parse(""))
    assertNull(BuildTime.parse("#1 SMP PREEMPT Wed Dec 10 04:46:02 PST 2025"))
    assertNull(BuildTime.parse("#1 SMP Foo 10 04:46:02 UTC 2025"))
    assertNull(BuildTime.parse("#1 SMP Wed Feb 31 04:46:02 UTC 2025"))
  }

  @Test
  fun `row keeps the kernel branch, the search text and its device`() {
    val row = dto("a1", device = "13", model = "CPH2655", kernel = "6.6.30-android15-8-g1234").toFirmware(Brand.ONEPLUS)
    assertEquals("oneplus:a1", row.uid)
    assertEquals("6.6", row.branch)
    assertEquals(DeviceId(Brand.ONEPLUS, "13", "EU"), row.deviceId)
    assertEquals("oneplus|13|EU", row.deviceId.key)
    assertEquals("OnePlus 13 EU", row.deviceId.label)
    assertTrue("oneplus 13" in row.haystack && "cph2655" in row.haystack && "6.6.30" in row.haystack && "oneplus" in row.haystack)
    assertNotNull(row.builtMs)
    assertTrue(row.ok)
  }

  @Test
  fun `failed row has no kernel, no branch and no build date`() {
    val row = dto("a2", ok = false).toFirmware(Brand.OPPO)
    assertFalse(row.ok)
    assertEquals("", row.kernel)
    assertEquals("", row.branch)
    assertNull(row.builtMs)
    assertEquals("link expired", row.error)
  }

  @Test
  fun `the device falls back to the model when the row has no device`() {
    assertEquals("realme|RMX1|EU", dto("x", device = "", model = "RMX1").toFirmware(Brand.REALME).deviceId.key)
  }

  @Test
  fun `name puts the brand before the device, or before the model when there is no device`() {
    assertEquals("OnePlus 13R", dto("a", device = "13R").toFirmware(Brand.ONEPLUS).name)
    assertEquals("Realme 10", dto("b", device = "10").toFirmware(Brand.REALME).name)
    assertEquals("Realme RMX3630", dto("c", device = "", model = "RMX3630").toFirmware(Brand.REALME).name)
  }

  @Test
  fun `rows of the real files parse with nulls, unknown and missing fields`() {
    val json = Json { ignoreUnknownKeys = true; isLenient = true; coerceInputValues = true }
    val text = """[{"id":"vt-1","brand":"OnePlus","device":"10 PRO","size":7482806174,"ok":true,"error":null,"new_field":[1,2]},{"id":"x"},{"id":7,"ok":false}]"""
    val rows = json.decodeFromString(ListSerializer(FirmwareDto.serializer()), text)
    assertEquals(3, rows.size)
    assertEquals(7482806174, rows[0].size)
    assertEquals("", rows[1].device.orEmpty())
    assertEquals("7", rows[2].id)
  }
}
