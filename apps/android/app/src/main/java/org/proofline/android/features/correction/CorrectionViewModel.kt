package org.proofline.android.features.correction

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.proofline.android.core.model.Expense
import org.proofline.android.core.model.UpdateExpenseRequest
import org.proofline.android.core.network.NetworkConfig
import org.proofline.android.core.network.ProoflineApiClient
import org.proofline.android.core.network.ProoflineApiException

sealed interface CorrectionUiState {
    data object Loading : CorrectionUiState
    data class Ready(val expense: Expense) : CorrectionUiState
    data object Submitting : CorrectionUiState
    data class Success(val expenseId: String) : CorrectionUiState
    data class Error(val message: String, val expense: Expense? = null) : CorrectionUiState
}

/**
 * CorrectionViewModel handles the correction PATCH flow with expected_version
 * concurrency control. On a STALE_VERSION error, it reloads the latest version
 * deterministically so the user can verify the current state and resubmit without
 * overwriting changes.
 */
class CorrectionViewModel(
    private val expenseId: String,
    private val apiClient: ProoflineApiClient
) : ViewModel() {

    private val _uiState = MutableStateFlow<CorrectionUiState>(CorrectionUiState.Loading)
    val uiState: StateFlow<CorrectionUiState> = _uiState.asStateFlow()

    var currentExpense: Expense? = null
        private set

    init {
        loadExpense()
    }

    fun loadExpense() {
        viewModelScope.launch {
            _uiState.value = CorrectionUiState.Loading
            apiClient.getExpense(expenseId)
                .onSuccess { exp ->
                    currentExpense = exp
                    _uiState.value = CorrectionUiState.Ready(exp)
                }
                .onFailure { err ->
                    _uiState.value = CorrectionUiState.Error(
                        NetworkConfig.describeConnectionProblem(err)
                    )
                }
        }
    }

    fun submitCorrection(
        merchant: String,
        date: String,
        amount: String,
        currency: String,
        category: String,
        purpose: String,
        clientName: String,
        attendeeCount: String
    ) {
        val exp = currentExpense ?: return
        viewModelScope.launch {
            _uiState.value = CorrectionUiState.Submitting
            val patchReq = UpdateExpenseRequest(
                expectedVersion = exp.version,
                merchant = merchant.ifBlank { null },
                expenseDate = date.ifBlank { null },
                amount = amount.ifBlank { null },
                currency = currency.ifBlank { null },
                category = category.ifBlank { null },
                businessPurpose = purpose.ifBlank { null },
                clientName = clientName.ifBlank { null },
                attendeeCount = attendeeCount.toIntOrNull()
            )

            apiClient.updateExpense(exp.id, patchReq)
                .onSuccess {
                    _uiState.value = CorrectionUiState.Success(exp.id)
                }
                .onFailure { err ->
                    if (err is ProoflineApiException && err.errorCode == "STALE_VERSION") {
                        // Reload latest version deterministically
                        apiClient.getExpense(exp.id)
                            .onSuccess { freshExp ->
                                currentExpense = freshExp
                                _uiState.value = CorrectionUiState.Error(
                                    message = "Claim was modified in another session. Refreshed to version ${freshExp.version}. Please verify and resubmit.",
                                    expense = freshExp
                                )
                            }
                            .onFailure { reloadErr ->
                                _uiState.value = CorrectionUiState.Error(
                                    NetworkConfig.describeConnectionProblem(reloadErr)
                                )
                            }
                    } else {
                        _uiState.value = CorrectionUiState.Error(
                            message = NetworkConfig.describeConnectionProblem(err),
                            expense = exp
                        )
                    }
                }
        }
    }

    class Factory(
        private val expenseId: String,
        private val apiClient: ProoflineApiClient
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return CorrectionViewModel(expenseId, apiClient) as T
        }
    }
}
