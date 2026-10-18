package org.proofline.android

import com.google.gson.Gson
import org.junit.Test
import org.junit.Assert.*
import org.proofline.android.data.model.Money

class MoneySerializationTest {
    @Test
    fun testMoneyDecimalPrecisionRoundTrip() {
        val gson = Gson()
        val original = Money(value = "1400.00", currency = "INR")
        val json = gson.toJson(original)
        val deserialized = gson.fromJson(json, Money::class.java)

        assertEquals("1400.00", deserialized.value)
        assertEquals("INR", deserialized.currency)
        assertTrue(json.contains("\"1400.00\""))
    }

    @Test(expected = com.google.gson.JsonSyntaxException::class)
    fun testMoneyRejectsDoubleInsteadOfString() {
        val gson = Gson()
        val badJson = "{\"value\": 1400.00, \"currency\": \"INR\"}"
        gson.fromJson(badJson, Money::class.java)
    }
}
