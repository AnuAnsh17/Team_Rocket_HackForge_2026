package org.proofline.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.lifecycle.viewmodel.compose.viewModel
import org.proofline.android.data.repository.TravelDayRepository
import org.proofline.android.ui.navigation.ProoflineNavGraph
import org.proofline.android.ui.theme.ProoflineTheme
import org.proofline.android.ui.viewmodel.LoginViewModel
import org.proofline.android.ui.viewmodel.ProoflineViewModel

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val container = ProoflineApplication.container
        val travelRepo = TravelDayRepository(applicationContext)

        setContent {
            ProoflineTheme {
                val prooflineViewModel: ProoflineViewModel = viewModel()
                val loginViewModel: LoginViewModel = viewModel()

                ProoflineNavGraph(
                    viewModel = prooflineViewModel,
                    loginViewModel = loginViewModel,
                    travelRepo = travelRepo,
                    sessionManager = container.sessionManager
                )
            }
        }
    }
}
