package io.github.oemkbv.ui

import io.github.oemkbv.data.Brand
import io.github.oemkbv.data.toFirmware
import io.github.oemkbv.dto
import kotlin.test.Test
import kotlin.test.assertEquals

class ShareTextTest {
  @Test
  fun `the shared text names the device, then the kernel version and the build`() {
    val row = dto(
      "1", "13", "CPH2655", "EU", "CPH2655_15.0.0.100(EX01)",
      kernel = "6.6.30-android15-8-g1", build = "#1 SMP PREEMPT Wed Dec 10 04:46:02 UTC 2025",
    ).toFirmware(Brand.ONEPLUS)
    assertEquals(
      "OnePlus 13 EU (CPH2655) CPH2655_15.0.0.100(EX01)\n6.6.30-android15-8-g1\n#1 SMP PREEMPT Wed Dec 10 04:46:02 UTC 2025",
      shareText(row),
    )
  }

  @Test
  fun `the whole Linux version string is not shared`() {
    val row = dto("1", "13", "CPH2655", "EU", "CPH2655_15.0.0.100(EX01)").toFirmware(Brand.ONEPLUS)
    assert(row.linuxVersion.isNotEmpty() && row.linuxVersion !in shareText(row))
  }

  @Test
  fun `a part the firmware does not have is left out`() {
    val onlyKernel = dto("3", "Find X8", "CPH2651", "CN", "CPH2651_15.0.0.50(CN01)", kernel = "6.6.46-android15-8-g9", build = "").toFirmware(Brand.OPPO)
    assertEquals("OPPO Find X8 CN (CPH2651) CPH2651_15.0.0.50(CN01)\n6.6.46-android15-8-g9", shareText(onlyKernel))
  }

  @Test
  fun `a firmware that failed shares just its name`() {
    val failed = dto("2", "Find X8", "CPH2651", "CN", "CPH2651_15.0.0.50(CN01)", ok = false).toFirmware(Brand.OPPO)
    assertEquals("OPPO Find X8 CN (CPH2651) CPH2651_15.0.0.50(CN01)", shareText(failed))
  }
}
