export type AuditStatus = 'PASS' | 'FAIL' | 'UNKNOWN';

export type Priority = 'HIGH' | 'MEDIUM' | 'LOW';

export type IssueType =
  | 'POLICY_VIOLATION'
  | 'DUPLICATE_CANDIDATE'
  | 'MISSING_INFO'
  | 'UNREADABLE_RECEIPT'
  | 'ARITHMETIC_MISMATCH'
  | 'NONE';

export type ExpenseCategory =
  | 'Travel'
  | 'Meals'
  | 'Lodging'
  | 'Supplies'
  | 'Client Entertainment';

export type ApprovalStage =
  | 'Manager Approval'
  | 'Finance Audit'
  | 'Returned for Correction'
  | 'Approved for Payout'
  | 'Reimbursed';

export interface LineItem {
  id: string;
  description: string;
  quantity: number;
  unitPrice: number;
  total: number;
  isProhibited?: boolean;
}

export interface BoundingBoxHighlight {
  id: string;
  x: number; // percentage 0-100
  y: number;
  w: number;
  h: number;
  label: string;
  field: string;
  issueType?: 'faded' | 'handwritten' | 'cropped' | 'mismatch' | 'flagged';
  confidence: number;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  prevStatus?: AuditStatus;
  newStatus?: AuditStatus;
  note: string;
  policyClause?: string;
}

export interface Claim {
  id: string; // e.g. "CLM-8491"
  employeeId: string; // e.g. "EMP-1048"
  employeeName: string;
  employeeDept: string;
  employeeRole: string;
  managerName: string;
  costCenter: string;
  
  merchantName: string;
  merchantGstin?: string;
  merchantCity: string;
  cityTier: 'Tier 1' | 'Tier 2' | 'Tier 3';
  category: ExpenseCategory;
  
  submissionDate: string;
  expenseDate: string;
  submissionLatencyDays: number; // days between expenseDate and submissionDate
  
  claimedAmount: number;
  extractedSubtotal: number;
  extractedTax: number;
  extractedTotal: number;
  arithmeticMismatch: boolean;
  
  lineItems: LineItem[];
  
  status: AuditStatus;
  priority: Priority;
  issueType: IssueType;
  issueDescription: string;
  
  policyClauseCited?: string;
  policyRuleTitle?: string;
  
  // Cumulative context
  priorSpendSameDay: number;
  priorSpendSameMonth: number;
  dailyCap?: number;
  monthlyCap?: number;
  
  // Investigation fields
  receiptImageUrl?: string;
  receiptType: 'tax_invoice' | 'thermal_slip' | 'handwritten_bill' | 'digital_invoice';
  boundingBoxes: BoundingBoxHighlight[];
  confidenceScore: number;
  
  attendeesCount?: number;
  requiredAttendees?: number;
  hasClientAttendee?: boolean;
  
  duplicateCandidateId?: string;
  duplicateMatchScore?: number;
  
  approvalStage: ApprovalStage;
  assignedAuditor: string;
  daysWaiting: number;
  
  notes?: string;
  auditTrail: AuditLogEntry[];
}

export interface PolicyRule {
  id: string;
  code: string; // e.g. "POL-4.2"
  title: string;
  category: ExpenseCategory;
  description: string;
  ruleLogic: string;
  clauseCitation: string; // e.g. "Page 5, Sec 2.1"
  limitAmount?: number;
  currency: string;
  period: 'Daily' | 'Monthly' | 'Per-Claim' | 'None';
  cityTier?: 'Tier 1' | 'Tier 2' | 'Tier 3' | 'All';
  status: 'Active' | 'Draft' | 'Deprecated';
  lastUpdated: string;
}

export interface DuplicatePair {
  id: string;
  claimA: Claim;
  claimB: Claim;
  perceptualHashMatch: number; // e.g. 96.5%
  fuzzyMerchantMatch: number; // e.g. 100%
  amountMatch: boolean;
  dateMatch: boolean;
  channelComparison: string;
  status: 'Possible Match (Under Review)' | 'Confirmed Duplicate' | 'Dismissed (Legitimate)';
  resolutionNotes?: string;
}

export interface EmployeeProfile {
  id: string;
  name: string;
  department: string;
  role: string;
  manager: string;
  costCenter: string;
  corporateCardAssigned: boolean;
  complianceHealthScore: number; // 0-100
  totalClaimsCount: number;
  onTimeSubmissionsCount: number;
  delayedSubmissionsCount: number;
  overdueSubmissionsCount: number;
  monthlySpendHistory: { month: string; amount: number; budget: number }[];
  categoryDistribution: { category: ExpenseCategory; amount: number }[];
}

export interface MerchantInsight {
  id: string;
  name: string;
  category: ExpenseCategory;
  totalVolume: number;
  claimCount: number;
  errorRate: number; // percentage
  missingTaxRate: number; // percentage
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH';
  commonIssue: string;
}

export type ActiveTab =
  | 'landing'
  | 'overview'
  | 'audit-queue'
  | 'workbench'
  | 'duplicates'
  | 'spending-analytics'
  | 'approvals'
  | 'employee-merchants'
  | 'policy-studio'
  | 'audit-trail';
