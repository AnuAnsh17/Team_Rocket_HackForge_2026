package org.proofline.android.features.capture

import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddPhotoAlternate
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.UploadFile
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import coil.compose.rememberAsyncImagePainter
import kotlinx.coroutines.launch
import org.proofline.android.core.designsystem.ProoflineCard
import org.proofline.android.core.designsystem.ProoflineColors
import org.proofline.android.core.designsystem.ProoflineDimensions
import org.proofline.android.core.designsystem.ProoflineScaffold
import org.proofline.android.core.model.CreateExpenseRequest
import org.proofline.android.core.model.ExpenseChannel
import org.proofline.android.core.network.NetworkConfig
import org.proofline.android.core.network.ProoflineApiClient

@Composable
fun CaptureScreen(
    apiClient: ProoflineApiClient,
    onBackClick: () -> Unit,
    onUploadSuccess: (expenseId: String) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var selectedImageUri by remember { mutableStateOf<Uri?>(null) }
    var selectedFileBytes by remember { mutableStateOf<ByteArray?>(null) }
    var selectedFileName by remember { mutableStateOf<String>("receipt.jpg") }
    var selectedMimeType by remember { mutableStateOf<String>("image/jpeg") }

    var isUploading by remember { mutableStateOf(false) }
    var uploadStatusMessage by remember { mutableStateOf<String?>(null) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    val photoPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        uri?.let {
            selectedImageUri = it
            errorMessage = null
            try {
                val inputStream = context.contentResolver.openInputStream(it)
                val bytes = inputStream?.readBytes()
                inputStream?.close()

                val mime = context.contentResolver.getType(it) ?: "image/jpeg"
                selectedMimeType = mime
                selectedFileName = "receipt_${System.currentTimeMillis()}.${if (mime.contains("png")) "png" else if (mime.contains("pdf")) "pdf" else "jpg"}"

                if (bytes != null) {
                    if (bytes.size > 10 * 1024 * 1024) {
                        errorMessage = "File size exceeds 10MB limit. Please choose a smaller image."
                        selectedFileBytes = null
                    } else {
                        selectedFileBytes = bytes
                    }
                }
            } catch (e: Exception) {
                errorMessage = "Could not read receipt file: ${e.message}"
            }
        }
    }

    fun startUpload() {
        val bytes = selectedFileBytes ?: return
        scope.launch {
            isUploading = true
            errorMessage = null
            uploadStatusMessage = "Creating expense claim draft..."

            // 1. Create Draft
            apiClient.createExpense(
                CreateExpenseRequest(
                    channel = ExpenseChannel.ANDROID
                )
            ).onSuccess { draftExpense ->
                uploadStatusMessage = "Uploading receipt evidence (${(bytes.size / 1024)} KB)..."
                
                // 2. Upload Receipt Content
                apiClient.uploadReceipt(
                    expenseId = draftExpense.id,
                    filename = selectedFileName,
                    mimeType = selectedMimeType,
                    fileBytes = bytes
                ).onSuccess {
                    uploadStatusMessage = "Receipt uploaded! Loading extraction review..."
                    isUploading = false
                    onUploadSuccess(draftExpense.id)
                }.onFailure { uploadErr ->
                    isUploading = false
                    uploadStatusMessage = null
                    errorMessage = NetworkConfig.describeConnectionProblem(uploadErr)
                }
            }.onFailure { draftErr ->
                isUploading = false
                uploadStatusMessage = null
                errorMessage = NetworkConfig.describeConnectionProblem(draftErr)
            }
        }
    }

    ProoflineScaffold(
        title = "Capture Receipt",
        onBackClick = onBackClick
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(ProoflineDimensions.SpacingMd),
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Text(
                    text = "Photograph or Import Receipt",
                    style = MaterialTheme.typography.titleLarge
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Ensure merchant name, date, itemization, and total amount are clearly visible.",
                    style = MaterialTheme.typography.bodyMedium
                )

                Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))

                // Upload & Preview Card
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(280.dp)
                        .clip(RoundedCornerShape(ProoflineDimensions.RadiusMd))
                        .background(ProoflineColors.SurfaceMuted)
                        .border(
                            1.dp,
                            if (selectedImageUri != null) ProoflineColors.Accent else ProoflineColors.Border,
                            RoundedCornerShape(ProoflineDimensions.RadiusMd)
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    if (selectedImageUri != null) {
                        Image(
                            painter = rememberAsyncImagePainter(model = selectedImageUri),
                            contentDescription = "Receipt preview",
                            modifier = Modifier.fillMaxSize(),
                            contentScale = ContentScale.Fit
                        )
                    } else {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.Center
                        ) {
                            Icon(
                                imageVector = Icons.Default.AddPhotoAlternate,
                                contentDescription = "Select photo",
                                tint = ProoflineColors.TextMuted,
                                modifier = Modifier.size(56.dp)
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = "No receipt selected",
                                style = MaterialTheme.typography.bodyLarge,
                                color = ProoflineColors.TextMuted
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "Supports JPG, PNG, or PDF up to 10MB",
                                style = MaterialTheme.typography.labelSmall
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingMd))

                if (errorMessage != null) {
                    ProoflineCard {
                        Text(
                            text = "Notice",
                            style = MaterialTheme.typography.headlineMedium,
                            color = ProoflineColors.StatusRejected
                        )
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = errorMessage ?: "",
                            style = MaterialTheme.typography.bodyMedium,
                            color = ProoflineColors.Text
                        )
                    }
                    Spacer(modifier = Modifier.height(ProoflineDimensions.SpacingSm))
                }

                if (uploadStatusMessage != null) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(ProoflineDimensions.RadiusSm))
                            .background(ProoflineColors.SurfaceRaised)
                            .padding(ProoflineDimensions.SpacingSm),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            color = ProoflineColors.Accent,
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = uploadStatusMessage ?: "",
                            style = MaterialTheme.typography.bodyMedium,
                            color = ProoflineColors.Text
                        )
                    }
                }
            }

            // Bottom Action Buttons
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(ProoflineDimensions.SpacingSm)
            ) {
                OutlinedButton(
                    onClick = { photoPickerLauncher.launch("image/*") },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(ProoflineDimensions.MinTouchTarget),
                    shape = RoundedCornerShape(ProoflineDimensions.RadiusSm)
                ) {
                    Icon(imageVector = Icons.Default.UploadFile, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(if (selectedImageUri == null) "Select Image from Gallery" else "Choose Different Image")
                }

                Button(
                    onClick = { startUpload() },
                    enabled = selectedFileBytes != null && !isUploading,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(ProoflineDimensions.MinTouchTarget),
                    shape = RoundedCornerShape(ProoflineDimensions.RadiusSm),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = ProoflineColors.Accent,
                        disabledContainerColor = ProoflineColors.SurfaceRaised
                    )
                ) {
                    if (isUploading) {
                        CircularProgressIndicator(
                            color = ProoflineColors.Text,
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp
                        )
                    } else {
                        Text(
                            text = "Upload & Extract",
                            fontWeight = FontWeight.SemiBold,
                            color = ProoflineColors.Text
                        )
                    }
                }
            }
        }
    }
}
