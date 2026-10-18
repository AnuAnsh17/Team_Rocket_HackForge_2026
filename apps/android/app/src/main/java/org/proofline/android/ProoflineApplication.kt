package org.proofline.android

import android.app.Application
import org.proofline.android.di.AppContainer

class ProoflineApplication : Application() {

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }

    companion object {
        /**
         * Process-wide composition root, created in [onCreate].
         *
         * A plain property rather than a dependency-injection framework: the app
         * has one session, one HTTP client and one repository, and the Android
         * ViewModel factories need a no-argument constructor.
         */
        lateinit var container: AppContainer
            private set
    }
}
