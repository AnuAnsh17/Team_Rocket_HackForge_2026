package org.proofline.android.data.model

data class DemoActor(val key: String, val name: String, val uuid: String)

object DemoActors {
    val all = listOf(
        DemoActor("employee.asha", "Asha Menon (Employee)", "6dbc60b8-8577-56ec-806e-4201fa5993c4"),
        DemoActor("employee.rohit", "Rohit Verma (Employee)", "d2f41053-55b2-5425-8914-996792256d45"),
        DemoActor("manager.priya", "Priya Nair (Manager)", "bdcc13dc-e744-5f80-b8f4-6e11758dd783"),
        DemoActor("finance.reviewer", "Kabir Shah (Finance Reviewer)", "21d298e6-e589-5485-8900-3cbbfdc0c66b"),
        DemoActor("finance.admin", "Meera Iyer (Finance Admin)", "01613bdb-528d-5ff3-979b-ba292d858d77"),
        DemoActor("hr.reviewer", "Sana Qureshi (HR Reviewer)", "ffda55e4-4ec1-54ed-8bf6-ac585cf18550"),
        DemoActor("org.admin", "Dev Anand (Org Admin)", "ca08fe0d-20b9-5771-b61e-99465e56ba0e"),
        DemoActor("policy.admin", "Ira Bose (Policy Admin)", "1a234278-3386-531c-9b51-af650c9fb34d"),
        DemoActor("auditor", "Nikhil Rao (Auditor)", "fbe06d8f-3735-59f1-bed9-8f6154257584")
    )
    val default = all[0].uuid
}
