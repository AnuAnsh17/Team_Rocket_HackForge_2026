import React, { useState } from 'react';
import {
  ZoomIn,
  ZoomOut,
  RotateCw,
  Eye,
  EyeOff,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  Send,
  FileCheck,
  DollarSign,
  UserCheck,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import { Claim, AuditStatus, BoundingBoxHighlight } from '../types';

interface InvestigationWorkbenchProps {
  claims: Claim[];
  selectedClaimId: string;
  onSelectClaim: (claimId: string) => void;
  onUpdateClaimStatus: (
    claimId: string,
    newStatus: AuditStatus,
    actionName: string,
    note: string,
    policyClause?: string
  ) => void;
}

export const InvestigationWorkbench: React.FC<InvestigationWorkbenchProps> = ({
  claims,
  selectedClaimId,
  onSelectClaim,
  onUpdateClaimStatus,
}) => {
  const [zoomLevel, setZoomLevel] = useState(100);
  const [rotation, setRotation] = useState(0);
  const [showBoundingBoxes, setShowBoundingBoxes] = useState(true);
  const [activeBox, setActiveBox] = useState<BoundingBoxHighlight | null>(null);
  const [actionModal, setActionModal] = useState<{
    type: 'approve' | 'request_info' | 'escalate' | 'reject';
    open: boolean;
  }>({ type: 'approve', open: false });
  const [modalReason, setModalReason] = useState('');

  const currentClaim = claims.find((c) => c.id === selectedClaimId) || claims[0];
  const currentIndex = claims.findIndex((c) => c.id === currentClaim.id);

  const handleNext = () => {
    if (currentIndex < claims.length - 1) {
      onSelectClaim(claims[currentIndex + 1].id);
      setActiveBox(null);
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      onSelectClaim(claims[currentIndex - 1].id);
      setActiveBox(null);
    }
  };

  const handleZoomIn = () => setZoomLevel((prev) => Math.min(prev + 20, 200));
  const handleZoomOut = () => setZoomLevel((prev) => Math.max(prev - 20, 60));
  const handleResetZoom = () => {
    setZoomLevel(100);
    setRotation(0);
  };
  const handleRotate = () => setRotation((prev) => (prev + 90) % 360);

  const openActionDialog = (type: 'approve' | 'request_info' | 'escalate' | 'reject') => {
    if (type === 'reject') {
      setModalReason(`Rejected under ${currentClaim.policyClauseCited || 'Enterprise Expense Policy'}.`);
    } else if (type === 'request_info') {
      setModalReason('Please provide original tax invoice breakdown and attendee attendance sheet.');
    } else if (type === 'escalate') {
      setModalReason(`Escalated to Department Manager ${currentClaim.managerName} for policy exception review.`);
    } else {
      setModalReason('Approved compliant claim based on verified OCR invoice and itemized tax.');
    }
    setActionModal({ type, open: true });
  };

  const submitAction = () => {
    let newStatus: AuditStatus = 'PASS';
    let actionName = 'Auditor Approval';

    if (actionModal.type === 'reject') {
      newStatus = 'FAIL';
      actionName = 'Claim Rejected';
    } else if (actionModal.type === 'request_info') {
      newStatus = 'UNKNOWN';
      actionName = 'Correction Requested';
    } else if (actionModal.type === 'escalate') {
      newStatus = 'UNKNOWN';
      actionName = 'Escalated to Manager';
    } else {
      newStatus = 'PASS';
      actionName = 'Claim Approved';
    }

    onUpdateClaimStatus(
      currentClaim.id,
      newStatus,
      actionName,
      modalReason,
      currentClaim.policyClauseCited
    );
    setActionModal({ type: 'approve', open: false });
  };

  const calculatedItemsSum = currentClaim.lineItems.reduce((acc, item) => acc + item.total, 0);
  const expectedTotal = currentClaim.extractedTotal || calculatedItemsSum + currentClaim.extractedTax;
  const isArithmeticDiff = Math.abs(expectedTotal - currentClaim.claimedAmount) > 1;

  return (
    <div className="space-y-4 pb-12">
      {/* Workbench Navigation Strip */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-3 rounded-lg border border-slate-200">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <button
              onClick={handlePrev}
              disabled={currentIndex === 0}
              className="p-1 rounded border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title="Previous Claim"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={handleNext}
              disabled={currentIndex === claims.length - 1}
              className="p-1 rounded border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title="Next Claim"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-400">Claim:</span>
            <select
              value={currentClaim.id}
              onChange={(e) => onSelectClaim(e.target.value)}
              className="h-8 px-2 text-xs font-mono font-semibold bg-slate-50 border border-slate-200 rounded text-slate-900 focus:outline-none"
            >
              {claims.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.id} · {c.employeeName} ({c.merchantName.split(' ')[0]}) - ₹{c.claimedAmount.toLocaleString('en-IN')} [{c.status}]
                </option>
              ))}
            </select>
          </div>

          <span
            className={`text-xs font-semibold px-2 py-0.5 rounded ${
              currentClaim.status === 'PASS'
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : currentClaim.status === 'FAIL'
                ? 'bg-rose-50 text-rose-700 border border-rose-200'
                : 'bg-amber-50 text-amber-700 border border-amber-200'
            }`}
          >
            Status: {currentClaim.status}
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>Assigned to: <strong className="text-slate-800">{currentClaim.assignedAuditor}</strong></span>
          <span className="text-slate-300">·</span>
          <span>Waiting {currentClaim.daysWaiting} days</span>
        </div>
      </div>

      {/* Split-Screen Main Container */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* LEFT PANE: Interactive Receipt / Bill Viewer (5 cols) */}
        <div className="lg:col-span-5 bg-white rounded-lg border border-slate-200 overflow-hidden flex flex-col h-[750px] shadow-2xs">
          {/* Viewer Toolbar */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-slate-200 bg-slate-50 text-xs">
            <div className="flex items-center gap-1 text-slate-600 font-medium">
              <span>Receipt Inspection</span>
              <span className="text-slate-300">·</span>
              <span className="font-mono text-[11px] text-slate-500">
                {currentClaim.receiptType.replace('_', ' ')}
              </span>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={handleZoomIn}
                className="p-1 rounded text-slate-600 hover:bg-slate-200/60"
                title="Zoom In"
              >
                <ZoomIn className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={handleZoomOut}
                className="p-1 rounded text-slate-600 hover:bg-slate-200/60"
                title="Zoom Out"
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={handleResetZoom}
                className="px-1.5 py-0.5 text-[10px] font-mono rounded text-slate-600 hover:bg-slate-200/60"
                title="Reset Zoom"
              >
                {zoomLevel}%
              </button>
              <button
                onClick={handleRotate}
                className="p-1 rounded text-slate-600 hover:bg-slate-200/60"
                title="Rotate 90 deg"
              >
                <RotateCw className="h-3.5 w-3.5" />
              </button>
              <div className="h-3.5 w-px bg-slate-200 mx-1" />
              <button
                onClick={() => setShowBoundingBoxes(!showBoundingBoxes)}
                className={`p-1 rounded flex items-center gap-1 text-[11px] ${
                  showBoundingBoxes ? 'text-slate-900 bg-slate-200/70 font-semibold' : 'text-slate-400'
                }`}
                title="Toggle OCR Bounding Boxes"
              >
                {showBoundingBoxes ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                <span className="text-[10px]">Boxes</span>
              </button>
            </div>
          </div>

          {/* Viewer Canvas Area */}
          <div className="flex-1 bg-slate-100 overflow-auto p-4 flex items-center justify-center relative select-none">
            <div
              style={{
                transform: `scale(${zoomLevel / 100}) rotate(${rotation}deg)`,
                transformOrigin: 'center center',
                transition: 'transform 0.15s cubic-bezier(0.16, 1, 0.3, 1)',
              }}
              className="relative w-[340px] min-h-[580px] bg-white text-slate-900 p-5 rounded shadow-sm border border-slate-300 font-mono text-[11px] leading-tight"
            >
              {/* Paper Watermark / Header */}
              <div className="border-b-2 border-dashed border-slate-300 pb-3 text-center">
                <div className="font-bold text-xs uppercase tracking-wider text-slate-800">
                  {currentClaim.merchantName}
                </div>
                <div className="text-[9px] text-slate-500 mt-0.5">
                  GSTIN: {currentClaim.merchantGstin || 'NOT DETECTED / MISSING'}
                </div>
                <div className="text-[9px] text-slate-500">
                  Location: {currentClaim.merchantCity}, India
                </div>
                <div className="text-[9px] text-slate-400 mt-1">
                  Tax Invoice / POS Ref #{currentClaim.id}-TAX
                </div>
                <div className="text-[9px] text-slate-400">
                  Tx Date: {currentClaim.expenseDate} · Sub: {currentClaim.submissionDate}
                </div>
              </div>

              {/* Bill Line Items Table */}
              <div className="py-3 border-b border-dashed border-slate-300 space-y-1.5">
                <div className="flex justify-between font-bold text-[10px] text-slate-600 border-b border-slate-200 pb-1">
                  <span>ITEM DESCRIPTION</span>
                  <span>QTY</span>
                  <span>AMT (INR)</span>
                </div>
                {currentClaim.lineItems.map((item) => (
                  <div
                    key={item.id}
                    className={`flex justify-between py-0.5 ${
                      item.isProhibited ? 'bg-rose-50 text-rose-900 font-semibold px-1 rounded' : ''
                    }`}
                  >
                    <span className="truncate max-w-[170px]" title={item.description}>
                      {item.description}
                      {item.isProhibited && ' [PROHIBITED]'}
                    </span>
                    <span className="text-slate-500">x{item.quantity}</span>
                    <span className="font-bold">₹{item.total.toFixed(2)}</span>
                  </div>
                ))}
              </div>

              {/* Tax & Breakdown */}
              <div className="py-2.5 border-b-2 border-dashed border-slate-300 space-y-1 text-right text-[10px]">
                <div className="flex justify-between text-slate-500">
                  <span>Subtotal:</span>
                  <span>₹{currentClaim.extractedSubtotal.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-slate-500">
                  <span>CGST + SGST (Integrated):</span>
                  <span>₹{currentClaim.extractedTax.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-xs font-bold text-slate-900 pt-1 border-t border-slate-200">
                  <span>INVOICE TOTAL:</span>
                  <span className="text-slate-900">
                    ₹{currentClaim.extractedTotal.toFixed(2)}
                  </span>
                </div>
              </div>

              {/* Thermal / Ink Notice Footer */}
              <div className="pt-3 text-center text-[9px] text-slate-400 space-y-0.5">
                <div>* THANK YOU FOR PATRONAGE *</div>
                <div>Computer Generated Tax Document</div>
                {currentClaim.receiptType === 'thermal_slip' && (
                  <div className="text-amber-600 font-sans font-medium mt-1">
                    [Thermal Paper Degradation Detected]
                  </div>
                )}
              </div>

              {/* Bounding Box Highlights Overlays */}
              {showBoundingBoxes &&
                currentClaim.boundingBoxes.map((box) => {
                  const isSelected = activeBox?.id === box.id;
                  let borderColor = 'border-blue-500 bg-blue-500/10 text-blue-800';
                  if (box.issueType === 'flagged') {
                    borderColor = 'border-rose-500 bg-rose-500/15 text-rose-800';
                  } else if (box.issueType === 'faded' || box.issueType === 'handwritten') {
                    borderColor = 'border-amber-500 bg-amber-500/15 text-amber-800';
                  } else if (box.issueType === 'mismatch') {
                    borderColor = 'border-amber-600 bg-amber-600/15 text-amber-900';
                  }

                  return (
                    <div
                      key={box.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveBox(box);
                      }}
                      style={{
                        top: `${box.y}%`,
                        left: `${box.x}%`,
                        width: `${box.w}%`,
                        height: `${box.h}%`,
                      }}
                      className={`absolute border-2 rounded-xs cursor-pointer transition-all ${borderColor} ${
                        isSelected ? 'ring-2 ring-slate-900 ring-offset-1' : ''
                      }`}
                    >
                      <div className="absolute -top-4 left-0 px-1 py-0.2 text-[9px] font-sans font-semibold bg-slate-900 text-white rounded-xs whitespace-nowrap shadow-xs">
                        {box.label} ({(box.confidence * 100).toFixed(0)}%)
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>

          {/* Active Box Info Footer */}
          {activeBox && (
            <div className="p-2.5 bg-slate-50 border-t border-slate-200 text-xs flex items-center justify-between">
              <div>
                <span className="font-semibold text-slate-800">{activeBox.label}</span>
                <span className="text-slate-400 font-mono ml-2">
                  Confidence: {(activeBox.confidence * 100).toFixed(1)}%
                </span>
              </div>
              <button
                onClick={() => setActiveBox(null)}
                className="text-[11px] text-slate-500 hover:text-slate-800"
              >
                Clear selection
              </button>
            </div>
          )}
        </div>

        {/* RIGHT PANE: Extracted Fields, Arithmetic & Policy Context (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Card 1: Extracted Fields vs Claimed Discrepancies */}
          <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-2xs">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Extracted Fields vs. Claimed Values
              </h3>
              <span className="text-[11px] font-mono text-slate-500">
                OCR Confidence: {(currentClaim.confidenceScore * 100).toFixed(1)}%
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3.5 pt-3 text-xs">
              <div>
                <span className="text-[10px] text-slate-400 uppercase font-semibold">
                  Merchant
                </span>
                <div className="font-semibold text-slate-900 truncate">
                  {currentClaim.merchantName}
                </div>
                <div className="text-[11px] text-slate-500 font-mono">
                  {currentClaim.merchantCity} ({currentClaim.cityTier})
                </div>
              </div>

              <div>
                <span className="text-[10px] text-slate-400 uppercase font-semibold">
                  GSTIN Status
                </span>
                <div className="font-mono text-slate-800 text-[11px]">
                  {currentClaim.merchantGstin || 'None / Not on receipt'}
                </div>
                <div className="text-[11px] text-emerald-700 font-medium">
                  {currentClaim.merchantGstin ? 'Verified Active State' : 'Missing GSTIN Flag'}
                </div>
              </div>

              <div>
                <span className="text-[10px] text-slate-400 uppercase font-semibold">
                  Expense Date vs Submitted
                </span>
                <div className="font-mono text-slate-900">
                  {currentClaim.expenseDate}
                </div>
                <div className="text-[11px] text-slate-500 font-mono">
                  Latency: {currentClaim.submissionLatencyDays} days (SLA: 7d)
                </div>
              </div>

              <div>
                <span className="text-[10px] text-slate-400 uppercase font-semibold">
                  Employee / Cost Center
                </span>
                <div className="font-semibold text-slate-900">
                  {currentClaim.employeeName} ({currentClaim.employeeId})
                </div>
                <div className="text-[11px] text-slate-500">
                  {currentClaim.costCenter}
                </div>
              </div>

              <div>
                <span className="text-[10px] text-slate-400 uppercase font-semibold">
                  Claimed Amount
                </span>
                <div className="font-mono font-bold text-sm text-slate-900">
                  ₹{currentClaim.claimedAmount.toLocaleString('en-IN')}
                </div>
                <div className="text-[11px] text-slate-400">
                  INR Reimbursable
                </div>
              </div>

              <div>
                <span className="text-[10px] text-slate-400 uppercase font-semibold">
                  Attendee Count
                </span>
                <div className="font-mono text-slate-800">
                  {currentClaim.attendeesCount !== undefined ? `${currentClaim.attendeesCount} Attendees` : 'Not Applicable'}
                </div>
                {currentClaim.requiredAttendees && currentClaim.attendeesCount! < currentClaim.requiredAttendees && (
                  <span className="text-[10px] text-rose-700 font-semibold">
                    Requires &ge; {currentClaim.requiredAttendees} named attendees
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Card 2: Arithmetic Verification Box */}
          <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-2xs">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                  Arithmetic Verification Box
                </span>
                {isArithmeticDiff ? (
                  <span className="text-[10px] font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-1.5 py-0.2 rounded">
                    Mismatch Detected
                  </span>
                ) : (
                  <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.2 rounded">
                    Reconciled OK
                  </span>
                )}
              </div>
              <span className="text-[11px] font-mono text-slate-500">
                Formula: &Sigma; Line Items + Tax
              </span>
            </div>

            <div className="pt-3">
              <div className="bg-slate-50 rounded p-3 font-mono text-xs flex flex-wrap items-center justify-between gap-2 border border-slate-200">
                <div className="flex items-center gap-2">
                  <span>Items: <strong className="text-slate-900">₹{calculatedItemsSum.toFixed(2)}</strong></span>
                  <span className="text-slate-400">+</span>
                  <span>Tax: <strong className="text-slate-900">₹{currentClaim.extractedTax.toFixed(2)}</strong></span>
                  <span className="text-slate-400">=</span>
                  <span className="bg-white px-2 py-0.5 rounded border border-slate-200">
                    Expected: <strong className="text-slate-900">₹{expectedTotal.toFixed(2)}</strong>
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-400">vs</span>
                  <span className={`px-2 py-0.5 rounded font-bold ${
                    isArithmeticDiff ? 'bg-rose-100 text-rose-900 border border-rose-300' : 'bg-emerald-100 text-emerald-900'
                  }`}>
                    Claimed: ₹{currentClaim.claimedAmount.toFixed(2)}
                  </span>
                </div>
              </div>

              {isArithmeticDiff && (
                <div className="mt-2 text-xs text-rose-700 flex items-center gap-1.5 font-medium">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                  <span>
                    Discrepancy of ₹{Math.abs(expectedTotal - currentClaim.claimedAmount).toFixed(2)} between OCR calculated total and claimed reimbursement amount.
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Card 3: Policy & Cumulative Context Card */}
          <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-2xs space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-slate-700" />
                <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                  Policy & Cumulative Context
                </h3>
              </div>
              <span className="text-[11px] font-mono font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                {currentClaim.policyRuleTitle || 'Standard Expense Rules'}
              </span>
            </div>

            <div className="space-y-2 text-xs">
              <div className="p-3 bg-slate-50 border border-slate-200 rounded">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-800">
                    Cited Clause:
                  </span>
                  <span className="font-mono text-[11px] text-slate-500">
                    {currentClaim.policyClauseCited || 'General Travel & Entertainment v2026.4'}
                  </span>
                </div>
                <p className="text-slate-600 mt-1 leading-relaxed">
                  {currentClaim.issueDescription}
                </p>
              </div>

              {/* Cumulative Prior Spend Bar */}
              {currentClaim.category === 'Meals' && (
                <div className="p-3 bg-slate-50 border border-slate-200 rounded space-y-1.5">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-medium text-slate-700">
                      Same-Day Cumulative Spend ({currentClaim.expenseDate})
                    </span>
                    <span className="font-mono font-bold text-slate-900">
                      ₹{currentClaim.priorSpendSameDay + currentClaim.claimedAmount} / ₹{currentClaim.dailyCap} Cap
                    </span>
                  </div>

                  <div className="h-2 w-full bg-slate-200 rounded-full overflow-hidden">
                    <div
                      style={{
                        width: `${Math.min(
                          ((currentClaim.priorSpendSameDay + currentClaim.claimedAmount) / (currentClaim.dailyCap || 1000)) * 100,
                          100
                        )}%`,
                      }}
                      className={`h-full ${
                        currentClaim.priorSpendSameDay + currentClaim.claimedAmount > (currentClaim.dailyCap || 1000)
                          ? 'bg-rose-600'
                          : 'bg-emerald-600'
                      }`}
                    />
                  </div>

                  <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                    <span>Prior same-day: ₹{currentClaim.priorSpendSameDay}</span>
                    <span>This claim: ₹{currentClaim.claimedAmount}</span>
                    <span className={currentClaim.priorSpendSameDay + currentClaim.claimedAmount > (currentClaim.dailyCap || 1000) ? 'text-rose-700 font-bold' : ''}>
                      {currentClaim.priorSpendSameDay + currentClaim.claimedAmount > (currentClaim.dailyCap || 1000)
                        ? `Exceeds cap by ₹${currentClaim.priorSpendSameDay + currentClaim.claimedAmount - (currentClaim.dailyCap || 1000)}`
                        : `Remaining allowance: ₹${(currentClaim.dailyCap || 1000) - (currentClaim.priorSpendSameDay + currentClaim.claimedAmount)}`}
                    </span>
                  </div>
                </div>
              )}

              {/* Recommended Action Advice */}
              <div className="flex items-center gap-2 p-2.5 bg-blue-50/50 border border-blue-200 rounded text-xs text-blue-900">
                <Sparkles className="h-4 w-4 text-blue-600 shrink-0" />
                <span>
                  <strong>AI Recommendation:</strong>{' '}
                  {currentClaim.status === 'FAIL'
                    ? 'Reject with cited policy clause or request employee trim non-compliant portion.'
                    : currentClaim.status === 'UNKNOWN'
                    ? 'Request missing proof / attendance verification before approving.'
                    : 'All criteria satisfied. Approved for automated batch payout.'}
                </span>
              </div>
            </div>
          </div>

          {/* Action Footer: 4 Working Decision Buttons */}
          <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-2xs">
            <h4 className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-2.5">
              Auditor Decision & Escalation
            </h4>
            <div className="flex flex-wrap items-center gap-2.5">
              <button
                onClick={() => openActionDialog('approve')}
                className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded transition-colors shadow-xs"
              >
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                <span>Approve Claim</span>
              </button>

              <button
                onClick={() => openActionDialog('request_info')}
                className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded transition-colors"
              >
                <HelpCircle className="h-3.5 w-3.5 text-amber-600" />
                <span>Request Correction / Info</span>
              </button>

              <button
                onClick={() => openActionDialog('escalate')}
                className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded transition-colors"
              >
                <UserCheck className="h-3.5 w-3.5 text-slate-500" />
                <span>Escalate to Manager</span>
              </button>

              <button
                onClick={() => openActionDialog('reject')}
                className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-rose-800 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded transition-colors"
              >
                <XCircle className="h-3.5 w-3.5 text-rose-600" />
                <span>Reject with Cited Clause</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Decision Modal */}
      {actionModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-lg border border-slate-200 shadow-xl max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-bold text-slate-900 capitalize">
                Confirm {actionModal.type.replace('_', ' ')}
              </h3>
              <button
                onClick={() => setActionModal({ ...actionModal, open: false })}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <div className="text-xs text-slate-600 space-y-3">
              <p>
                You are updating <strong className="text-slate-900">{currentClaim.id}</strong> (
                {currentClaim.employeeName} · ₹{currentClaim.claimedAmount.toLocaleString('en-IN')}).
              </p>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Audit Log Reason & Policy Reference
                </label>
                <textarea
                  value={modalReason}
                  onChange={(e) => setModalReason(e.target.value)}
                  rows={3}
                  className="w-full text-xs p-2 bg-slate-50 border border-slate-200 rounded focus:outline-none focus:border-slate-400 focus:bg-white"
                />
              </div>

              <div className="text-[11px] text-slate-500">
                This action is permanently recorded in the immutable compliance audit trail.
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setActionModal({ ...actionModal, open: false })}
                className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded"
              >
                Cancel
              </button>
              <button
                onClick={submitAction}
                className="px-4 py-1.5 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded shadow-xs"
              >
                Confirm & Record in Audit Trail
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
