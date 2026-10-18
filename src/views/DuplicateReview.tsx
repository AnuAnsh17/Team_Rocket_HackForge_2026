import React, { useState } from 'react';
import {
  Copy,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  ArrowRight,
  ShieldCheck,
  Search,
  ExternalLink,
} from 'lucide-react';
import { DuplicatePair, ActiveTab } from '../types';

interface DuplicateReviewProps {
  duplicatePairs: DuplicatePair[];
  onUpdatePairStatus: (
    pairId: string,
    status: DuplicatePair['status'],
    notes: string
  ) => void;
  onSelectClaim: (claimId: string) => void;
  onNavigate: (tab: ActiveTab) => void;
}

export const DuplicateReview: React.FC<DuplicateReviewProps> = ({
  duplicatePairs,
  onUpdatePairStatus,
  onSelectClaim,
  onNavigate,
}) => {
  const [selectedPairId, setSelectedPairId] = useState<string>(duplicatePairs[0]?.id || '');
  const [resolutionNote, setResolutionNote] = useState('');

  const currentPair = duplicatePairs.find((p) => p.id === selectedPairId) || duplicatePairs[0];

  const handleStatusChange = (status: DuplicatePair['status']) => {
    onUpdatePairStatus(currentPair.id, status, resolutionNote || currentPair.resolutionNotes || '');
  };

  const handleInspectClaim = (claimId: string) => {
    onSelectClaim(claimId);
    onNavigate('workbench');
  };

  if (!currentPair) {
    return (
      <div className="p-8 text-center text-slate-500 bg-white rounded-lg border border-slate-200">
        No duplicate candidates currently pending investigation.
      </div>
    );
  }

  return (
    <div className="space-y-5 pb-12">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-lg border border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <Copy className="h-4 w-4 text-slate-700" />
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Duplicate & Anomaly Investigation
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Side-by-side evidence comparison protecting corporate spend without premature fraud accusations.
          </p>
        </div>

        {/* Pair Switcher */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-500">Pair:</span>
          <div className="flex items-center gap-1.5">
            {duplicatePairs.map((pair, idx) => (
              <button
                key={pair.id}
                onClick={() => {
                  setSelectedPairId(pair.id);
                  setResolutionNote('');
                }}
                className={`px-3 py-1.5 text-xs font-mono rounded border transition-colors ${
                  selectedPairId === pair.id
                    ? 'bg-slate-900 text-white border-slate-900 font-semibold'
                    : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                }`}
              >
                Case #{idx + 1} ({pair.perceptualHashMatch}% Match)
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Evidence Match Breakdown Scoreboard */}
      <div className="bg-white p-4 rounded-lg border border-slate-200">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Evidence Match Breakdown
          </h3>
          <span className="text-xs font-mono text-slate-500">
            Perceptual Hash & Heuristic Match
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-3">
          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-[10px] text-slate-400 uppercase font-semibold">
              Perceptual Image Hash
            </span>
            <div className="text-lg font-bold font-mono text-rose-700 mt-0.5">
              {currentPair.perceptualHashMatch}%
            </div>
            <div className="text-[11px] text-slate-500">
              Visual layout similarity
            </div>
          </div>

          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-[10px] text-slate-400 uppercase font-semibold">
              Merchant Fuzzy Match
            </span>
            <div className="text-lg font-bold font-mono text-slate-900 mt-0.5">
              {currentPair.fuzzyMerchantMatch}%
            </div>
            <div className="text-[11px] text-slate-500">
              Exact string & GSTIN match
            </div>
          </div>

          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-[10px] text-slate-400 uppercase font-semibold">
              Amount & Date Delta
            </span>
            <div className="text-sm font-bold font-mono text-slate-900 mt-1">
              ₹0.00 / Same Day
            </div>
            <div className="text-[11px] text-slate-500">
              Identical billing amount
            </div>
          </div>

          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-[10px] text-slate-400 uppercase font-semibold">
              Channel Comparison
            </span>
            <div className="text-xs font-medium text-slate-800 mt-1 truncate" title={currentPair.channelComparison}>
              {currentPair.channelComparison}
            </div>
            <div className="text-[11px] text-slate-500">
              Dual submission pathway
            </div>
          </div>
        </div>
      </div>

      {/* Side-by-Side Comparison Columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* SUBMISSION A */}
        <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-4 shadow-2xs">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-400">
                Candidate A
              </span>
              <h3 className="text-sm font-bold font-mono text-slate-900">
                {currentPair.claimA.id}
              </h3>
            </div>
            <button
              onClick={() => handleInspectClaim(currentPair.claimA.id)}
              className="flex items-center gap-1 px-2.5 py-1 text-xs text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded transition-colors"
            >
              <span>Inspect Workbench</span>
              <ExternalLink className="h-3 w-3" />
            </button>
          </div>

          {/* Simulated Receipt Preview Box */}
          <div className="bg-slate-100 border border-slate-300 rounded p-4 font-mono text-[11px] space-y-2 min-h-[220px]">
            <div className="text-center font-bold border-b border-dashed border-slate-300 pb-2">
              {currentPair.claimA.merchantName}
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Employee:</span>
              <span className="font-semibold text-slate-900">{currentPair.claimA.employeeName} ({currentPair.claimA.employeeId})</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Expense Date:</span>
              <span>{currentPair.claimA.expenseDate}</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Submission Date:</span>
              <span>{currentPair.claimA.submissionDate}</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Cost Center:</span>
              <span>{currentPair.claimA.costCenter}</span>
            </div>
            <div className="flex justify-between border-t border-dashed border-slate-300 pt-2 text-xs font-bold text-slate-900">
              <span>Amount Billed:</span>
              <span>₹{currentPair.claimA.claimedAmount.toLocaleString('en-IN')}</span>
            </div>
          </div>

          {/* Details */}
          <div className="space-y-1.5 text-xs text-slate-600">
            <div>
              <span className="text-[10px] text-slate-400 uppercase font-semibold">Line Items:</span>
              <ul className="list-disc list-inside mt-0.5 space-y-0.5 text-slate-700 font-mono text-[11px]">
                {currentPair.claimA.lineItems.map((li) => (
                  <li key={li.id}>
                    {li.description} - ₹{li.total.toFixed(2)}
                  </li>
                ))}
              </ul>
            </div>
            <div className="pt-2">
              <span className="text-[10px] text-slate-400 uppercase font-semibold">Status:</span>
              <span className="ml-2 font-semibold text-slate-900">{currentPair.claimA.approvalStage}</span>
            </div>
          </div>
        </div>

        {/* SUBMISSION B */}
        <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-4 shadow-2xs">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-400">
                Candidate B (Suspected Duplicate)
              </span>
              <h3 className="text-sm font-bold font-mono text-slate-900">
                {currentPair.claimB.id}
              </h3>
            </div>
            <button
              onClick={() => handleInspectClaim(currentPair.claimB.id)}
              className="flex items-center gap-1 px-2.5 py-1 text-xs text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded transition-colors"
            >
              <span>Inspect Workbench</span>
              <ExternalLink className="h-3 w-3" />
            </button>
          </div>

          {/* Simulated Receipt Preview Box */}
          <div className="bg-slate-100 border border-slate-300 rounded p-4 font-mono text-[11px] space-y-2 min-h-[220px]">
            <div className="text-center font-bold border-b border-dashed border-slate-300 pb-2">
              {currentPair.claimB.merchantName}
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Employee:</span>
              <span className="font-semibold text-slate-900">{currentPair.claimB.employeeName} ({currentPair.claimB.employeeId})</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Expense Date:</span>
              <span>{currentPair.claimB.expenseDate}</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Submission Date:</span>
              <span>{currentPair.claimB.submissionDate}</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Cost Center:</span>
              <span>{currentPair.claimB.costCenter}</span>
            </div>
            <div className="flex justify-between border-t border-dashed border-slate-300 pt-2 text-xs font-bold text-slate-900">
              <span>Amount Billed:</span>
              <span>₹{currentPair.claimB.claimedAmount.toLocaleString('en-IN')}</span>
            </div>
          </div>

          {/* Details */}
          <div className="space-y-1.5 text-xs text-slate-600">
            <div>
              <span className="text-[10px] text-slate-400 uppercase font-semibold">Line Items:</span>
              <ul className="list-disc list-inside mt-0.5 space-y-0.5 text-slate-700 font-mono text-[11px]">
                {currentPair.claimB.lineItems.map((li) => (
                  <li key={li.id}>
                    {li.description} - ₹{li.total.toFixed(2)}
                  </li>
                ))}
              </ul>
            </div>
            <div className="pt-2">
              <span className="text-[10px] text-slate-400 uppercase font-semibold">Status:</span>
              <span className="ml-2 font-semibold text-slate-900">{currentPair.claimB.approvalStage}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Resolution & Status Determination */}
      <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-4 shadow-2xs">
        <div>
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Reviewer Resolution & Determination
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Categorize this candidate without penalizing honest administrative double-uploads.
          </p>
        </div>

        {/* 3 Status Choices */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            {
              id: 'Possible Match (Under Review)' as const,
              title: 'Under Review',
              desc: 'Investigating whether co-attendees split receipt or accidentally uploaded dual slips.',
              color: 'border-amber-300 bg-amber-50/40 text-amber-900',
            },
            {
              id: 'Confirmed Duplicate' as const,
              title: 'Confirmed Duplicate',
              desc: 'Verified dual claim for single transaction. One claim will be voided.',
              color: 'border-rose-300 bg-rose-50/40 text-rose-900',
            },
            {
              id: 'Dismissed (Legitimate)' as const,
              title: 'Dismiss (Legitimate)',
              desc: 'Distinct back-to-back expenses (e.g. 2 taxi trips on same day). Verified safe.',
              color: 'border-emerald-300 bg-emerald-50/40 text-emerald-900',
            },
          ].map((opt) => {
            const isSelected = currentPair.status === opt.id;
            return (
              <div
                key={opt.id}
                onClick={() => handleStatusChange(opt.id)}
                className={`cursor-pointer p-3.5 rounded border transition-all ${
                  isSelected ? `${opt.color} ring-1 ring-slate-900` : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold">{opt.title}</span>
                  {isSelected && <CheckCircle2 className="h-4 w-4" />}
                </div>
                <p className="text-[11px] text-slate-600 mt-1">
                  {opt.desc}
                </p>
              </div>
            );
          })}
        </div>

        {/* Auditor Notes Field */}
        <div>
          <label className="block text-[11px] font-semibold text-slate-700 mb-1">
            Resolution Notes
          </label>
          <textarea
            value={resolutionNote || currentPair.resolutionNotes || ''}
            onChange={(e) => setResolutionNote(e.target.value)}
            placeholder="Add findings regarding corporate card feed vs personal reimbursement..."
            rows={2}
            className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded focus:outline-none focus:border-slate-400 focus:bg-white transition-colors"
          />
        </div>

        <div className="flex justify-end pt-1">
          <button
            onClick={() => handleStatusChange(currentPair.status)}
            className="px-4 py-2 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded transition-colors shadow-xs"
          >
            Save Resolution & Update Case Status
          </button>
        </div>
      </div>
    </div>
  );
};
