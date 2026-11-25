package io.github.oemkbv

import io.github.oemkbv.data.Brand
import io.github.oemkbv.data.FetchResult
import io.github.oemkbv.data.Firmware
import io.github.oemkbv.data.FirmwareApi
import io.github.oemkbv.data.FirmwareDto
import io.github.oemkbv.data.toFirmware
import java.io.File
import java.io.IOException

/** A firmware row as the data files have it, for tests. */
fun dto(
  id: String,
  device: String = "OP 13",
  model: String = "CPH2655",
  region: String = "EU",
  version: String = "CPH2655_15.0.0.100(EX01)",
  android: String = "15",
  kernel: String = "6.6.30-android15-8-g1234",
  build: String = "#1 SMP PREEMPT Wed Dec 10 04:46:02 UTC 2025",
  ok: Boolean = true,
) = FirmwareDto(
  id = id,
  device = device,
  model = model,
  region = region,
  version = version,
  androidVersion = android,
  linuxVersion = if (ok) "Linux version $kernel (build-user@build-host) $build" else null,
  kernelRelease = if (ok) kernel else "",
  build = if (ok) build else "",
  ok = ok,
  error = if (ok) null else "link expired",
)

fun firmware(brand: Brand = Brand.ONEPLUS, id: String = "1", block: () -> FirmwareDto = { dto(id) }): Firmware = block().toFirmware(brand)

fun json(vararg rows: FirmwareDto): String =
  rows.joinToString(prefix = "[", postfix = "]", separator = ",") { r ->
    fun s(v: String?) = if (v == null) "null" else "\"" + v.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
    """{"id":${s(r.id)},"device":${s(r.device)},"region":${s(r.region)},"model":${s(r.model)},"version":${s(r.version)},""" +
      """"ota_version":"","build_timestamp":"","md5":"","size":${r.size ?: 0},"ok":${r.ok},"android_version":${s(r.androidVersion)},""" +
      """"linux_version":${s(r.linuxVersion)},"kernel_release":${s(r.kernelRelease)},"build":${s(r.build)},"compiler":"","source":"payload.bin","error":${s(r.error)},"unknown_field":1}"""
  }

/** An in-memory stand-in for the Pages data files: one body per brand, a version-based ETag, failures on demand. */
class FakeApi(private val bodies: MutableMap<Brand, String> = HashMap()) : FirmwareApi {
  val calls = mutableListOf<Pair<Brand, String?>>()
  var failing: Set<Brand> = emptySet()
  private val versions = HashMap<Brand, Int>()

  fun publish(brand: Brand, vararg rows: FirmwareDto) {
    bodies[brand] = json(*rows)
    versions[brand] = (versions[brand] ?: 0) + 1
  }

  fun publishRaw(brand: Brand, body: String) {
    bodies[brand] = body
    versions[brand] = (versions[brand] ?: 0) + 1
  }

  override suspend fun fetch(brand: Brand, etag: String?): FetchResult {
    calls += brand to etag
    if (brand in failing) throw IOException("offline")
    val body = bodies[brand] ?: throw io.github.oemkbv.data.HttpStatusException(404)
    val tag = "\"v${versions[brand]}\""
    return if (etag == tag) FetchResult.NotModified else FetchResult.Updated(body.toByteArray(), tag)
  }
}

/** What the UI and worker tests talk to: the test application reads it, each test sets it up. */
object TestWorld {
  var api = FakeApi()
}

class TestApp : OemKbvApp() {
  override fun createContainer() = AppContainer(
    this,
    api = { brand, etag -> TestWorld.api.fetch(brand, etag) },
    cacheDir = File(cacheDir, "data-${System.nanoTime()}"),
    scheduleChecks = {},
  )
}
