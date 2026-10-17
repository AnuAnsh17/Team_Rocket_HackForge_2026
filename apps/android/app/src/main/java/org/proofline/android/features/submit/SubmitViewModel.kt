package org.proofline.android.features.submit

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.proofline.android.core.model.Expense
import org.proofline.android.core.network.NetworkConfig
import org.proofline.android.core.network.ProoflineApiClient
import java.util.UUID

sealed interface SubmitUiState {
    data object Loading : SubmitUiState
    data class Ready(val expense: Expense) : SubmitUiState
    data class Submitting(val expense: Expense) : SubmitUiState
    data class Success(val expense: Expense, val claimId: String) : SubmitUiState
    data class Error(val message: String, val expense: Expense? = null) : SubmitUiState
}

/**
 * SubmitViewModel manages submission lifecycle and retains a single
 * Idempotency-Key UUID per submission attempt, surviving device rotation and
 * guaranteeing that retries replay the same key to the backend.
 */
class SubmitViewModel(
    private val expenseId: String,
    private val apiClient: ProoflineApiClient
) : ViewModel() {

    private val _uiState = MutableStateFlow<SubmitUiState>(SubmitUiState.Loading)
    val uiState: StateFlow<SubmitUiState> = _uiState.asStateFlow()

    // Generated ONCE per ViewModel instance and reused across retries
    val idempotencyKey: String = UUID.randomUUID().toString()

    private var currentExpense: Expense? = null

    init {
        loadExpense()
    }

    fun loadExpense() {
        viewModelScope.launch {
            _uiState.value = SubmitUiState.Loading
            apiClient.getExpense(expenseId)
                .onSuccess { exp ->
                    currentExpense = exp
                    _uiState.value = SubmitUiState.Ready(exp)
                }
                .onFailure { err ->
                    _uiState.value = SubmitUiState.Error(
                        message = NetworkConfig.describeConnectionProblem(err)
                    )
                }
        }
    }

    fun submit() {
        val exp = currentExpense ?: return
        viewModelScope.launch {
            _uiState.value = SubmitUiState.Submitting(exp)
            apiClient.submitExpense(expenseId, idempotencyKey)
                .onSuccess { updated ->
                    currentExpense = updated
                    _uiState.value = SubmitUiState.Success(updated, updated.id)
                }
                .onFailure { err ->
                    _uiState.value = SubmitUiState.Error(
                        message = NetworkConfig.describeConnectionProblem(err),
                        expense = exp
                    )
                }
        }
    }

    class Factory(
        private val expenseId: String,
        private val apiClient: ProoflineApiClient
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return SubmitViewModel(expenseId, apiClient) as T
        }
    }
}
