package org.proofline.android.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import org.proofline.android.data.model.Expense
import org.proofline.android.data.model.MembershipSummary
import org.proofline.android.data.repository.ProoflineRepository
import org.proofline.android.data.sample.SampleDataProvider

data class ProoflineUiState(
    val isLoading: Boolean = false,
    val membership: MembershipSummary? = null,
    val expenses: List<Expense> = emptyList(),
    val errorMessage: String? = null,
    val isDemoMode: Boolean = true,
    val useSampleData: Boolean = false
)

class ProoflineViewModel : ViewModel() {
    private val repository = ProoflineRepository()

    private val _uiState = MutableStateFlow(ProoflineUiState())
    val uiState: StateFlow<ProoflineUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    fun loadData() {
        val currentState = _uiState.value
        if (currentState.useSampleData) {
            _uiState.update {
                it.copy(
                    isLoading = false,
                    membership = SampleDataProvider.sampleMembership,
                    expenses = SampleDataProvider.sampleExpenses,
                    errorMessage = null
                )
            }
            return
        }

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }

            val meResult = repository.getMe()
            val expensesResult = repository.getExpenses()

            val errorMessage = meResult.exceptionOrNull()?.localizedMessage
                ?: expensesResult.exceptionOrNull()?.localizedMessage

            _uiState.update { state ->
                state.copy(
                    isLoading = false,
                    membership = meResult.getOrNull(),
                    expenses = expensesResult.getOrNull()?.items ?: emptyList(),
                    errorMessage = errorMessage
                )
            }
        }
    }

    fun setDemoActor(uuid: String) {
        repository.currentDemoActor = uuid
        loadData()
    }

    fun toggleSampleData(enabled: Boolean) {
        _uiState.update { it.copy(useSampleData = enabled) }
        loadData()
    }

    fun seedDemoDataset() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            repository.seedDemo()
            loadData()
        }
    }
}
