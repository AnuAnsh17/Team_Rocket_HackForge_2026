package org.proofline.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.lifecycle.viewmodel.compose.viewModel
import org.proofline.android.ui.navigation.NavGraph
import org.proofline.android.ui.theme.ProoflineTheme
import org.proofline.android.ui.viewmodel.ProoflineViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            ProoflineTheme {
                val viewModel: ProoflineViewModel = viewModel()
                NavGraph(viewModel = viewModel)
            }
        }
    }
}
