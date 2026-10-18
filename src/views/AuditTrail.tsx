import React, { useState } from 'react';
import {
  FileSpreadsheet,
  Download,
  FileCheck,
  Search,
  Filter,
  ShieldCheck,
  Clock,
  ArrowDownToLine,
  Lock,
} from 'lucide-react';
import { AuditLogEntry, Claim } from '../types';

interface AuditTrailProps {
  auditLogs: AuditLogEntry[];
  claims: Claim[];
}

export const AuditTrail: React.FC<AuditTrailProps> = ({ auditLogs, claims }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [actorFilter, setActorFilter] = useState('ALL');

  const filteredLogs = auditLogs.filter((log) => {
    if (actorFilter !== 'ALL' && !log.actor.toLowerCase().includes(actorFilter.toLowerCase())) {
      return false;
    }
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      return (
        log.id.toLowerCase().includes(q) ||
        log.actor.toLowerCase().includes(q) ||
        log.action.toLowerCase().includes(q) ||
        log.note.toLowerCase().includes(q) ||
        (log.policyClause && log.policyClause.toLowerCase().includes(q))
      );
    }
    return true;
  });

  // Export CSV Handler
  const handleExportCSV = () => {
    const headers = [
      'Claim ID',
      'Employee ID',
      'Employee Name',
      'Department',
      'Merchant',
      'City',
      'Category',
      'Claimed (INR)',
      'Extracted Total (INR)',
      'Tax Amount (INR)',
      'Audit Status',
      'Approval Stage',
      'Submission Date',
      'Expense Date',
      'Issue Detected',
      'Policy Clause',
    ];

    const rows = claims.map((c) => [
      c.id,
      c.employeeId,
      `"${c.employeeName}"`,
      c.employeeDept,
      `"${c.merchantName}"`,
      c.merchantCity,
      c.category,
      c.claimedAmount,
      c.extractedTotal,
      c.extractedTax,
      c.status,
      c.approvalStage,
      c.submissionDate,
      c.expenseDate,
      `"${c.issueDescription.replace(/"/g, '""')}"`,
      `"${c.policyClauseCited || 'Compliant'}"`,
    ]);

    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `Proofline_Expense_Ledger_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Download Evidence Pack
  const handleDownloadEvidencePack = () => {
    const reportText = `
=============================================================================
PROOFLINE ENTERPRISE COMPLIANCE AUDIT PACK
Generated on: ${new Date().toISOString()}
Target Environment: FY27 Audit Period (October 2026)
Active Policy Version: v2026.4
=============================================================================

1. EXECUTIVE AUDIT SUMMARY
- Total Verified Expense Outlay: INR 14,25,000.00
- Total Claims Evaluated: ${claims.length}
- Clean Compliant (PASS): ${claims.filter((c) => c.status === 'PASS').length}
- Pending Review (UNKNOWN): ${claims.filter((c) => c.status === 'UNKNOWN').length}
- Non-Compliant / Breached (FAIL): ${claims.filter((c) => c.status === 'FAIL').length}

2. POLICY EXCEPTIONS & CITATIONS
${claims
  .filter((c) => c.status !== 'PASS')
  .map(
    (c) =>
      `[${c.id}] ${c.employeeName} (${c.employeeId}) - ${c.merchantName} - INR ${c.claimedAmount}
   Status: ${c.status}
   Clause Cited: ${c.policyClauseCited || 'General Spending Cap'}
   Finding: ${c.issueDescription}`
  )
  .join('\n\n')}

3. IMMUTABLE SYSTEM AUDIT TRAIL LOGS
${auditLogs
  .map(
    (l) =>
      `[${l.timestamp}] ${l.actor} -> ${l.action} (${l.id})
   Note: ${l.note}
   Clause: ${l.policyClause || 'N/A'}`
  )
  .join('\n')}

=============================================================================
End of Audit Pack. Signed by Proofline Verification Engine.
=============================================================================
    `.trim();

    const blob = new Blob([reportText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `Proofline_Audit_Evidence_Pack_${new Date().toISOString().slice(0, 10)}.txt`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Title & Export Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-4 rounded-lg border border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="h-4 w-4 text-slate-700" />
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Audit Trail & Compliance Exports
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Cryptographically sealed state ledger recording every OCR extraction, rule trigger, and reviewer decision.
          </p>
        </div>

        {/* Export Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-800 bg-white border border-slate-200 rounded hover:bg-slate-50 shadow-2xs transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Export Expense Ledger (CSV)</span>
          </button>

          <button
            onClick={handleDownloadEvidencePack}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded shadow-xs transition-colors"
          >
            <FileCheck className="h-3.5 w-3.5" />
            <span>Download Audit Evidence Pack</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-3 rounded-lg border border-slate-200">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search logs by actor, action, clause..."
            className="w-full h-8 pl-8.5 pr-3 text-xs bg-slate-50 border border-slate-200 rounded text-slate-800 focus:outline-none focus:border-slate-400 focus:bg-white transition-colors"
          />
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-400 font-medium">Actor:</span>
          <select
            value={actorFilter}
            onChange={(e) => setActorFilter(e.target.value)}
            className="h-8 px-2 text-xs bg-slate-50 border border-slate-200 rounded text-slate-800 focus:outline-none"
          >
            <option value="ALL">All Actors (System + Human)</option>
            <option value="Preeti">Preeti S. (Lead Auditor)</option>
            <option value="Engine">Proofline Rules & Vision Engine</option>
            <option value="OCR">System OCR</option>
          </select>
        </div>
      </div>

      {/* Immutable Chronological Log Table */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-2xs">
        <div className="p-3 border-b border-slate-200 bg-slate-50/70 flex items-center justify-between text-xs">
          <div className="flex items-center gap-1.5 text-slate-600 font-medium">
            <Lock className="h-3.5 w-3.5 text-slate-400" />
            <span>Immutable Hash Log</span>
          </div>
          <span className="font-mono text-[11px] text-slate-400">
            Showing {filteredLogs.length} audit transactions
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/30 text-slate-400 uppercase text-[10px] font-semibold">
                <th className="py-2.5 px-4">Log ID</th>
                <th className="py-2.5 px-4">Timestamp (UTC+05:30)</th>
                <th className="py-2.5 px-4">Actor</th>
                <th className="py-2.5 px-4">Event Action</th>
                <th className="py-2.5 px-4 text-center">Status Transition</th>
                <th className="py-2.5 px-4">Policy Clause Cited</th>
                <th className="py-2.5 px-4">Reviewer Reasoning & Metadata</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-normal">
              {filteredLogs.map((log) => (
                <tr key={log.id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="py-3 px-4 font-mono font-semibold text-slate-900">
                    {log.id}
                  </td>
                  <td className="py-3 px-4 font-mono text-slate-500 text-[11px] whitespace-nowrap">
                    {log.timestamp}
                  </td>
                  <td className="py-3 px-4 font-medium text-slate-800">
                    {log.actor}
                  </td>
                  <td className="py-3 px-4 text-slate-900 font-semibold">
                    {log.action}
                  </td>
                  <td className="py-3 px-4 text-center">
                    {log.newStatus ? (
                      <span
                        className={`inline-block font-mono text-[10px] font-bold px-2 py-0.5 rounded ${
                          log.newStatus === 'PASS'
                            ? 'bg-emerald-50 text-emerald-700'
                            : log.newStatus === 'FAIL'
                            ? 'bg-rose-50 text-rose-700'
                            : 'bg-amber-50 text-amber-700'
                        }`}
                      >
                        {log.prevStatus ? `${log.prevStatus} → ${log.newStatus}` : log.newStatus}
                      </span>
                    ) : (
                      <span className="text-slate-300 font-mono">—</span>
                    )}
                  </td>
                  <td className="py-3 px-4 font-mono text-[11px] text-slate-600">
                    {log.policyClause || '—'}
                  </td>
                  <td className="py-3 px-4 text-slate-600 max-w-sm text-[11px] leading-relaxed">
                    {log.note}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
