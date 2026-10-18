package org.proofline.android

import com.google.gson.GsonBuilder
import com.google.gson.JsonParseException
import org.junit.Test
import org.junit.Assert.*
import org.proofline.android.data.model.Money
import org.proofline.android.data.model.MoneyDeserializer

class MoneySerializationTest {
    private val gson = GsonBuilder()
        .registerTypeAdapter(Money::class.java, MoneyDeserializer())
        .create()

    @Test
    fun testMoneyDecimalPrecisionRoundTrip() {
        val original = Money(value = "1400.00", currency = "INR")
        val json = gson.toJson(original)
        val deserialized = gson.fromJson(json, Money::class.java)

        assertEquals("1400.00", deserialized.value)
        assertEquals("INR", deserialized.currency)
        assertTrue(json.contains("\"1400.00\""))
    }

    @Test(expected = JsonParseException::class)
    fun testMoneyRejectsDoubleInsteadOfString() {
        val badJson = "{\"value\": 1400.00, \"currency\": \"INR\"}"
        gson.fromJson(badJson, Money::class.java)
    }
}
