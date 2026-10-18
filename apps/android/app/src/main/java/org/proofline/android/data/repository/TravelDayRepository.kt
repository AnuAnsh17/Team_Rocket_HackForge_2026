package org.proofline.android.data.repository

import android.content.Context
import android.content.SharedPreferences

class TravelDayRepository(context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences("proofline_travel_days", Context.MODE_PRIVATE)

    fun markTravel(date: String) {
        val current = getAll().toMutableSet()
        current.add(date)
        prefs.edit().putString("travel_days", current.joinToString(",")).apply()
    }

    fun unmarkTravel(date: String) {
        val current = getAll().toMutableSet()
        current.remove(date)
        prefs.edit().putString("travel_days", current.joinToString(",")).apply()
    }

    fun isTravel(date: String): Boolean {
        return getAll().contains(date)
    }

    fun getAll(): Set<String> {
        val str = prefs.getString("travel_days", "") ?: ""
        if (str.isBlank()) return emptySet()
        return str.split(",").toSet()
    }
}
