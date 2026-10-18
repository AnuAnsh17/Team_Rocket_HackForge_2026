package org.proofline.android.ui.viewmodel

import android.app.Application
import android.content.SharedPreferences
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
    val useSampleData: Boolean = false,
    val backendUrl: String = ProoflineRepository.DEFAULT_BASE_URL,
    val editingBackendUrl: String = ProoflineRepository.DEFAULT_BASE_URL
)

class ProoflineViewModel : ViewModel() {
    private val repository = ProoflineRepository()
    private var prefs: SharedPreferences? = null

    private val _uiState = MutableStateFlow(ProoflineUiState())
    val uiState: StateFlow<ProoflineUiState> = _uiState.asStateFlow()

    fun initialize(context: Application, sharedPrefs: SharedPreferences) {
        this.prefs = sharedPrefs
        val savedSampleData = sharedPrefs.getBoolean("use_sample_data", false)
        val savedBackendUrl = sharedPrefs.getString("backend_url", ProoflineRepository.DEFAULT_BASE_URL) ?: ProoflineRepository.DEFAULT_BASE_URL

        repository.setBaseUrl(savedBackendUrl)

        _uiState.update {
            it.copy(
                useSampleData = savedSampleData,
                backendUrl = savedBackendUrl,
                editingBackendUrl = savedBackendUrl
            )
        }

        if (savedSampleData) {
            applySampleData()
        } else {
            loadData()
        }
    }

    fun loadData() {
        if (_uiState.value.useSampleData) {
            applySampleData()
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
        prefs?.edit()?.putBoolean("use_sample_data", enabled)?.apply()
        _uiState.update { it.copy(useSampleData = enabled) }
        if (enabled) {
            applySampleData()
        } else {
            loadData()
        }
    }

    private fun applySampleData() {
        _uiState.update {
            it.copy(
                isLoading = false,
                membership = SampleDataProvider.sampleMembership,
                expenses = SampleDataProvider.sampleExpenses,
                errorMessage = null
            )
        }
    }

    fun updateEditingBackendUrl(newUrl: String) {
        _uiState.update { it.copy(editingBackendUrl = newUrl) }
    }

    fun saveBackendUrl() {
        val newUrl = _uiState.value.editingBackendUrl.trim()
        if (newUrl.isNotBlank()) {
            prefs?.edit()?.putString("backend_url", newUrl)?.apply()
            repository.setBaseUrl(newUrl)
            _uiState.update { it.copy(backendUrl = newUrl) }
            loadData()
        }
    }

    fun resetBackendUrl() {
        val defaultUrl = ProoflineRepository.DEFAULT_BASE_URL
        prefs?.edit()?.putString("backend_url", defaultUrl)?.apply()
        repository.setBaseUrl(defaultUrl)
        _uiState.update { it.copy(backendUrl = defaultUrl, editingBackendUrl = defaultUrl) }
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
