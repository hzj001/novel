// Top-level build file where you can add configuration options common to all sub-projects/modules.
val kotlinVersion: String = "1.7.10"

plugins {
    id("com.android.application") apply false
    id("com.android.library") apply false
    id("org.jetbrains.kotlin.android") version "1.5.31" apply false
}

buildscript {
    repositories {
        maven {}
        google()
    }
    dependencies {
         classpath("com.android.tools.build:gradle:8.3.2")
         classpath("org.jetbrains.kotlin:kotlin-gradle-plugin:1.7.10")
    }
}