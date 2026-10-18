package org.proofline.android

import android.content.Context
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import org.proofline.android.data.repository.TravelDayRepository
import org.proofline.android.ui.navigation.NavGraph
import org.proofline.android.ui.theme.ProoflineTheme
import org.proofline.android.ui.viewmodel.ProoflineViewModel

class MainActivity : ComponentActivity() {
    private lateinit var travelRepo: TravelDayRepository
    private val viewModel: ProoflineViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        travelRepo = TravelDayRepository(applicationContext)
        val prefs = getSharedPreferences("proofline_prefs", Context.MODE_PRIVATE)
        viewModel.initialize(application, prefs)

        setContent {
            ProoflineTheme {
                NavGraph(viewModel = viewModel, travelRepo = travelRepo)
            }
        }
    }

    override fun onResume() {
        super.onResume()
        viewModel.loadData()
        val drafts = viewModel.uiState.value.expenses.count { it.status == "draft" }
        if (drafts > 0) {
            Log.d("ProoflineApp", "REMINDER: $drafts drafts pending")
        }
    }
}
