pluginManagement {
  repositories {
    google {
      content {
        includeGroupByRegex("androidx.*")
        includeGroupByRegex("com\\.android.*")
        includeGroupByRegex("com\\.google.*")
      }
    }
    // Google's mirror of Maven Central first: Maven Central answers 429 to the shared addresses of CI runners. Same files, and Maven Central
    // stays as the fallback for anything the mirror does not have yet.
    maven("https://maven-central.storage-download.googleapis.com/maven2/")
    mavenCentral()
    gradlePluginPortal()
  }
}

dependencyResolutionManagement {
  repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
  repositories {
    google {
      content {
        includeGroupByRegex("androidx.*")
        includeGroupByRegex("com\\.android.*")
        includeGroupByRegex("com\\.google.*")
      }
    }
    // Google's mirror of Maven Central first: Maven Central answers 429 to the shared addresses of CI runners. Same files, and Maven Central
    // stays as the fallback for anything the mirror does not have yet.
    maven("https://maven-central.storage-download.googleapis.com/maven2/")
    mavenCentral()
  }
}

plugins {
  id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}

rootProject.name = "OEM-KernelBuildVersion"

include(":app")
