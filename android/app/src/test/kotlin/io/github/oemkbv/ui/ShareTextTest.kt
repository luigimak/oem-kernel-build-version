package io.github.oemkbv.ui

import io.github.oemkbv.data.Brand
import io.github.oemkbv.data.toFirmware
import io.github.oemkbv.dto
import kotlin.test.Test
import kotlin.test.assertEquals

class ShareTextTest {
  @Test
  fun `the shared text names the device, then the Linux version`() {
    val row = dto("1", "13", "CPH2655", "EU", "CPH2655_15.0.0.100(EX01)", kernel = "6.6.30-android15-8-g1").toFirmware(Brand.ONEPLUS)
    assertEquals("OnePlus 13 EU (CPH2655) CPH2655_15.0.0.100(EX01)\n" + row.linuxVersion, shareText(row))
  }

  @Test
  fun `a firmware without a Linux version shares what it has`() {
    val failed = dto("2", "Find X8", "CPH2651", "CN", "CPH2651_15.0.0.50(CN01)", ok = false).toFirmware(Brand.OPPO)
    assertEquals("OPPO Find X8 CN (CPH2651) CPH2651_15.0.0.50(CN01)", shareText(failed))
  }
}
