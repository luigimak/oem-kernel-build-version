package io.github.oemkbv

import android.app.Application
import android.content.Context
import io.github.oemkbv.data.AppPrefs
import io.github.oemkbv.data.FirmwareApi
import io.github.oemkbv.data.FirmwareCache
import io.github.oemkbv.data.FirmwareRepository
import io.github.oemkbv.data.HttpFirmwareApi
import io.github.oemkbv.background.CheckScheduler
import io.github.oemkbv.background.NewFirmwareNotifier
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.launch

/** Hand-wired dependencies: small enough that a DI framework would cost more than it saves. */
class AppContainer(
  context: Context,
  api: FirmwareApi = HttpFirmwareApi(userAgent = "OEM-KernelBuildVersion/${BuildConfig.VERSION_NAME}"),
  cacheDir: File = File(context.filesDir, "data"),
  /** Called whenever the periodic "new firmware" check should start (`true`) or stop (`false`). */
  val scheduleChecks: (Boolean) -> Unit = { CheckScheduler.sync(context, it) },
) {
  val prefs = AppPrefs(context.getSharedPreferences("prefs", Context.MODE_PRIVATE))
  val repository = FirmwareRepository(api, FirmwareCache(cacheDir))
  val notifier = NewFirmwareNotifier(context)
}

open class OemKbvApp : Application() {
  lateinit var container: AppContainer
    private set

  private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

  protected open fun createContainer(): AppContainer = AppContainer(this)

  override fun onCreate() {
    super.onCreate()
    container = createContainer()
    // the check runs only while there is something to notify about
    scope.launch {
      combine(container.prefs.notifications, container.prefs.favorites) { on, favorites -> on && favorites.isNotEmpty() }
        .distinctUntilChanged()
        .collect { container.scheduleChecks(it) }
    }
  }
}
