plugins {
  alias(libs.plugins.android.application)
  alias(libs.plugins.compose.compiler)
  alias(libs.plugins.kotlin.serialization)
}

// Release signing comes from the environment (CI secrets or a local keystore kept outside the repository).
// Without it the release APK is simply left unsigned: nothing secret is ever read from, or written to, the repo.
val releaseKeystore: String? = providers.environmentVariable("OEMKBV_KEYSTORE_FILE").orNull

android {
  namespace = "io.github.oemkbv"
  compileSdk = 36
  defaultConfig {
    applicationId = "io.github.oemkbv"
    minSdk = 26
    targetSdk = 36
    // the release workflow sets both from the `app-vX.Y.Z` tag (versionCode = X*10000 + Y*100 + Z)
    versionCode = providers.environmentVariable("OEMKBV_VERSION_CODE").orNull?.toInt() ?: 1
    versionName = providers.environmentVariable("OEMKBV_VERSION_NAME").orNull ?: "1.0.0-dev"
    testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
  }

  // one APK language list generated from the res/values-xx folders: Android 13+ shows it in the per-app language settings
  androidResources {
    generateLocaleConfig = true
  }

  signingConfigs {
    if (releaseKeystore != null) {
      create("release") {
        storeFile = file(releaseKeystore)
        storePassword = providers.environmentVariable("OEMKBV_KEYSTORE_PASSWORD").get()
        keyAlias = providers.environmentVariable("OEMKBV_KEY_ALIAS").get()
        keyPassword = providers.environmentVariable("OEMKBV_KEY_PASSWORD").get()
      }
    }
  }

  buildTypes {
    release {
      // not minified on purpose: the release build cannot be exercised on a device from CI, so no R8 surprises
      isMinifyEnabled = false
      if (releaseKeystore != null) signingConfig = signingConfigs.getByName("release")
    }
  }
  compileOptions {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
  }
  buildFeatures {
    compose = true
    aidl = false
    buildConfig = true
    shaders = false
  }

  testOptions {
    unitTests {
      // Robolectric needs the merged resources and manifest to render Compose screens on the JVM
      isIncludeAndroidResources = true
      isReturnDefaultValues = true
    }
  }

  packaging {
    resources {
      excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
  }

  lint {
    // fail on real problems, not on "a newer library exists"
    warningsAsErrors = false
    abortOnError = true
    // ObsoleteSdkInt: the adaptive-icon folder keeps its -v26 qualifier, which aapt2 needs for anydpi
    disable += setOf("GradleDependency", "AndroidGradlePluginVersion", "NewerVersionAvailable", "ObsoleteSdkInt")
  }
}

kotlin {
  jvmToolchain(17)
}

dependencies {
  val composeBom = platform(libs.androidx.compose.bom)
  implementation(composeBom)
  androidTestImplementation(composeBom)
  testImplementation(composeBom)

  // Core Android dependencies
  implementation(libs.androidx.core.ktx)
  implementation(libs.androidx.lifecycle.runtime.ktx)
  implementation(libs.androidx.activity.compose)

  // Arch Components
  implementation(libs.androidx.lifecycle.runtime.compose)
  implementation(libs.androidx.lifecycle.viewmodel.compose)

  // Compose
  implementation(libs.androidx.compose.ui)
  implementation(libs.androidx.compose.ui.tooling.preview)
  implementation(libs.androidx.compose.material3)
  implementation(libs.androidx.compose.material.icons.core)

  // Navigation
  implementation(libs.androidx.navigation3.ui)
  implementation(libs.androidx.navigation3.runtime)

  // Data: JSON and the periodic "new firmware" check
  implementation(libs.kotlinx.serialization.json)
  implementation(libs.androidx.work.runtime)

  // Tooling
  debugImplementation(libs.androidx.compose.ui.tooling)
  debugImplementation(libs.androidx.compose.ui.test.manifest)

  // Local tests (JVM): jUnit, coroutines, Robolectric + Compose test rule
  testImplementation(libs.junit)
  testImplementation(libs.kotlin.test)
  testImplementation(libs.kotlinx.coroutines.test)
  testImplementation(libs.robolectric)
  testImplementation(libs.androidx.compose.ui.test.junit4)
  testImplementation(libs.androidx.compose.ui.test.manifest)
  testImplementation(libs.androidx.test.core)
  testImplementation(libs.androidx.test.ext.junit)
  testImplementation(libs.androidx.work.testing)

  // Instrumented tests
  androidTestImplementation(libs.androidx.compose.ui.test.junit4)
  androidTestImplementation(libs.androidx.test.core)
  androidTestImplementation(libs.androidx.test.ext.junit)
  androidTestImplementation(libs.androidx.test.runner)
}
