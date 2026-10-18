import React, { useState } from 'react';
import {
  Search,
  Filter,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ExternalLink,
  ShieldCheck,
  ShieldAlert,
  ArrowUpDown,
  Check,
  Info,
} from 'lucide-react';
import { Claim, AuditStatus, Priority, ActiveTab } from '../types';

interface AuditQueueProps {
  claims: Claim[];
  selectedFilter: string;
  onFilterChange: (filter: string) => void;
  onSelectClaim: (claimId: string) => void;
  onNavigate: (tab: ActiveTab) => void;
  onBatchApprovePass: (claimIds: string[]) => void;
}

export const AuditQueue: React.FC<AuditQueueProps> = ({
  claims,
  selectedFilter,
  onFilterChange,
  onSelectClaim,
  onNavigate,
  onBatchApprovePass,
}) => {
  const [tableSearch, setTableSearch] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState<'ALL' | AuditStatus>('ALL');
  const [sortField, setSortField] = useState<'date' | 'amount' | 'priority'>('date');
  const [sortAsc, setSortAsc] = useState(false);

  const filterTabs = [
    { id: 'All', label: 'All Claims', count: claims.length },
    {
      id: 'High Risk',
      label: 'High Risk',
      count: claims.filter((c) => c.priority === 'HIGH').length,
    },
    {
      id: 'Duplicate Candidate',
      label: 'Duplicates',
      count: claims.filter((c) => c.issueType === 'DUPLICATE_CANDIDATE').length,
    },
    {
      id: 'Missing Info',
      label: 'Missing Info',
      count: claims.filter((c) => c.issueType === 'MISSING_INFO').length,
    },
    {
      id: 'Policy Violation',
      label: 'Violations',
      count: claims.filter((c) => c.status === 'FAIL').length,
    },
    {
      id: 'Unreadable Receipt',
      label: 'Unreadable',
      count: claims.filter((c) => c.issueType === 'UNREADABLE_RECEIPT').length,
    },
    {
      id: 'Pending Approval',
      label: 'Pending Payout',
      count: claims.filter((c) => c.approvalStage === 'Approved for Payout').length,
    },
  ];

  // Filtering Logic
  const filteredClaims = claims.filter((claim) => {
    // Top tab filter
    if (selectedFilter === 'High Risk' && claim.priority !== 'HIGH') return false;
    if (selectedFilter === 'Duplicate Candidate' && claim.issueType !== 'DUPLICATE_CANDIDATE') return false;
    if (selectedFilter === 'Missing Info' && claim.issueType !== 'MISSING_INFO') return false;
    if (selectedFilter === 'Policy Violation' && claim.status !== 'FAIL') return false;
    if (selectedFilter === 'Unreadable Receipt' && claim.issueType !== 'UNREADABLE_RECEIPT') return false;
    if (selectedFilter === 'Pending Approval' && claim.approvalStage !== 'Approved for Payout') return false;

    // Status filter
    if (statusFilter !== 'ALL' && claim.status !== statusFilter) return false;

    // Search query
    if (tableSearch.trim()) {
      const q = tableSearch.toLowerCase();
      const match =
        claim.id.toLowerCase().includes(q) ||
        claim.employeeName.toLowerCase().includes(q) ||
        claim.employeeId.toLowerCase().includes(q) ||
        claim.merchantName.toLowerCase().includes(q) ||
        claim.issueDescription.toLowerCase().includes(q);
      if (!match) return false;
    }

    return true;
  });

  // Sorting
  const sortedClaims = [...filteredClaims].sort((a, b) => {
    if (sortField === 'amount') {
      return sortAsc ? a.claimedAmount - b.claimedAmount : b.claimedAmount - a.claimedAmount;
    }
    if (sortField === 'priority') {
      const pMap = { HIGH: 3, MEDIUM: 2, LOW: 1 };
      return sortAsc ? pMap[a.priority] - pMap[b.priority] : pMap[b.priority] - pMap[a.priority];
    }
    // Default date
    return sortAsc
      ? new Date(a.submissionDate).getTime() - new Date(b.submissionDate).getTime()
      : new Date(b.submissionDate).getTime() - new Date(a.submissionDate).getTime();
  });

  // Guardrail analysis for selection
  const selectedClaimsObjects = claims.filter((c) => selectedIds.includes(c.id));
  const hasSuspiciousInSelection = selectedClaimsObjects.some((c) => c.status !== 'PASS');
  const allSelectedArePass = selectedClaimsObjects.length > 0 && selectedClaimsObjects.every((c) => c.status === 'PASS');

  const toggleSelectAllPass = () => {
    const passIds = sortedClaims.filter((c) => c.status === 'PASS').map((c) => c.id);
    if (selectedIds.length === passIds.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(passIds);
    }
  };

  const toggleSelectOne = (id: string) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter((item) => item !== id));
    } else {
      setSelectedIds([...selectedIds, id]);
    }
  };

  const handleRowClick = (claimId: string) => {
    onSelectClaim(claimId);
    onNavigate('workbench');
  };

  const handleBatchApprove = () => {
    if (allSelectedArePass) {
      onBatchApprovePass(selectedIds);
      setSelectedIds([]);
    }
  };

  return (
    <div className="space-y-4 pb-12">
      {/* Title & Stats Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            AI Audit Queue
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time compliance triage with 3-valued verification (PASS / FAIL / UNKNOWN).
          </p>
        </div>

        {/* Action Controls & Guardrail Notice */}
        <div className="flex items-center gap-2">
          {selectedIds.length > 0 && (
            <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded border border-slate-200 text-xs">
              <span className="font-mono font-semibold text-slate-900">
                {selectedIds.length} selected
              </span>

              {allSelectedArePass ? (
                <button
                  onClick={handleBatchApprove}
                  className="px-2.5 py-1 text-xs font-semibold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded transition-colors"
                >
                  Batch Approve ({selectedIds.length} PASS Items)
                </button>
              ) : (
                <div
                  className="flex items-center gap-1.5 px-2 py-0.5 text-[11px] font-medium text-rose-800 bg-rose-50 border border-rose-200 rounded cursor-not-allowed"
                  title="Guardrail rule: Claims with UNKNOWN or FAIL status cannot be batch rejected or approved. They must be inspected in the Workbench."
                >
                  <ShieldAlert className="h-3 w-3 text-rose-600" />
                  <span>Bulk Action Blocked on Flags</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Quick Filter Segmented Buttons */}
      <div className="flex items-center gap-1 overflow-x-auto pb-1 p-1 bg-slate-100 rounded-lg">
        {filterTabs.map((tab) => {
          const isActive = selectedFilter === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => {
                onFilterChange(tab.id);
                setSelectedIds([]);
              }}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors whitespace-nowrap ${
                isActive
                  ? 'bg-white text-slate-900 shadow-xs font-semibold'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`text-[10px] font-mono px-1.5 py-0.2 rounded ${
                  isActive ? 'bg-slate-100 text-slate-900' : 'text-slate-400'
                }`}
              >
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Search & Secondary Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-3 rounded-lg border border-slate-200">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            value={tableSearch}
            onChange={(e) => setTableSearch(e.target.value)}
            placeholder="Filter table by employee, ID, merchant..."
            className="w-full h-8 pl-8.5 pr-3 text-xs bg-slate-50 border border-slate-200 rounded text-slate-800 focus:outline-none focus:border-slate-400 focus:bg-white transition-colors"
          />
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
          {/* Status Dropdown */}
          <div className="flex items-center gap-1.5 text-xs text-slate-600">
            <span className="text-[11px] font-medium text-slate-400">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
              className="h-8 px-2 text-xs bg-slate-50 border border-slate-200 rounded text-slate-800 focus:outline-none"
            >
              <option value="ALL">All Statuses</option>
              <option value="PASS">PASS Only</option>
              <option value="UNKNOWN">UNKNOWN (Needs Review)</option>
              <option value="FAIL">FAIL (Violations)</option>
            </select>
          </div>

          {/* Sort Control */}
          <div className="flex items-center gap-1 text-xs text-slate-600">
            <button
              onClick={() => {
                if (sortField === 'date') setSortAsc(!sortAsc);
                else {
                  setSortField('date');
                  setSortAsc(false);
                }
              }}
              className={`flex items-center gap-1 h-8 px-2.5 rounded border ${
                sortField === 'date'
                  ? 'border-slate-300 bg-slate-50 text-slate-900 font-medium'
                  : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
              }`}
            >
              <span>Date</span>
              <ArrowUpDown className="h-3 w-3 text-slate-400" />
            </button>

            <button
              onClick={() => {
                if (sortField === 'amount') setSortAsc(!sortAsc);
                else {
                  setSortField('amount');
                  setSortAsc(false);
                }
              }}
              className={`flex items-center gap-1 h-8 px-2.5 rounded border ${
                sortField === 'amount'
                  ? 'border-slate-300 bg-slate-50 text-slate-900 font-medium'
                  : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
              }`}
            >
              <span>Amount</span>
              <ArrowUpDown className="h-3 w-3 text-slate-400" />
            </button>
          </div>
        </div>
      </div>

      {/* Guardrail Policy Banner */}
      <div className="flex items-center justify-between px-3.5 py-2 bg-slate-50 border border-slate-200 rounded text-xs text-slate-600">
        <div className="flex items-center gap-2">
          <Info className="h-4 w-4 text-slate-400 shrink-0" />
          <span>
            <strong className="font-semibold text-slate-800">Compliance Guardrail Active:</strong>{' '}
            Bulk operations are strictly limited to clean PASS claims. Flagged items require individual reviewer inspection with cited clauses.
          </span>
        </div>
        <button
          onClick={toggleSelectAllPass}
          className="text-[11px] font-medium text-slate-700 hover:text-slate-900 underline whitespace-nowrap ml-3"
        >
          Select All Clean PASS ({sortedClaims.filter((c) => c.status === 'PASS').length})
        </button>
      </div>

      {/* Master Data Table */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-2xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-500 font-semibold uppercase tracking-wider text-[10px]">
                <th className="py-2.5 px-3 w-8 text-center">
                  <input
                    type="checkbox"
                    checked={
                      selectedIds.length > 0 &&
                      selectedIds.length === sortedClaims.filter((c) => c.status === 'PASS').length
                    }
                    onChange={toggleSelectAllPass}
                    className="rounded border-slate-300 text-slate-900 focus:ring-0"
                    title="Select all compliant PASS items"
                  />
                </th>
                <th className="py-2.5 px-3">Claim ID</th>
                <th className="py-2.5 px-3">Employee</th>
                <th className="py-2.5 px-3">Merchant & City</th>
                <th className="py-2.5 px-3">Category</th>
                <th className="py-2.5 px-3 text-right">Claimed (INR)</th>
                <th className="py-2.5 px-3">Date</th>
                <th className="py-2.5 px-3">Detected Issue / Reason</th>
                <th className="py-2.5 px-3">Priority</th>
                <th className="py-2.5 px-3 text-center">Status</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-normal">
              {sortedClaims.length > 0 ? (
                sortedClaims.map((claim) => {
                  const isSelected = selectedIds.includes(claim.id);
                  const isPass = claim.status === 'PASS';
                  return (
                    <tr
                      key={claim.id}
                      className={`hover:bg-slate-50/80 transition-colors group ${
                        isSelected ? 'bg-slate-50' : ''
                      }`}
                    >
                      <td className="py-2.5 px-3 text-center" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          disabled={!isPass}
                          onChange={() => toggleSelectOne(claim.id)}
                          className="rounded border-slate-300 text-slate-900 focus:ring-0 disabled:opacity-30 disabled:cursor-not-allowed"
                          title={!isPass ? 'Suspicious flags require individual workbench review.' : 'Select for batch approval'}
                        />
                      </td>

                      <td
                        className="py-2.5 px-3 font-mono font-semibold text-slate-900 cursor-pointer"
                        onClick={() => handleRowClick(claim.id)}
                      >
                        {claim.id}
                      </td>

                      <td
                        className="py-2.5 px-3 cursor-pointer"
                        onClick={() => handleRowClick(claim.id)}
                      >
                        <div className="font-semibold text-slate-800">
                          {claim.employeeName}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono">
                          {claim.employeeId} · {claim.employeeDept}
                        </div>
                      </td>

                      <td
                        className="py-2.5 px-3 cursor-pointer"
                        onClick={() => handleRowClick(claim.id)}
                      >
                        <div className="font-medium text-slate-800 truncate max-w-[160px]">
                          {claim.merchantName}
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {claim.merchantCity} ({claim.cityTier})
                        </div>
                      </td>

                      <td className="py-2.5 px-3 text-slate-600">
                        {claim.category}
                      </td>

                      <td className="py-2.5 px-3 text-right font-mono font-semibold text-slate-900">
                        ₹{claim.claimedAmount.toLocaleString('en-IN')}
                      </td>

                      <td className="py-2.5 px-3 font-mono text-[11px] text-slate-500 whitespace-nowrap">
                        {claim.submissionDate}
                      </td>

                      <td
                        className="py-2.5 px-3 max-w-xs cursor-pointer"
                        onClick={() => handleRowClick(claim.id)}
                      >
                        <p className="text-[11px] text-slate-600 line-clamp-2 leading-relaxed">
                          {claim.issueDescription}
                        </p>
                      </td>

                      <td className="py-2.5 px-3">
                        <span
                          className={`text-[10px] font-semibold uppercase tracking-wider ${
                            claim.priority === 'HIGH'
                              ? 'text-rose-700'
                              : claim.priority === 'MEDIUM'
                              ? 'text-amber-700'
                              : 'text-slate-500'
                          }`}
                        >
                          {claim.priority}
                        </span>
                      </td>

                      <td className="py-2.5 px-3 text-center">
                        <span
                          className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded ${
                            claim.status === 'PASS'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : claim.status === 'FAIL'
                              ? 'bg-rose-50 text-rose-700 border border-rose-200'
                              : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}
                        >
                          {claim.status}
                        </span>
                      </td>

                      <td className="py-2.5 px-3 text-right">
                        <button
                          onClick={() => handleRowClick(claim.id)}
                          className="px-2.5 py-1 text-[11px] font-medium text-slate-700 bg-white border border-slate-200 rounded hover:bg-slate-100 hover:text-slate-900 transition-colors shadow-2xs whitespace-nowrap"
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={11} className="py-10 text-center text-slate-500 text-xs">
                    No claims match your search filters. Try selecting "All Claims" or resetting search.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
