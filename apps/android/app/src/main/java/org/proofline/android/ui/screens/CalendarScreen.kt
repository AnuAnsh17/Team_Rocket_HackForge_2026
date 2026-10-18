package org.proofline.android.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronLeft
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import org.proofline.android.data.repository.TravelDayRepository
import org.proofline.android.ui.viewmodel.ProoflineUiState
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.TextStyle
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CalendarScreen(
    state: ProoflineUiState,
    travelRepo: TravelDayRepository,
    onNavigateToCapture: () -> Unit,
    onExpenseClick: (String) -> Unit
) {
    var currentYearMonth by remember { mutableStateOf(YearMonth.now()) }
    var selectedDate by remember { mutableStateOf<LocalDate?>(null) }
    val sheetState = rememberModalBottomSheetState()
    var showBottomSheet by remember { mutableStateOf(false) }

    val daysInMonth = currentYearMonth.lengthOfMonth()
    val firstDayOfMonth = currentYearMonth.atDay(1)
    val dayOfWeekValue = firstDayOfMonth.dayOfWeek.value
    val startOffset = dayOfWeekValue % 7

    val claimedDates = state.expenses
        .filter { it.status != "draft" && it.expense_date?.value != null }
        .mapNotNull { it.expense_date?.value }
        .toSet()

    val travelDates = travelRepo.getAll()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "Expense Calendar",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )

        // Month Navigation Header
        Card(
            modifier = Modifier.fillMaxWidth()
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = { currentYearMonth = currentYearMonth.minusMonths(1) }) {
                    Icon(Icons.Default.ChevronLeft, contentDescription = "Previous Month")
                }
                Text(
                    text = "${currentYearMonth.month.getDisplayName(TextStyle.FULL, Locale.getDefault())} ${currentYearMonth.year}",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                IconButton(onClick = { currentYearMonth = currentYearMonth.plusMonths(1) }) {
                    Icon(Icons.Default.ChevronRight, contentDescription = "Next Month")
                }
            }
        }

        // Weekday Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceAround
        ) {
            val weekdays = listOf("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
            for (day in weekdays) {
                Text(
                    text = day,
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.width(40.dp),
                    textAlign = TextAlign.Center
                )
            }
        }

        // Calendar Grid
        Card(
            modifier = Modifier.fillMaxWidth()
        ) {
            LazyVerticalGrid(
                columns = GridCells.Fixed(7),
                modifier = Modifier.padding(8.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                items(startOffset) {
                    Box(modifier = Modifier.size(40.dp))
                }

                items(daysInMonth) { index ->
                    val dayNum = index + 1
                    val date = currentYearMonth.atDay(dayNum)
                    val dateStr = date.toString()
                    val isClaimed = claimedDates.contains(dateStr)
                    val isTravel = travelDates.contains(dateStr)
                    val isToday = date == LocalDate.now()

                    val cellBg = when {
                        isClaimed -> Color(0xFF3FA87A)
                        isTravel -> Color(0xFFD4665F)
                        else -> MaterialTheme.colorScheme.surfaceVariant
                    }

                    val textColor = if (isClaimed || isTravel) Color.White else MaterialTheme.colorScheme.onSurfaceVariant

                    Box(
                        modifier = Modifier
                            .size(44.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(cellBg)
                            .then(
                                if (isToday) Modifier.border(2.dp, MaterialTheme.colorScheme.primary, RoundedCornerShape(8.dp))
                                else Modifier
                            )
                            .clickable {
                                selectedDate = date
                                showBottomSheet = true
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = dayNum.toString(),
                            color = textColor,
                            fontWeight = FontWeight.Bold,
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }
            }
        }

        // Legend
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly
        ) {
            LegendItem(color = Color(0xFF3FA87A), label = "Claimed")
            LegendItem(color = Color(0xFFD4665F), label = "Travel (Unclaimed)")
            LegendItem(color = MaterialTheme.colorScheme.surfaceVariant, label = "Neutral")
        }
    }

    if (showBottomSheet && selectedDate != null) {
        val dateStr = selectedDate.toString()
        val expensesForDay = state.expenses.filter { it.expense_date?.value == dateStr }
        val isTravel = travelDates.contains(dateStr)

        ModalBottomSheet(
            onDismissRequest = { showBottomSheet = false },
            sheetState = sheetState
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(24.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                Text(
                    text = "Date: $dateStr",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold
                )

                if (expensesForDay.isNotEmpty()) {
                    Text("Claims on this date:", fontWeight = FontWeight.Bold)
                    for (exp in expensesForDay) {
                        Card(
                            onClick = {
                                showBottomSheet = false
                                onExpenseClick(exp.id)
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(12.dp),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(exp.merchant?.value ?: "Unknown")
                                Text("${exp.amount?.value?.currency ?: ""} ${exp.amount?.value?.value ?: "0"}")
                            }
                        }
                    }
                } else {
                    Text("No claims recorded for this date.")
                }

                Divider()

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("Travel day status:")
                    Button(
                        onClick = {
                            if (isTravel) travelRepo.unmarkTravel(dateStr)
                            else travelRepo.markTravel(dateStr)
                            showBottomSheet = false
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (isTravel) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.error
                        )
                    ) {
                        Text(if (isTravel) "Remove Travel Day" else "Mark as Travel Day")
                    }
                }

                Button(
                    onClick = {
                        showBottomSheet = false
                        onNavigateToCapture()
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Add receipt for this day")
                }
            }
        }
    }
}

@Composable
fun LegendItem(color: Color, label: String) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        Box(
            modifier = Modifier
                .size(14.dp)
                .clip(CircleShape)
                .background(color)
        )
        Text(text = label, style = MaterialTheme.typography.labelSmall)
    }
}
