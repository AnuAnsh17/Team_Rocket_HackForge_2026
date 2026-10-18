package org.proofline.android.core.network

import kotlinx.serialization.json.Json

/**
 * One JSON configuration for every non-Gson call in the app.
 *
 * `ignoreUnknownKeys` is deliberate: the backend may add response fields without
 * this client failing, which is the difference between "we ignore a field we do
 * not model" and "the app stops working".
 */
object ProoflineJson {
    val instance: Json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        encodeDefaults = true
    }
}
