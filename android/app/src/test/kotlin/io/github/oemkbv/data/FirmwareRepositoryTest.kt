package io.github.oemkbv.data

import io.github.oemkbv.FakeApi
import io.github.oemkbv.dto
import java.io.File
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlinx.coroutines.test.runTest
import org.junit.Rule
import org.junit.rules.TemporaryFolder

class FirmwareRepositoryTest {
  @get:Rule val tmp = TemporaryFolder()
  private lateinit var dir: File
  private val api = FakeApi()

  @BeforeTest
  fun setUp() {
    dir = File(tmp.newFolder(), "data")
    api.publish(Brand.ONEPLUS, dto("o1"), dto("o2", ok = false))
    api.publish(Brand.OPPO, dto("p1", device = "Find X8", model = "CPH2651"))
    api.publish(Brand.REALME, dto("r1", device = "10", model = "RMX3630"))
    Brand.entries.drop(3).forEach { api.publish(it) } // the newer brands have a file, with nothing in it yet
  }

  private fun repo() = FirmwareRepository(api, FirmwareCache(dir))

  @Test
  fun `nothing cached, nothing loaded`() = runTest {
    assertEquals(emptyList(), repo().loadCached().rows)
  }

  @Test
  fun `refresh downloads every brand and stores it for the next start`() = runTest {
    val first = repo().refresh()
    assertEquals(setOf("oneplus:o1", "oneplus:o2", "oppo:p1", "realme:r1"), first.rows.map { it.uid }.toSet())
    assertEquals(Brand.entries.toSet(), first.updatedBrands)
    assertTrue(first.failedBrands.isEmpty())

    // a new process: no network, the cached copy is there
    assertEquals(4, repo().loadCached().rows.size)
  }

  @Test
  fun `second refresh sends the etag and reuses the rows on not modified`() = runTest {
    val repo = repo()
    repo.refresh()
    api.calls.clear()
    val second = repo.refresh()
    assertEquals(4, second.rows.size)
    assertTrue(second.updatedBrands.isEmpty())
    assertTrue(api.calls.all { (_, etag) -> etag != null })
  }

  @Test
  fun `a changed brand file replaces the rows`() = runTest {
    val repo = repo()
    repo.refresh()
    api.publish(Brand.OPPO, dto("p1", device = "Find X8", model = "CPH2651"), dto("p2", device = "Find X8", model = "CPH2651"))
    val result = repo.refresh()
    assertEquals(setOf(Brand.OPPO), result.updatedBrands)
    assertEquals(2, result.rows.count { it.brand == Brand.OPPO })
  }

  @Test
  fun `a failing brand keeps its cached rows and is reported`() = runTest {
    repo().refresh()
    api.failing = setOf(Brand.OPPO)
    val result = FirmwareRepository(api, FirmwareCache(dir)).refresh() // new process: rows come from disk
    assertEquals(setOf(Brand.OPPO), result.failedBrands)
    assertEquals(1, result.rows.count { it.brand == Brand.OPPO })
    assertEquals(4, result.rows.size)
  }

  @Test
  fun `a failing brand with no cache is just empty`() = runTest {
    api.failing = setOf(Brand.REALME)
    val result = repo().refresh()
    assertEquals(setOf(Brand.REALME), result.failedBrands)
    assertEquals(3, result.rows.size)
  }

  @Test
  fun `a broken download does not replace a good copy`() = runTest {
    val repo = repo()
    repo.refresh()
    api.publishRaw(Brand.ONEPLUS, "<html>maintenance</html>")
    val result = repo.refresh()
    assertEquals(setOf(Brand.ONEPLUS), result.failedBrands)
    assertEquals(2, result.rows.count { it.brand == Brand.ONEPLUS })
    assertEquals(2, FirmwareRepository(api, FirmwareCache(dir)).loadCached().rows.count { it.brand == Brand.ONEPLUS })
  }

  @Test
  fun `a damaged cache file is ignored, the next refresh repairs it`() = runTest {
    repo().refresh()
    File(dir, "oneplus.json").writeText("not json")
    File(dir, "oneplus.etag").delete()
    val repo = repo()
    assertEquals(2, repo.loadCached().rows.size) // oppo and realme only
    assertEquals(4, repo.refresh().rows.size)
  }
}
