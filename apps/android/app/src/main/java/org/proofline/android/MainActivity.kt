package org.proofline.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.navigation.compose.rememberNavController
import org.proofline.android.core.designsystem.ProoflineTheme
import org.proofline.android.navigation.ProoflineNavGraph

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val app = application as ProoflineApplication

        setContent {
            ProoflineTheme {
                val navController = rememberNavController()
                ProoflineNavGraph(
                    navController = navController,
                    apiClient = app.apiClient
                )
            }
        }
    }
}
