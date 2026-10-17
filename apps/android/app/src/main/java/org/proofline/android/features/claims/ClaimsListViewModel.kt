package org.proofline.android.features.claims

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.proofline.android.core.model.ExpenseStatus
import org.proofline.android.core.model.ExpenseSummary
import org.proofline.android.core.network.NetworkConfig
import org.proofline.android.core.network.ProoflineApiClient

enum class ClaimsFilterTab(val label: String) {
    ALL("All"),
    PENDING("Pending"),
    NEEDS_INFO("Needs Info"),
    APPROVED("Approved"),
    NOT_REIMBURSED("Not Reimbursed")
}

sealed interface ClaimsListUiState {
    data object Loading : ClaimsListUiState
    data class Success(
        val allClaims: List<ExpenseSummary>,
        val filteredClaims: List<ExpenseSummary>,
        val currentTab: ClaimsFilterTab,
        val isRefreshing: Boolean = false
    ) : ClaimsListUiState
    data class Error(val message: String) : ClaimsListUiState
}

class ClaimsListViewModel(
    private val apiClient: ProoflineApiClient
) : ViewModel() {

    private val _uiState = MutableStateFlow<ClaimsListUiState>(ClaimsListUiState.Loading)
    val uiState: StateFlow<ClaimsListUiState> = _uiState.asStateFlow()

    private var currentFilter = ClaimsFilterTab.ALL
    private var cachedClaims: List<ExpenseSummary> = emptyList()

    init {
        loadClaims(isRefresh = false)
    }

    fun loadClaims(isRefresh: Boolean = false) {
        viewModelScope.launch {
            if (isRefresh && _uiState.value is ClaimsListUiState.Success) {
                val current = _uiState.value as ClaimsListUiState.Success
                _uiState.value = current.copy(isRefreshing = true)
            } else {
                _uiState.value = ClaimsListUiState.Loading
            }

            apiClient.getExpenses()
                .onSuccess { response ->
                    cachedClaims = response.items
                    _uiState.value = ClaimsListUiState.Success(
                        allClaims = cachedClaims,
                        filteredClaims = filterClaims(cachedClaims, currentFilter),
                        currentTab = currentFilter,
                        isRefreshing = false
                    )
                }
                .onFailure { err ->
                    _uiState.value = ClaimsListUiState.Error(
                        message = NetworkConfig.describeConnectionProblem(err)
                    )
                }
        }
    }

    fun setFilterTab(tab: ClaimsFilterTab) {
        currentFilter = tab
        if (_uiState.value is ClaimsListUiState.Success) {
            _uiState.value = ClaimsListUiState.Success(
                allClaims = cachedClaims,
                filteredClaims = filterClaims(cachedClaims, tab),
                currentTab = tab,
                isRefreshing = false
            )
        }
    }

    private fun filterClaims(claims: List<ExpenseSummary>, tab: ClaimsFilterTab): List<ExpenseSummary> {
        return when (tab) {
            ClaimsFilterTab.ALL -> claims
            ClaimsFilterTab.PENDING -> claims.filter {
                it.status == ExpenseStatus.SUBMITTED || it.status == ExpenseStatus.IN_REVIEW
            }
            ClaimsFilterTab.NEEDS_INFO -> claims.filter { it.status == ExpenseStatus.NEEDS_INFO }
            ClaimsFilterTab.APPROVED -> claims.filter { it.status == ExpenseStatus.APPROVED }
            ClaimsFilterTab.NOT_REIMBURSED -> claims.filter { it.status == ExpenseStatus.REJECTED }
        }
    }

    class Factory(
        private val apiClient: ProoflineApiClient
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return ClaimsListViewModel(apiClient) as T
        }
    }
}
