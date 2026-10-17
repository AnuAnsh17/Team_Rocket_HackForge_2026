export interface paths {
    "/api/v1/demo/import/email": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Simulate an email-channel submission (NOT IMPLEMENTED)
         * @description The contract describes this route for demoing a cross-channel duplicate. It is not implemented, and it must never be presented as a real email integration.
         */
        post: operations["simulate_email_import_api_v1_demo_import_email_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/demo/reset": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Remove only the synthetic demo dataset (demo mode only)
         * @description Deletes the fixed demo organization and demo-provider users. Non-demo data is not reachable from this operation. Audit events are append-only and survive the reset; the reset itself is recorded as an audit event.
         */
        post: operations["reset_api_v1_demo_reset_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/demo/seed": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Load the synthetic demo dataset (demo mode only)
         * @description Loads deterministic, clearly labelled synthetic data: one fictional organization, fictional people, memberships, role grants and reporting edges, plus an unapproved and empty policy version. Creates no policy rules and no allowance limits, because both require real organizational data and a verified policy clause.
         */
        post: operations["seed_api_v1_demo_seed_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/expenses": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create an employee-owned draft expense
         * @description Creates a draft for the caller's active membership so a receipt can be attached. This workflow slice does not support creating claims for another employee.
         */
        post: operations["create_draft_expense_api_v1_expenses_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/expenses/{expense_id}/receipts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List authorized receipts and extraction runs for an expense */
        get: operations["list_expense_receipts_api_v1_expenses__expense_id__receipts_get"];
        put?: never;
        /**
         * Upload a private receipt and queue extraction
         * @description Uploads one original receipt to a caller-owned draft, validates its content and persists a pending extraction run for background processing. Exact duplicate files remain separate receipts and are linked only by their SHA-256 signal.
         */
        post: operations["upload_receipt_api_v1_expenses__expense_id__receipts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/expenses/{expense_id}/receipts/batch": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Upload a batch of up to 20 independent receipts
         * @description Stores each validated receipt and creates its own persisted pending extraction run. A batch is limited to 20 files; each receipt is processed independently.
         */
        post: operations["upload_receipt_batch_api_v1_expenses__expense_id__receipts_batch_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Service health
         * @description Reports service health, the database probe result and the status of each dependency. Contains no secrets, no connection strings and no stack traces. Unauthenticated by design so a load balancer can reach it.
         */
        get: operations["health_api_v1_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * The authenticated employee's own membership
         * @description Resolves the caller's own organization membership. The actor is derived from the validated identity and server-side role grants; nothing about identity, role or scope is taken from the request body or query string.
         */
        get: operations["read_me_api_v1_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Audit events attributed to the authenticated actor
         * @description An employee may read their own audit trail. Reading another actor's trail requires a scoped review permission and is not exposed here.
         */
        get: operations["read_my_audit_api_v1_me_audit_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/roles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * The authenticated actor's own role grants
         * @description Returns the caller's own non-revoked role grants with the scope each applies to. Granted only through organization memberships; a client cannot request someone else's grants, because the membership is taken from the validated identity.
         */
        get: operations["read_my_roles_api_v1_me_roles_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/meta": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Service and contract metadata
         * @description Contract version, implemented endpoint count and the list of capabilities the contract describes but this build does not implement.
         */
        get: operations["meta_api_v1_meta_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/meta/enums": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Canonical enum catalogue
         * @description Every enumerated value in the canonical contract, keyed by the name used in docs/api-contract.md. Clients must not invent local alternatives; a divergence between a client's list and this endpoint is a bug.
         */
        get: operations["enums_api_v1_meta_enums_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/receipts/{receipt_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read authorized receipt metadata and OCR status */
        get: operations["read_receipt_api_v1_receipts__receipt_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/receipts/{receipt_id}/content": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Stream authorized private receipt content
         * @description The endpoint rechecks receipt and expense authorization on every request.
         */
        get: operations["read_receipt_content_api_v1_receipts__receipt_id__content_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/receipts/{receipt_id}/extractions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Retry extraction for an authorized receipt
         * @description Appends a new extraction run for a receipt owned by the caller. Previous run results are preserved and never overwritten.
         */
        post: operations["retry_receipt_extraction_api_v1_receipts__receipt_id__extractions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * ApiMetaResponse
         * @description Service and contract identity.
         */
        ApiMetaResponse: {
            /** Api Version */
            api_version: string;
            /** App Version */
            app_version: string;
            /**
             * Contract Version
             * @description Version label of docs/api-contract.md this build implements.
             */
            contract_version: string;
            /** Demo Mode */
            demo_mode: boolean;
            /** Environment */
            environment: string;
            /**
             * Implemented Endpoint Count
             * @description Number of routes this build actually serves. Exposed so a caller can tell a scaffold apart from a complete implementation without guessing.
             */
            implemented_endpoint_count: number;
            /**
             * Unimplemented Capabilities
             * @description Capabilities the contract describes but this build does not implement. Reported explicitly so nothing silently pretends to work.
             */
            unimplemented_capabilities?: string[];
        };
        /**
         * AuditActorType
         * @enum {string}
         */
        AuditActorType: "user" | "system" | "service" | "demo";
        /** AuditEventListResponse */
        AuditEventListResponse: {
            /** Items */
            items: components["schemas"]["AuditEventResponse"][];
            page: components["schemas"]["PageInfo"];
        };
        /**
         * AuditEventResponse
         * @description One append-only audit event.
         *
         *     ``before``/``after`` are safe diffs: they contain the fields that changed and
         *     never raw receipt content, OCR text or credentials.
         */
        AuditEventResponse: {
            /** Action */
            action: string;
            /** Actor Label */
            actor_label?: string | null;
            actor_type: components["schemas"]["AuditActorType"];
            /** Actor User Id */
            actor_user_id?: string | null;
            /** After */
            after?: {
                [key: string]: unknown;
            } | null;
            /** Before */
            before?: {
                [key: string]: unknown;
            } | null;
            /**
             * Correlation Id
             * @description Ties this event to the request that caused it and to the server log line.
             */
            correlation_id?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Entity Id */
            entity_id?: string | null;
            /** Entity Type */
            entity_type: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Policy Version Id */
            policy_version_id?: string | null;
            /** Reason */
            reason?: string | null;
        };
        /** Body_upload_receipt_api_v1_expenses__expense_id__receipts_post */
        Body_upload_receipt_api_v1_expenses__expense_id__receipts_post: {
            /** File */
            file: string;
        };
        /** Body_upload_receipt_batch_api_v1_expenses__expense_id__receipts_batch_post */
        Body_upload_receipt_batch_api_v1_expenses__expense_id__receipts_batch_post: {
            /** Files */
            files: string[];
        };
        /**
         * CreateExpenseRequest
         * @description Create a draft claim from JSON metadata.
         *
         *     Receipt images are uploaded separately through
         *     ``POST /api/v1/expenses/{expense_id}/receipts`` - the single canonical upload
         *     route. This request deliberately carries no ``source`` or ``reviewed``
         *     fields: provenance is assigned by the server from the caller's role, so a
         *     client cannot claim reviewer provenance.
         */
        CreateExpenseRequest: {
            /** Amount */
            amount?: string | null;
            /** Attendee Count */
            attendee_count?: number | null;
            /** Business Purpose */
            business_purpose?: string | null;
            /** Category */
            category?: string | null;
            /** @default web */
            channel: components["schemas"]["ExpenseChannel"];
            /** Client Name */
            client_name?: string | null;
            /** Currency */
            currency?: string | null;
            /**
             * Employee Membership Id
             * @description Only accepted from a caller authorized to create on behalf of another employee. An employee's own claims are always created against their own membership.
             */
            employee_membership_id?: string | null;
            /** Expense Date */
            expense_date?: string | null;
            /** Merchant */
            merchant?: string | null;
            /** Trip Id */
            trip_id?: string | null;
        };
        /** DemoResetResponse */
        DemoResetResponse: {
            /** Dataset */
            dataset: string;
            /** Notes */
            notes?: string[];
            /** Organizations Removed */
            organizations_removed: number;
            /** Users Removed */
            users_removed: number;
        };
        /** DemoSeedResponse */
        DemoSeedResponse: {
            /**
             * Dataset
             * @description Identifier of the synthetic fixture set that was loaded.
             */
            dataset: string;
            /** Memberships */
            memberships: number;
            /** Notes */
            notes?: string[];
            /** Organizations */
            organizations: number;
            /**
             * Policy Rules Activated
             * @description Always 0. The seed never activates a policy rule, because no source policy document has been supplied and a rule cannot be activated without a verified clause.
             * @default 0
             */
            policy_rules_activated: number;
            /**
             * Synthetic
             * @description Always true. No real receipt or employee data is ever seeded.
             * @default true
             */
            synthetic: boolean;
            /** Users */
            users: number;
        };
        /**
         * DerivationType
         * @description How a derived receipt object relates to its parent.
         * @enum {string}
         */
        DerivationType: "original" | "crop" | "rotation" | "recompression" | "thumbnail";
        /**
         * DraftExpenseResponse
         * @description Minimal response needed to attach a receipt to an employee-owned draft.
         */
        DraftExpenseResponse: {
            channel: components["schemas"]["ExpenseChannel"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            status: components["schemas"]["ExpenseStatus"];
            /** Version */
            version: number;
        };
        /**
         * EnumCatalogueResponse
         * @description Every canonical enum, keyed by the name used in docs/api-contract.md.
         */
        EnumCatalogueResponse: {
            /**
             * Enums
             * @description Enum name -> ordered list of permitted values.
             */
            enums: {
                [key: string]: string[];
            };
        };
        /**
         * ExpenseChannel
         * @description How a claim entered the system.
         *
         *     ``EMAIL_SIMULATED`` is demo-only and must never be presented as a real
         *     email integration.
         * @enum {string}
         */
        ExpenseChannel: "android" | "web" | "bulk" | "email_simulated";
        /**
         * ExpenseStatus
         * @description Workflow status of an expense claim.
         *
         *     Deliberately NOT used to represent individual findings: a claim can carry
         *     many findings while holding exactly one workflow status.
         *
         *     ``WITHDRAWN`` is reserved. No endpoint currently produces it; see
         *     docs/api-contract.md section 5 for the explanation.
         * @enum {string}
         */
        ExpenseStatus: "draft" | "submitted" | "needs_info" | "in_review" | "approved" | "rejected" | "withdrawn";
        /**
         * ExtractionRunSummary
         * @description One historical extraction attempt. Past runs are never rewritten.
         */
        ExtractionRunSummary: {
            /**
             * Attempt Count
             * @default 0
             */
            attempt_count: number;
            /** Error Code */
            error_code?: string | null;
            /** Finished At */
            finished_at?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Is Cached Result
             * @description True when the result came from a verified cache rather than live inference. A cached result is never presented as live extraction.
             * @default false
             */
            is_cached_result: boolean;
            /** Latency Ms */
            latency_ms?: number | null;
            /** Model */
            model?: string | null;
            /** Prompt Version */
            prompt_version?: string | null;
            /** Provider */
            provider: string;
            /** Started At */
            started_at?: string | null;
            status: components["schemas"]["ExtractionStatus"];
            structured_result?: components["schemas"]["ReceiptExtractionData"] | null;
            validation_result?: components["schemas"]["ReceiptValidationResult"] | null;
        };
        /**
         * ExtractionStatus
         * @enum {string}
         */
        ExtractionStatus: "pending" | "running" | "success" | "partial" | "failed" | "unavailable";
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * HealthComponent
         * @description Status of one dependency.
         */
        HealthComponent: {
            /**
             * Detail
             * @description Stable machine-readable code such as DATABASE_UNAVAILABLE. Never a raw error.
             */
            detail?: string | null;
            /** Latency Ms */
            latency_ms?: number | null;
            /**
             * Status
             * @enum {string}
             */
            status: "ok" | "unavailable" | "not_configured" | "not_implemented" | "degraded";
        };
        /**
         * HealthResponse
         * @description Aggregate service health.
         */
        HealthResponse: {
            /**
             * Api Version
             * @description Advertised API version prefix, for example v1.
             */
            api_version: string;
            /** App Version */
            app_version: string;
            /**
             * Checked At
             * Format: date-time
             */
            checked_at: string;
            /**
             * Components
             * @description Per-dependency status keyed by a stable component name.
             */
            components: {
                [key: string]: components["schemas"]["HealthComponent"];
            };
            /**
             * Demo Mode
             * @description True when demo routes and the demo identity switcher are active.
             */
            demo_mode: boolean;
            /** Environment */
            environment: string;
            /**
             * Status
             * @enum {string}
             */
            status: "ok" | "degraded" | "unavailable";
        };
        /**
         * MembershipStatus
         * @description Employment state of an organization membership.
         * @enum {string}
         */
        MembershipStatus: "active" | "on_leave" | "suspended" | "terminated" | "invited";
        /**
         * MembershipSummary
         * @description An employee's organizational position, as needed for display and routing.
         */
        MembershipSummary: {
            /** Cost Center Name */
            cost_center_name?: string | null;
            /** Department Name */
            department_name?: string | null;
            /** Employee Code */
            employee_code?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Job Grade Name
             * @description Grade label only. Never used by a client to infer an allowance: the effective allowance comes from the resolved policy assignment.
             */
            job_grade_name?: string | null;
            /** Joined On */
            joined_on?: string | null;
            /** Manager Membership Id */
            manager_membership_id?: string | null;
            /** Office Location Name */
            office_location_name?: string | null;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            status: components["schemas"]["MembershipStatus"];
            user: components["schemas"]["UserSummary"];
        };
        /**
         * PageInfo
         * @description Pagination metadata.
         */
        PageInfo: {
            /** Limit */
            limit: number;
            /**
             * Next Cursor
             * @description Opaque cursor for the next page. Null on the final page.
             */
            next_cursor?: string | null;
            /**
             * Total
             * @description Total matching rows, or null when the count is intentionally omitted.
             */
            total?: number | null;
        };
        /**
         * ReceiptExtractionData
         * @description Persisted/public extraction data with server-owned version metadata.
         */
        ReceiptExtractionData: {
            currency?: components["schemas"]["ReceiptField_Annotated_str__FieldInfo_annotation_NoneType__required_True__metadata___PydanticGeneralMetadata_pattern____A-Z__3________"];
            discount?: components["schemas"]["ReceiptField_Annotated_Decimal__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            grand_total?: components["schemas"]["ReceiptField_Annotated_Decimal__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            /** Line Items */
            line_items?: components["schemas"]["ReceiptLineItem"][];
            merchant?: components["schemas"]["ReceiptField_Annotated_str__FieldInfo_annotation_NoneType__required_True__metadata__MinLen_min_length_1___MaxLen_max_length_300_____"];
            receipt_number?: components["schemas"]["ReceiptField_Annotated_str__FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_120_____"];
            /**
             * Schema Version
             * @default 1.0
             * @constant
             */
            schema_version: "1.0";
            subtotal?: components["schemas"]["ReceiptField_Annotated_Decimal__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            tax_total?: components["schemas"]["ReceiptField_Annotated_Decimal__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            tip?: components["schemas"]["ReceiptField_Annotated_Decimal__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            transaction_date?: components["schemas"]["ReceiptField_Annotated_date__BeforeValidator__"];
        };
        /**
         * ReceiptFieldStatus
         * @enum {string}
         */
        ReceiptFieldStatus: "extracted" | "missing" | "ambiguous" | "illegible" | "not_applicable";
        /** ReceiptField[Annotated[Decimal, BeforeValidator, PlainSerializer, WithJsonSchema]] */
        ReceiptField_Annotated_Decimal__BeforeValidator__PlainSerializer__WithJsonSchema__: {
            status: components["schemas"]["ReceiptFieldStatus"];
            /** Value */
            value?: string | null;
        };
        /** ReceiptField[Annotated[date, BeforeValidator]] */
        ReceiptField_Annotated_date__BeforeValidator__: {
            status: components["schemas"]["ReceiptFieldStatus"];
            /** Value */
            value?: string | null;
        };
        /** ReceiptField[Annotated[str, FieldInfo(annotation=NoneType, required=True, metadata=[MaxLen(max_length=120)])]] */
        ReceiptField_Annotated_str__FieldInfo_annotation_NoneType__required_True__metadata__MaxLen_max_length_120_____: {
            status: components["schemas"]["ReceiptFieldStatus"];
            /** Value */
            value?: string | null;
        };
        /** ReceiptField[Annotated[str, FieldInfo(annotation=NoneType, required=True, metadata=[MinLen(min_length=1), MaxLen(max_length=300)])]] */
        ReceiptField_Annotated_str__FieldInfo_annotation_NoneType__required_True__metadata__MinLen_min_length_1___MaxLen_max_length_300_____: {
            status: components["schemas"]["ReceiptFieldStatus"];
            /** Value */
            value?: string | null;
        };
        /** ReceiptField[Annotated[str, FieldInfo(annotation=NoneType, required=True, metadata=[_PydanticGeneralMetadata(pattern='^[A-Z]{3}$')])]] */
        "ReceiptField_Annotated_str__FieldInfo_annotation_NoneType__required_True__metadata___PydanticGeneralMetadata_pattern____A-Z__3________": {
            status: components["schemas"]["ReceiptFieldStatus"];
            /** Value */
            value?: string | null;
        };
        /** ReceiptLineItem */
        ReceiptLineItem: {
            description?: components["schemas"]["ReceiptField_Annotated_str__FieldInfo_annotation_NoneType__required_True__metadata__MinLen_min_length_1___MaxLen_max_length_300_____"];
            line_total?: components["schemas"]["ReceiptField_Annotated_Decimal__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            quantity?: components["schemas"]["ReceiptField_Annotated_Decimal__BeforeValidator__PlainSerializer__WithJsonSchema__"];
            unit_price?: components["schemas"]["ReceiptField_Annotated_Decimal__BeforeValidator__PlainSerializer__WithJsonSchema__"];
        };
        /**
         * ReceiptResponse
         * @description Receipt metadata and extraction history.
         */
        ReceiptResponse: {
            /** Byte Size */
            byte_size: number;
            /** Content Url */
            content_url: string;
            derivation_type: components["schemas"]["DerivationType"];
            /** Detected Mime Type */
            detected_mime_type: string;
            /**
             * Expense Id
             * Format: uuid
             */
            expense_id: string;
            /** Extraction Runs */
            extraction_runs?: components["schemas"]["ExtractionRunSummary"][];
            extraction_status: components["schemas"]["ExtractionStatus"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Image Height */
            image_height?: number | null;
            /** Image Width */
            image_width?: number | null;
            /** Original Filename */
            original_filename?: string | null;
            /** Page Count */
            page_count?: number | null;
            /** Parent Receipt Id */
            parent_receipt_id?: string | null;
            /**
             * Perceptual Hash
             * @description Image similarity signal, valid only after orientation normalisation. Present only when a perceptual hash was actually computed.
             */
            perceptual_hash?: string | null;
            /**
             * Sha256
             * @description Byte hash. Used as an exact-duplicate signal.
             */
            sha256: string;
            storage_backend: components["schemas"]["StorageBackend"];
            /** Uploaded At */
            uploaded_at?: string | null;
        };
        /**
         * ReceiptUploadResponse
         * @description Receipt metadata and its initial persisted extraction state.
         */
        ReceiptUploadResponse: {
            /**
             * Extraction Scheduled
             * @description True when a persisted extraction run was queued for background processing.
             */
            extraction_scheduled: boolean;
            receipt: components["schemas"]["ReceiptResponse"];
        };
        /** ReceiptValidationFinding */
        ReceiptValidationFinding: {
            /** Code */
            code: string;
            /** Message */
            message: string;
            /** @default warning */
            severity: components["schemas"]["ValidationSeverity"];
        };
        /** ReceiptValidationResult */
        ReceiptValidationResult: {
            /** Findings */
            findings?: components["schemas"]["ReceiptValidationFinding"][];
            /**
             * Human Review Required
             * @default true
             */
            human_review_required: boolean;
            /** Review Reasons */
            review_reasons?: string[];
            /**
             * Validator Version
             * @default 1
             * @constant
             */
            validator_version: "1";
        };
        /**
         * RoleAssignmentSummary
         * @description A granted role, with the scope it applies to.
         */
        RoleAssignmentSummary: {
            /** Granted At */
            granted_at?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Revoked At */
            revoked_at?: string | null;
            role: components["schemas"]["RoleCode"];
            /**
             * Scope Id
             * Format: uuid
             */
            scope_id: string;
            /**
             * Scope Type
             * @description organization | department | cost_center | team | self
             */
            scope_type: string;
        };
        /**
         * RoleCode
         * @description Role identifiers granted through organization memberships.
         *
         *     A privileged-sounding role name never implies permissions. The actual
         *     permission set for each role lives in app/core/permissions.py and is
         *     documented in docs/authorization-matrix.md.
         * @enum {string}
         */
        RoleCode: "employee" | "manager" | "hr_reviewer" | "finance_reviewer" | "finance_admin" | "org_admin" | "policy_admin" | "auditor" | "service";
        /**
         * StorageBackend
         * @enum {string}
         */
        StorageBackend: "local" | "supabase" | "s3";
        /**
         * UserSummary
         * @description Minimal, safe representation of a person.
         */
        UserSummary: {
            /** Display Name */
            display_name: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Is Active
             * @default true
             */
            is_active: boolean;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /**
         * ValidationSeverity
         * @enum {string}
         */
        ValidationSeverity: "warning";
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    simulate_email_import_api_v1_demo_import_email_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    reset_api_v1_demo_reset_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DemoResetResponse"];
                };
            };
        };
    };
    seed_api_v1_demo_seed_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DemoSeedResponse"];
                };
            };
        };
    };
    create_draft_expense_api_v1_expenses_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateExpenseRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DraftExpenseResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_expense_receipts_api_v1_expenses__expense_id__receipts_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                expense_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReceiptResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_receipt_api_v1_expenses__expense_id__receipts_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                expense_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_receipt_api_v1_expenses__expense_id__receipts_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReceiptUploadResponse"];
                };
            };
            /** @description The upload exceeds RECEIPT_MAX_UPLOAD_BYTES. */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description The file content is not an accepted receipt format. */
            415: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_receipt_batch_api_v1_expenses__expense_id__receipts_batch_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                expense_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_receipt_batch_api_v1_expenses__expense_id__receipts_batch_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReceiptUploadResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    health_api_v1_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
    read_me_api_v1_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MembershipSummary"];
                };
            };
        };
    };
    read_my_audit_api_v1_me_audit_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuditEventListResponse"];
                };
            };
        };
    };
    read_my_roles_api_v1_me_roles_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RoleAssignmentSummary"][];
                };
            };
        };
    };
    meta_api_v1_meta_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiMetaResponse"];
                };
            };
        };
    };
    enums_api_v1_meta_enums_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnumCatalogueResponse"];
                };
            };
        };
    };
    read_receipt_api_v1_receipts__receipt_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                receipt_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReceiptResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_receipt_content_api_v1_receipts__receipt_id__content_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                receipt_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retry_receipt_extraction_api_v1_receipts__receipt_id__extractions_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                receipt_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReceiptResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
