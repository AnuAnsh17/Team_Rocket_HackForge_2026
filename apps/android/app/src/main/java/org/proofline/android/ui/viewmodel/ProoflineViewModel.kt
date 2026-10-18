package org.proofline.android.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import org.proofline.android.ProoflineApplication
import org.proofline.android.core.network.NetworkConfig
import org.proofline.android.data.model.Expense
import org.proofline.android.data.model.MembershipSummary
import org.proofline.android.data.repository.ProoflineRepository

/**
 * List/home state.
 *
 * There is no `useSampleData` flag and no sample provider: every expense shown in
 * this app comes from the backend, and a failure is displayed as a failure. An
 * offline fixture list used to be togglable here and was removed because a
 * fabricated claim presented in the same card as a real one is indistinguishable
 * from a real claim to the person reading it.
 */
data class ProoflineUiState(
    val isLoading: Boolean = false,
    val membership: MembershipSummary? = null,
    val expenses: List<Expense> = emptyList(),
    val errorMessage: String? = null
)

/** Detail state for one claim. `expense == null` means "not loaded", never "unknown status". */
data class ExpenseDetailState(
    val expenseId: String? = null,
    val isLoading: Boolean = false,
    val expense: Expense? = null,
    val errorMessage: String? = null
)

class ProoflineViewModel private constructor(
    private val repository: ProoflineRepository
) : ViewModel() {

    constructor() : this(ProoflineApplication.container.repository)

    private val _uiState = MutableStateFlow(ProoflineUiState())
    val uiState: StateFlow<ProoflineUiState> = _uiState.asStateFlow()

    private val _detailState = MutableStateFlow(ExpenseDetailState())
    val detailState: StateFlow<ExpenseDetailState> = _detailState.asStateFlow()

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

    /**
     * Load one claim for the detail screen.
     *
     * Nothing is displayed until the backend answers, and a failure is shown as a
     * failure: this screen previously printed a hard-coded status and claimed a
     * receipt stream was "authorized and ready", neither of which was read from
     * anywhere.
     */
    fun loadExpense(expenseId: String) {
        if (_detailState.value.expenseId == expenseId && !_detailState.value.isLoading) return
        viewModelScope.launch {
            _detailState.update {
                it.copy(expenseId = expenseId, isLoading = true, expense = null, errorMessage = null)
            }
            val result = repository.getExpense(expenseId)
            _detailState.update {
                it.copy(
                    isLoading = false,
                    expense = result.getOrNull(),
                    errorMessage = result.exceptionOrNull()?.localizedMessage
                )
            }
        }
    }

    /**
     * Debug-only: switch the demo actor used by the `X-Demo-Actor-Id` fallback.
     *
     * This is a no-op in a release build because the header is never sent there.
     */
    fun setDemoActor(uuid: String) {
        if (!NetworkConfig.demoHeaderEnabled) return
        NetworkConfig.demoActorId = uuid
        loadData()
    }

    fun seedDemoDataset() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }
            repository.seedDemo()
            loadData()
        }
    }

    /**
     * Drop everything this process is holding about the signed-out user.
     *
     * The ViewModels are activity-scoped (`viewModel()` at the activity level),
     * so signing out pops the app graph but does *not* clear them: the previous
     * user's membership and claim list would stay in memory, and the next person
     * to sign in would see the previous user's name and claims rendered from the
     * cached [ProoflineUiState] until the first backend call returned. Sign-out
     * therefore has to clear this state explicitly.
     */
    fun clearSessionState() {
        _uiState.value = ProoflineUiState()
        _detailState.value = ExpenseDetailState()
    }
}
