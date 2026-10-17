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
}
