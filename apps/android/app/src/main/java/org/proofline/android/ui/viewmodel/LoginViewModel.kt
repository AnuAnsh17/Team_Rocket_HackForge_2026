package org.proofline.android.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import org.proofline.android.ProoflineApplication
import org.proofline.android.core.auth.LoginErrorMessages
import org.proofline.android.core.auth.SessionManager

data class LoginUiState(
    val email: String = "",
    val password: String = "",
    val isSubmitting: Boolean = false,
    val errorMessage: String? = null
) {
    /** The submit button is disabled until there is something to submit. */
    val canSubmit: Boolean
        get() = !isSubmitting && email.isNotBlank() && password.isNotBlank()
}

class LoginViewModel private constructor(
    private val sessionManager: SessionManager
) : ViewModel() {

    constructor() : this(ProoflineApplication.container.sessionManager)

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    fun onEmailChange(value: String) {
        _uiState.update { it.copy(email = value, errorMessage = null) }
    }

    fun onPasswordChange(value: String) {
        _uiState.update { it.copy(password = value, errorMessage = null) }
    }

    /**
     * Sign in against Supabase Auth.
     *
     * The password field is cleared as soon as the attempt finishes, whether it
     * succeeded or not, so a credential does not sit in memory behind the login
     * screen. [onSignedIn] only runs after the session has been persisted.
     */
    fun signIn(onSignedIn: () -> Unit) {
        val state = _uiState.value
        if (!state.canSubmit) return

        viewModelScope.launch {
            _uiState.update { it.copy(isSubmitting = true, errorMessage = null) }
            try {
                sessionManager.signInAsync(state.email.trim(), state.password)
                _uiState.update { it.copy(isSubmitting = false, password = "") }
                onSignedIn()
            } catch (error: Throwable) {
                _uiState.update {
                    it.copy(
                        isSubmitting = false,
                        password = "",
                        errorMessage = LoginErrorMessages.messageFor(error)
                    )
                }
            }
        }
    }
}
