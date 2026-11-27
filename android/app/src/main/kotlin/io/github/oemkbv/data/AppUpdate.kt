package io.github.oemkbv.data

import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json

/** The GitHub releases of this app: a tag `app-vX.Y.Z` per version. Only a link to the release page is ever followed from them. */
const val RELEASES_API_URL = "https://api.github.com/repos/luigimak/oem-kernel-build-version/releases?per_page=10"
const val RELEASES_PAGE_PREFIX = "https://github.com/luigimak/oem-kernel-build-version/releases/"

/** `1.2.3`, or `1.2.3-dev` for a build that is not a release: older than the release of the same number. */
data class AppVersion(val major: Int, val minor: Int, val patch: Int, val preRelease: Boolean) : Comparable<AppVersion> {
  override fun compareTo(other: AppVersion): Int =
    compareValuesBy(this, other, AppVersion::major, AppVersion::minor, AppVersion::patch, { !it.preRelease })

  companion object {
    private val PATTERN = Regex("""^(\d{1,4})\.(\d{1,4})\.(\d{1,4})(-[0-9A-Za-z.-]{1,30})?$""")

    /** The version name of the app: `1.2.3` or `1.2.3-dev`. */
    fun parse(text: String): AppVersion? =
      PATTERN.matchEntire(text)?.destructured?.let { (major, minor, patch, suffix) ->
        AppVersion(major.toInt(), minor.toInt(), patch.toInt(), suffix.isNotEmpty())
      }

    /** The version of a release tag `app-v1.2.3`; any other tag (or a pre-release suffix) is not an app release. */
    fun fromTag(tag: String): AppVersion? = if (tag.startsWith("app-v")) parse(tag.removePrefix("app-v"))?.takeIf { !it.preRelease } else null
  }
}

@Serializable
data class ReleaseDto(
  @SerialName("tag_name") val tagName: String = "",
  @SerialName("html_url") val htmlUrl: String = "",
  val draft: Boolean = false,
  val prerelease: Boolean = false,
)

/** A published newer release: [version] is `1.2.3`, [url] the release page on GitHub. */
data class AppUpdate(val version: String, val url: String) {
  fun isNewerThan(current: String): Boolean {
    val mine = AppVersion.parse(current) ?: AppVersion(0, 0, 0, preRelease = true)
    val theirs = AppVersion.parse(version) ?: return false
    return theirs > mine
  }
}

fun interface UpdateApi {
  suspend fun releases(): List<ReleaseDto>
}

/** One small read-only request to the public GitHub API; no token, no account. */
class HttpUpdateApi(
  private val url: String = RELEASES_API_URL,
  private val userAgent: String = "OEM-KernelBuildVersion",
  private val maxBytes: Int = 4 * 1024 * 1024,
) : UpdateApi {
  private val json = Json { ignoreUnknownKeys = true; isLenient = true; coerceInputValues = true }

  override suspend fun releases(): List<ReleaseDto> = withContext(Dispatchers.IO) {
    val conn = URL(url).openConnection() as HttpURLConnection
    val body = try {
      conn.connectTimeout = 15_000
      conn.readTimeout = 20_000
      conn.setRequestProperty("User-Agent", userAgent)
      conn.setRequestProperty("Accept", "application/vnd.github+json")
      conn.setRequestProperty("X-GitHub-Api-Version", "2022-11-28")
      if (conn.responseCode != HttpURLConnection.HTTP_OK) throw HttpStatusException(conn.responseCode)
      conn.inputStream.use { input ->
        val out = ByteArrayOutputStream()
        val buf = ByteArray(32 * 1024)
        while (true) {
          val n = input.read(buf)
          if (n < 0) break
          if (out.size() + n > maxBytes) throw IOException("response too large")
          out.write(buf, 0, n)
        }
        out.toString(Charsets.UTF_8.name())
      }
    } finally {
      conn.disconnect()
    }
    json.decodeFromString(ListSerializer(ReleaseDto.serializer()), body)
  }
}

object AppUpdates {
  /** The newest published (not draft, not pre-release) app release whose page is on this repository's releases. */
  fun newest(releases: List<ReleaseDto>): AppUpdate? =
    releases.asSequence()
      .filter { !it.draft && !it.prerelease && it.htmlUrl.startsWith(RELEASES_PAGE_PREFIX) }
      .mapNotNull { r -> AppVersion.fromTag(r.tagName)?.let { it to r } }
      .maxByOrNull { it.first }
      ?.let { (_, r) -> AppUpdate(r.tagName.removePrefix("app-v"), r.htmlUrl) }
}

/** Looks for a newer release at most once a day, and when asked. Remembers the answer for the screens. */
class UpdateChecker(
  private val api: UpdateApi,
  private val prefs: AppPrefs,
  private val currentVersion: String,
  private val now: () -> Long = System::currentTimeMillis,
) {
  enum class Outcome { SKIPPED, CHECKED, FAILED }

  /** On start: only when the user did not switch the check off and a day has passed since the last answer. */
  suspend fun checkIfDue(): Outcome {
    if (!prefs.updateChecks.value) return Outcome.SKIPPED
    if (now() - prefs.lastUpdateCheck < DAY_MILLIS) return Outcome.SKIPPED
    return check()
  }

  /** Asks now, whatever the switch says: the user pressed "Check now". */
  suspend fun check(): Outcome =
    try {
      val newest = AppUpdates.newest(api.releases())
      prefs.setAvailableUpdate(newest?.takeIf { it.isNewerThan(currentVersion) })
      prefs.setLastUpdateCheck(now())
      Outcome.CHECKED
    } catch (e: CancellationException) {
      throw e
    } catch (_: IOException) { // no network, GitHub down, rate limit
      Outcome.FAILED
    } catch (_: IllegalArgumentException) { // an answer that is not what we expect (includes SerializationException)
      Outcome.FAILED
    }

  private companion object {
    const val DAY_MILLIS = 24L * 60 * 60 * 1000
  }
}
