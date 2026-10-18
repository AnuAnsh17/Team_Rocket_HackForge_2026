/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import {
  INITIAL_CLAIMS,
  INITIAL_POLICY_RULES,
  DUPLICATE_PAIRS,
  EMPLOYEE_PROFILES,
  MERCHANT_INSIGHTS,
  INITIAL_AUDIT_LOGS,
} from './data/mockData';
import {
  Claim,
  PolicyRule,
  DuplicatePair,
  EmployeeProfile,
  MerchantInsight,
  AuditLogEntry,
  ActiveTab,
  AuditStatus,
} from './types';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { AuthModal } from './components/AuthModal';
import { OverviewDashboard } from './views/OverviewDashboard';
import { AuditQueue } from './views/AuditQueue';
import { InvestigationWorkbench } from './views/InvestigationWorkbench';
import { DuplicateReview } from './views/DuplicateReview';
import { SpendingAnalytics } from './views/SpendingAnalytics';
import { ApprovalsPipeline } from './views/ApprovalsPipeline';
import { EmployeeMerchantProfiles } from './views/EmployeeMerchantProfiles';
import { PolicyStudio } from './views/PolicyStudio';
import { AuditTrail } from './views/AuditTrail';
import { LandingPage } from './views/LandingPage';
import { Check, Info, X } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('landing');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [currentUserRole, setCurrentUserRole] = useState('Lead Finance Auditor');

  // Application Data State
  const [claims, setClaims] = useState<Claim[]>(INITIAL_CLAIMS);
  const [policyRules, setPolicyRules] = useState<PolicyRule[]>(INITIAL_POLICY_RULES);
  const [duplicatePairs, setDuplicatePairs] = useState<DuplicatePair[]>(DUPLICATE_PAIRS);
  const [employees, setEmployees] = useState<EmployeeProfile[]>(EMPLOYEE_PROFILES);
  const [merchants, setMerchants] = useState<MerchantInsight[]>(MERCHANT_INSIGHTS);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>(INITIAL_AUDIT_LOGS);

  // Selected entities for drill-down
  const [selectedClaimId, setSelectedClaimId] = useState<string>('CLM-8491');
  const [queueFilter, setQueueFilter] = useState<string>('All');

  // Notification Toast
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 3500);
  };

  // Claim Status update handler
  const handleUpdateClaimStatus = (
    claimId: string,
    newStatus: AuditStatus,
    actionName: string,
    note: string,
    policyClause?: string
  ) => {
    const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);

    let nextStage = 'Finance Audit';
    if (newStatus === 'PASS') {
      nextStage = 'Approved for Payout';
    } else if (newStatus === 'FAIL') {
      nextStage = 'Returned for Correction';
    } else if (actionName.includes('Manager')) {
      nextStage = 'Manager Approval';
    }

    setClaims((prev) =>
      prev.map((c) => {
        if (c.id === claimId) {
          return {
            ...c,
            status: newStatus,
            approvalStage: nextStage as any,
            auditTrail: [
              {
                id: `log-${Date.now()}`,
                timestamp,
                actor: `Preeti S. (${currentUserRole})`,
                action: actionName,
                prevStatus: c.status,
                newStatus,
                note,
                policyClause,
              },
              ...c.auditTrail,
            ],
          };
        }
        return c;
      })
    );

    // Also record in global immutable audit log
    const newLog: AuditLogEntry = {
      id: `AUD-${Math.floor(1000 + Math.random() * 9000)}`,
      timestamp,
      actor: `Preeti S. (${currentUserRole})`,
      action: `${actionName} on ${claimId}`,
      newStatus,
      note,
      policyClause,
    };
    setAuditLogs((prev) => [newLog, ...prev]);

    showToast(`Claim ${claimId} successfully updated: ${actionName}`);
  };

  // Batch approve PASS items
  const handleBatchApprovePass = (claimIds: string[]) => {
    const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);

    setClaims((prev) =>
      prev.map((c) => {
        if (claimIds.includes(c.id)) {
          return {
            ...c,
            approvalStage: 'Approved for Payout',
            auditTrail: [
              {
                id: `log-${Date.now()}-${c.id}`,
                timestamp,
                actor: `Preeti S. (${currentUserRole})`,
                action: 'Batch Approved Compliant Claim',
                prevStatus: c.status,
                newStatus: 'PASS',
                note: 'Clean batch verification approved for payout cycle.',
              },
              ...c.auditTrail,
            ],
          };
        }
        return c;
      })
    );

    const newLog: AuditLogEntry = {
      id: `AUD-${Math.floor(1000 + Math.random() * 9000)}`,
      timestamp,
      actor: `Preeti S. (${currentUserRole})`,
      action: `Batch approved ${claimIds.length} compliant claims`,
      newStatus: 'PASS',
      note: `Approved claims: ${claimIds.join(', ')}`,
    };
    setAuditLogs((prev) => [newLog, ...prev]);

    showToast(`Batch approved ${claimIds.length} compliant claims for payout`);
  };

  // Disburse Payout
  const handleDisbursePayout = (claimId: string) => {
    const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);

    setClaims((prev) =>
      prev.map((c) => {
        if (c.id === claimId) {
          return {
            ...c,
            approvalStage: 'Reimbursed',
            auditTrail: [
              {
                id: `log-${Date.now()}`,
                timestamp,
                actor: 'Payment Gateway (RazorpayX)',
                action: 'Direct Bank Deposit Disbursed',
                note: `UTR transaction release completed for ₹${c.claimedAmount}`,
              },
              ...c.auditTrail,
            ],
          };
        }
        return c;
      })
    );

    const newLog: AuditLogEntry = {
      id: `AUD-${Math.floor(1000 + Math.random() * 9000)}`,
      timestamp,
      actor: 'Banking Gateway (RazorpayX)',
      action: `Disbursed reimbursement for ${claimId}`,
      note: 'Funds released to employee salary account.',
    };
    setAuditLogs((prev) => [newLog, ...prev]);

    showToast(`Disbursed reimbursement for ${claimId}`);
  };

  // Update duplicate pair status
  const handleUpdatePairStatus = (
    pairId: string,
    status: DuplicatePair['status'],
    notes: string
  ) => {
    setDuplicatePairs((prev) =>
      prev.map((p) => {
        if (p.id === pairId) {
          return {
            ...p,
            status,
            resolutionNotes: notes,
          };
        }
        return p;
      })
    );

    const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);
    const newLog: AuditLogEntry = {
      id: `AUD-${Math.floor(1000 + Math.random() * 9000)}`,
      timestamp,
      actor: `Preeti S. (${currentUserRole})`,
      action: `Updated Duplicate Pair (${pairId}) Status to "${status}"`,
      note: notes || 'Reviewed duplicate evidence match.',
    };
    setAuditLogs((prev) => [newLog, ...prev]);

    showToast(`Duplicate review resolved as "${status}"`);
  };

  // Policy rule management
  const handleUpdateRule = (updatedRule: PolicyRule) => {
    setPolicyRules((prev) =>
      prev.map((r) => (r.id === updatedRule.id ? updatedRule : r))
    );
    showToast(`Policy rule ${updatedRule.code} updated.`);
  };

  const handleAddRule = (newRule: PolicyRule) => {
    setPolicyRules((prev) => [...prev, newRule]);
    showToast(`Added new rule ${newRule.code} to active policy.`);
  };

  return (
    <div className="flex h-screen w-full flex-col bg-[#F8FAFC] text-[#0F172A] overflow-hidden antialiased font-sans">
      {/* Top Header */}
      <Header
        activeTab={activeTab}
        onNavigate={setActiveTab}
        onSelectClaim={setSelectedClaimId}
        claims={claims}
        currentUserRole={currentUserRole}
        onOpenLogin={() => setIsAuthModalOpen(true)}
      />

      {/* Main Workspace: Sidebar + Viewport */}
      <div className="flex flex-1 overflow-hidden relative">
        <Sidebar
          activeTab={activeTab}
          onNavigate={setActiveTab}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          claims={claims}
        />

        {/* Dynamic View Content Area */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          <div className="max-w-[1400px] mx-auto">
            {activeTab === 'landing' && (
              <LandingPage onNavigate={setActiveTab} />
            )}

            {activeTab === 'overview' && (
              <OverviewDashboard
                claims={claims}
                onNavigate={setActiveTab}
                onFilterQueue={(filter) => {
                  setQueueFilter(filter);
                  setActiveTab('audit-queue');
                }}
                onSelectClaim={setSelectedClaimId}
              />
            )}

            {activeTab === 'audit-queue' && (
              <AuditQueue
                claims={claims}
                selectedFilter={queueFilter}
                onFilterChange={setQueueFilter}
                onSelectClaim={setSelectedClaimId}
                onNavigate={setActiveTab}
                onBatchApprovePass={handleBatchApprovePass}
              />
            )}

            {activeTab === 'workbench' && (
              <InvestigationWorkbench
                claims={claims}
                selectedClaimId={selectedClaimId}
                onSelectClaim={setSelectedClaimId}
                onUpdateClaimStatus={handleUpdateClaimStatus}
              />
            )}

            {activeTab === 'duplicates' && (
              <DuplicateReview
                duplicatePairs={duplicatePairs}
                onUpdatePairStatus={handleUpdatePairStatus}
                onSelectClaim={setSelectedClaimId}
                onNavigate={setActiveTab}
              />
            )}

            {activeTab === 'spending-analytics' && (
              <SpendingAnalytics
                claims={claims}
                employees={employees}
                onSelectClaim={setSelectedClaimId}
                onNavigate={setActiveTab}
              />
            )}

            {activeTab === 'approvals' && (
              <ApprovalsPipeline
                claims={claims}
                onSelectClaim={setSelectedClaimId}
                onNavigate={setActiveTab}
                onDisbursePayout={handleDisbursePayout}
              />
            )}

            {activeTab === 'employee-merchants' && (
              <EmployeeMerchantProfiles
                employees={employees}
                merchants={merchants}
                claims={claims}
                onSelectClaim={setSelectedClaimId}
                onNavigate={setActiveTab}
              />
            )}

            {activeTab === 'policy-studio' && (
              <PolicyStudio
                policyRules={policyRules}
                onUpdateRule={handleUpdateRule}
                onAddRule={handleAddRule}
              />
            )}

            {activeTab === 'audit-trail' && (
              <AuditTrail auditLogs={auditLogs} claims={claims} />
            )}
          </div>
        </main>
      </div>

      {/* Enterprise Auth Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        currentRole={currentUserRole}
        onRoleChange={(newRole) => {
          setCurrentUserRole(newRole);
          showToast(`Delegated role switched to ${newRole}`);
        }}
      />

      {/* Floating Action Feedback Toast */}
      {toastMessage && (
        <div className="fixed bottom-5 right-5 z-50 flex items-center gap-2 bg-slate-900 text-white text-xs px-3.5 py-2.5 rounded shadow-lg animate-in slide-in-from-bottom-2 duration-150 font-medium">
          <Check className="h-4 w-4 text-emerald-400 shrink-0" />
          <span>{toastMessage}</span>
          <button
            onClick={() => setToastMessage(null)}
            className="ml-2 text-slate-400 hover:text-white"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
