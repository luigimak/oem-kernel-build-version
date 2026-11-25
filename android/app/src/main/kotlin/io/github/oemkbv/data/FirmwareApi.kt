package io.github.oemkbv.data

import java.io.ByteArrayOutputStream
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.zip.GZIPInputStream
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Where the daily-refreshed data lives: the files the GitHub Pages table reads. */
const val DATA_BASE_URL = "https://luigimak.github.io/oem-kernel-build-version"

sealed interface FetchResult {
  /** The copy we already have is still the current one (HTTP 304). */
  data object NotModified : FetchResult

  class Updated(val body: ByteArray, val etag: String?) : FetchResult
}

class HttpStatusException(val code: Int) : IOException("HTTP $code")

fun interface FirmwareApi {
  /** Fetches the data file of [brand]; [etag] is the validator of the cached copy, if any. */
  suspend fun fetch(brand: Brand, etag: String?): FetchResult
}

/** Plain `HttpURLConnection`: one small, read-only request per brand. */
class HttpFirmwareApi(
  private val baseUrl: String = DATA_BASE_URL,
  private val userAgent: String = "OEM-KernelBuildVersion",
  private val maxBytes: Int = 32 * 1024 * 1024,
) : FirmwareApi {
  override suspend fun fetch(brand: Brand, etag: String?): FetchResult = withContext(Dispatchers.IO) {
    val conn = URL("$baseUrl/${brand.key}.json").openConnection() as HttpURLConnection
    try {
      conn.connectTimeout = 15_000
      conn.readTimeout = 30_000
      conn.setRequestProperty("User-Agent", userAgent)
      conn.setRequestProperty("Accept", "application/json")
      // asked for and decoded here, so it behaves the same on every platform (the JDK does not decode on its own)
      conn.setRequestProperty("Accept-Encoding", "gzip")
      if (etag != null) conn.setRequestProperty("If-None-Match", etag)
      when (val code = conn.responseCode) {
        HttpURLConnection.HTTP_NOT_MODIFIED -> FetchResult.NotModified
        HttpURLConnection.HTTP_OK -> {
          val raw = conn.inputStream
          val body = (if (conn.contentEncoding.equals("gzip", ignoreCase = true)) GZIPInputStream(raw) else raw).use { readCapped(it) }
          FetchResult.Updated(body, conn.getHeaderField("ETag"))
        }
        else -> throw HttpStatusException(code)
      }
    } finally {
      conn.disconnect()
    }
  }

  private fun readCapped(input: java.io.InputStream): ByteArray {
    val out = ByteArrayOutputStream()
    val buf = ByteArray(64 * 1024)
    while (true) {
      val n = input.read(buf)
      if (n < 0) break
      if (out.size() + n > maxBytes) throw IOException("response too large")
      out.write(buf, 0, n)
    }
    return out.toByteArray()
  }
}

/** The last good copy of every brand file, so the app works offline and can ask "has it changed?". */
class FirmwareCache(private val dir: File) {
  private fun body(brand: Brand) = File(dir, "${brand.key}.json")

  private fun etagFile(brand: Brand) = File(dir, "${brand.key}.etag")

  fun read(brand: Brand): ByteArray? = body(brand).takeIf { it.isFile }?.readBytes()

  /** Only offered while the body it belongs to exists. */
  fun etag(brand: Brand): String? =
    etagFile(brand).takeIf { body(brand).isFile && it.isFile }?.readText()?.trim()?.ifEmpty { null }

  fun write(brand: Brand, bytes: ByteArray, etag: String?) {
    dir.mkdirs()
    val tmp = File(dir, "${brand.key}.json.tmp")
    tmp.writeBytes(bytes)
    if (!tmp.renameTo(body(brand))) {
      tmp.delete()
      throw IOException("cannot store ${brand.key}")
    }
    if (etag != null) etagFile(brand).writeText(etag) else etagFile(brand).delete()
  }
}
