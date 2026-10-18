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

data class ProoflineUiState(
    val isLoading: Boolean = false,
    val membership: MembershipSummary? = null,
    val expenses: List<Expense> = emptyList(),
    val errorMessage: String? = null,
    val isDemoMode: Boolean = true
)

class ProoflineViewModel : ViewModel() {
    private val repository = ProoflineRepository()

    private val _uiState = MutableStateFlow(ProoflineUiState())
    val uiState: StateFlow<ProoflineUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    fun loadData() {
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

    fun seedDemoDataset() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            repository.seedDemo()
            loadData()
        }
    }
}
