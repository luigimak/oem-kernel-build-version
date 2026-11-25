package io.github.oemkbv.data

import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json

/** The rows of every brand plus the brands whose file could not be refreshed (their rows are the cached ones). */
data class LoadResult(val rows: List<Firmware>, val failedBrands: Set<Brand> = emptySet(), val updatedBrands: Set<Brand> = emptySet())

class FirmwareRepository(private val api: FirmwareApi, private val cache: FirmwareCache) {
  private val json = Json {
    ignoreUnknownKeys = true
    isLenient = true
    coerceInputValues = true
  }
  // only one refresh at a time (the screen and the background check can overlap); reading what is cached never waits for it
  private val mutex = Mutex()
  private val memory = ConcurrentHashMap<Brand, List<Firmware>>()

  /** What is on disk, no network. */
  suspend fun loadCached(): LoadResult = LoadResult(Brand.entries.flatMap { rows(it) })

  /** Asks for every brand file with the cached validator; a brand that fails keeps its cached rows. */
  suspend fun refresh(): LoadResult = mutex.withLock {
    val results = coroutineScope { Brand.entries.map { b -> async { refreshBrand(b) } }.awaitAll() }
    LoadResult(
      rows = results.flatMap { it.rows },
      failedBrands = results.filter { it.failed }.map { it.brand }.toSet(),
      updatedBrands = results.filter { it.updated }.map { it.brand }.toSet(),
    )
  }

  private class BrandResult(val brand: Brand, val rows: List<Firmware>, val updated: Boolean = false, val failed: Boolean = false)

  private suspend fun refreshBrand(brand: Brand): BrandResult =
    try {
      when (val r = api.fetch(brand, cache.etag(brand))) {
        FetchResult.NotModified -> BrandResult(brand, rows(brand))
        is FetchResult.Updated -> {
          val parsed = parse(r.body, brand) // a broken download must not replace a good copy
          withContext(Dispatchers.IO) { cache.write(brand, r.body, r.etag) }
          memory[brand] = parsed
          BrandResult(brand, parsed, updated = true)
        }
      }
    } catch (e: CancellationException) {
      throw e
    } catch (_: java.io.IOException) {
      BrandResult(brand, rows(brand), failed = true)
    } catch (_: IllegalArgumentException) { // includes SerializationException
      BrandResult(brand, rows(brand), failed = true)
    }

  private suspend fun rows(brand: Brand): List<Firmware> {
    memory[brand]?.let { return it }
    val bytes = withContext(Dispatchers.IO) { cache.read(brand) } ?: return emptyList()
    // a damaged cached file is treated as missing: the next refresh replaces it
    val parsed = try {
      parse(bytes, brand)
    } catch (_: IllegalArgumentException) { // includes SerializationException
      return emptyList()
    }
    memory[brand] = parsed
    return parsed
  }

  private suspend fun parse(bytes: ByteArray, brand: Brand): List<Firmware> = withContext(Dispatchers.Default) {
    json.decodeFromString(ListSerializer(FirmwareDto.serializer()), bytes.decodeToString()).map { it.toFirmware(brand) }
  }
}
