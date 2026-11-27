package io.github.oemkbv.data

import com.sun.net.httpserver.HttpExchange
import com.sun.net.httpserver.HttpServer
import io.github.oemkbv.release
import java.io.IOException
import java.net.InetAddress
import java.net.InetSocketAddress
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlinx.coroutines.test.runTest

class AppUpdateTest {
  @Test
  fun `versions compare number by number, and a dev build is older than its release`() {
    fun v(s: String) = AppVersion.parse(s)!!
    assertTrue(v("1.10.0") > v("1.9.9"))
    assertTrue(v("2.0.0") > v("1.99.99"))
    assertTrue(v("1.0.1") > v("1.0.0"))
    assertTrue(v("1.0.0") > v("1.0.0-dev"))
    assertTrue(v("1.0.1-dev") > v("1.0.0"))
    assertEquals(0, v("1.2.3").compareTo(v("1.2.3")))
  }

  @Test
  fun `only well formed versions and app release tags are understood`() {
    assertNull(AppVersion.parse("1.0"))
    assertNull(AppVersion.parse("v1.0.0"))
    assertNull(AppVersion.parse("1.0.0.0"))
    assertNull(AppVersion.parse("../../1.0.0"))
    assertEquals(AppVersion(1, 2, 3, false), AppVersion.fromTag("app-v1.2.3"))
    assertNull(AppVersion.fromTag("v1.2.3")) // not an app tag
    assertNull(AppVersion.fromTag("data-2026-11-27"))
    assertNull(AppVersion.fromTag("app-v1.2.3-rc1")) // pre-release suffixes are not offered
  }

  @Test
  fun `the newest published app release wins`() {
    val releases = listOf(release("1.0.1"), release("1.2.0"), release("1.10.0"), release("1.9.9"))
    assertEquals(AppUpdate("1.10.0", "https://github.com/luigimak/oem-kernel-build-version/releases/tag/app-v1.10.0"), AppUpdates.newest(releases))
  }

  @Test
  fun `drafts, pre-releases, other tags and foreign links are ignored`() {
    val foreign = release("9.9.9").copy(htmlUrl = "https://evil.example/releases/tag/app-v9.9.9")
    val releases = listOf(
      release("3.0.0", draft = true),
      release("3.1.0", prerelease = true),
      release("4.0.0", tag = "something-4.0.0"),
      foreign,
      release("1.1.0"),
    )
    assertEquals("1.1.0", AppUpdates.newest(releases)?.version)
    assertNull(AppUpdates.newest(emptyList()))
    assertNull(AppUpdates.newest(releases.take(4)))
  }

  @Test
  fun `a release is an update only when newer than the running app`() {
    val update = AppUpdate("1.1.0", "https://github.com/luigimak/oem-kernel-build-version/releases/tag/app-v1.1.0")
    assertTrue(update.isNewerThan("1.0.0"))
    assertTrue(update.isNewerThan("1.0.0-dev"))
    assertTrue(update.isNewerThan("1.1.0-dev")) // the dev build of 1.1.0 is older than the release
    assertFalse(update.isNewerThan("1.1.0"))
    assertFalse(update.isNewerThan("2.0.0"))
    assertTrue(update.isNewerThan("not a version")) // unreadable: better to offer than to hide
  }
}

class HttpUpdateApiTest {
  private lateinit var server: HttpServer
  private var handler: (HttpExchange) -> Unit = {}
  private val requests = mutableListOf<Map<String, String>>()

  @BeforeTest
  fun start() {
    server = HttpServer.create(InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0)
    server.createContext("/") { ex ->
      requests += mapOf("ua" to ex.requestHeaders.getFirst("User-Agent").orEmpty(), "accept" to ex.requestHeaders.getFirst("Accept").orEmpty(), "auth" to ex.requestHeaders.getFirst("Authorization").orEmpty())
      handler(ex)
      ex.close()
    }
    server.start()
  }

  @AfterTest
  fun stop() = server.stop(0)

  private fun api(maxBytes: Int = 1024 * 1024) = HttpUpdateApi("http://127.0.0.1:${server.address.port}/releases", "test-agent", maxBytes)

  private fun reply(ex: HttpExchange, code: Int, body: String) {
    val bytes = body.toByteArray()
    ex.sendResponseHeaders(code, bytes.size.toLong())
    ex.responseBody.write(bytes)
  }

  @Test
  fun `reads the releases, ignoring what it does not know`() = runTest {
    handler = { reply(it, 200, """[{"tag_name":"app-v1.0.0","html_url":"https://github.com/x","draft":false,"prerelease":false,"body":"long text","assets":[{"id":1}]},{"tag_name":"app-v0.9.0"}]""") }
    val releases = api().releases()
    assertEquals(listOf("app-v1.0.0", "app-v0.9.0"), releases.map { it.tagName })
    assertEquals("test-agent", requests.single()["ua"])
    assertTrue(requests.single()["accept"]!!.contains("github+json"))
    assertEquals("", requests.single()["auth"]) // no token, no account
  }

  @Test
  fun `a rate limit or an error is an exception, not an empty answer`() = runTest {
    handler = { reply(it, 403, """{"message":"rate limit exceeded"}""") }
    assertEquals(403, assertFailsWith<HttpStatusException> { api().releases() }.code)
  }

  @Test
  fun `an answer that is not a list of releases is refused`() = runTest {
    handler = { reply(it, 200, "<html>maintenance</html>") }
    assertFailsWith<IllegalArgumentException> { api().releases() }
  }

  @Test
  fun `an oversized answer is refused`() = runTest {
    handler = { reply(it, 200, "[" + "1,".repeat(5000) + "1]") }
    assertFailsWith<IOException> { api(maxBytes = 1000).releases() }
  }
}
