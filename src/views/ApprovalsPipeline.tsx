import React, { useState } from 'react';
import {
  GitPullRequest,
  Clock,
  AlertTriangle,
  CheckCircle2,
  Send,
  ExternalLink,
  ChevronRight,
  ArrowRight,
  User,
  Zap,
} from 'lucide-react';
import { Claim, ApprovalStage, ActiveTab } from '../types';

interface ApprovalsPipelineProps {
  claims: Claim[];
  onSelectClaim: (claimId: string) => void;
  onNavigate: (tab: ActiveTab) => void;
  onDisbursePayout: (claimId: string) => void;
}

export const ApprovalsPipeline: React.FC<ApprovalsPipelineProps> = ({
  claims,
  onSelectClaim,
  onNavigate,
  onDisbursePayout,
}) => {
  const [selectedStage, setSelectedStage] = useState<ApprovalStage | 'ALL'>('ALL');
  const [pingedApprovers, setPingedApprovers] = useState<string[]>([]);

  const stages: { stage: ApprovalStage; count: number; volume: string; desc: string }[] = [
    {
      stage: 'Manager Approval',
      count: 14,
      volume: '₹1,45,000',
      desc: 'First-line operational signoff',
    },
    {
      stage: 'Finance Audit',
      count: 38,
      volume: '₹3,80,000',
      desc: 'Active policy & OCR verification',
    },
    {
      stage: 'Returned for Correction',
      count: 9,
      volume: '₹94,000',
      desc: 'Waiting for employee receipts',
    },
    {
      stage: 'Approved for Payout',
      count: 22,
      volume: '₹2,68,000',
      desc: 'Queued for banking disbursement',
    },
    {
      stage: 'Reimbursed',
      count: 115,
      volume: '₹11,40,000',
      desc: 'Direct deposit completed',
    },
  ];

  const handlePing = (approver: string) => {
    setPingedApprovers([...pingedApprovers, approver]);
    setTimeout(() => {
      // Toast or indicator remains
    }, 2000);
  };

  const slaRows = [
    {
      claimId: 'CLM-8500',
      employee: 'Rahul Sharma (EMP-1048)',
      stage: 'Finance Audit' as ApprovalStage,
      approver: 'Preeti S. (Lead Auditor)',
      amount: 12800,
      daysWaiting: 7,
      avgTurnaround: '2.0 days',
      isBottleneck: true,
      reason: 'Missing IT pre-approval ticket for 4K display',
    },
    {
      claimId: 'CLM-8498',
      employee: 'Vikram Patel (EMP-1120)',
      stage: 'Finance Audit' as ApprovalStage,
      approver: 'Preeti S. (Lead Auditor)',
      amount: 3600,
      daysWaiting: 5,
      avgTurnaround: '2.0 days',
      isBottleneck: true,
      reason: '₹150 arithmetic line item discrepancy',
    },
    {
      claimId: 'CLM-8494',
      employee: 'Vikram Patel (EMP-1120)',
      stage: 'Finance Audit' as ApprovalStage,
      approver: 'Preeti S. (Lead Auditor)',
      amount: 380,
      daysWaiting: 4,
      avgTurnaround: '2.0 days',
      isBottleneck: false,
      reason: 'Faded thermal receipt unreadable',
    },
    {
      claimId: 'CLM-8496',
      employee: 'Priya Nair (EMP-1092)',
      stage: 'Finance Audit' as ApprovalStage,
      approver: 'Preeti S. (Lead Auditor)',
      amount: 14200,
      daysWaiting: 3,
      avgTurnaround: '2.0 days',
      isBottleneck: false,
      reason: 'Pending client attendee names',
    },
    {
      claimId: 'CLM-8492',
      employee: 'Rahul Sharma (EMP-1048)',
      stage: 'Approved for Payout' as ApprovalStage,
      approver: 'Disbursement Desk (RazorpayX)',
      amount: 8450,
      daysWaiting: 1,
      avgTurnaround: '1.2 days',
      isBottleneck: false,
      reason: 'Ready for batch payout release',
    },
  ];

  const filteredSlaRows = selectedStage === 'ALL'
    ? slaRows
    : slaRows.filter((r) => r.stage === selectedStage);

  return (
    <div className="space-y-6 pb-12">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-lg border border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <GitPullRequest className="h-4 w-4 text-slate-700" />
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Approvals & Reimbursement Pipeline
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            End-to-end lifecycle monitoring from department signoff to automated banking disbursement.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-500 font-mono">Overall SLA Health:</span>
          <span className="font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200">
            94.2% On-Time
          </span>
        </div>
      </div>

      {/* Stage Pipeline Interactive Diagram */}
      <div className="bg-white p-5 rounded-lg border border-slate-200 space-y-3 shadow-2xs">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Reimbursement Lifecycle Stages
          </h2>
          <span className="text-[11px] text-slate-400">
            Click any stage to filter the SLA queue below
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5 pt-2">
          {stages.map((st, idx) => {
            const isSelected = selectedStage === st.stage;
            return (
              <div
                key={st.stage}
                onClick={() => setSelectedStage(isSelected ? 'ALL' : st.stage)}
                className={`cursor-pointer p-3.5 rounded border transition-all relative ${
                  isSelected
                    ? 'border-slate-900 bg-slate-50 shadow-xs ring-1 ring-slate-900'
                    : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50'
                }`}
              >
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span className="font-mono">0{idx + 1}.</span>
                  <span className="font-mono font-bold text-slate-900 text-xs">
                    {st.volume}
                  </span>
                </div>
                <div className="mt-2 text-xs font-bold text-slate-900">
                  {st.stage}
                </div>
                <div className="mt-0.5 text-[11px] text-slate-500 truncate">
                  {st.desc}
                </div>
                <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
                  <span className="font-mono font-semibold text-slate-700">
                    {st.count} claims
                  </span>
                  <ChevronRight className="h-3 w-3 text-slate-300" />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* SLA Table & Bottleneck Alert Queue */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow-2xs">
        <div className="p-4 border-b border-slate-200 bg-slate-50/70 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-slate-700" />
            <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Approver SLA Tracking & Bottleneck Registry
            </h2>
          </div>
          {selectedStage !== 'ALL' && (
            <button
              onClick={() => setSelectedStage('ALL')}
              className="text-xs text-slate-500 hover:text-slate-800 underline"
            >
              Reset filter (Showing {selectedStage})
            </button>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 text-slate-400 uppercase text-[10px] font-semibold bg-slate-50/30">
                <th className="py-2.5 px-4">Claim ID</th>
                <th className="py-2.5 px-4">Employee</th>
                <th className="py-2.5 px-4">Current Approver</th>
                <th className="py-2.5 px-4">Stage</th>
                <th className="py-2.5 px-4 text-right">Outstanding (INR)</th>
                <th className="py-2.5 px-4 text-center">Days Waiting</th>
                <th className="py-2.5 px-4">SLA Benchmark</th>
                <th className="py-2.5 px-4">Audit Bottleneck Note</th>
                <th className="py-2.5 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredSlaRows.map((row) => (
                <tr
                  key={row.claimId}
                  className={`hover:bg-slate-50/70 transition-colors ${
                    row.isBottleneck ? 'bg-rose-50/20' : ''
                  }`}
                >
                  <td className="py-3 px-4 font-mono font-semibold text-slate-900">
                    {row.claimId}
                  </td>
                  <td className="py-3 px-4 text-slate-800 font-medium">
                    {row.employee}
                  </td>
                  <td className="py-3 px-4 text-slate-700">
                    {row.approver}
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-[11px] font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                      {row.stage}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right font-mono font-bold text-slate-900">
                    ₹{row.amount.toLocaleString('en-IN')}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span
                      className={`inline-block font-mono font-semibold text-xs px-2 py-0.5 rounded ${
                        row.daysWaiting >= 5
                          ? 'bg-rose-100 text-rose-800 border border-rose-300'
                          : row.daysWaiting >= 3
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-slate-100 text-slate-700'
                      }`}
                    >
                      {row.daysWaiting} days
                    </span>
                  </td>
                  <td className="py-3 px-4 font-mono text-[11px] text-slate-500">
                    Target: {row.avgTurnaround}
                  </td>
                  <td className="py-3 px-4 text-slate-600 max-w-xs text-[11px]">
                    {row.isBottleneck ? (
                      <span className="text-rose-700 font-semibold flex items-center gap-1">
                        <AlertTriangle className="h-3 w-3 shrink-0" />
                        {row.reason}
                      </span>
                    ) : (
                      <span>{row.reason}</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-right space-x-1.5 whitespace-nowrap">
                    {row.stage === 'Approved for Payout' ? (
                      <button
                        onClick={() => onDisbursePayout(row.claimId)}
                        className="px-2.5 py-1 text-[11px] font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded transition-colors"
                      >
                        Release Payout
                      </button>
                    ) : (
                      <button
                        onClick={() => handlePing(row.approver)}
                        className="px-2 py-1 text-[11px] font-medium text-slate-700 bg-white border border-slate-200 rounded hover:bg-slate-50 transition-colors"
                      >
                        {pingedApprovers.includes(row.approver) ? 'Pinged' : 'Nudge SLA'}
                      </button>
                    )}
                    <button
                      onClick={() => {
                        onSelectClaim(row.claimId);
                        onNavigate('workbench');
                      }}
                      className="px-2 py-1 text-[11px] font-medium text-slate-600 hover:text-slate-900 transition-colors"
                    >
                      Inspect
                    </button>
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
