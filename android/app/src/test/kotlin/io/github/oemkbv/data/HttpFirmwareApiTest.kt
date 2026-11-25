package io.github.oemkbv.data

import com.sun.net.httpserver.HttpExchange
import com.sun.net.httpserver.HttpServer
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.InetAddress
import java.net.InetSocketAddress
import java.util.zip.GZIPOutputStream
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlinx.coroutines.test.runTest

class HttpFirmwareApiTest {
  private lateinit var server: HttpServer
  private val requests = mutableListOf<Map<String, String>>()
  private var handler: (HttpExchange) -> Unit = {}

  @BeforeTest
  fun start() {
    server = HttpServer.create(InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0)
    server.createContext("/") { ex ->
      requests += mapOf("path" to ex.requestURI.path, "ua" to ex.requestHeaders.getFirst("User-Agent").orEmpty(), "inm" to ex.requestHeaders.getFirst("If-None-Match").orEmpty())
      handler(ex)
      ex.close()
    }
    server.start()
  }

  @AfterTest
  fun stop() = server.stop(0)

  private fun api(maxBytes: Int = 1024 * 1024) = HttpFirmwareApi("http://127.0.0.1:${server.address.port}", "test-agent", maxBytes)

  private fun reply(ex: HttpExchange, code: Int, body: ByteArray = ByteArray(0), headers: Map<String, String> = emptyMap()) {
    headers.forEach { (k, v) -> ex.responseHeaders.add(k, v) }
    ex.sendResponseHeaders(code, if (body.isEmpty() && code == 304) -1 else body.size.toLong())
    if (body.isNotEmpty()) ex.responseBody.write(body)
  }

  @Test
  fun `downloads the brand file and keeps its etag`() = runTest {
    handler = { reply(it, 200, "[]".toByteArray(), mapOf("ETag" to "\"abc\"")) }
    val result = assertIs<FetchResult.Updated>(api().fetch(Brand.OPPO, null))
    assertContentEquals("[]".toByteArray(), result.body)
    assertEquals("\"abc\"", result.etag)
    assertEquals("/oppo.json", requests.single()["path"])
    assertEquals("test-agent", requests.single()["ua"])
    assertEquals("", requests.single()["inm"])
  }

  @Test
  fun `sends the validator and understands not modified`() = runTest {
    handler = { reply(it, 304) }
    assertIs<FetchResult.NotModified>(api().fetch(Brand.REALME, "\"abc\""))
    assertEquals("\"abc\"", requests.single()["inm"])
  }

  @Test
  fun `a response without etag has none`() = runTest {
    handler = { reply(it, 200, "[]".toByteArray()) }
    assertNull(assertIs<FetchResult.Updated>(api().fetch(Brand.ONEPLUS, null)).etag)
  }

  @Test
  fun `gzip is decoded`() = runTest {
    val gz = ByteArrayOutputStream().also { o -> GZIPOutputStream(o).use { it.write("[1]".toByteArray()) } }.toByteArray()
    handler = { reply(it, 200, gz, mapOf("Content-Encoding" to "gzip")) }
    assertContentEquals("[1]".toByteArray(), assertIs<FetchResult.Updated>(api().fetch(Brand.ONEPLUS, null)).body)
  }

  @Test
  fun `an http error is reported with its code`() = runTest {
    handler = { reply(it, 503, "x".toByteArray()) }
    assertEquals(503, assertFailsWith<HttpStatusException> { api().fetch(Brand.ONEPLUS, null) }.code)
  }

  @Test
  fun `a response over the limit is refused`() = runTest {
    handler = { reply(it, 200, ByteArray(5000)) }
    assertFailsWith<IOException> { api(maxBytes = 1000).fetch(Brand.ONEPLUS, null) }
  }
}
