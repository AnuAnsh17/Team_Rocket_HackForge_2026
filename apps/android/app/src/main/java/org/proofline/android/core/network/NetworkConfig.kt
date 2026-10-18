package org.proofline.android.core.network

import org.proofline.android.BuildConfig

/**
 * Runtime network configuration.
 *
 * The demo actor header is a development-only affordance: with the backend
 * running `AUTH_PROVIDER=supabase` the header is ignored entirely, and the
 * header must never be sent from a release build. Both conditions are folded
 * into [demoHeaderEnabled] so there is exactly one place that decides it.
 */
object NetworkConfig {

    /** Base URL of the Proofline backend, including the `/api/v1` prefix. */
    var baseUrl: String = BuildConfig.API_BASE_URL

    /**
     * The seeded demo user uuid sent as `X-Demo-Actor-Id` when the debug
     * fallback is in use. It identifies a *user*, never a role.
     */
    var demoActorId: String = BuildConfig.DEMO_ACTOR_ID

    /**
     * True only when the debug build was asked for the demo fallback. Always
     * false in a release build because [BuildConfig.DEBUG] is compiled in.
     */
    val demoHeaderEnabled: Boolean
        get() = BuildConfig.DEBUG && BuildConfig.DEMO_ACTOR_FALLBACK && demoActorId.isNotBlank()

    /** Whether a debug build may talk to a plain-HTTP backend. */
    val cleartextAllowed: Boolean
        get() = BuildConfig.DEBUG
}
