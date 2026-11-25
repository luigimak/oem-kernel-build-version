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
  fun `build time is null when it cannot be read`() {
    assertNull(BuildTime.parse(""))
    assertNull(BuildTime.parse("#1 SMP PREEMPT Wed Dec 10 04:46:02 PST 2025"))
    assertNull(BuildTime.parse("#1 SMP Foo 10 04:46:02 UTC 2025"))
    assertNull(BuildTime.parse("#1 SMP Wed Feb 31 04:46:02 UTC 2025"))
  }

  @Test
  fun `row keeps the kernel branch, the search text and a follow key`() {
    val row = dto("a1", device = "OP 13", model = "CPH2655", kernel = "6.6.30-android15-8-g1234").toFirmware(Brand.ONEPLUS)
    assertEquals("oneplus:a1", row.uid)
    assertEquals("6.6", row.branch)
    assertEquals("oneplus:CPH2655", row.followKey)
    assertTrue("op 13" in row.haystack && "cph2655" in row.haystack && "6.6.30" in row.haystack && "oneplus" in row.haystack)
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
  fun `follow key falls back to the device when the model is empty`() {
    assertEquals("realme:Realme 10", dto("x", device = "Realme 10", model = "").toFirmware(Brand.REALME).followKey)
  }

  @Test
  fun `rows of the real files parse with nulls, unknown and missing fields`() {
    val json = Json { ignoreUnknownKeys = true; isLenient = true; coerceInputValues = true }
    val text = """[{"id":"vt-1","device":"OP 10 PRO","size":7482806174,"ok":true,"error":null,"new_field":[1,2]},{"id":"x"},{"id":7,"ok":false}]"""
    val rows = json.decodeFromString(ListSerializer(FirmwareDto.serializer()), text)
    assertEquals(3, rows.size)
    assertEquals(7482806174, rows[0].size)
    assertEquals("", rows[1].device.orEmpty())
    assertEquals("7", rows[2].id)
  }
}
