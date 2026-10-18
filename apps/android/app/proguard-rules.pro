# ProGuard/R8 rules for the Proofline Android app.
#
# Referenced from app/build.gradle.kts. Keep this file in sync with the release
# build: if minification is switched on (`isMinifyEnabled = true`), these rules
# are what keeps reflection-driven deserialisation working.

# Kotlin metadata and annotations are read reflectively by serializers and by
# androidx' lifecycle helpers.
-keepattributes *Annotation*,Signature,InnerClasses,EnclosingMethod

# --- kotlinx.serialization -------------------------------------------------
# Generated serializers are looked up through the companion `serializer()`
# function, so the generated classes must survive shrinking.
-keepattributes RuntimeVisibleAnnotations,AnnotationDefault
-keepclassmembers class **$$serializer { *; }
-keepclasseswithmembers class ** {
    public static ** Companion;
}
-keepclassmembers class * {
    @kotlinx.serialization.SerialName <fields>;
}
-if @kotlinx.serialization.Serializable class **
-keepclassmembers class <1> {
    static <1>$Companion Companion;
}
-keep class kotlinx.serialization.** { *; }

# --- OkHttp / Okio ---------------------------------------------------------
# OkHttp references optional platform classes that are absent on Android.
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn javax.annotation.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**

# --- Gson ------------------------------------------------------------------
# The Retrofit/Gson layer deserialises plain data classes by field name.
-keepattributes EnclosingMethod
-keep class com.google.gson.** { *; }
-keepclassmembers,allowobfuscation class * {
    @com.google.gson.annotations.SerializedName <fields>;
}
-keep class org.proofline.android.data.model.** { *; }
