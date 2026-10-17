package org.proofline.android

import android.app.Application
import org.proofline.android.core.network.NetworkConfig
import org.proofline.android.core.network.ProoflineApiClient

class ProoflineApplication : Application() {
    lateinit var apiClient: ProoflineApiClient
        private set

    override fun onCreate() {
        super.onCreate()
        NetworkConfig.baseUrl = BuildConfig.DEFAULT_API_BASE_URL
        NetworkConfig.isDemoMode = BuildConfig.DEFAULT_DEMO_MODE
        NetworkConfig.demoActorId = BuildConfig.DEFAULT_DEMO_ACTOR_ID

        apiClient = ProoflineApiClient()
    }
}
