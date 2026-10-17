package org.proofline.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.ui.Modifier
import androidx.navigation.compose.rememberNavController
import org.proofline.android.core.designsystem.DemoModeBanner
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
                Column(modifier = Modifier.fillMaxSize()) {
                    DemoModeBanner(modifier = Modifier.statusBarsPadding())
                    Box(modifier = Modifier.weight(1f)) {
                        ProoflineNavGraph(
                            navController = navController,
                            apiClient = app.apiClient
                        )
                    }
                }
            }
        }
    }
}
